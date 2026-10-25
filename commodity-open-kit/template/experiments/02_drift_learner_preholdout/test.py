#!/usr/bin/env python3
"""Experiment 02: can an online barrier-order learner beat its own frozen copy? PRE-HOLDOUT ONLY.

Every read is made at 2026-06-01 03:00 UTC through PointInTime, so no holdout row can enter.

Label per (asset, session, h): y = +1 up barrier first, -1 down barrier first, 0 neither
(scorer's evaluate_path on daily bars, adverse-first inside a bar, as the scorer does pre-June).
Delivery: the outcome becomes usable at the pre-open of the session after the touching session
(or after the window end for y=0), which is what loop.matured_outcomes does with daily bars
(experiment 01 measured 42% at +1, 70% at +2 on the holdout with the loop's own function).

Model family (one statistic, so learning and frozen are the same function):
    m = exponentially weighted mean of delivered y, half-life L outcomes; direction = sign(m).
    frozen: m computed in fit from outcomes delivered before train_end, never updated.
    learning: same start, updated with each delivered outcome of its own asset.
Comparators: 5-session prevailing null (scorer's trailing_move_pct), and the same EW statistic
computed from PRICES at predict (sign of trailing K-session move) to test whether "learning" is
just price momentum a frozen model could read itself.

Selection of L uses 2022-2024 blocks only; 2025-01..2026-05 is the confirmation set.
Writes results.json next to this file.
"""

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np
import pandas as pd

from swing_dataset.kit import ASSETS, loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

HERE = Path(__file__).resolve().parent
CUTOFF = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
HALF_LIVES = (3, 5, 10, 20, 40, 80)
PRICE_LOOKBACKS = (5, 10, 20, 60, 120)
H = 5
BLOCK_SESSIONS = 104  # holdout length
FWD = 5


def labels(prices, asset):
    dates = prices.session_dates(asset)
    out = []
    for i, d in enumerate(dates):
        t = loop.preopen_instant(d)
        if ns_of(t) >= ns_of(CUTOFF):
            break
        thr = THRESHOLD_PCT[asset]
        p = {s: prices.evaluate_path(asset, t, H, s, {"f": thr}, {"a": thr}) for s in ("up", "down")}
        if any(v is None or not v.window_complete for v in p.values()):
            continue
        up, dn = p["up"], p["down"]
        y = 1 if up.first("f", "a") else -1 if dn.first("f", "a") else 0
        touch = [v.touches.get("f") for v in (up, dn) if v.touches.get("f") is not None]
        _, _, _, first, last = prices.window(asset, t, H)
        decided_pos = min(tp[0] for tp in touch) if touch else last
        deliver_pos = decided_pos + 1  # pre-open of the next session
        if deliver_pos >= len(dates) or ns_of(loop.preopen_instant(dates[deliver_pos])) >= ns_of(CUTOFF):
            continue
        null = prices.trailing_move_pct(asset, t, 5)
        mom = {k: prices.trailing_move_pct(asset, t, k) for k in PRICE_LOOKBACKS}
        out.append(dict(asset=asset, i=i, date=d, y=y, deliver=deliver_pos,
                        null=1 if (null is None or null >= 0) else -1,
                        **{f"mom{k}": (np.nan if v is None else np.sign(v) or 1) for k, v in mom.items()}))
    return pd.DataFrame(out)


def ew_state(ys, L):
    a = 0.5 ** (1.0 / L)
    m = 0.0
    for y in ys:
        m = a * m + (1 - a) * y
    return m


def run_block(df, start_i, n, L, asset):
    """Fit at session start_i (outcomes delivered at or before start_i), score n sessions."""
    hist = df[df["deliver"] <= start_i].sort_values(["deliver", "i"])
    m0 = ew_state(hist["y"].to_numpy(), L)
    block = df[(df["i"] >= start_i) & (df["i"] < start_i + n)].sort_values("i")
    if len(block) < n * 0.8:
        return None
    a = 0.5 ** (1.0 / L)
    m = m0
    # outcomes delivered during the block, from any issue time (learning signals every session)
    stream = df[(df["deliver"] > start_i)].sort_values(["deliver", "i"])
    s_idx = 0
    sv = stream[["deliver", "y"]].to_numpy()
    rec = []
    for r in block.itertuples():
        while s_idx < len(sv) and sv[s_idx, 0] <= r.i:
            m = a * m + (1 - a) * sv[s_idx, 1]
            s_idx += 1
        dl = 1 if m >= 0 else -1
        df_ = 1 if m0 >= 0 else -1
        rec.append((r.i, int(r.y == dl), int(r.y == df_), int(r.y == r.null),
                    *[int(r.y == getattr(r, f"mom{k}")) for k in PRICE_LOOKBACKS]))
    return np.array(rec)


def summarize(recs):
    a = np.vstack(recs)
    half = len(a) // 2
    o = dict(n=len(a), learning=100 * a[:, 1].mean(), frozen=100 * a[:, 2].mean(), null=100 * a[:, 3].mean())
    for j, k in enumerate(PRICE_LOOKBACKS):
        o[f"price_mom{k}"] = 100 * a[:, 4 + j].mean()
    o["gain_pp"] = o["learning"] - o["frozen"]
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in o.items()}


def main():
    pit = PointInTime(Path(__import__("sys").argv[1]))
    prices, _ = loop.price_view(pit, CUTOFF, lookback_sessions=None)
    frames = {a: labels(prices, a) for a in ASSETS}
    for a, f in frames.items():
        f["year"] = pd.to_datetime(f["date"]).dt.year
    results = {"base_rates": {}, "blocks": {}, "forward_like": {}}
    for a, f in frames.items():
        results["base_rates"][a] = {str(y): dict(n=len(g), up=round(100*(g.y==1).mean(),1),
                                     down=round(100*(g.y==-1).mean(),1), neither=round(100*(g.y==0).mean(),1))
                                    for y, g in f.groupby("year")}
    # holdout-like blocks: start every ~6 months
    starts = ["2022-01-03", "2022-06-01", "2023-01-02", "2023-06-01", "2024-01-01",
              "2024-06-03", "2025-01-01", "2025-06-02", "2026-01-01"]
    for L in HALF_LIVES:
        per_block = {}
        for s in starts:
            recs, halves = [], []
            for a, f in frames.items():
                dates = pd.to_datetime(pd.Series(prices.session_dates(a)))
                si = int(np.searchsorted(dates, pd.Timestamp(s)))
                r = run_block(f, si, BLOCK_SESSIONS, L, a)
                if r is not None:
                    recs.append(r)
            sm = summarize(recs)
            # halves by within-block position
            allr = np.vstack([r for r in recs])
            pos = np.concatenate([np.arange(len(r)) for r in recs])
            mid = np.median(pos)
            sm["first_half"] = round(100 * allr[pos < mid, 1].mean(), 2)
            sm["second_half"] = round(100 * allr[pos >= mid, 1].mean(), 2)
            per_block[s] = sm
        results["blocks"][f"L{L}"] = per_block
        # forward-like: every 5-session window, fit at window start
        gains, lw, fz = [], [], []
        by_period = {"select_2022_2024": [], "confirm_2025_2026": []}
        for a, f in frames.items():
            dates = pd.to_datetime(pd.Series(prices.session_dates(a)))
            for si in range(int(np.searchsorted(dates, pd.Timestamp("2022-01-01"))), len(dates) - FWD):
                r = run_block(f, si, FWD, L, a)
                if r is None:
                    continue
                key = "select_2022_2024" if dates.iloc[si].year <= 2024 else "confirm_2025_2026"
                by_period[key].append((dates.iloc[si], a, r[:, 1].sum(), r[:, 2].sum(), len(r)))
        fw = {}
        for key, rows in by_period.items():
            d = pd.DataFrame(rows, columns=["start", "asset", "learn", "frozen", "n"])
            w = d.groupby("start")[["learn", "frozen", "n"]].sum()  # all four assets pooled per window
            g = 100 * (w["learn"] - w["frozen"]) / w["n"]
            fw[key] = dict(windows=len(w), mean_gain_pp=round(g.mean(), 2),
                           p_gain_positive=round(100 * (g > 0).mean(), 1),
                           p_gain_zero=round(100 * (g == 0).mean(), 1),
                           p_gain_ge_5pp=round(100 * (g >= 5).mean(), 1),
                           mean_learning_dir=round(100 * (w["learn"] / w["n"]).mean(), 1))
        results["forward_like"][f"L{L}"] = fw
    (HERE / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main()
