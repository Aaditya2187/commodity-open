#!/usr/bin/env python3
"""Experiment 01: what the Task 2 scoring contract allows, measured with the scorer's own code.

No model. For every holdout session, asset, horizon 1..5 and both directions, grade a pre-open
signal with ``scoring2.outcomes.grade_c2`` on (a) the scorer's view (ticks where it has them) and
(b) the update view (``matured_outcomes`` builds prices without quotes). Then report:

1. ceilings: P(up first), P(down first), P(neither) per asset and horizon. An oracle that knows
   the direction scores at most 1 - P(neither); the null and "always up" are given for reference.
2. update delay: sessions from issue to the pre-open at which ``loop.matured_outcomes`` would
   deliver the outcome (daily-bar view, as the loop does), and how many deliveries can reach a
   scored forward prediction in a 5-session window.
3. daily-vs-tick disagreement on ``realized``: how often update labels differ from scorer labels.

Reads go through PointInTime only. Writes JSON + CSV next to this file.

    python experiments/01_learnability/diag.py --pack /path/to/v2.1
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from swing_dataset.kit import ASSETS, loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import outcomes as O
from swing_dataset.scoring2 import signals as SIG
from swing_dataset.scoring2.prices import ns_of

HERE = Path(__file__).resolve().parent
HORIZONS = (1, 2, 3, 5)
FORWARD_SESSIONS = 5  # Tue 27 Oct .. Mon 2 Nov


def build_rows(pit: PointInTime, asof, start: date, end: date) -> pd.DataFrame:
    days = loop.trading_days(pit, loop.preopen_instant(start), start, end)
    rows = []
    for day in days:
        t = loop.preopen_instant(day)
        for asset in ASSETS:
            for h in HORIZONS:
                for d in ("up", "down"):
                    rows.append(
                        {
                            "asset": asset,
                            "signal_utc": pd.Timestamp(t),
                            "direction": d,
                            "horizon": h,
                            "expected_pct": 3.0,
                            "p10_pct": 1.0,
                            "p90_pct": 5.0,
                            "invalidation_pct": 1.0,
                            "evidence": "diag",
                            "session_date": day,
                        }
                    )
    return pd.DataFrame(rows)


def grade(rows: pd.DataFrame, prices) -> pd.DataFrame:
    norm = SIG.normalize(rows.drop(columns=["session_date"]).reset_index(drop=True), 2).signals
    g = O.grade_c2(norm, prices)
    g["session_date"] = rows["session_date"].to_numpy()
    return g


def delivery_delay(pit: PointInTime, rows: pd.DataFrame, days: list[date]) -> pd.Series:
    """Sessions after issue at whose pre-open ``loop.matured_outcomes`` first returns the row.

    Uses the loop's own function, so it includes its daily-bar view and availability rules.
    """
    delay = pd.Series(np.nan, index=rows.index)
    pending = rows.index.to_numpy()
    for k, day in enumerate(days):
        asof = loop.preopen_instant(day)
        cand = rows.loc[pending]
        cand = cand[cand["session_date"] < day]
        if cand.empty:
            continue
        m = loop.matured_outcomes(pit, asof, cand.drop(columns=["session_date"]).reset_index(drop=True), 2)
        if len(m):
            idx = cand.index.to_numpy()[m["signal_index"].astype(int).to_numpy()]
            pos = {d: i for i, d in enumerate(days)}
            delay.loc[idx] = [k - pos[s] for s in rows.loc[idx, "session_date"]]
            pending = np.setdiff1d(pending, idx)
    return delay


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--start", type=date.fromisoformat, default=date(2026, 6, 1))
    ap.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 23))
    args = ap.parse_args()

    pit = PointInTime(args.pack)
    asof = pd.Timestamp("2026-10-24 06:00", tz="UTC").to_pydatetime()
    rows = build_rows(pit, asof, args.start, args.end)
    days = sorted(rows["session_date"].unique())

    tick_prices, _ = loop.price_view(pit, asof, quotes=True)
    daily_prices, _ = loop.price_view(pit, asof, quotes=False)
    gt = grade(rows, tick_prices)
    gd = grade(rows, daily_prices)

    # trailing 5-session null direction at each instant (scorer's own function)
    null_dir = [
        ("up" if (m := tick_prices.trailing_move_pct(a, t, 5)) is None or m >= 0 else "down")
        for a, t in zip(gt["asset"], gt["signal_utc"])
    ]
    gt["null_dir"] = null_dir

    out: dict = {"window": [str(args.start), str(args.end)], "sessions": len(days), "ceilings": {}}
    for (asset, h), g in gt[gt["scorable"].astype(bool)].groupby(["asset", "horizon"]):
        up = g[g["direction"] == "up"].set_index("signal_utc")
        dn = g[g["direction"] == "down"].set_index("signal_utc")
        up_first = up["realized"].astype(bool)
        dn_first = dn["realized"].astype(bool).reindex(up.index)
        neither = ~(up_first | dn_first)
        null_hit = np.where(up["null_dir"] == "up", up_first, dn_first)
        out["ceilings"][f"{asset}_h{h}"] = {
            "n": int(len(up)),
            "p_up_first": round(100 * up_first.mean(), 1),
            "p_down_first": round(100 * dn_first.mean(), 1),
            "p_neither": round(100 * neither.mean(), 1),
            "oracle_direction": round(100 * (1 - neither.mean()), 1),
            "null_direction": round(100 * float(np.mean(null_hit)), 1),
            "ambiguous_daily_bars": int(g["ambiguous"].fillna(False).astype(bool).sum()),
        }

    # pooled h=5 / h=3 ceilings
    for h in (3, 5):
        sub = {k: v for k, v in out["ceilings"].items() if k.endswith(f"_h{h}")}
        n = sum(v["n"] for v in sub.values())
        out[f"pooled_h{h}"] = {
            k: round(sum(v[k] * v["n"] for v in sub.values()) / n, 1)
            for k in ("p_up_first", "p_down_first", "p_neither", "oracle_direction", "null_direction")
        }

    # daily vs tick label disagreement on rows the scorer grades with ticks
    both = gt[["realized", "price_source", "bars"]].join(gd[["realized"]], rsuffix="_daily")
    sc = gt["scorable"].astype(bool) & gd["scorable"].astype(bool)
    dis = both[sc & (both["realized"].astype(bool) != both["realized_daily"].astype(bool))]
    out["update_vs_scorer_label_disagreement"] = {
        "rows_compared": int(sc.sum()),
        "disagree": int(len(dis)),
        "pct": round(100 * len(dis) / max(1, sc.sum()), 2),
        "from_2026_06_22_rows": int(sc[gt["session_date"] >= date(2026, 6, 22)].sum()),
        "disagree_from_2026_06_22": int((gt.loc[dis.index, "session_date"] >= date(2026, 6, 22)).sum()),
    }

    # update delay via the loop's own matured_outcomes (h=3 and 5 only, to bound runtime)
    sel = rows[rows["horizon"].isin([3, 5])].copy()
    sel["delay"] = delivery_delay(pit, sel, days)
    delays = {}
    for h in (3, 5):
        d = sel.loc[sel["horizon"] == h, "delay"]
        delays[f"h{h}"] = {
            f"delivered_by_preopen_plus_{k}": round(100 * float((d <= k).mean()), 1) for k in range(1, 7)
        }
    out["delivery_delay_pct"] = delays

    # forward-window simulation: in every rolling 5-session window of the holdout, a learner that
    # signals every asset at every session (one direction per key) gets deliveries before day j
    # only from issues on days < j. Count scored predictions that come after at least one
    # delivery of a SAME-ASSET outcome, and the number of deliveries available, per window.
    sim = []
    for h in (3, 5):
        s = sel[(sel["horizon"] == h) & (sel["direction"] == "up")]
        for w0 in range(0, len(days) - FORWARD_SESSIONS + 1):
            win = days[w0 : w0 + FORWARD_SESSIONS]
            pos = {d: i for i, d in enumerate(win)}
            ws = s[s["session_date"].isin(win)]
            # direction does not change delivery timing much; use 'up' rows' delays (either barrier)
            arrive = ws.assign(i=ws["session_date"].map(pos), arrive=lambda x: x["i"] + x["delay"])
            arrive = arrive[arrive["arrive"] <= FORWARD_SESSIONS - 1]
            affected = 0
            for asset in ASSETS:
                a = arrive[arrive["asset"] == asset]
                if len(a):
                    affected += FORWARD_SESSIONS - int(a["arrive"].min())
            sim.append({"h": h, "deliveries_in_window": len(arrive), "affected_scored_predictions": affected,
                        "scored_predictions": FORWARD_SESSIONS * len(ASSETS)})
    sim = pd.DataFrame(sim)
    out["forward_window_learnability"] = {
        f"h{h}": {
            "mean_deliveries_usable": round(float(g["deliveries_in_window"].mean()), 2),
            "mean_predictions_that_can_differ": round(float(g["affected_scored_predictions"].mean()), 2),
            "of_scored_predictions": int(g["scored_predictions"].iloc[0]),
            "share_windows_with_zero_deliveries": round(100 * float((g["deliveries_in_window"] == 0).mean()), 1),
        }
        for h, g in sim.groupby("h")
    }

    gt.drop(columns=["invalid_reasons"], errors="ignore").to_parquet(HERE / "graded_tick.parquet")
    (HERE / "learnability.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
