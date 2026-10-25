#!/usr/bin/env python3
"""Feasibility bound only (no predictor): the best catch rate any model could get on the holdout if
it signals ONLY at 08:30 IST pre-opens, with an oracle choosing the right direction. A swing counts
as catchable if some pre-open in (turn, extreme] has an entry price (scorer's price_at, designated
contract) with at least half the threshold of the move still ahead. Correctness of the oracle
signal is not even required here, so this is an upper bound."""
import json, sys
from pathlib import Path
import pandas as pd
from swing_dataset.kit import loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import CATCH_ROOM_SHARE
pack = Path(sys.argv[1]); pit = PointInTime(pack)
asof = pd.Timestamp("2026-10-24 06:00", tz="UTC").to_pydatetime()
prices, _ = loop.price_view(pit, asof, quotes=True)
sw = pd.read_parquet(pack / "swings" / "swings.parquet")
sw = sw[(pd.to_datetime(sw.turn_utc, utc=True) >= "2026-06-01") & (pd.to_datetime(sw.extreme_utc, utc=True) <= "2026-10-24")]
days = loop.trading_days(pit, loop.preopen_instant(pd.Timestamp("2026-06-01").date()), pd.Timestamp("2026-06-01").date(), pd.Timestamp("2026-10-23").date())
pre = [pd.Timestamp(loop.preopen_instant(d)) for d in days]
ok = []
for s in sw.itertuples():
    t0, t1 = pd.Timestamp(s.turn_utc), pd.Timestamp(s.extreme_utc)
    hit = False
    for t in pre:
        if t0 < t <= t1:
            c = prices.designated_contract(s.asset, t)
            q = prices.price_at(s.asset, c, t) if c else None
            if q is None: continue
            ahead = (s.extreme_price - q[0]) / q[0] * 100 if s.direction == "up" else (q[0] - s.extreme_price) / q[0] * 100
            if ahead >= CATCH_ROOM_SHARE * s.threshold_pct - 1e-12: hit = True; break
    ok.append(hit)
sw = sw.assign(catchable=ok)
out = {"swings": len(sw), "catchable_preopen_only_upper_bound_pct": round(100 * sw.catchable.mean(), 1),
       "per_asset": sw.groupby("asset").catchable.mean().mul(100).round(1).to_dict()}
print(json.dumps(out, indent=1)); (Path(__file__).with_suffix(".json")).write_text(json.dumps(out, indent=1))
