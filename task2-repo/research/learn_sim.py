#!/usr/bin/env python3
"""Research only: offline replay of the learning-vs-frozen mechanic on the slot tables.

    python research/learn_sim.py                      # run every registered learner on every fold

Folds: F2 (fit 2026-03-16, scored 16 Mar - 22 May), F1 (fit 1 Apr, scored 1 Apr - 22 May), HO (fit
1 Jun, scored the holdout). Keys = core + auxiliary. Core keys are the shipped model's signals
(holdout: predictions_v3; development folds: the v2 rule at h5) and keep the gap direction in both
copies. Auxiliary keys take their direction from a learner. Both copies start from the same ``fit``;
the learning copy receives, at each pre-open, the outcomes of its own keys whose ``deliver`` session
has come (daily-bar decision index from research/labels_daily.parquet), as loop.matured_outcomes does.
Outcomes and directions are the scorer's (``grade_c2`` columns of research/slots2_*.parquet).

Scores per fold: direction (learning, pooled), paired gain (pp), improvement = clip(10 x gain),
success = (direction + 100 + improvement) / 3 (depth is 100 for these bands), the null (sign of the
5-session move) at the same keys, halves, and flips (learning right & frozen wrong / the reverse).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

R = "research/"
FOLDS = {"F2": ("pre", "2026-03-16"), "F1": ("pre", "2026-04-01"), "HO": ("holdout", "2026-06-01")}


# ----------------------------------------------------------------------------- data
def _calendar(labels: pd.DataFrame) -> dict:
    days = sorted(pd.to_datetime(labels["cutoff_date"]).dt.normalize().unique())
    return {pd.Timestamp(d): i for i, d in enumerate(days)}


LABELS = pd.read_parquet(R + "labels_daily.parquet")
LABELS["cutoff_date"] = pd.to_datetime(LABELS["cutoff_date"]).dt.normalize()
CAL = _calendar(LABELS)
LABELS["gidx"] = LABELS["cutoff_date"].map(CAL)
LABELS["deliver_g"] = LABELS["gidx"] + LABELS["deliver_k"]


def _keys(table: str) -> pd.DataFrame:
    s = pd.read_parquet(R + f"slots2_{table}.parquet")
    s = s[s["gap_thr"].notna()].copy()
    s["session_date"] = pd.to_datetime(s["session_date"]).dt.normalize()
    s["gidx"] = s["session_date"].map(CAL)
    rows = []
    for h in (1, 2, 3, 4, 5):
        k = s[["asset", "gidx", "session_date", "signal_utc", "gap_thr", "night_range", "f_ret_5", "f_ret_20", "f_vol_20",
               "f_hl_night_pos", "f_dist_ma_20"]].copy()
        k["h"] = h
        k["up"] = s[f"real_up_h{h}"].astype(bool).to_numpy()
        k["dn"] = s[f"real_down_h{h}"].astype(bool).to_numpy()
        rows.append(k)
    k = pd.concat(rows, ignore_index=True)
    k["y"] = np.where(k["up"], 1, np.where(k["dn"], -1, 0))
    lab = LABELS[["asset", "gidx", "horizon", "deliver_k"]].rename(columns={"horizon": "h"})
    k = k.merge(lab, on=["asset", "gidx", "h"], how="left")
    k["deliver_g"] = k["gidx"] + k["deliver_k"].fillna(k["h"]).astype(int)
    k["null"] = np.where(k["f_ret_5"] >= 0, 1, -1)
    k["gap_sign"] = np.sign(k["gap_thr"]).astype(int)
    return k.sort_values(["gidx", "asset", "h"]).reset_index(drop=True)


KEYS = {"pre": _keys("pre"), "holdout": _keys("holdout")}
V3 = pd.read_parquet("predictions_v3/c2_holdout.parquet")
V3 = V3[V3["signal_utc"].notna()]
V3_KEYS = set(zip(V3["asset"], pd.to_datetime(V3["signal_utc"], utc=True), V3["horizon"].astype(int)))


def core_mask(fold: str, k: pd.DataFrame) -> np.ndarray:
    if fold == "HO":
        return np.array([(a, pd.Timestamp(t), h) in V3_KEYS for a, t, h in zip(k["asset"], pd.to_datetime(k["signal_utc"], utc=True), k["h"])])
    return ((k["gap_thr"].abs() >= 0.3) & (k["night_range"] >= 1.0) & (k["h"] == 5)).to_numpy()


def fold_data(fold: str):
    table, start = FOLDS[fold]
    cut = CAL[pd.Timestamp(start)]
    k = KEYS[table]
    test = k[k["gidx"] >= cut].reset_index(drop=True)
    if table == "pre":
        test = test[test["session_date"] <= pd.Timestamp("2026-05-22")].reset_index(drop=True)
    train_slots = pd.concat([KEYS["pre"]], ignore_index=True)
    train_slots = train_slots[(train_slots["gidx"] < cut) & (train_slots["deliver_g"] <= cut)].reset_index(drop=True)
    hist = LABELS[(LABELS["gidx"] < cut) & (LABELS["deliver_g"] <= cut) & LABELS["complete"]].reset_index(drop=True)
    return test, train_slots, hist, cut


# ----------------------------------------------------------------------------- universes
def aux_mask(spec: str, k: pd.DataFrame, core: np.ndarray) -> np.ndarray:
    core_sessions = set(zip(k.loc[core, "asset"], k.loc[core, "gidx"]))
    in_core_session = np.array([(a, g) in core_sessions for a, g in zip(k["asset"], k["gidx"])])
    kind, hs = spec.split(":")
    hs = {int(x) for x in hs.split(",")}
    hmask = k["h"].isin(hs).to_numpy()
    if kind == "coreh":      # other horizons on the core asset-sessions
        return in_core_session & hmask & ~core
    if kind == "noncore":    # asset-sessions without a core signal
        return ~in_core_session & hmask
    if kind == "all":
        return hmask & ~core
    raise ValueError(spec)


# ----------------------------------------------------------------------------- learners
class Learner:
    """Interface: fit(train_slots, hist, cut) once; predict(row) -> +1/-1; update(rows, gidx) per pre-open."""

    def fit(self, train_slots, hist, cut): ...

    def predict(self, r) -> int: ...

    def update(self, rows: pd.DataFrame, g: int): ...


class GapSign(Learner):
    def predict(self, r):
        return int(r.gap_sign) or 1

    def update(self, rows, g):
        pass

    def fit(self, *a):
        pass


@dataclass
class Drift(Learner):
    """L1: per-asset exponentially weighted mean of up-first (+1) / down-first (-1) outcomes, half-life
    ``half`` outcomes, shrunk toward the pooled mean with weight ``pool``. Fit on every daily label
    delivered before the cutoff at the horizons ``hs``; learning adds its own delivered outcomes."""
    half: float = 20.0
    pool: float = 0.0
    hs: tuple = (1, 2, 3, 4, 5)
    num: dict = field(default_factory=dict)
    den: dict = field(default_factory=dict)

    def _add(self, asset, y):
        a = 0.5 ** (1.0 / self.half)
        self.num[asset] = a * self.num.get(asset, 0.0) + y
        self.den[asset] = a * self.den.get(asset, 0.0) + 1.0

    def fit(self, train_slots, hist, cut):
        h = hist[hist["horizon"].isin(self.hs)].sort_values(["deliver_g", "gidx", "asset", "horizon"], kind="stable")
        for a, y in zip(h["asset"], h["y"]):
            self._add(a, y)

    def state(self, asset):
        m = self.num.get(asset, 0.0) / max(self.den.get(asset, 0.0), 1e-9)
        if self.pool <= 0:
            return m
        mp = sum(self.num.values()) / max(sum(self.den.values()), 1e-9)
        d = self.den.get(asset, 0.0)
        return (d * m + self.pool * mp) / (d + self.pool)

    def predict(self, r):
        return 1 if self.state(r.asset) >= 0 else -1

    def update(self, rows, g):
        for a, y in zip(rows["asset"], rows["y"]):
            self._add(a, y)


@dataclass
class Hedge(Learner):
    """L2: exponentially weighted experts. Votes in {-1, 0, +1}; discounted losses (gamma) over decided
    outcomes; weight exp(-eta * loss). Fit runs the same updates over training slots before the cutoff."""
    eta: float = 0.5
    gamma: float = 0.97
    experts: tuple = ("gap", "mom5", "mom20", "rev5", "drift")
    drift_half: float = 20.0
    loss: dict = field(default_factory=dict)
    drift: Drift = None

    def votes(self, r) -> dict:
        v = {}
        for e in self.experts:
            if e == "gap":
                v[e] = int(r.gap_sign)
            elif e == "mom5":
                v[e] = 1 if r.f_ret_5 >= 0 else -1
            elif e == "rev5":
                v[e] = -1 if r.f_ret_5 >= 0 else 1
            elif e == "mom20":
                v[e] = 1 if r.f_ret_20 >= 0 else -1
            elif e == "drift":
                v[e] = self.drift.predict(r)
            elif e == "up":
                v[e] = 1
            elif e == "down":
                v[e] = -1
        return v

    def _learn(self, rows):
        for r in rows.itertuples():
            if r.y == 0:
                continue
            for e, vote in self.votes(r).items():
                l = 0.5 if vote == 0 else float(vote != r.y)
                self.loss[e] = self.gamma * self.loss.get(e, 0.0) + l
        if self.drift is not None:
            self.drift.update(rows, None)

    def fit(self, train_slots, hist, cut):
        self.drift = Drift(half=self.drift_half)
        self.drift.fit(train_slots, hist, cut)
        self.loss = {e: 0.0 for e in self.experts}
        t = train_slots.sort_values(["deliver_g", "gidx", "asset", "h"], kind="stable")
        for r in t.itertuples():
            if r.y == 0:
                continue
            for e, vote in self.votes(r).items():
                l = 0.5 if vote == 0 else float(vote != r.y)
                self.loss[e] = self.gamma * self.loss.get(e, 0.0) + l

    def predict(self, r):
        s = sum(np.exp(-self.eta * self.loss[e]) * v for e, v in self.votes(r).items())
        return 1 if s > 0 else -1 if s < 0 else (int(r.gap_sign) or 1)

    def update(self, rows, g):
        self._learn(rows)


@dataclass
class Refit(Learner):
    """L3: up-first vs down-first classifier on decided rows; the learning copy refits every ``every``
    sessions on the training rows plus its delivered outcomes (recent rows weighted ``recent_w``)."""
    kind: str = "logit"
    every: int = 10
    recent_w: float = 2.0
    feats: tuple = ("gap_thr", "f_ret_5", "f_ret_20", "f_hl_night_pos", "f_dist_ma_20", "h")
    seed: int = 20261025
    train: pd.DataFrame = None
    buf: list = field(default_factory=list)
    last_refit: int = -10 ** 9
    model: object = None

    def _X(self, d):
        X = d[list(self.feats)].astype(float).fillna(0.0).to_numpy()
        A = np.stack([(d["asset"] == a).to_numpy(float) for a in ("gold", "silver", "copper", "crude")], 1)
        return np.hstack([X, A])

    def _fit(self, d, w):
        d = d[d["y"] != 0]
        y = (d["y"] == 1).to_numpy(int)
        if len(d) < 20 or y.min() == y.max():
            self.model = None
            return
        X = self._X(d)
        if self.kind == "logit":
            from sklearn.linear_model import LogisticRegression
            self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
            self.model = LogisticRegression(C=0.3, max_iter=2000).fit((X - self.mu) / self.sd, y, sample_weight=w[(d.index)] if w is not None else None)
        else:
            from catboost import CatBoostClassifier
            self.mu, self.sd = 0.0, 1.0
            self.model = CatBoostClassifier(iterations=200, depth=3, learning_rate=0.05, l2_leaf_reg=5, random_seed=self.seed,
                                            verbose=False, thread_count=1, allow_writing_files=False)
            self.model.fit(X, y, sample_weight=w[(d.index)] if w is not None else None)

    def fit(self, train_slots, hist, cut):
        self.train = train_slots.reset_index(drop=True)
        self._fit(self.train, None)

    def predict(self, r):
        if self.model is None:
            return int(r.gap_sign) or 1
        X = self._X(pd.DataFrame([r._asdict()]))
        p = self.model.predict_proba((X - self.mu) / self.sd)[:, 1][0]
        return 1 if p >= 0.5 else -1

    def update(self, rows, g):
        self.buf.append(rows)
        if g - self.last_refit >= self.every:
            d = pd.concat([self.train] + self.buf, ignore_index=True)
            w = np.ones(len(d))
            w[len(self.train):] = self.recent_w
            self._fit(d, w)
            self.last_refit = g


# ----------------------------------------------------------------------------- replay
def replay(fold: str, learner: Learner, aux: str, apply_core: bool = False) -> dict:
    test, train_slots, hist, cut = fold_data(fold)
    core = core_mask(fold, test)
    auxm = aux_mask(aux, test, core) if aux else np.zeros(len(test), bool)
    keys = test[core | auxm].reset_index(drop=True)
    is_core = (core[core | auxm])
    learner.fit(train_slots, hist, cut)
    frozen, learning = copy.deepcopy(learner), copy.deepcopy(learner)
    dl, df = np.zeros(len(keys), int), np.zeros(len(keys), int)
    for g in sorted(keys["gidx"].unique()):
        due = keys[(keys["deliver_g"] == g) & (keys["gidx"] < g)]
        if len(due):
            learning.update(due, g)
        idx = np.where(keys["gidx"].to_numpy() == g)[0]
        for i in idx:
            r = keys.iloc[i]
            if is_core[i] and not apply_core:
                dl[i] = df[i] = int(r.gap_sign) or 1
            else:
                rr = next(keys.iloc[[i]].itertuples())
                dl[i], df[i] = learning.predict(rr), frozen.predict(rr)
    y = keys["y"].to_numpy()
    hit_l, hit_f, hit_n = dl == y, df == y, keys["null"].to_numpy() == y
    n = len(keys)
    D, F, N = 100 * hit_l.mean(), 100 * hit_f.mean(), 100 * hit_n.mean()
    gain = D - F
    I = min(100.0, max(0.0, 10 * gain))
    sess = sorted(keys["gidx"].unique())
    half = keys["gidx"].isin(sess[: len(sess) // 2]).to_numpy()
    return {"fold": fold, "n": n, "core": int(is_core.sum()), "aux": int((~is_core).sum()), "D": round(D, 2), "F": round(F, 2),
            "gain": round(gain, 2), "I": round(I, 1), "success": round((D + 100 + I) / 3, 2), "null": round(N, 2),
            "aux_D": round(100 * hit_l[~is_core].mean(), 1) if (~is_core).any() else None,
            "aux_F": round(100 * hit_f[~is_core].mean(), 1) if (~is_core).any() else None,
            "h1": round(100 * hit_l[half].mean(), 1), "h2": round(100 * hit_l[~half].mean(), 1),
            "LwFl": int(((dl != df) & hit_l & ~hit_f).sum()), "FwLl": int(((dl != df) & ~hit_l & hit_f).sum())}


def gates(r: dict) -> str:
    ok = [r["D"] >= 60, r["F"] > r["null"], r["gain"] > 0, r["h2"] >= r["h1"], r["success"] >= 70]
    return "".join("Y" if x else "." for x in ok)  # dir>=60, frozen>null, learn>frozen, halves, success>=70


def show(name: str, learner_factory, aux: str, apply_core: bool = False, folds=("F2", "F1", "HO")) -> list[dict]:
    out = []
    for f in folds:
        r = replay(f, learner_factory(), aux, apply_core)
        out.append(r)
    line = " | ".join(f"{r['fold']}: n={r['n']:4d} D={r['D']:5.1f} gain={r['gain']:+5.2f} S={r['success']:5.1f} "
                      f"aux {r['aux_F']}->{r['aux_D']} flips {r['LwFl']}/{r['FwLl']} [{gates(r)}]" for r in out)
    print(f"{name:34s} {aux:16s} {line}", flush=True)
    return out


if __name__ == "__main__":
    show("core only (gap)", GapSign, "")
    show("gap on aux", GapSign, "coreh:1,2")
