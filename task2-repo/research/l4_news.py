#!/usr/bin/env python3
"""Research only: L4, headline sentiment as a feature only the learning copy can learn (news starts 16 Jul).

    python research/l4_news.py

1. Univariate: on holdout keys, the realized rate of the news-sentiment direction, and who wins when
   it disagrees with the gap. Split into a development half (16 Jul - 31 Aug) and the rest.
2. Learner: learn_sim.Refit with news_night / news_day added as features. Training rows before the
   fit carry 0 news, so the frozen fit cannot use them; the learning copy's refits can.
"""
from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd

import learn_sim as S

news = pd.read_parquet("research/news_holdout.parquet")
news["session_date"] = pd.to_datetime(news["session_date"]).dt.normalize()
news["gidx"] = news["session_date"].map(S.CAL)
cols = ["news_night", "news_day", "news_night_n", "news_day_n"]
for t in ("pre", "holdout"):
    k = S.KEYS[t].drop(columns=[c for c in cols if c in S.KEYS[t].columns])
    if t == "holdout":
        k = k.merge(news[["asset", "gidx"] + cols], on=["asset", "gidx"], how="left")
    for c in cols:
        k[c] = k[c].fillna(0.0) if c in k else 0.0
    S.KEYS[t] = k

k = S.KEYS["holdout"]
k = k[k["news_day_n"] > 0]
for name, part in (("16 Jul-31 Aug", k[k["session_date"] <= "2026-08-31"]), ("Sep-Oct", k[k["session_date"] > "2026-08-31"])):
    for c in ("news_night", "news_day"):
        sg = np.sign(part[c]).astype(int)
        m = sg != 0
        hit = (sg == part["y"])[m]
        dis = m & (sg != part["gap_sign"])
        print(f"{name:14s} {c:10s} n={m.sum():4d} dir={100 * hit.mean():5.1f} | disagree with gap n={dis.sum():4d} "
              f"news right {100 * (sg[dis] == part['y'][dis]).mean():5.1f} gap right {100 * (part['gap_sign'][dis] == part['y'][dis]).mean():5.1f}")

base = ("gap_thr", "f_ret_5", "f_ret_20", "f_hl_night_pos", "f_dist_ma_20", "h")
for aux in ("coreh:1,2,3,4", "noncore:5"):
    S.show("L3 cat every=5 (no news)", partial(S.Refit, kind="cat", every=5, feats=base), aux, folds=("HO",))
    S.show("L4 = L3 + news", partial(S.Refit, kind="cat", every=5, feats=base + ("news_night", "news_day")), aux, folds=("HO",))
    S.show("L4 logit + news", partial(S.Refit, kind="logit", every=5, feats=base + ("news_night", "news_day")), aux, folds=("HO",))
