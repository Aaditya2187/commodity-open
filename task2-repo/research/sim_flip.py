#!/usr/bin/env python3
"""Research only: can any online learner, fed only delivered outcomes, flip the gap direction profitably?

Reads research/slots_holdout.parquet. At each session index, a learner is refitted on the slots whose
outcome was delivered by that session (deliver_idx <= session), then decides each slot of the session:
keep the gap direction or flip it. Reports net flips and paired gain on the issued keys and on every
gap slot, for several learners and margins.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

S = pd.read_parquet("research/slots_holdout.parquet")
S = S[S["gap_thr"].notna()].sort_values(["session_idx", "asset", "horizon"]).reset_index(drop=True)
sg = np.sign(S["gap_thr"].to_numpy())
up, dn = S["realized_up"].astype(bool).to_numpy(), S["realized_down"].astype(bool).to_numpy()
S["hit"] = np.where(sg > 0, up, dn)
S["opp"] = np.where(sg > 0, dn, up)
DIRECTIONAL = {"ret_1", "ret_2", "ret_5", "ret_10", "ret_20", "ret_60", "dist_ma_20", "dist_ma_50", "gap_open",
               "hl_gap_last3", "hl_ret_1d", "hl_ret_5d", "funding_last", "funding_mean_24", "premium_last",
               "cot_mm_chg_1w", "oi_chg_1", "inr_chg_1", "inr_chg_5", "others_ret5_gold", "others_ret5_silver",
               "others_ret5_copper", "others_ret5_crude"}
CENTERED = {"hl_night_pos", "range_pos_20", "close_loc"}
X = {}
for c in [c for c in S.columns if c.startswith("f_")]:
    b = c[2:]
    v = S[c].to_numpy(float)
    X[b] = v * sg if b in DIRECTIONAL else (v - 0.5) * sg if b in CENTERED else v
X["abs_gap"] = np.abs(S["gap_thr"].to_numpy())
X["p_move"] = S["p_move"].to_numpy(float)
X["h"] = S["horizon"].to_numpy(float)
for t in ("hlq", "te", "cx", "sh"):
    X[f"src_{t}"] = S[f"gap_{t}"].to_numpy(float) * sg
for a in ("gold", "silver", "copper", "crude"):
    X[f"is_{a}"] = (S["asset"] == a).to_numpy(float)
X = pd.DataFrame(X).replace([np.inf, -np.inf], np.nan)
X = X.loc[:, X.notna().mean() > 0.5]

SETS = {
    "small": ["abs_gap", "ret_5", "hl_night_range", "vol_60", "p_move", "h"],
    "small+asset": ["abs_gap", "ret_5", "hl_night_range", "vol_60", "p_move", "h", "is_gold", "is_silver", "is_copper", "is_crude"],
    "sources": ["abs_gap", "src_hlq", "src_te", "src_sh", "h"],
    "all": list(X.columns),
}


def run(cols, C, margin, scope):
    Xs = X[cols].to_numpy(float)
    flips = np.zeros(len(S), bool)
    for i in sorted(S["session_idx"].unique()):
        now = (S["session_idx"] == i).to_numpy()
        train = (S["deliver_idx"] <= i).to_numpy() & (S["session_idx"] < i).to_numpy() & scope
        decisive = train & (S["hit"] | S["opp"]).to_numpy()
        y = S["opp"].to_numpy()[decisive].astype(int)
        if decisive.sum() < 30 or y.sum() < 5 or y.sum() == len(y) or not (now & scope).any():
            continue
        Xt = Xs[decisive]
        mu, sd = np.nanmean(Xt, 0), np.nanstd(Xt, 0)
        sd[~np.isfinite(sd) | (sd == 0)] = 1.0
        mu[~np.isfinite(mu)] = 0.0
        f = lambda A: np.nan_to_num((A - mu) / sd)
        m = LogisticRegression(C=C, max_iter=500).fit(f(Xt), y)
        p = m.predict_proba(f(Xs[now & scope]))[:, 1]
        idx = np.where(now & scope)[0]
        flips[idx] = p > 0.5 + margin
    hit, opp = S["hit"].to_numpy(), S["opp"].to_numpy()
    sel = scope
    gain = (opp & flips & sel).sum() - (hit & flips & sel).sum()
    return int((flips & sel).sum()), int(gain), 100.0 * gain / sel.sum(), int(sel.sum())


issued = S["issued"].fillna(False).astype(bool).to_numpy()
everything = np.ones(len(S), bool)
print("scope set C margin | flips net_keys gain_pp n")
for scope_name, scope in (("issued", issued), ("all_gap_slots", everything)):
    for name, cols in SETS.items():
        cols = [c for c in cols if c in X.columns]
        for C in (0.05, 0.3, 1.0):
            for margin in (0.0, 0.1):
                r = run(cols, C, margin, scope)
                print(scope_name, name, C, margin, "|", r)
