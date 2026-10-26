"""Would refiling the 08:30 call later in the session add right rows?

Takes the distinct keys of an official holdout file, refiles each at a later instant the same day
with the same direction and band, and grades both with the scorer's own ``grade_c2`` and price
series (ticks included, as the scorer prices an intraday entry). A refile is "extended" when the
last Hyperliquid 1h candle closed before the later instant is further in the call's direction than
the last one closed before 08:30 IST. Writes nothing.

    python research/probe_confirm_instant.py --signals predictions_v4/c2_holdout.parquet
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from swing_dataset.pack.pit import PointInTime  # noqa: E402
from swing_dataset.scoring2 import outcomes as O  # noqa: E402
from swing_dataset.scoring2 import signals as SIG  # noqa: E402
from swing_dataset.scoring2.prices import PriceSeries  # noqa: E402

PACK = ROOT / "v2.1"
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
LATER_MINUTES = (45, 90, 270)  # 09:15, 10:00 and 13:00 IST after an 08:30 IST pre-open
TICKS_FROM = pd.Timestamp("2026-06-22", tz="UTC")
KEY = ["asset", "signal_utc", "horizon"]


def last_close(c1: pd.DataFrame, instrument: str, t: pd.Timestamp) -> float | None:
    s = c1[(c1["instrument"] == instrument) & (c1["close_utc"] < t) & (c1["available_utc"] < t)]
    return None if s.empty else float(s.sort_values("close_utc")["close"].iloc[-1])


def share(frame: pd.DataFrame) -> str:
    scorable = frame[frame["scorable"].fillna(False).astype(bool)]
    if scorable.empty:
        return "n=   0"
    return f"n={len(scorable):4d} direction={100 * scorable['realized'].fillna(False).mean():5.1f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", type=Path, default=ROOT / "predictions_v4" / "c2_holdout.parquet")
    args = parser.parse_args()
    raw = pd.read_parquet(args.signals)
    raw = raw[raw["signal_utc"].notna()].drop_duplicates(KEY).reset_index(drop=True)
    raw["signal_utc"] = pd.to_datetime(raw["signal_utc"], utc=True)
    cols = ["asset", "signal_utc", "direction", "horizon", "expected_pct", "p10_pct", "p90_pct",
            "invalidation_pct", "evidence"]
    prices = PriceSeries.from_paths(
        PACK / "mcx" / "mcx_daily.parquet",
        PACK / "labels" / "designations.parquet",
        PACK / "mcx" / "mcx_sessions.parquet",
        PACK / "pack" / "quotes" / "mcx_quotes.parquet",
    )
    c1 = PointInTime(PACK).frame("macro/hl_candles_1h", datetime(2026, 10, 24, tzinfo=UTC)).collect(
        columns=["instrument", "close_utc", "close", "available_utc"]
    )
    c1["close_utc"] = pd.to_datetime(c1["close_utc"], utc=True)
    c1["available_utc"] = pd.to_datetime(c1["available_utc"], utc=True)

    base = O.grade_c2(SIG.normalize(raw[cols], 2).signals, prices)
    print(f"08:30 rows        all {share(base)}  | before 22 Jun {share(base[base['signal_utc'] < TICKS_FROM])}"
          f"  | from 22 Jun {share(base[base['signal_utc'] >= TICKS_FROM])}", flush=True)
    for minutes in LATER_MINUTES:
        later = raw[cols].copy()
        later["signal_utc"] = later["signal_utc"] + pd.Timedelta(minutes=minutes)
        extended = []
        for row, moved in zip(raw.itertuples(), later["signal_utc"]):
            inst = HL_SYMBOL[row.asset]
            p0, p1 = last_close(c1, inst, row.signal_utc), last_close(c1, inst, moved)
            sign = 1.0 if row.direction == "up" else -1.0
            extended.append(p0 is not None and p1 is not None and sign * (p1 / p0 - 1.0) > 0)
        graded = O.grade_c2(SIG.normalize(later, 2).signals, prices)
        ext = dict(zip(zip(later["asset"], later["signal_utc"]), extended))
        graded["extended"] = [ext.get((a, t), False) for a, t in zip(graded["asset"], graded["signal_utc"])]
        ticks = graded["signal_utc"] >= TICKS_FROM
        print(f"+{minutes:3d} min refile  all {share(graded)}  | before 22 Jun {share(graded[~ticks])}"
              f"  | from 22 Jun {share(graded[ticks])}", flush=True)
        print(f"   extended only  all {share(graded[graded['extended']])}"
              f"  | from 22 Jun {share(graded[ticks & graded['extended']])}", flush=True)
        print(f"   entry sources from 22 Jun: {graded.loc[ticks, 'price_source'].value_counts().to_dict()}", flush=True)


if __name__ == "__main__":
    main()
