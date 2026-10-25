"""Task 2 online logistic forecaster ("ologit"): frozen copy = fit only; learning copy = fit + updates.

Per horizon (3 and 5) a logistic model of P(up barrier first | a barrier was hit) on four
pre-open features, each divided by the asset's threshold and clipped to [-3, 3]:

    gap   overseas (Hyperliquid xyz 1h) move from the entry-price observation to the signal
    m5    trailing 5-session move of the designated contract (the null's input)
    m20   trailing 20-session move
    plus an intercept.

fit(): Gaussian prior N(0, PRIOR_VAR I), Newton iterations (a Laplace fit) on every decided
pre-open label whose outcome is known from rows available before train_end. Standardization is fixed
at fit.
update(): each delivered outcome of the model's own signal becomes a label (up first / down first;
neither and ambiguous daily bars are skipped). The weights take one online-Newton step per label
(Laplace posterior update): precision A <- LAMBDA * A + p(1-p) x x^T, then w <- w + A^-1 x (y - p).
LAMBDA < 1 forgets old evidence so the weights can track drift. Prediction = sign(p - 0.5); no
abstention.

The frozen copy and the learning copy run the same fit and the same predict. Only update() differs,
and the loop never calls it for the frozen copy.
Pack reads go only through the PointInTime client. Timestamps are compared as nanosecond integers.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from swing_dataset.kit.loop import price_view, preopen_instant, trading_days
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

SPEC_VERSION = "ologit-v1"
SEED = 20261025  # nothing random; recorded for the manifest
ISSUED_HORIZONS = (3, 5)
ASSETS = ("copper", "crude", "gold", "silver")
HL_TABLE = "macro/hl_candles_1h"
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
FEATURES = ("intercept", "gap", "m5", "m20")
CLIP = 3.0
PRIOR_VAR = 1.0
NEWTON_ITERS = 25
LAMBDA = float(os.environ.get("OLOGIT_LAMBDA", "1.0"))  # set per predeclared config; recorded in fit info
#: Which weights update() may move: "all" (round 1) or "gap" (revision R1).
UPDATE_MASK = os.environ.get("OLOGIT_UPDATE_MASK", "all")
PRICE_LOOKBACK_SESSIONS = 40
P10_SHARE, WIDTH_SHARE, EXPECTED_SHARE = 0.999, 1.0 - 1e-9, 2.0


def to_ns(values) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ns").asi8


def last_close(series, t_ns: int, *, strict: bool):
    close_ns, avail_ns, px = series
    i = int(np.searchsorted(close_ns, t_ns, side="left" if strict else "right")) - 1
    while i >= 0 and (avail_ns[i] > t_ns or (strict and avail_ns[i] >= t_ns)):
        i -= 1
    return None if i < 0 else (float(px[i]), int(close_ns[i]))


def candle_series(pack, asof) -> dict:
    frame = pack.frame(HL_TABLE, pd.Timestamp(asof).to_pydatetime()).collect(
        columns=["instrument", "close_utc", "close", "available_utc"])
    out = {}
    for inst, g in frame.groupby("instrument", sort=True):
        g = g.sort_values("close_utc", kind="stable")
        out[str(inst)] = (to_ns(g["close_utc"]), to_ns(g["available_utc"]), g["close"].to_numpy(float))
    return out


def features(prices, series: dict, asset: str, when) -> dict:
    """Raw features at a pre-open instant, or {'reason': ...}. Uses only rows available before ``when``."""
    t_ns = ns_of(when)
    if asset not in prices.assets():
        return {"reason": "no MCX prices for this asset"}
    contract = prices.designated_contract(asset, when)
    if contract is None:
        return {"reason": "no designated contract for this session"}
    quoted = prices.price_at(asset, contract, when)
    if quoted is None:
        return {"reason": f"no entry price for {contract}"}
    _p0, source, p_avail = quoted
    # Anchor = when the entry price was traded. A tick captured after the last session closed
    # (e.g. a 08:29 IST pre-open snapshot) carries a trade from at most that close, so the anchor
    # is capped at the last completed session's close (gap-v1 defect, found in exp 05).
    closes = prices.frame(asset)["close_utc"]
    closes_ns = to_ns(closes)
    k = int(np.searchsorted(closes_ns, t_ns, side="left")) - 1
    anchor_ns = ns_of(p_avail)
    if k >= 0:
        anchor_ns = min(anchor_ns, int(closes_ns[k]))
    s = series.get(HL_SYMBOL[asset])
    if s is None:
        return {"reason": f"no {HL_SYMBOL[asset]} candles"}
    r0, r1 = last_close(s, anchor_ns, strict=False), last_close(s, t_ns, strict=True)
    if r0 is None or r1 is None or r1[1] <= r0[1]:
        return {"reason": f"no {HL_SYMBOL[asset]} candle closed between the entry trade and the signal"}
    m5 = prices.trailing_move_pct(asset, when, 5)
    m20 = prices.trailing_move_pct(asset, when, 20)
    if m5 is None or m20 is None:
        return {"reason": "fewer than 20 published sessions of history"}
    thr = THRESHOLD_PCT[asset]
    raw = {"gap": 100.0 * (r1[0] / r0[0] - 1.0) / thr, "m5": m5 / thr, "m20": m20 / thr}
    return {"raw": raw, "contract": contract, "source": source, "anchor_ns": anchor_ns}


def vec(raw: dict) -> np.ndarray:
    return np.array([1.0] + [float(np.clip(raw[f], -CLIP, CLIP)) for f in FEATURES[1:]])


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def laplace_fit(X: np.ndarray, y: np.ndarray, prior_var: float) -> tuple[np.ndarray, np.ndarray]:
    d = X.shape[1]
    w = np.zeros(d)
    P0 = np.eye(d) / prior_var
    for _ in range(NEWTON_ITERS):
        p = sigmoid(X @ w)
        g = X.T @ (y - p) - P0 @ w
        H = (X * (p * (1 - p))[:, None]).T @ X + P0
        step = np.linalg.solve(H, g)
        w = w + step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = sigmoid(X @ w)
    A = (X * (p * (1 - p))[:, None]).T @ X + P0
    return w, A


def band(asset: str):
    thr = THRESHOLD_PCT[asset]
    p10 = P10_SHARE * thr
    return EXPECTED_SHARE * thr, p10, p10 + BAND_WIDTH_CAP * thr * WIDTH_SHARE


def training_panel(pack, train_end) -> pd.DataFrame:
    """Decided pre-open labels known from rows available before train_end, with their features."""
    prices, _ = price_view(pack, train_end, lookback_sessions=None, quotes=True)
    series = candle_series(pack, train_end)
    first_candle = min(int(s[0][0]) for s in series.values()) if series else None
    if first_candle is None:
        return pd.DataFrame()
    start = pd.Timestamp(first_candle, tz="UTC").date()
    days = trading_days(pack, train_end, start, pd.Timestamp(train_end).date())
    rows = []
    for d in days:
        t = preopen_instant(d)
        if ns_of(t) >= ns_of(train_end):
            break
        for asset in ASSETS:
            f = features(prices, series, asset, t)
            if "reason" in f:
                continue
            thr = THRESHOLD_PCT[asset]
            for h in ISSUED_HORIZONS:
                p = {s: prices.evaluate_path(asset, t, h, s, {"f": thr}, {"a": thr}) for s in ("up", "down")}
                if any(v is None for v in p.values()):
                    continue
                up = p["up"].first("f", "a")
                dn = p["down"].first("f", "a")
                decided = p["up"].decided(("f", "a"))
                if not decided:
                    continue  # neither (or not yet decided): not a direction label
                if p["up"].ambiguous or p["down"].ambiguous:
                    continue
                if up == dn:
                    continue
                rows.append({"asset": asset, "t_ns": ns_of(t), "h": h, "y": 1.0 if up else 0.0, **f["raw"]})
    return pd.DataFrame(rows)


class OnlineLogit:
    SEED = SEED
    TRAINING_DATA_CUTOFF = "the train_end passed to fit(); no pretrained weights"

    def __init__(self, challenge: int = 2, horizons=ISSUED_HORIZONS, lam: float | None = None) -> None:
        if challenge != 2:
            raise ValueError("Task 2 only")
        self.called_horizons = tuple(sorted(int(h) for h in horizons))
        self.lam = LAMBDA if lam is None else float(lam)
        self.mask = UPDATE_MASK
        self.pack = None
        self.w: dict[int, np.ndarray] = {}
        self.A: dict[int, np.ndarray] = {}
        self.pending: dict[tuple, np.ndarray] = {}
        self._cache_ns = None
        self._cache: dict = {}
        self.update_log: list[dict] = []

    # ---- state helpers (for tests and logs)
    def state_digest(self) -> str:
        import hashlib
        h = hashlib.sha256()
        for k in sorted(self.w):
            h.update(np.round(self.w[k], 12).tobytes())
            h.update(np.round(self.A[k], 12).tobytes())
        return h.hexdigest()

    def fit(self, pack, train_end: datetime) -> dict:
        self.pack = pack
        panel = training_panel(pack, train_end)
        if panel.empty:
            raise ValueError("no training labels before train_end")
        info = {"spec": SPEC_VERSION, "lambda": self.lam, "update_mask": self.mask, "prior_var": PRIOR_VAR, "features": list(FEATURES),
                "train_end_utc": pd.Timestamp(train_end).isoformat(), "rows": {}}
        for h in ISSUED_HORIZONS:
            g = panel[panel["h"] == h].sort_values(["t_ns", "asset"], kind="stable")
            X = np.stack([vec(r) for r in g[list(FEATURES[1:])].to_dict("records")])
            w, A = laplace_fit(X, g["y"].to_numpy(float), PRIOR_VAR)
            self.w[h], self.A[h] = w, A
            info["rows"][str(h)] = int(len(g))
            info[f"w_h{h}"] = [round(float(v), 6) for v in w]
            info[f"first_label_utc_h{h}"] = str(pd.Timestamp(int(g["t_ns"].min()), tz="UTC"))
            info[f"last_label_signal_utc_h{h}"] = str(pd.Timestamp(int(g["t_ns"].max()), tz="UTC"))
        info["state_digest"] = self.state_digest()
        return info

    def _features(self, as_of) -> dict:
        t_ns = ns_of(as_of)
        if self._cache_ns != t_ns:
            prices, _ = price_view(self.pack, as_of, lookback_sessions=PRICE_LOOKBACK_SESSIONS, quotes=True)
            series = candle_series(self.pack, as_of)
            self._cache = {a: features(prices, series, a, as_of) for a in ASSETS}
            self._cache_ns = t_ns
        return self._cache

    def predict(self, as_of, asset: str, horizon: int):
        if int(horizon) != self.called_horizons[0]:
            return {"reason": f"issues horizons {ISSUED_HORIZONS} on the first call at this instant"}
        f = self._features(as_of).get(asset)
        if f is None or "reason" in f:
            return {"reason": (f or {}).get("reason", "asset not covered")}
        x = vec(f["raw"])
        out = []
        expected, p10, p90 = band(asset)
        for h in ISSUED_HORIZONS:
            p = float(sigmoid(x @ self.w[h]))
            self.pending[(asset, ns_of(as_of), h)] = x
            out.append({
                "direction": "up" if p >= 0.5 else "down", "horizon": h,
                "expected_pct": expected, "p10_pct": p10, "p90_pct": p90,
                "invalidation_pct": THRESHOLD_PCT[asset],
                "evidence": (f"{SPEC_VERSION} lam={self.lam}: P(up first)={p:.4f}; gap={f['raw']['gap']:+.3f} "
                             f"m5={f['raw']['m5']:+.3f} m20={f['raw']['m20']:+.3f} thresholds; entry {f['source']} of "
                             f"{f['contract']} anchored {pd.Timestamp(f['anchor_ns'], tz='UTC').isoformat()}"),
            })
        return out

    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        used = skipped = 0
        latest_signal = None
        latest_window_end = None
        before = self.state_digest()
        rows = matured_outcomes.sort_values(["signal_utc", "asset", "horizon"], kind="stable")
        for r in rows.itertuples():
            key = (str(r.asset), ns_of(r.signal_utc), int(r.horizon))
            x = self.pending.pop(key, None)
            thr = float(r.threshold_pct)
            realized = bool(r.realized) if pd.notna(r.realized) else False
            adverse = bool(pd.notna(r.mae_pct) and float(r.mae_pct) >= thr - 1e-9)
            if x is None or int(r.horizon) not in self.w or bool(r.ambiguous) or not (realized or adverse):
                skipped += 1
                continue
            up_first = realized if r.direction == "up" else (not realized)
            y = 1.0 if up_first else 0.0
            h = int(r.horizon)
            w, A = self.w[h], self.A[h] * self.lam
            p = float(sigmoid(x @ w))
            A = A + p * (1 - p) * np.outer(x, x)
            if self.mask == "gap":
                j = FEATURES.index("gap")
                step = np.zeros_like(w)
                step[j] = x[j] * (y - p) / A[j, j]
                self.w[h] = w + step
            else:
                self.w[h] = w + np.linalg.solve(A, x * (y - p))
            self.A[h] = A
            used += 1
            ts = pd.Timestamp(r.signal_utc)
            latest_signal = ts if latest_signal is None or ts > latest_signal else latest_signal
            we = pd.Timestamp(r.window_end_utc) if pd.notna(r.window_end_utc) else None
            if we is not None and (latest_window_end is None or we > latest_window_end):
                latest_window_end = we
        rec = {"received": int(len(matured_outcomes)), "used": used, "skipped": skipped,
               "latest_label_signal_utc": None if latest_signal is None else latest_signal.isoformat(),
               "latest_label_window_end_utc": None if latest_window_end is None else latest_window_end.isoformat(),
               "state_before": before[:12], "state_after": self.state_digest()[:12]}
        self.update_log.append(rec)
        path = os.environ.get("OLOGIT_UPDATE_LOG")
        if path:
            with open(path, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
        return rec


def build(challenge: int, horizons=ISSUED_HORIZONS) -> OnlineLogit:
    return OnlineLogit(challenge, horizons)
