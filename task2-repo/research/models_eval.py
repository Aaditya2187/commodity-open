#!/usr/bin/env python3
"""Research only: trust models for abstention, trained on one period and tested on the other.

    python research/models_eval.py

Rows: every slot with |gap| >= 0.3 thresholds. Target: the gap direction realized at h5. A model
scores P(hit); it signals the slots above a threshold set on the training period so that its
training coverage equals the v2 rule's (|gap| >= 0.3 and night range >= 1.0). Primary test:
train 20 Feb - 22 May, test the holdout, which is what a fit at 1 June can do. Reverse test:
train holdout, test 20 Feb - 22 May. Reported: direction at h5 and h3+h5 pooled on the test
period, count, halves, against the v2 rule and the h5-only rule on the same period.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier

warnings.filterwarnings("ignore")
SEED = 20261025
STATIC = ["abs_gap", "night_range", "nr_anchor", "eff", "pos_al", "last1_al", "last3_al", "agree", "f_vol_20"]
PATH = [f"path_{k}" for k in range(12)]


def load(path: str) -> pd.DataFrame:
    s = pd.read_parquet(path)
    s = s[s["gap_thr"].notna()].copy()
    sg = np.sign(s["gap_thr"].to_numpy())
    for h in (3, 5):
        s[f"hit_h{h}"] = np.where(sg > 0, s[f"real_up_h{h}"], s[f"real_down_h{h}"]).astype(bool)
    s["abs_gap"] = s["gap_thr"].abs()
    s["last1_al"], s["last3_al"] = s["last1"] * sg, s["last3"] * sg
    s["pos_al"] = (s["pos_anchor"] - 0.5) * sg
    for c in PATH:
        s[c] = s[c] * sg
    piv = s.pivot_table(index="session_idx", columns="asset", values="gap_thr")
    agree = []
    for r in s.itertuples():
        others = piv.loc[r.session_idx].drop(r.asset)
        if r.asset != "crude":
            others = others[[a for a in ("gold", "silver", "copper") if a != r.asset and a in others.index]]
        o = others.dropna()
        agree.append(float(np.mean(np.sign(o.to_numpy()) == np.sign(r.gap_thr))) if len(o) else 0.5)
    s["agree"] = agree
    n = s["session_idx"].max() + 1
    s["half"] = np.where(s["session_idx"] < n // 2, 1, 2)
    return s[s["abs_gap"] >= 0.3].reset_index(drop=True)


def standardize(tr, te):
    mu, sd = np.nanmean(tr, 0), np.nanstd(tr, 0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    mu[~np.isfinite(mu)] = 0.0
    return np.nan_to_num((tr - mu) / sd), np.nan_to_num((te - mu) / sd)


def m_logit(tr, te, y):
    a, b = standardize(tr[STATIC].to_numpy(float), te[STATIC].to_numpy(float))
    return LogisticRegression(C=0.3, max_iter=1000).fit(a, y).predict_proba(b)[:, 1], \
        LogisticRegression(C=0.3, max_iter=1000).fit(a, y).predict_proba(a)[:, 1]


def m_lgbm(tr, te, y):
    m = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.03, num_leaves=4, min_child_samples=15, reg_lambda=2.0,
                           subsample=0.8, subsample_freq=1, colsample_bytree=0.8, deterministic=True,
                           force_row_wise=True, num_threads=1, verbose=-1, random_state=SEED)
    m.fit(tr[STATIC], y)
    return m.predict_proba(te[STATIC])[:, 1], m.predict_proba(tr[STATIC])[:, 1]


def m_cat(tr, te, y):
    m = CatBoostClassifier(iterations=300, depth=3, learning_rate=0.03, l2_leaf_reg=5, random_seed=SEED,
                           verbose=False, thread_count=1, allow_writing_files=False)
    m.fit(tr[STATIC], y)
    return m.predict_proba(te[STATIC])[:, 1], m.predict_proba(tr[STATIC])[:, 1]


def m_knn_path(tr, te, y):
    cols = PATH + ["abs_gap", "nr_anchor"]
    a, b = standardize(tr[cols].to_numpy(float), te[cols].to_numpy(float))
    m = KNeighborsClassifier(n_neighbors=25, weights="distance").fit(a, y)
    return m.predict_proba(b)[:, 1], KNeighborsClassifier(n_neighbors=25).fit(a, y).predict_proba(a)[:, 1]


def m_gru(tr, te, y):
    import torch
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    seq_tr = np.nan_to_num(tr[PATH[::-1]].to_numpy(float))[:, :, None]
    seq_te = np.nan_to_num(te[PATH[::-1]].to_numpy(float))[:, :, None]
    st_tr, st_te = standardize(tr[STATIC].to_numpy(float), te[STATIC].to_numpy(float))

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.gru = torch.nn.GRU(1, 8, batch_first=True)
            self.head = torch.nn.Linear(8 + len(STATIC), 1)
            self.drop = torch.nn.Dropout(0.3)

        def forward(self, s, x):
            _, hN = self.gru(s)
            return self.head(self.drop(torch.cat([hN[-1], x], 1))).squeeze(1)

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=0.01, weight_decay=1e-2)
    S, X, Y = torch.tensor(seq_tr, dtype=torch.float32), torch.tensor(st_tr, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
    for _ in range(150):
        net.train()
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(net(S, X), Y)
        loss.backward()
        opt.step()
    net.eval()
    with torch.no_grad():
        p_te = torch.sigmoid(net(torch.tensor(seq_te, dtype=torch.float32), torch.tensor(st_te, dtype=torch.float32))).numpy()
        p_tr = torch.sigmoid(net(S, X)).numpy()
    return p_te, p_tr


MODELS = {"logistic": m_logit, "lightgbm": m_lgbm, "catboost": m_cat, "knn_path": m_knn_path, "gru_path": m_gru}


def describe(x: pd.DataFrame) -> str:
    if not len(x):
        return "n=0"
    h5, pooled = 100 * x.hit_h5.mean(), 100 * np.r_[x.hit_h3, x.hit_h5].mean()
    h1, h2 = 100 * x[x.half == 1].hit_h5.mean(), 100 * x[x.half == 2].hit_h5.mean()
    return f"n={len(x):3d} h5={h5:5.1f} h3+h5={pooled:5.1f} halves(h5)={h1:5.1f}/{h2:5.1f}"


def main() -> None:
    P, H = load("research/slots2_pre.parquet"), load("research/slots2_holdout.parquet")
    for name, (tr, te) in {"train pre -> test holdout": (P, H), "train holdout -> test pre": (H, P)}.items():
        print(f"\n== {name}")
        rule_tr = (tr.night_range >= 1.0).to_numpy()
        rule_te = (te.night_range >= 1.0).to_numpy()
        cover = rule_tr.mean()
        print(f"{'all |gap|>=0.3':22s} {describe(te)}")
        print(f"{'v2 rule (nr>=1.0)':22s} {describe(te[rule_te])}")
        print(f"{'v2 + agree<1':22s} {describe(te[rule_te & (te.agree < 1).to_numpy()])}")
        y = tr.hit_h5.to_numpy(int)
        for mname, fn in MODELS.items():
            p_te, p_tr = fn(tr, te, y)
            thr = np.quantile(p_tr, 1 - cover)
            sel = p_te >= thr
            print(f"{mname:22s} {describe(te[sel])}")
            both = sel & rule_te
            print(f"{'  ' + mname + ' & v2':22s} {describe(te[both])}")


if __name__ == "__main__":
    main()
