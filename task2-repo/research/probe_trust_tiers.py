"""Trust and cross-asset-agreement buckets, for the repeat schedule and the disagreement gate.

Fits gap-night-cat at ``--fit`` and walks ``--from`` to ``--to``. Prints, for horizon-5 gap
slots that pass the night-range rule, how often the gap direction won (chain labels), by the
CatBoost trust probability and by whether the other metals' gaps all agreed. Writes nothing.

    python research/probe_trust_tiers.py --fit 2026-04-01 --from 2026-04-01 --to 2026-05-22
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model import GapNightCat, ISSUED_HORIZONS, MIN_GAP, NIGHT_RANGE_MIN  # noqa: E402
from swing_dataset.kit.loop import session_bounds, trading_days  # noqa: E402
from swing_dataset.pack.pit import PointInTime  # noqa: E402
from task2.labels import build_labels  # noqa: E402

PACK = ROOT / "v2.1"
EDGES = (0.0, 0.70, 0.75, 0.80, 0.83, 0.87, 0.91, 1.01)
CHAIN_COLUMNS = ["asset", "cutoff_utc", "horizon", "k", "session_date", "w_high", "w_low", "w_close", "denominator"]


def _won(frame: pd.DataFrame) -> str:
    return f"n={len(frame):4d} won={frame['won'].mean():.3f}" if len(frame) else "n=   0"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit", type=date.fromisoformat, default=date(2026, 6, 1))
    parser.add_argument("--from", dest="start", type=date.fromisoformat, default=date(2026, 6, 1))
    parser.add_argument("--to", dest="end", type=date.fromisoformat, default=date(2026, 8, 31))
    args = parser.parse_args()
    fit_at = datetime(args.fit.year, args.fit.month, args.fit.day, 3, 0, tzinfo=UTC)
    pit = PointInTime(PACK)
    model = GapNightCat(2, ISSUED_HORIZONS)
    info = model.fit(pit, fit_at)
    print("fit", info["trust"], flush=True)
    labels_asof = datetime(args.end.year, args.end.month, args.end.day, 3, 0, tzinfo=UTC) + timedelta(days=21)
    chain = pit.frame("labels/chain_daily", labels_asof).collect(columns=CHAIN_COLUMNS)
    labels = build_labels(chain, horizons=ISSUED_HORIZONS)
    labels = labels[labels["complete"]]
    outcome = {
        (a, int(pd.Timestamp(c).value)): lab
        for a, c, lab in zip(labels["asset"], labels["cutoff_utc"], labels["label"])
    }
    bounds = session_bounds(pit, fit_at, args.start, args.end)
    rows = []
    for day in trading_days(pit, fit_at, args.start, args.end):
        instant = bounds[day][0]
        instant_ns = int(pd.Timestamp(instant).value)
        for asset, g in model._state(instant).items():
            if "reason" in g or abs(g["gap_thr"]) < MIN_GAP or not g["night_range"] >= NIGHT_RANGE_MIN:
                continue
            label = outcome.get((asset, instant_ns))
            if label is None:
                continue
            p = model.trust.score(g["trust"])
            won = label == ("up" if g["gap_thr"] > 0 else "down")
            rows.append((p, won, asset, float(g["trust"].get("agree", 0.5))))
    frame = pd.DataFrame(rows, columns=["p", "won", "asset", "agree"])
    issued = frame[frame["p"] >= model.trust.threshold]
    print(f"rule slots {_won(frame)}", flush=True)
    print(f"issued (trust) {_won(issued)}", flush=True)
    print(f"issued, others do not all agree {_won(issued[issued['agree'] < 1.0])}", flush=True)
    print(f"issued, others all agree        {_won(issued[issued['agree'] >= 1.0])}", flush=True)
    for lo, hi in zip(EDGES, EDGES[1:]):
        part = frame[(frame["p"] >= lo) & (frame["p"] < hi)]
        if len(part):
            print(f"  trust [{lo:.2f},{hi:.2f}) {_won(part)}", flush=True)


if __name__ == "__main__":
    main()
