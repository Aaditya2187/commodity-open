#!/usr/bin/env python3
"""POST-HOC mechanism checks for experiment 03 (not part of the pre-registered screen; no selection).

1. Placebo: direction = sign of the xyz perp move over the 9 hours BEFORE the entry-price observation
   (information already inside p0). If this also beats the null by ~20pp, the effect is generic
   momentum, not a stale entry price.
2. Pass-through: does the next MCX session open (designated contract, first window session) move
   from p0 in the direction of the overnight gap?
Reads at the cutoff only. Writes posthoc.json.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gaplib
from gap_test import CUTOFF, signal_rows
from swing_dataset.kit import loop
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import outcomes as O, signals as SIG
from swing_dataset.scoring2.prices import ns_of

pit = PointInTime(Path(sys.argv[1]))
prices, _ = loop.price_view(pit, CUTOFF.to_pydatetime())
gaps = pd.read_parquet(HERE / "gaps.parquet")
ok = gaps[gaps["missing"].isna()].reset_index(drop=True)
plac = []
for r in ok.itertuples():
    s = gaplib.candles(pit, r.signal_utc)[gaplib.HL_SYMBOL[r.asset]]
    a = ns_of(r.anchor_utc)
    x1 = gaplib.last_close(s, a, strict=False)
    x0 = gaplib.last_close(s, a - 9 * 3600 * 10**9, strict=False)
    plac.append(np.nan if (x0 is None or x1 is None) else 100 * (x1[0] / x0[0] - 1))
out = {"note": "post-hoc diagnostics; not used for any selection"}
for h in (3, 5):
    res = {}
    for name, col in (("overnight_gap", ok["gap_pct"]), ("placebo_pre_anchor_9h", pd.Series(plac))):
        g = ok.assign(gap_pct=col).dropna(subset=["gap_pct"])
        sig, _ = signal_rows(g, h)
        gr = O.grade_c2(SIG.normalize(sig, 2).signals, prices)
        gr = gr[gr["scorable"].fillna(False).astype(bool)]
        res[name] = {"n": int(len(gr)), "direction": round(100 * gr["realized"].astype(bool).mean(), 1)}
    out[f"h{h}"] = res
# pass-through to the next MCX open
daily = pit.frame('mcx/mcx_daily', CUTOFF.to_pydatetime()).collect(columns=['asset','session_date','contract_id','open'])
agree, mov = [], []
for r in ok.itertuples():
    _, _, _, first, _ = prices.window(r.asset, r.signal_utc, 1)
    fr = prices.frame(r.asset)
    if first >= len(fr):
        continue
    d = prices.session_dates(r.asset)[first]
    hit = daily[(daily.asset == r.asset) & (daily.session_date == d) & (daily.contract_id == r.contract)]
    o = float(hit["open"].iloc[0]) if len(hit) else np.nan
    if np.isfinite(o) and o > 0:
        m = 100 * (o / r.p0 - 1)
        mov.append((r.asset, r.gap_pct, m))
mv = pd.DataFrame(mov, columns=["asset", "gap", "open_move"])
out["passthrough_open_vs_p0"] = {a: {"n": len(g), "sign_agree_pct": round(100 * (np.sign(g.gap) == np.sign(g.open_move)).mean(), 1),
                                     "slope": round(float(np.polyfit(g.gap, g.open_move, 1)[0]), 2),
                                     "corr": round(float(g.gap.corr(g.open_move)), 2)} for a, g in mv.groupby("asset")}
(HERE / "posthoc.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=1))
