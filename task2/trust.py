"""Trust features and the CatBoost trust model for gap-night-cat.

Features of one (pre-open, asset) slot, all from what the model read at that pre-open: the gap and
the overnight range in thresholds, the hourly Hyperliquid path between the entry observation and
the signal (its range, where the last price sits in it, how much of the range the gap covers, the
last one and three hours aligned with the gap), whether the other assets' gaps point the same way
(metals against the other metals, crude against the metals), and the 20-session volatility.

``TrustModel`` is a CatBoost classifier of whether the gap direction wins the barrier race within
the horizon, fitted once in ``fit`` on slots before ``train_end``. Its threshold keeps the share of
training slots that the night-range rule keeps.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

TRUST_FEATURES = ["abs_gap", "night_range", "nr_anchor", "eff", "pos_al", "last1_al", "last3_al", "agree", "vol_20"]
METALS = ("gold", "silver", "copper")
CATBOOST_PARAMS = dict(iterations=300, depth=3, learning_rate=0.03, l2_leaf_reg=5, verbose=False,
                       thread_count=1, allow_writing_files=False)


def _ns(values) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ns").asi8


def path_features(c1: pd.DataFrame, instrument: str, g: dict, thr: float) -> dict:
    """Range, position and last moves of the hourly path from the entry candle to the signal candle."""
    s = c1[c1["instrument"] == instrument].sort_values("close_utc", kind="stable")
    close_ns = _ns(s["close_utc"])
    i0 = int(np.searchsorted(close_ns, g["ref0_ns"], side="left"))
    i1 = int(np.searchsorted(close_ns, g["ref1_ns"], side="left"))
    if i1 >= len(s) or i1 <= i0 or close_ns[i0] != g["ref0_ns"] or close_ns[i1] != g["ref1_ns"]:
        return {}
    px, hi, lo = s["close"].to_numpy(float), s["high"].to_numpy(float), s["low"].to_numpy(float)
    seg_hi, seg_lo = hi[i0 + 1 : i1 + 1].max(), lo[i0 + 1 : i1 + 1].min()
    sign = 1.0 if g["gap_thr"] > 0 else -1.0
    nr = 100.0 * (seg_hi / seg_lo - 1.0) / thr
    return {
        "nr_anchor": nr,
        "eff": abs(g["gap_thr"]) / nr if nr > 0 else np.nan,
        "pos_al": ((px[i1] - seg_lo) / (seg_hi - seg_lo) - 0.5) * sign if seg_hi > seg_lo else 0.0,
        "last1_al": 100.0 * (px[i1] / px[i1 - 1] - 1.0) / thr * sign,
        "last3_al": 100.0 * (px[i1] / px[max(i0, i1 - 3)] - 1.0) / thr * sign,
    }


def slot_features(states: dict[str, dict], c1: pd.DataFrame, hl_symbol: dict, thresholds: dict) -> dict[str, dict]:
    """Trust features for every asset with a gap at one pre-open."""
    gaps = {a: g["gap_thr"] for a, g in states.items() if "reason" not in g}
    out = {}
    for asset, g in states.items():
        if "reason" in g:
            continue
        others = [a for a in METALS if a != asset] if asset in METALS else list(METALS)
        signs = [np.sign(gaps[a]) for a in others if a in gaps]
        f = {"abs_gap": abs(g["gap_thr"]), "night_range": g["night_range"], "vol_20": g["vol_20"],
             "agree": float(np.mean(np.array(signs) == np.sign(g["gap_thr"]))) if signs else 0.5}
        f.update(path_features(c1, hl_symbol[asset], g, thresholds[asset]))
        out[asset] = f
    return out


class TrustModel:
    def __init__(self, seed: int) -> None:
        self.model = CatBoostClassifier(random_seed=seed, **CATBOOST_PARAMS)
        self.threshold = None

    def _frame(self, rows) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=TRUST_FEATURES).astype(float)

    def fit(self, rows: list[dict], won: np.ndarray, keep_share: float) -> dict:
        X = self._frame(rows)
        self.model.fit(X, won.astype(int))
        p = self.model.predict_proba(X)[:, 1]
        self.threshold = float(np.quantile(p, 1.0 - keep_share))
        return {"rows": int(len(X)), "won_share": round(float(won.mean()), 6), "keep_share": round(float(keep_share), 6),
                "threshold": round(self.threshold, 6)}

    def score(self, row: dict) -> float:
        return float(self.model.predict_proba(self._frame([row]))[:, 1][0])
