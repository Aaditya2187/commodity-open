#!/usr/bin/env python3
"""Research only: one row per (session, asset, horizon) with the model's state, features and both outcomes.

    python research/slots.py --pack ../v2.1                                         # holdout
    python research/slots.py --pack ../v2.1 --train-end 2026-02-20T03:00:00+00:00 \
        --from 2026-02-20 --to 2026-05-22 --grade-asof 2026-06-01T03:00:00+00:00 --out research/slots_pre.parquet

Every pack read goes through ``PointInTime``. The model is visited at each pre-open exactly as
``loop.run`` calls it; the gap measurement, the overnight range and the full feature row are
recorded for every asset. Path features are built from the hourly Hyperliquid candles the model
itself read at that instant (between the entry observation and the signal). Each slot is graded
for both directions at horizons 1-5 by the scorer's own ``grade_c2``, on prices available at
``--grade-asof``. ``gap_<src>`` columns measure the same overnight move on the quote feeds that
start in June/July, each row admitted by the clock the point-in-time filter uses.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import model as M
from swing_dataset.kit import loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import THRESHOLD_PCT
from swing_dataset.scoring2 import outcomes as O
from swing_dataset.scoring2 import signals as SIG
from task2.features import FEATURE_COLUMNS

OUT = Path(__file__).resolve().parent / "slots_holdout.parquet"
HORIZONS = (1, 2, 3, 4, 5)
PATH_HOURS = 12
SOURCES = {
    "hlq": ("pack/quotes/hl_quotes", "instrument", {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}, "mid"),
    "te": ("pack/quotes/te_quotes", "symbol", {"gold": "XAUUSD:CUR", "silver": "XAGUSD:CUR", "copper": "HG1:COM", "crude": "CL1:COM"}, "price"),
    "sh": ("pack/quotes/reference_quotes", "symbol", {"gold": "nf_AU0", "silver": "nf_AG0", "copper": "nf_CU0", "crude": "nf_SC0"}, "price"),
}


def admitted(pit: PointInTime, name: str, asof: datetime, cols: list[str]) -> pd.DataFrame:
    """Rows the client returns at ``asof``, with the instant its filter admitted each by."""
    t = pit.frame(name, asof).collect(columns=list(dict.fromkeys(cols + ["clock_quality", "fetched_utc", "available_utc"])))
    q = t["clock_quality"].astype(str)
    adm = pd.to_datetime(t["available_utc"], utc=True).where(q == "published", pd.to_datetime(t["fetched_utc"], utc=True))
    t["admit_ns"] = pd.DatetimeIndex(adm).as_unit("ns").asi8
    return t.sort_values("admit_ns", kind="stable")


def last_before(series, t_ns: int, strict: bool = True) -> float | None:
    ns, px = series
    i = int(np.searchsorted(ns, t_ns, side="left" if strict else "right")) - 1
    return None if i < 0 else float(px[i])


def path_features(c1: pd.DataFrame, inst: str, g: dict, thr: float) -> dict:
    s = c1[c1["instrument"] == inst].sort_values("close_utc", kind="stable")
    close_ns = M.to_ns(s["close_utc"])
    i0 = int(np.searchsorted(close_ns, g["ref0_ns"], side="left"))
    i1 = int(np.searchsorted(close_ns, g["ref1_ns"], side="left"))
    if i0 >= len(s) or i1 >= len(s) or close_ns[i0] != g["ref0_ns"] or close_ns[i1] != g["ref1_ns"] or i1 <= i0:
        return {}
    px, hi, lo = s["close"].to_numpy(float), s["high"].to_numpy(float), s["low"].to_numpy(float)
    seg_hi, seg_lo = hi[i0 + 1 : i1 + 1].max(), lo[i0 + 1 : i1 + 1].min()
    out = {"nr_anchor": 100.0 * (seg_hi / seg_lo - 1.0) / thr,
           "pos_anchor": (px[i1] - seg_lo) / (seg_hi - seg_lo) if seg_hi > seg_lo else 0.5,
           "n_hours": int(i1 - i0),
           "last1": 100.0 * (px[i1] / px[i1 - 1] - 1.0) / thr,
           "last3": 100.0 * (px[i1] / px[max(i0, i1 - 3)] - 1.0) / thr}
    out["eff"] = abs(g["gap_thr"]) / out["nr_anchor"] if out["nr_anchor"] > 0 else np.nan
    lr = np.diff(np.log(px[max(0, i1 - PATH_HOURS) : i1 + 1])) * 100.0 / thr
    lr = np.concatenate([np.full(PATH_HOURS - len(lr), 0.0), lr])
    for k in range(PATH_HOURS):
        out[f"path_{k}"] = float(lr[-1 - k])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--train-end", default=None, help="ISO instant with offset; default the holdout cutoff")
    ap.add_argument("--from", dest="start", default="2026-06-01")
    ap.add_argument("--to", dest="end", default="2026-10-23")
    ap.add_argument("--grade-asof", default="2026-10-24T06:00:00+00:00")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    pit = PointInTime(args.pack.resolve())
    start, end = pd.Timestamp(args.start).date(), pd.Timestamp(args.end).date()
    period = loop.period_for("holdout", start, end, datetime.fromisoformat(args.train_end) if args.train_end else None)
    first = loop.preopen_instant(period.start)
    days = loop.trading_days(pit, first, start, end)
    bounds = loop.session_bounds(pit, first, start, end)

    model = M.build(2)
    model.fit(pit, period.train_end)
    captured = {}
    orig_frame, orig_tables = M.build_frame, model._tables

    def spy_frame(*a, **k):
        captured["frame"] = orig_frame(*a, **k)
        return captured["frame"]

    def spy_tables(*a, **k):
        captured["tables"] = orig_tables(*a, **k)
        return captured["tables"]

    M.build_frame, model._tables = spy_frame, spy_tables
    rows = []
    for i, day in enumerate(days):
        instant = bounds[day][0]
        st = model._state(instant)
        feats = captured["frame"].set_index("asset")
        c1 = captured["tables"]["c1"]
        for asset in sorted(st):
            g = st[asset]
            r = {"session_idx": i, "session_date": pd.Timestamp(day), "signal_utc": pd.Timestamp(instant),
                 "asset": asset, "reason": g.get("reason")}
            if "reason" not in g:
                r.update({k: g[k] for k in ("gap_pct", "gap_thr", "night_range", "contract", "source", "anchor_ns", "ref0_ns", "ref1_ns")})
                r.update(path_features(c1, M.HL_SYMBOL[asset], g, THRESHOLD_PCT[asset]))
                for c in FEATURE_COLUMNS:
                    r[f"f_{c}"] = float(feats.loc[asset, c]) if c in feats.columns else np.nan
            rows.append(r)
        print(f"{i + 1}/{len(days)} {day}", flush=True)
    M.build_frame = orig_frame
    slots = pd.DataFrame(rows)
    slots["issued_v2"] = (slots["gap_thr"].abs() >= M.MIN_GAP) & (slots["night_range"] >= M.NIGHT_RANGE_MIN)

    asof = datetime.fromisoformat(args.grade_asof)
    prices, _ = loop.price_view(pit, asof, quotes=True)
    has = slots[slots["gap_thr"].notna()]
    for h in HORIZONS:
        for d in ("up", "down"):
            e, p10, p90 = zip(*[M.band(a) for a in has["asset"]])
            sig = pd.DataFrame({"asset": has["asset"].to_numpy(), "signal_utc": has["signal_utc"].to_numpy(), "direction": d,
                                "horizon": h, "expected_pct": e, "p10_pct": p10, "p90_pct": p90,
                                "invalidation_pct": [THRESHOLD_PCT[a] for a in has["asset"]], "evidence": "slot"})
            g = O.grade_c2(SIG.normalize(sig, 2).signals, prices)
            slots.loc[has.index, f"real_{d}_h{h}"] = g["realized"].to_numpy(bool)
            slots.loc[has.index, f"scor_{d}_h{h}"] = g["scorable"].fillna(False).to_numpy(bool)

    for tag, (name, key, sym, col) in SOURCES.items():
        t = admitted(pit, name, asof, [key, col])
        t = t[t[col].notna()]
        series = {a: (g["admit_ns"].to_numpy(), g[col].to_numpy(float)) for a, g in t.groupby(key) if a in sym.values()}
        vals = []
        for r in slots.itertuples():
            s = series.get(sym[r.asset])
            if s is None or pd.isna(getattr(r, "anchor_ns", np.nan)):
                vals.append(np.nan)
                continue
            p1 = last_before(s, int(pd.Timestamp(r.signal_utc).value))
            p0 = last_before(s, int(r.anchor_ns), strict=False)
            vals.append(np.nan if p0 is None or p1 is None or p0 <= 0 else 100.0 * (p1 / p0 - 1.0) / THRESHOLD_PCT[r.asset])
        slots[f"gap_{tag}"] = vals
        print(tag, "coverage", round(float(np.isfinite(slots[f"gap_{tag}"]).mean()), 3), flush=True)
    slots.to_parquet(args.out)
    print("wrote", args.out, len(slots))


if __name__ == "__main__":
    main()
