#!/usr/bin/env python3
"""Research only: daily barrier-race labels for h1-h5 at every pre-open since 2021, with delivery offsets.

    python research/deliveries.py --pack ../v2.1        # writes research/labels_daily.parquet

Read through PointInTime at 2026-10-24 06:00 UTC. ``deliver_k`` is how many sessions after the signal's
session the outcome reaches ``update``: the decisive bar's index (1-based) when a barrier was touched,
the horizon when neither was, matching ``loop.matured_outcomes`` on daily bars.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

import model as M
from swing_dataset.pack.pit import PointInTime
from task2.labels import build_labels

OUT = Path(__file__).resolve().parent / "labels_daily.parquet"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    pit = PointInTime(ap.parse_args().pack.resolve())
    chain = pit.frame("labels/chain_daily", datetime(2026, 10, 24, 6, tzinfo=UTC)).collect(columns=M.CHAIN_COLUMNS)
    lab = build_labels(chain, horizons=(1, 2, 3, 4, 5))
    lab["y"] = np.where(lab["label"] == "up", 1, np.where(lab["label"] == "down", -1, 0))
    lab["deliver_k"] = np.where(lab["hit_k"].notna(), lab["hit_k"], lab["horizon"]).astype(int)
    lab["cutoff_utc"] = pd.to_datetime(lab["cutoff_utc"], utc=True)
    lab[["asset", "cutoff_utc", "cutoff_date", "horizon", "label", "y", "hit_k", "deliver_k", "ambiguous", "complete"]].to_parquet(OUT)
    print("wrote", OUT, len(lab), lab.groupby("horizon")["complete"].mean().round(3).to_dict())


if __name__ == "__main__":
    main()
