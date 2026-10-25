#!/usr/bin/env python3
"""Research only: per-slot headline sentiment for the holdout slot table (news starts 16 July 2026).

    python research/news_feats.py --pack ../v2.1        # writes research/news_holdout.parquet

Reads pack/news/news_rows through PointInTime; each row is admitted at its fetch clock (exact) or
availability clock (published), the instant the point-in-time filter uses. A headline's score is
(up words - down words) / (up words + down words) from a small direction lexicon; a slot's score is
the trust-weighted mean over the asset's headlines admitted in a window before the signal:
``night`` from the entry observation to the signal, ``day`` the 24 hours before the signal.
"""
from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from swing_dataset.pack.pit import PointInTime

UP = {"rise", "rises", "rising", "rose", "gain", "gains", "gained", "rally", "rallies", "rallied", "surge", "surges",
      "surged", "jump", "jumps", "jumped", "climb", "climbs", "climbed", "soar", "soars", "soared", "higher", "high",
      "highs", "record", "bullish", "rebound", "rebounds", "rebounded", "advance", "advances", "advanced", "firm",
      "firms", "firmer", "boost", "boosts", "spike", "spikes", "strengthens", "strong", "upbeat", "up"}
DOWN = {"fall", "falls", "fell", "falling", "drop", "drops", "dropped", "decline", "declines", "declined", "slump",
        "slumps", "slumped", "plunge", "plunges", "plunged", "slide", "slides", "slid", "tumble", "tumbles", "tumbled",
        "sink", "sinks", "sank", "lower", "low", "lows", "bearish", "weaken", "weakens", "weaker", "retreat",
        "retreats", "loss", "losses", "ease", "eases", "eased", "slip", "slips", "slipped", "crash", "down", "weak"}
WORD = re.compile(r"[a-z]+")


def score(title: str) -> float:
    w = WORD.findall(str(title).lower())
    u, d = sum(x in UP for x in w), sum(x in DOWN for x in w)
    return np.nan if u + d == 0 else (u - d) / (u + d)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    pit = PointInTime(ap.parse_args().pack.resolve())
    t = pit.frame("pack/news/news_rows", datetime(2026, 10, 24, 6, tzinfo=UTC)).collect(
        columns=["asset", "original_title", "trust_weight", "fetched_utc", "available_utc", "clock_quality"])
    t = t[t["asset"].notna()].copy()
    q = t["clock_quality"].astype(str)
    adm = pd.to_datetime(t["available_utc"], utc=True).where(q == "published", pd.to_datetime(t["fetched_utc"], utc=True))
    t["admit_ns"] = pd.DatetimeIndex(adm).as_unit("ns").asi8
    t["s"] = t["original_title"].map(score)
    t = t[t["s"].notna()].sort_values("admit_ns")
    by = {a: (g["admit_ns"].to_numpy(), g["s"].to_numpy(float), g["trust_weight"].to_numpy(float)) for a, g in t.groupby("asset")}
    slots = pd.read_parquet(Path(__file__).resolve().parent / "slots2_holdout.parquet")
    rows = []
    for r in slots.itertuples():
        rec = {"asset": r.asset, "session_date": r.session_date}
        ns, s, w = by.get(r.asset, (np.array([], np.int64), np.array([]), np.array([])))
        t1 = int(pd.Timestamp(r.signal_utc).value)
        for name, t0 in (("night", int(r.anchor_ns) if pd.notna(getattr(r, "anchor_ns", np.nan)) else t1 - 12 * 3600 * 10 ** 9),
                         ("day", t1 - 24 * 3600 * 10 ** 9)):
            i0, i1 = np.searchsorted(ns, t0, side="right"), np.searchsorted(ns, t1, side="left")
            rec[f"news_{name}_n"] = int(i1 - i0)
            rec[f"news_{name}"] = float(np.average(s[i0:i1], weights=w[i0:i1])) if i1 > i0 else 0.0
        rows.append(rec)
    out = pd.DataFrame(rows)
    out.to_parquet(Path(__file__).resolve().parent / "news_holdout.parquet")
    nz = out[out["news_day_n"] > 0]
    print("slots", len(out), "with day news", len(nz), "mean n", round(nz["news_day_n"].mean(), 1))


if __name__ == "__main__":
    main()
