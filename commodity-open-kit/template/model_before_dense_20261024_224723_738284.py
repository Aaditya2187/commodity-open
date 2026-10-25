"""Task 2 experimental candidate. Five-session horizon, daily pre-open features.
Not runtime-tested against the kit. Uses only the supplied PointInTime client.
"""
from datetime import datetime
import math
import numpy as np
import pandas as pd
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2 import THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

ASSETS = ("gold", "silver", "copper", "crude")
FEATURES = ("r1", "r5", "r20", "vol", "stretch", "pos20", "range", "volume")


def features(chain, asset):
    c = chain.sort_values("session_date").reset_index(drop=True).copy()
    t = THRESHOLD_PCT[asset] / 100.0
    lw = c["log_w"].astype(float)
    hi, lo = lw.rolling(20).max(), lw.rolling(20).min()
    volume = c["volume_lots"].astype(float).where(lambda s: s > 0)
    f = pd.DataFrame({"available_utc": pd.to_datetime(c["available_utc"], utc=True)})
    f["r1"] = c["ret1"].astype(float) / t
    f["r5"] = c["ret5"].astype(float) / t
    f["r20"] = c["ret20"].astype(float) / t
    f["vol"] = c["rv20"].astype(float) / t
    f["stretch"] = c["stretch"].astype(float)
    f["pos20"] = (lw - lo) / (hi - lo).replace(0, np.nan)
    f["range"] = (c["high"] - c["low"]) / c["settlement"] / t
    f["volume"] = np.log(volume / volume.rolling(20).mean())
    return f


def vector(row, asset):
    values = row[list(FEATURES)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        return None
    return np.r_[np.clip(values, -50, 50), [float(asset == a) for a in ASSETS]]


class SwingForecaster:
    SEED = 20261024
    TRAINING_DATA_CUTOFF = "train_end supplied to fit; no pretrained weights"
    SIGNAL_CUTOFF = 0.60  # Predeclared pilot value, not calibrated or optimized.

    def __init__(self, challenge=2, horizons=(5,)):
        if challenge != 2:
            raise ValueError("This candidate implements Task 2 only")
        self.horizons = tuple(horizons)
        self.pending = {}
        self.bands = {}
        self.models = {}
        self._instant = None
        self._current = {}
        self.updates_used = 0
        self.updates_skipped = 0

    def fit(self, pack, train_end):
        self.pack = pack
        prices, chains = price_view(pack, train_end, lookback_sessions=None)
        X, ys = [], {"up": [], "down": []}
        samples = {}
        for asset in ASSETS:
            if asset not in chains.chains:
                continue
            f = features(chains.chains[asset], asset)
            clock = pd.DatetimeIndex(f["available_utc"]).asi8
            if not pd.Index(clock).is_monotonic_increasing:
                raise ValueError("Nonmonotonic feature availability; needs explicit as-of handling")
            threshold = THRESHOLD_PCT[asset]
            for i in range(len(prices.session_dates(asset))):
                instant, _ = prices.session_bounds(asset, i)
                if pd.Timestamp(instant) >= pd.Timestamp(train_end):
                    continue
                k = int(np.searchsorted(clock, ns_of(instant), side="left")) - 1
                if k < 60:
                    continue
                x = vector(f.iloc[k], asset)
                if x is None:
                    continue
                paths = {d: prices.evaluate_path(asset, instant, 5, d,
                         {"threshold": threshold}, {"adverse": threshold})
                         for d in ("up", "down")}
                if any(p is None or not p.window_complete for p in paths.values()):
                    continue
                if any(pd.Timestamp(p.window_end_utc) >= pd.Timestamp(train_end)
                       for p in paths.values()):
                    continue
                X.append(x)
                for d, p in paths.items():
                    correct = bool(p.first("threshold", "adverse"))
                    ys[d].append(int(correct))
                    if correct and math.isfinite(p.mfe_pct):
                        samples.setdefault((asset, d), []).append(float(p.mfe_pct))
        if len(X) < 200:
            raise ValueError(f"Only {len(X)} usable training examples")
        self.scaler = StandardScaler().fit(np.asarray(X))
        Z = self.scaler.transform(np.asarray(X))
        for d in ("up", "down"):
            y = np.asarray(ys[d], dtype=int)
            if len(np.unique(y)) != 2:
                raise ValueError(f"Missing training class for {d}")
            self.models[d] = SGDClassifier(loss="log_loss", alpha=0.01,
                max_iter=2000, tol=1e-4, random_state=self.SEED,
                shuffle=False, average=False).fit(Z, y)
        for key, v in samples.items():
            if len(v) >= 20:
                self.bands[key] = tuple(float(q) for q in np.quantile(v, [.1, .5, .9]))
        return {"model": "two incremental logistic success heads", "training_rows": len(X),
                "train_end": train_end.isoformat(), "horizon": 5,
                "signal_cutoff": self.SIGNAL_CUTOFF}

    def predict(self, as_of, asset, horizon):
        if int(horizon) != 5:
            return {"reason": "pilot candidate uses five-session forecasts only"}
        if self._instant != as_of:
            _, chains = price_view(self.pack, as_of, lookback_sessions=100)
            self._current = {}
            for a in ASSETS:
                if a not in chains.chains:
                    continue
                f = features(chains.chains[a], a)
                f = f[f["available_utc"] < pd.Timestamp(as_of)]
                if len(f):
                    self._current[a] = vector(f.iloc[-1], a)
            self._instant = as_of
        x = self._current.get(asset)
        if x is None:
            return {"reason": "insufficient finite published daily features"}
        z = self.scaler.transform(x.reshape(1, -1))
        probabilities = {d: float(m.predict_proba(z)[0, list(m.classes_).index(1)])
                         for d, m in self.models.items()}
        d = max(("up", "down"), key=lambda direction: probabilities[direction])
        if probabilities[d] < self.SIGNAL_CUTOFF:
            return {"reason": f"best predicted barrier success {probabilities[d]:.4f} below fixed 0.60 cutoff"}
        key = (asset, d)
        if key not in self.bands:
            return {"reason": "insufficient completed training outcomes for magnitude band"}
        lo, mid, hi = self.bands[key]
        hi = min(hi, lo + 12.0 * THRESHOLD_PCT[asset])
        mid = min(max(mid, lo), hi)
        self.pending[(asset, ns_of(as_of), 5)] = (z.copy(), d)
        return {"direction": d, "expected_pct": mid, "p10_pct": lo, "p90_pct": hi,
                "invalidation_pct": THRESHOLD_PCT[asset],
                "evidence": f"published daily momentum/volatility/range/volume; {d} success estimate {probabilities[d]:.4f}; training-only magnitude band"}

    def update(self, matured_outcomes):
        for row in matured_outcomes.itertuples():
            key = (str(row.asset), ns_of(row.signal_utc), int(row.horizon))
            saved = self.pending.pop(key, None)
            ambiguous = getattr(row, "ambiguous", None)
            if saved is None or pd.isna(ambiguous) or bool(ambiguous):
                self.updates_skipped += 1
                continue
            if pd.isna(row.realized) or bool(getattr(row, "no_price", False)):
                self.updates_skipped += 1
                continue
            z, d = saved
            self.models[d].partial_fit(z, np.array([int(bool(row.realized))]), classes=np.array([0, 1]))
            self.updates_used += 1
        return {"updates_used": self.updates_used, "updates_skipped": self.updates_skipped,
                "magnitude": "fixed completed-window training bands"}


def build(challenge, horizons=(5,)):
    return SwingForecaster(challenge, horizons)
