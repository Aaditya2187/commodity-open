"""Purged walk-forward validation on the barrier-race labels, scored the way the Task 2 scorer scores.

direction = share of issued signals whose direction was realized (label == predicted direction);
abstentions (``no_signal``) leave the denominator, as the rules allow, subject to the 90% coverage
floor which a no_signal row satisfies. Reported beside: the prevailing-direction null and the
gap rule at the same instants, and the coverage (share of slots signalled).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb

from task2.features import FEATURE_COLUMNS

CLASSES = ("up", "down", "neither")
SEED = 20261025


def folds(dates: pd.Series, blocks: list[tuple[str, str]], horizon: int, embargo: int = 5):
    """Expanding-window folds. Train = all cutoffs before block start minus purge (horizon) and embargo."""
    for start, end in blocks:
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        test = (dates >= start) & (dates <= end)
        purge_start = start - pd.tseries.offsets.BDay(horizon + embargo)
        train = dates < purge_start
        yield train.to_numpy(), test.to_numpy(), (start.date(), end.date())


DEFAULT_BLOCKS = [
    ("2023-01-01", "2023-06-30"), ("2023-07-01", "2023-12-31"),
    ("2024-01-01", "2024-06-30"), ("2024-07-01", "2024-12-31"),
    ("2025-01-01", "2025-06-30"), ("2025-07-01", "2025-12-31"),
    ("2026-01-01", "2026-05-31"),
]


LGB_PARAMS = dict(
    n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40, reg_lambda=1.0,
    colsample_bytree=0.6, subsample=0.8, subsample_freq=1,
    deterministic=True, force_row_wise=True, num_threads=1, verbose=-1,
)


class LGBModel:
    """LightGBM multiclass wrapper: asset_id as a categorical, fixed seed, deterministic single thread."""

    def __init__(self, features, seed: int = SEED, **kw) -> None:
        self.features = list(features)
        params = dict(LGB_PARAMS, random_state=seed)
        params.update(kw)
        self.model = lgb.LGBMClassifier(**params)

    def _frame(self, X) -> pd.DataFrame:
        df = pd.DataFrame(np.asarray(X, dtype=float), columns=self.features)
        if "asset_id" in df.columns:
            df["asset_id"] = pd.Categorical(df["asset_id"].round().astype("Int64"), categories=[0, 1, 2, 3])
        return df

    def fit(self, X, y, sample_weight=None):
        cat = ["asset_id"] if "asset_id" in self.features else "auto"
        self.model.fit(self._frame(X), y, sample_weight=sample_weight, categorical_feature=cat)
        return self

    def predict_proba(self, X):
        return self.model.predict_proba(self._frame(X))

    @property
    def classes_(self):
        return self.model.classes_


def make_model(features=FEATURE_COLUMNS, seed: int = SEED, **kw) -> LGBModel:
    return LGBModel(features, seed=seed, **kw)


def sample_weights(dates: pd.Series, half_life_days: float | None) -> np.ndarray | None:
    if not half_life_days:
        return None
    age = (dates.max() - dates).dt.days.to_numpy(float)
    return np.power(0.5, age / half_life_days)


def decide(proba: np.ndarray, classes: list[str], min_conf: float = 0.0, min_margin: float = 0.0):
    """Direction and whether to signal. ``p_dir`` = P(up) or P(down), whichever is larger."""
    pu = proba[:, classes.index("up")]
    pdn = proba[:, classes.index("down")]
    direction = np.where(pu >= pdn, "up", "down")
    p_dir = np.maximum(pu, pdn)
    margin = np.abs(pu - pdn)
    signal = (p_dir >= min_conf) & (margin >= min_margin)
    return direction, p_dir, margin, signal


def score_block(df: pd.DataFrame, direction, signal) -> dict:
    """Task 2 direction on issued rows, null and gap rule at the same instants."""
    issued = df[signal]
    d = direction[signal]
    out = {"n_slots": len(df), "n_issued": int(signal.sum()), "coverage": float(signal.mean())}
    if len(issued) == 0:
        return out
    out["direction"] = 100 * float((issued["label"].to_numpy() == d).mean())
    nd = issued["null_dir"].to_numpy()
    out["null"] = 100 * float((issued["label"].to_numpy() == nd).mean())
    g = issued["hl_gap"].to_numpy()
    has_gap = np.isfinite(g) & (g != 0)
    if has_gap.any():
        gd = np.where(g > 0, "up", "down")
        out["gap_rule_same_rows"] = 100 * float((issued["label"].to_numpy()[has_gap] == gd[has_gap]).mean())
        out["direction_on_gap_rows"] = 100 * float((issued["label"].to_numpy()[has_gap] == d[has_gap]).mean())
        out["n_gap_rows"] = int(has_gap.sum())
    half = len(issued) // 2
    out["first_half"] = 100 * float((issued["label"].to_numpy()[:half] == d[:half]).mean()) if half else np.nan
    out["second_half"] = 100 * float((issued["label"].to_numpy()[half:] == d[half:]).mean()) if half else np.nan
    return out


def walk_forward(frame: pd.DataFrame, horizon: int, blocks=DEFAULT_BLOCKS, features=FEATURE_COLUMNS,
                 half_life_days: float | None = 365.0, min_conf: float = 0.0, min_margin: float = 0.0,
                 model_kw: dict | None = None, drop_ambiguous_train: bool = True):
    df = frame[(frame["horizon"] == horizon) & frame["complete"]].sort_values(["cutoff_utc", "asset"]).reset_index(drop=True)
    dates = pd.to_datetime(df["cutoff_date"])
    results = []
    oof = []
    for tr, te, (s, e) in folds(dates, blocks, horizon):
        trn = df[tr]
        if drop_ambiguous_train:
            trn = trn[~trn["ambiguous"]]
        # a feature with fewer than 2 distinct values in this fold's training set carries nothing
        usable = [f for f in features if trn[f].nunique(dropna=True) >= 2]
        model = make_model(usable, **(model_kw or {}))
        w = sample_weights(pd.to_datetime(trn["cutoff_date"]), half_life_days)
        model.fit(trn[usable].to_numpy(float), trn["label"].to_numpy(), sample_weight=w)
        tst = df[te]
        proba = model.predict_proba(tst[usable].to_numpy(float))
        classes = list(model.classes_)
        direction, p_dir, margin, signal = decide(proba, classes, min_conf, min_margin)
        r = score_block(tst, direction, signal)
        r.update({"block": f"{s}..{e}", "n_train": len(trn)})
        results.append(r)
        oof.append(tst[["asset", "cutoff_utc", "cutoff_date", "label", "null_dir", "hl_gap"]].assign(
            pred=direction, p_dir=p_dir, margin=margin, signal=signal, block=f"{s}..{e}",
            p_up=proba[:, classes.index("up")], p_down=proba[:, classes.index("down")]))
    return pd.DataFrame(results), pd.concat(oof, ignore_index=True)


def summarize(res: pd.DataFrame) -> str:
    cols = [c for c in ["block", "n_train", "n_issued", "coverage", "direction", "null", "gap_rule_same_rows",
                        "direction_on_gap_rows", "n_gap_rows", "first_half", "second_half"] if c in res.columns]
    return res[cols].round(1).to_string(index=False)
