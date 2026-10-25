"""The learning layer used by ``update`` (learning copy only; the frozen copy never calls it).

``BetaGuard`` is shipped. ``AnalogLearner`` was replayed before the holdout (20 Feb - 22 May 2026,
fit at 20 Feb, research/knn_replay) and its vote never fired: 330 outcomes appended, the highest
neighbour miss share 0.62 against the declared 0.65, paired gain 0.00 pp on 343 keys.

``AnalogLearner``: a same-asset, same-horizon nearest-neighbour vote over past overnight
gaps. Each library row is one gap in threshold units with the 20-session volatility and the
5-session move at that pre-open, and whether the gap's own direction won the barrier race
(``neither`` and an ambiguous bar count as misses, as the scorer counts them). ``fit`` fills the
library from labels resolved before ``train_end``; ``update`` appends the run's own matured
signals. At a new signal the gap direction is kept unless at least VOTE_MISS_SHARE of the K
nearest library gaps missed, and a vote needs at least MIN_NEIGHBORS rows. The frozen copy keeps
its fitted library, so the two copies issue the same keys and differ only where new outcomes
change a vote.

``BetaGuard``: per asset, an exponentially forgotten Beta posterior of the gap
rule's hit rate that inverts the asset's direction when the mean falls below FLIP_BELOW. Measured
before the holdout it never fired (paired gain 0.00 pp), and faster variants lost 1-5 pp.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_dataset.scoring2 import THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

ANALOG_FEATURES = ("hl_gap", "vol_20", "ret_5")
K = 21
MIN_NEIGHBORS = 11
VOTE_MISS_SHARE = 0.65
ANALOG_TAG = "; analog vote flipped the gap direction"


class AnalogLearner:
    def __init__(self) -> None:
        self.library: dict[tuple[str, int], tuple[np.ndarray, np.ndarray]] = {}
        self.issued: dict[tuple[str, int, int], tuple[np.ndarray, str]] = {}
        self.received = 0
        self.appended = 0

    def fit(self, frame: pd.DataFrame, horizons, min_gap: float) -> dict:
        """Library rows from the fit frame: complete windows, a gap of at least ``min_gap`` thresholds."""
        if any(c not in frame.columns for c in ANALOG_FEATURES):
            return {}
        d = frame[frame["horizon"].isin(list(horizons)) & frame["complete"]]
        d = d[np.isfinite(d["hl_gap"].astype(float)) & (d["hl_gap"].astype(float).abs() >= min_gap)]
        d = d.dropna(subset=list(ANALOG_FEATURES)).sort_values(["cutoff_utc", "asset", "horizon"], kind="stable")
        gap_dir = np.where(d["hl_gap"].to_numpy(float) > 0, "up", "down")
        right = d["label"].to_numpy() == gap_dir
        X = d[list(ANALOG_FEATURES)].to_numpy(float)
        for (asset, h), idx in d.reset_index(drop=True).groupby(["asset", "horizon"], sort=True).indices.items():
            self.library[(str(asset), int(h))] = (X[idx], right[idx])
        return {f"{a}_h{h}": int(len(y)) for (a, h), (_, y) in sorted(self.library.items())}

    def _vote(self, asset: str, horizon: int, x: np.ndarray) -> tuple[int, int]:
        X, y = self.library.get((asset, horizon), (np.empty((0, len(ANALOG_FEATURES))), np.empty(0, bool)))
        if len(y) < MIN_NEIGHBORS or not np.isfinite(x).all():
            return 0, int(len(y))
        scale = X.std(axis=0)
        scale[scale <= 1e-12] = 1.0
        dist = np.sqrt((((X - x) / scale) ** 2).sum(axis=1))
        nearest = np.argsort(dist, kind="stable")[: min(K, len(y))]
        return int((~y[nearest]).sum()), int(len(nearest))

    def direction(self, asset: str, horizon: int, rule_dir: str, info: dict) -> tuple[str, str]:
        x = np.array([info["gap_thr"], info.get("vol_20", np.nan), info.get("ret_5", np.nan)], dtype=float)
        self.issued[(asset, int(info["signal_ns"]), int(horizon))] = (x, rule_dir)
        misses, n = self._vote(asset, int(horizon), x)
        if n >= MIN_NEIGHBORS and misses >= VOTE_MISS_SHARE * n:
            return ("down" if rule_dir == "up" else "up"), f"{ANALOG_TAG} ({misses}/{n} nearest gaps missed)"
        return rule_dir, ""

    def update(self, matured: pd.DataFrame) -> dict:
        n = 0 if matured is None else len(matured)
        self.received += n
        added = 0
        if n:
            for _, r in matured.sort_values(["signal_utc", "asset", "horizon"], kind="stable").iterrows():
                if bool(r.get("no_price", False)) or r.get("realized") is None:
                    continue
                key = (str(r["asset"]), ns_of(r["signal_utc"]), int(r["horizon"]))
                stored = self.issued.pop(key, None)
                if stored is None or not np.isfinite(stored[0]).all():
                    continue
                x, rule_dir = stored
                if str(r["direction"]) == rule_dir:
                    gap_right = bool(r["realized"])
                else:
                    adverse = r.get("mae_pct")
                    gap_right = (not bool(r["realized"]) and not bool(r.get("ambiguous", False))
                                 and adverse is not None and float(adverse) >= THRESHOLD_PCT[key[0]])
                X, y = self.library.get((key[0], key[2]), (np.empty((0, len(ANALOG_FEATURES))), np.empty(0, bool)))
                self.library[(key[0], key[2])] = (np.vstack([X, x]), np.append(y, gap_right))
                added += 1
        self.appended += added
        return {"received": self.received, "appended": self.appended, "state_changed": added > 0,
                "library": {f"{a}_h{h}": int(len(y)) for (a, h), (_, y) in sorted(self.library.items())}}


PRIOR_HITS, PRIOR_MISSES = 13.0, 7.0
FORGET = 0.5 ** (1.0 / 30.0)
MIN_EVIDENCE = 20.0
FLIP_BELOW = 0.40
UNFLIP_ABOVE = 0.50
INVERTED_TAG = "; learner inverted the gap direction"


class _Guard:
    def __init__(self) -> None:
        self.hits, self.misses, self.n, self.flipped = PRIOR_HITS, PRIOR_MISSES, 0, False

    def observe(self, rule_right: bool) -> None:
        self.hits = self.hits * FORGET + (1.0 if rule_right else 0.0)
        self.misses = self.misses * FORGET + (0.0 if rule_right else 1.0)
        self.n += 1
        evidence = self.hits + self.misses - (PRIOR_HITS + PRIOR_MISSES) * FORGET ** self.n
        mean = self.hits / (self.hits + self.misses)
        if not self.flipped and evidence >= MIN_EVIDENCE and mean < FLIP_BELOW:
            self.flipped = True
        elif self.flipped and mean > UNFLIP_ABOVE:
            self.flipped = False

    def state(self) -> dict:
        return {"hits": round(self.hits, 6), "misses": round(self.misses, 6), "n": self.n, "flipped": self.flipped}


class BetaGuard:
    def __init__(self) -> None:
        self.guards: dict[str, _Guard] = {}
        self.received = 0

    def fit(self, frame: pd.DataFrame, horizons, min_gap: float) -> dict:
        return {}

    def _g(self, asset: str) -> _Guard:
        return self.guards.setdefault(asset, _Guard())

    def direction(self, asset: str, horizon: int, rule_dir: str, info: dict) -> tuple[str, str]:
        if self._g(asset).flipped:
            return ("down" if rule_dir == "up" else "up"), INVERTED_TAG
        return rule_dir, ""

    def update(self, matured: pd.DataFrame) -> dict:
        n = 0 if matured is None else len(matured)
        self.received += n
        if not n:
            return {"received": self.received, "state_changed": False}
        before = {a: g.flipped for a, g in self.guards.items()}
        for _, r in matured.sort_values(["signal_utc", "asset", "horizon"], kind="stable").iterrows():
            if bool(r.get("no_price", False)) or r.get("realized") is None:
                continue
            inverted = INVERTED_TAG in str(r.get("evidence", ""))
            self._g(str(r["asset"])).observe(bool(r["realized"]) != inverted)
        changed = any(before.get(a, False) != g.flipped for a, g in self.guards.items())
        return {"received": self.received, "state_changed": changed,
                "guards": {a: g.state() for a, g in sorted(self.guards.items())}}


Learner = BetaGuard
