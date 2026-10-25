#!/usr/bin/env python3
"""Experiment 05 (diagnosis only, no new predictor): the gap rule broken down by a predefined table.

Inputs are existing rows only:
  - development (REUSED, already used by exp 03): exp03 rows_h3/h5.parquet, Feb 20 – May 29 2026
  - official holdout (EXPLORATORY, already used by exp 04): gap-v1 c2_holdout.parquet

Table dimensions (fixed before running): asset; chronological block (dev: Feb–Mar / Apr–May;
holdout: the scorer's first/second half by session count); gap sign; |gap| tercile with per-asset
cut points taken from the development rows (never from the holdout). Extra holdout-only splits
(exploratory): entry-price source (settlement/tick) and truncated gap interval (< 8 h).

Metrics: n, gap-rule direction (scorer's `realized`), matched null (scorer's prevailing_null),
neither rate, and 90% intervals from a date-block bootstrap: blocks of h consecutive trading dates
shared by all assets, so overlapping windows and same-date cross-asset correlation stay together.

    python experiments/05_gap_diagnosis/diag_table.py --pack ../../v2.1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from swing_dataset.kit import loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import outcomes as O
from swing_dataset.scoring2 import signals as SIG
from swing_dataset.scoring2.score import prevailing_null

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
N_BOOT, SEED = 2000, 0


def date_block_ci(df: pd.DataFrame, col: str, h: int) -> list[float] | None:
    if len(df) < 10:
        return None
    dates = np.array(sorted(df["d"].unique()))
    block = {d: i // h for i, d in enumerate(dates)}
    b = df["d"].map(block).to_numpy()
    uniq, inv = np.unique(b, return_inverse=True)
    s = np.bincount(inv, weights=df[col].to_numpy(float), minlength=len(uniq))
    n = np.bincount(inv, minlength=len(uniq)).astype(float)
    rng = np.random.default_rng(SEED)
    c = np.stack([np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq)) for _ in range(N_BOOT)])
    rep = (c @ s) / (c @ n)
    return [round(100 * float(np.quantile(rep, 0.05)), 1), round(100 * float(np.quantile(rep, 0.95)), 1)]


def cell(df, h):
    if not len(df):
        return {"n": 0}
    return {
        "n": int(len(df)),
        "direction": round(100 * df["ok"].mean(), 1),
        "direction_ci90": date_block_ci(df, "ok", h),
        "null": round(100 * df["null_ok"].mean(), 1),
        "diff_pp": round(100 * (df["ok"].mean() - df["null_ok"].mean()), 1),
        "diff_ci90": date_block_ci(df.assign(dd=df["ok"].astype(float) - df["null_ok"].astype(float)), "dd", h),
        "neither": round(100 * df["neither"].mean(), 1),
        "up_signals": round(100 * (df["direction"] == "up").mean(), 1),
    }


def table(df, h, extra=()):
    out = {"all": cell(df, h)}
    for dim in ("asset", "block", "sign", "tercile", *extra):
        out[dim] = {str(k): cell(g, h) for k, g in df.groupby(dim, sort=True)}
    out["block_x_sign"] = {f"{b}|{s}": cell(g, h) for (b, s), g in df.groupby(["block", "sign"], sort=True)}
    out["block_x_asset"] = {f"{b}|{a}": cell(g, h) for (b, a), g in df.groupby(["block", "asset"], sort=True)}
    return out


def prep(g: pd.DataFrame, cuts: dict) -> pd.DataFrame:
    g = g.copy()
    g["ok"] = g["realized"].astype(bool)
    g["null_ok"] = g["null_realized"].astype(bool)
    g["neither"] = ~g["ok"] & (g["mae_pct"] < g["threshold_pct"] - 1e-9)
    g["sign"] = np.where(g["gap_pct"] > 0, "up_gap", "down_gap")
    g["d"] = pd.to_datetime(g["signal_utc"]).dt.tz_convert("Asia/Kolkata").dt.date
    g["tercile"] = [
        "bottom" if abs(x) <= cuts[a][0] else ("middle" if abs(x) <= cuts[a][1] else "top")
        for a, x in zip(g["asset"], g["gap_pct"])
    ]
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    args = ap.parse_args()
    out = {"labels": {"development": "REUSED (exp 03 period, Feb 20 – May 29 2026)",
                      "holdout": "EXPLORATORY (official holdout, already used by exp 04)"}}
    cuts = {}
    for h in (3, 5):
        dev = pd.read_parquet(EXP / "03_overnight_gap" / f"rows_h{h}.parquet")
        if h == 3:  # tercile cut points from development only (h3 rows; same gaps as h5)
            cuts = {a: list(g["gap_pct"].abs().quantile([1 / 3, 2 / 3])) for a, g in dev.groupby("asset")}
        dev = prep(dev, cuts)
        dev["block"] = np.where(pd.to_datetime(dev["signal_utc"]).dt.month <= 3, "dev_A_feb_mar", "dev_B_apr_may")
        out[f"development_h{h}"] = table(dev, h)

    pit = PointInTime(args.pack)
    asof = pd.Timestamp("2026-10-24 06:00", tz="UTC").to_pydatetime()
    prices, _ = loop.price_view(pit, asof, quotes=True)
    hold = pd.read_parquet(EXP / "04_gap_model" / "holdout_run" / "c2_holdout.parquet")
    hold = hold[hold["signal_utc"].notna()].reset_index(drop=True)
    sess = sorted({d for a in prices.assets() for d in prices.sessions_between(
        a, pd.Timestamp("2026-06-01", tz="UTC"), pd.Timestamp("2026-10-23 23:59", tz="UTC"))})
    first = set(sess[: len(sess) // 2])
    for h in (3, 5):
        s = hold[hold["horizon"] == h].reset_index(drop=True)
        g = O.grade_c2(SIG.normalize(s, 2).signals, prices)
        g = g[g["scorable"].fillna(False).astype(bool)].reset_index(drop=True)
        n = O.grade_c2(prevailing_null(g, prices), prices).set_index("signal_index")
        g["null_realized"] = n["realized"].reindex(g["signal_index"]).to_numpy()
        g = g[n["scorable"].reindex(g["signal_index"]).fillna(False).astype(bool).to_numpy()].reset_index(drop=True)
        g["gap_pct"] = g["evidence"].str.extract(r"moved ([+-][\d.]+)%")[0].astype(float)
        g["src"] = g["evidence"].str.extract(r"entry (\w+) of")[0]
        ref0 = pd.to_datetime(g["evidence"].str.extract(r"from the candle closing (\S+) ")[0], utc=True, format="ISO8601")
        g["interval"] = np.where((pd.to_datetime(g["signal_utc"]) - ref0).dt.total_seconds() < 8 * 3600, "truncated_lt8h", "full")
        g = prep(g, cuts)
        g["block"] = np.where([session_of in first for session_of in
                               [prices.frame(a)["session_date"].iloc[prices.session_pos(a, t)] if prices.session_pos(a, t) is not None else None
                                for a, t in zip(g["asset"], g["signal_utc"])]], "hold_H1", "hold_H2")
        out[f"holdout_h{h}_EXPLORATORY"] = table(g, h, extra=("src", "interval"))
    out["dev_tercile_cuts_abs_gap_pct"] = {a: [round(x, 3) for x in v] for a, v in cuts.items()}
    (HERE / "diag_table.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    for key in [k for k in out if k.startswith(("development", "holdout"))]:
        t = out[key]
        print("==", key, t["all"])
        for dim in ("block", "block_x_sign", "tercile", "src", "interval"):
            if dim in t:
                for k, v in t[dim].items():
                    print(f"   {dim:13s} {k:24s} n={v['n']:4d} dir={v.get('direction')} ci={v.get('direction_ci90')} "
                          f"null={v.get('null')} diff={v.get('diff_pp')} dci={v.get('diff_ci90')} neither={v.get('neither')} up%={v.get('up_signals')}")


if __name__ == "__main__":
    main()
