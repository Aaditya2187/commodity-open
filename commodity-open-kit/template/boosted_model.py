"""Task 2 gradient-boosted candidate; no claim of prize qualification.
Selection: 2024; adaptation selection: 2025; diagnostic audit: Jan-May 2026.
All these periods precede the official holdout. No direct pack reads or network.
"""
from __future__ import annotations
import json
import math
import sys
from datetime import datetime, UTC
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2 import THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

ASSETS = ("gold", "silver", "copper", "crude")
HS = (3, 5)
SEED = 20261024
CUTOFFS = (0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)
ETAS = (0.0, 0.05, 0.15)


def log(s):
    print("[boosted] " + s, file=sys.stderr, flush=True)


def feature_table(chain, asset):
    c = chain.sort_values("session_date").reset_index(drop=True).copy()
    t = THRESHOLD_PCT[asset] / 100.0
    lw = c["log_w"].astype(float)
    rv = c["rv20"].astype(float).where(lambda v: v > 0)
    f = pd.DataFrame(index=c.index)
    for k in (1, 5, 20):
        r = c[f"ret{k}"].astype(float)
        f[f"r{k}"] = r / t
        f[f"z{k}"] = r / (rv * math.sqrt(k))
    f["z60"] = (lw - lw.shift(60)) / (rv * math.sqrt(60))
    f["rv"] = rv / t
    f["rv_change"] = np.log(rv / rv.shift(20))
    f["stretch"] = c["stretch"].astype(float)
    for w in (20, 60):
        hi, lo = lw.rolling(w).max(), lw.rolling(w).min()
        f[f"pos{w}"] = (lw - lo) / (hi - lo).replace(0, np.nan)
        f[f"dhi{w}"] = (hi - lw) / t
        f[f"dlo{w}"] = (lw - lo) / t
    ran = (c["high"] - c["low"]).astype(float)
    f["range"] = ran / c["settlement"] / t
    f["clv"] = (c["settlement"] - c["low"]) / ran.replace(0, np.nan)
    vol = c["volume_lots"].astype(float).where(lambda v: v > 0)
    f["volume"] = np.log(vol / vol.rolling(20).mean())
    f["expiry"] = (pd.to_datetime(c["expiry_date"]) - pd.to_datetime(c["session_date"])).dt.days
    clock = pd.DatetimeIndex(pd.to_datetime(c["available_utc"], utc=True))
    if clock.hasnans:
        raise ValueError("Missing chain availability clock")
    # Every feature depends only on this row and earlier chain rows.
    effective = np.maximum.accumulate(clock.asi8)
    return effective, f.replace([np.inf, -np.inf], np.nan), c["session_date"].tolist()


def tables(chains):
    return {a: feature_table(chains.chains[a], a) for a in ASSETS if a in chains.chains}


def snapshot(ts, instant, asset):
    own = ts.get(asset)
    if own is None:
        return None
    instant_ns = ns_of(instant)
    positions = {a: int(np.searchsorted(v[0], instant_ns, side="left")) - 1 for a, v in ts.items()}
    k = positions[asset]
    if k < 60:
        return None
    row = own[1].iloc[k]
    if not np.isfinite(row["rv"]) or not np.isfinite(row["r20"]):
        return None
    vals = list(row.to_numpy(dtype=float))
    for a in ASSETS:
        j = positions.get(a, -1)
        if j < 0:
            vals.extend([np.nan, np.nan])
        else:
            other = ts[a][1].iloc[j]
            vals.extend([float(other["z5"]), float(other["z20"])])
    vals.extend(float(a == asset) for a in ASSETS)
    return np.asarray(vals, dtype=float)


def build_panel(pack, end):
    prices, chains = price_view(pack, end, lookback_sessions=None)
    ts = tables(chains)
    rows, xx = [], []
    for asset in ASSETS:
        log(f"building training labels: {asset}")
        for i in range(len(prices.session_dates(asset))):
            instant, _ = prices.session_bounds(asset, i)
            if pd.Timestamp(instant) >= pd.Timestamp(end):
                continue
            x = snapshot(ts, instant, asset)
            if x is None:
                continue
            threshold = THRESHOLD_PCT[asset]
            for h in HS:
                paths = {d: prices.evaluate_path(asset, instant, h, d,
                    {"target": threshold}, {"adverse": threshold}) for d in ("up", "down")}
                if any(p is None or not p.window_complete for p in paths.values()):
                    continue
                finish = max(pd.Timestamp(p.window_end_utc) for p in paths.values())
                # Require the following pre-open's daily information to be available as well.
                maturity_ns = ns_of(finish) + 12 * 3600 * 10**9
                if maturity_ns >= ns_of(end):
                    continue
                u, d = paths["up"], paths["down"]
                yu, yd = bool(u.first("target", "adverse")), bool(d.first("target", "adverse"))
                if yu and yd:
                    raise ValueError("Both directions realized; inspect price-path implementation")
                rows.append(dict(asset=asset, t=ns_of(instant), end=maturity_ns, h=h,
                    y=1 if yu else -1 if yd else 0,
                    up=float(u.mfe_pct), down=float(d.mfe_pct),
                    amb_up=bool(u.ambiguous), amb_down=bool(d.ambiguous)))
                xx.append(np.r_[x, float(h)])
    panel = pd.DataFrame(rows)
    if len(panel) < 2000:
        raise ValueError(f"Only {len(panel)} training rows")
    order = panel.sort_values(["t", "asset", "h"], kind="stable").index.to_numpy()
    return panel.loc[order].reset_index(drop=True), np.asarray(xx)[order]


def fit_hgb(X, y):
    with threadpool_limits(limits=1):
        m = HistGradientBoostingClassifier(max_iter=180, learning_rate=0.04,
            max_depth=3, min_samples_leaf=80, l2_regularization=3.0,
            early_stopping=False, random_state=SEED).fit(X, y)
    return m


def probabilities(model, X):
    with threadpool_limits(limits=1):
        p = model.predict_proba(X)
    return np.column_stack([p[:, list(model.classes_).index(c)]
        if c in model.classes_ else np.zeros(len(X)) for c in (1, -1)])


def best_rows(panel, prob, cutoff):
    f = panel[["asset", "t", "h"]].copy()
    f["i"] = np.arange(len(f))
    f["conf"] = prob.max(axis=1)
    # Stable tie break favors the smaller horizon.
    f = f.sort_values(["conf", "h"], ascending=[False, True], kind="stable")
    f = f.drop_duplicates(["asset", "t"])
    return np.sort(f.loc[f["conf"] >= cutoff, "i"].to_numpy())


def policy_selection(panel, p):
    choices = []
    for cutoff in CUTOFFS:
        ids = best_rows(panel, p, cutoff)
        counts = panel.iloc[ids]["asset"].value_counts()
        if len(ids) < 120 or any(counts.get(a, 0) < 15 for a in ASSETS):
            continue
        d = np.where(p[ids, 0] >= p[ids, 1], 1, -1)
        acc = float(np.mean(d == panel.iloc[ids]["y"].to_numpy()))
        # Selection heuristic, not an official uncertainty interval.
        objective = acc - 0.15 / math.sqrt(len(ids) / 5.0)
        choices.append((objective, -cutoff, cutoff, len(ids), acc))
    if not choices:
        raise ValueError("No selection policy has adequate pre-holdout sample support")
    best = max(choices)
    return best[2], [dict(cutoff=c[2], n=c[3], direction=100*c[4]) for c in choices]


def corrected(p, asset, bias):
    logits = np.log(np.clip(p, 1e-5, 1-1e-5) / np.clip(1-p, 1e-5, 1))
    return 1 / (1 + np.exp(-np.clip(logits + bias.get(asset, np.zeros(2)), -15, 15)))


def adjust(bias, asset, side, p, outcome, eta):
    b = bias.setdefault(asset, np.zeros(2))
    b[side] = float(np.clip(0.995*b[side] + eta*(outcome-p), -0.75, 0.75))


def simulate(panel, p, cutoff, eta):
    ids = best_rows(panel, p, cutoff)
    bias, waiting, records = {}, [], []
    t_all = panel["t"].to_numpy()
    for instant in np.unique(t_all[ids]):
        remaining = []
        for end, a, side, estimate, outcome, ambiguous in waiting:
            if end < instant:
                if not ambiguous:
                    adjust(bias, a, side, estimate, outcome, eta)
            else:
                remaining.append((end, a, side, estimate, outcome, ambiguous))
        waiting = remaining
        for i in ids[t_all[ids] == instant]:
            r = panel.iloc[i]
            q = corrected(p[i], r.asset, bias)
            side, base = int(np.argmax(q)), int(np.argmax(p[i]))
            d = 1 if side == 0 else -1
            ok, frozen = int(r.y == d), int(r.y == (1 if base == 0 else -1))
            amb = bool(r.amb_up if side == 0 else r.amb_down)
            waiting.append((int(r.end), r.asset, side, float(q[side]), ok, amb))
            records.append((int(instant), ok, frozen))
    if not records:
        return dict(n=0, direction=None, frozen=None, gain_pp=None, first=None, second=None)
    a = np.asarray(records)
    days = np.unique(t_all)
    middle = days[len(days)//2]
    first, second = a[:, 0] < middle, a[:, 0] >= middle
    learning, frozen = float(a[:, 1].mean()), float(a[:, 2].mean())
    return dict(n=len(a), direction=100*learning, frozen=100*frozen,
        gain_pp=100*(learning-frozen),
        first=float(100*a[first, 1].mean()) if first.any() else None,
        second=float(100*a[second, 1].mean()) if second.any() else None)


def cutoff_ns(s):
    return ns_of(pd.Timestamp(s, tz="UTC"))


def validation(panel, X):
    outputs = {}
    preds = {}
    for year, start, stop in (("2024", "2024-01-01", "2025-01-01"),
                              ("2025", "2025-01-01", "2026-01-01"),
                              ("2026_preJune", "2026-01-01", "2026-06-01")):
        train = panel["end"].to_numpy() < cutoff_ns(start)
        test = (panel["t"].to_numpy() >= cutoff_ns(start)) & (panel["end"].to_numpy() < cutoff_ns(stop))
        if train.sum() < 1000 or test.sum() < 100:
            raise ValueError(f"Not enough examples for validation {year}")
        log(f"validation {year}: train {train.sum()}, test {test.sum()}")
        m = fit_hgb(X[train], panel.loc[train, "y"].to_numpy())
        preds[year] = (panel.loc[test].reset_index(drop=True), probabilities(m, X[test]))
    frame, p = preds["2024"]
    cutoff, choices = policy_selection(frame, p)
    frame, p = preds["2025"]
    trials = [dict(eta=eta, **simulate(frame, p, cutoff, eta)) for eta in ETAS]
    viable = [r for r in trials if r["n"] >= 80]
    if not viable:
        raise ValueError("Too few selected signals in 2025 to choose an update strength")
    # Conservative: zero adaptation is allowed to win. It is not prize-eligible learning.
    pick = max(viable, key=lambda r: (r["direction"], -r["eta"]))
    eta = pick["eta"]
    frame, p = preds["2026_preJune"]
    audit = simulate(frame, p, cutoff, eta)
    outputs.update(policy_selection_2024=choices, selected_cutoff=cutoff,
        adaptation_selection_2025=trials, selected_eta=eta, audit_2026_preJune=audit,
        audit_note="daily-bar labels; conservative completed-window delayed updates; NOT official replay",
        positive_learning_evidence=bool(eta > 0 and audit["gain_pp"] is not None and audit["gain_pp"] > 0),
        audit_direction_at_least_60=bool(audit["direction"] is not None and audit["direction"] >= 60))
    log(json.dumps(outputs, sort_keys=True))
    return cutoff, eta, outputs


class SwingForecaster:
    SEED = SEED
    TRAINING_DATA_CUTOFF = "capped at 2026-06-01 03:00 UTC; no pretrained weights"

    def __init__(self, challenge=2, horizons=(3, 5)):
        if challenge != 2:
            raise ValueError("This candidate supports Task 2 only")
        if set(horizons) != set(HS):
            raise ValueError("Run this candidate with --horizons 3,5")
        self.horizons = HS
        self.pending = {}
        self.bias = {}
        self.received = self.used = self.skipped = 0
        self._asof = None
        self._decisions = {}

    def fit(self, pack, train_end):
        self.pack = pack
        limit = datetime(2026, 6, 1, 3, 0, tzinfo=UTC)
        end = min(pd.Timestamp(train_end), pd.Timestamp(limit)).to_pydatetime()
        panel, X = build_panel(pack, end)
        self.cutoff, self.eta, self.validation_info = validation(panel, X)
        log(f"fitting final classifier on {len(panel)} pre-cutoff examples")
        self.selector = fit_hgb(X, panel["y"].to_numpy())
        self.band_samples = {}
        for h in HS:
            for direction, label in (("up", 1), ("down", -1)):
                pooled = panel[(panel.h == h) & (panel.y == label)][direction].to_numpy(dtype=float)
                for asset in ASSETS:
                    v = panel[(panel.h == h) & (panel.y == label) & (panel.asset == asset)][direction].to_numpy(dtype=float)
                    if len(v) < 30:
                        # Normalize pooled magnitudes to this asset's threshold.
                        pool = panel[(panel.h == h) & (panel.y == label)]
                        v = pool[direction].to_numpy(dtype=float) / np.array([THRESHOLD_PCT[a] for a in pool.asset]) * THRESHOLD_PCT[asset]
                    v = v[np.isfinite(v) & (v > 0)]
                    if len(v) < 10:
                        raise ValueError(f"Insufficient band data for {asset}/{h}/{direction}")
                    self.band_samples[(asset, h, direction)] = tuple(float(q) for q in np.quantile(v, [.1, .5, .9]))
        return dict(model="HGB shared selector plus online success calibration", rows=len(panel),
            feature_count=X.shape[1], train_end=end.isoformat(), validation=self.validation_info,
            magnitude="fixed training-only successful completed-window quantiles",
            limitations="preJune validation is a daily-bar delayed-update proxy, not official tick replay")

    def _prepare(self, as_of):
        if self._asof == as_of:
            return
        # Whole available history avoids truncation-dependent feature differences.
        _, chains = price_view(self.pack, as_of, lookback_sessions=None)
        ts = tables(chains)
        self._decisions = {}
        for asset in ASSETS:
            x = snapshot(ts, as_of, asset)
            if x is None:
                continue
            xx = np.stack([np.r_[x, h] for h in HS])
            p = probabilities(self.selector, xx)
            k = int(np.argmax(p.max(axis=1)))
            h = HS[k]
            self._decisions[asset] = (h, p[k])
        self._asof = as_of

    def predict(self, as_of, asset, horizon):
        self._prepare(as_of)
        choice = self._decisions.get(asset)
        if choice is None:
            return {"reason": "insufficient published history for daily features"}
        h, p = choice
        if int(horizon) != h:
            return {"reason": "the unchanged selector preferred the other eligible horizon"}
        conf = float(p.max())
        if conf < self.cutoff:
            return {"reason": f"selector confidence {conf:.4f} below preJune-selected cutoff {self.cutoff:.2f}"}
        q = corrected(p, asset, self.bias)
        side = int(np.argmax(q))
        direction = "up" if side == 0 else "down"
        lo, mid, hi = self.band_samples[(asset, h, direction)]
        hi = min(hi, lo + (12.0 - 1e-9) * THRESHOLD_PCT[asset])
        mid = min(max(mid, lo), hi)
        self.pending[(asset, ns_of(as_of), h)] = (side, float(q[side]))
        return dict(direction=direction, expected_pct=mid, p10_pct=lo, p90_pct=hi,
            invalidation_pct=THRESHOLD_PCT[asset],
            evidence=f"available daily momentum/volatility/range/expiry and as-of cross-asset features; HGB selector {conf:.4f}; success calibration eta={self.eta:.2f}; completed training-window magnitude quantiles")

    def update(self, matured_outcomes):
        for row in matured_outcomes.itertuples():
            self.received += 1
            saved = self.pending.pop((str(row.asset), ns_of(row.signal_utc), int(row.horizon)), None)
            ambiguous = getattr(row, "ambiguous", None)
            realized = getattr(row, "realized", None)
            if saved is None or pd.isna(ambiguous) or bool(ambiguous) or pd.isna(realized) or bool(getattr(row, "no_price", False)):
                self.skipped += 1
                continue
            side, p = saved
            adjust(self.bias, str(row.asset), side, p, int(bool(realized)), self.eta)
            self.used += 1
        return dict(received=self.received, used=self.used, skipped=self.skipped,
            eta=self.eta, bias={a: b.tolist() for a,b in sorted(self.bias.items())})


def build(challenge, horizons=(3, 5)):
    return SwingForecaster(challenge, horizons)


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    from swing_dataset.pack.pit import PointInTime
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("boosted_preJune_validation.json"))
    a = ap.parse_args()
    m = SwingForecaster()
    result = m.fit(PointInTime(a.pack), datetime(2026, 6, 1, 3, tzinfo=UTC))
    a.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["validation"], indent=2, allow_nan=False))
    print("Validation written to", a.out)
