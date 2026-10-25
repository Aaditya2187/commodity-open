"""Task 2 model "gap-lgbm": overseas-gap direction, LightGBM move filter, online learning layer.

Three stages, all fitted in ``fit`` from rows the ``PointInTime`` client returns before ``train_end``:

A. **Move model (LightGBM).** Per horizon, a binary LightGBM predicts whether the designated
   contract touches either barrier (the asset threshold up or down) within the horizon. Trained on
   barrier-race labels from ``labels/chain_daily`` (2021 to ``train_end``) with point-in-time daily,
   cross-asset, USD/INR and COT features. Walk-forward AUC 0.59-0.72 over 2023-2025 test blocks.
B. **Direction.** The sign of the Hyperliquid perpetual's move from the scorer's entry observation
   to the pre-open (experiment 03's stale-entry-price mechanism), measured exactly as gap-v1 did.
C. **Abstention.** Signal only when |gap| >= MIN_GAP thresholds and stage A's P(move) is at least its
   MOVE_QUANTILE quantile over the training rows; otherwise a ``no_signal`` row. Both copies apply
   the same rule, so learning and frozen files share every key. Pre-holdout validation
   (Feb-May 2026, five rolling chunks): h3 85.5% on 35% of slots, h5 77.3% on 65%.

``update`` (learning copy only): see ``task2.learner``.

Reads go only through the client handed to ``fit``; LightGBM is deterministic and single-threaded.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import lightgbm as lgb

from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

from task2.features import FEATURE_COLUMNS, build_frame
from task2.labels import build_labels
from task2.learner import Learner

SPEC_VERSION = "gap-lgbm-v1"
SEED = 20261025
ISSUED_HORIZONS = (3, 5)
MIN_GAP = 0.3  # thresholds; chosen on 2026-02-20..2026-05-29 (experiment 03 window), pre-holdout
MOVE_QUANTILE = 0.25  # stage-A filter quantile; chosen on the same pre-holdout window
RECENT_SESSIONS_FOR_QUANTILE = 120
MOVE_FEATURES = [f for f in FEATURE_COLUMNS if not f.startswith(("hl_", "funding", "premium"))]
MOVE_PARAMS = dict(
    n_estimators=300, learning_rate=0.03, num_leaves=7, min_child_samples=60, reg_lambda=1.0,
    colsample_bytree=0.6, subsample=0.8, subsample_freq=1,
    deterministic=True, force_row_wise=True, num_threads=1, verbose=-1, random_state=SEED,
)
RECENCY_HALF_LIFE_DAYS = 730.0
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
DAILY_COLUMNS = ["session_date", "asset", "contract_id", "open", "high", "low", "close", "settlement",
                 "volume_lots", "open_interest", "available_utc"]
CHAIN_COLUMNS = ["asset", "cutoff_utc", "horizon", "k", "session_date", "w_high", "w_low", "w_close", "denominator"]
CANDLE_COLUMNS = ["instrument", "open_utc", "close_utc", "open", "high", "low", "close", "available_utc"]
DAILY_LOOKBACK_DAYS = 450  # covers the 60-session windows and the 20-session ratio z-scores
P10_SHARE = 0.999
WIDTH_SHARE = 1.0 - 1e-9
EXPECTED_SHARE = 2.0


def to_ns(values) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ns").asi8


def last_close(series, t_ns: int, *, strict: bool):
    close_ns, avail_ns, px = series
    i = int(np.searchsorted(close_ns, t_ns, side="left" if strict else "right")) - 1
    while i >= 0 and (avail_ns[i] > t_ns or (strict and avail_ns[i] >= t_ns)):
        i -= 1
    return None if i < 0 else (float(px[i]), int(close_ns[i]))


def band(asset: str) -> tuple[float, float, float]:
    thr = THRESHOLD_PCT[asset]
    p10 = P10_SHARE * thr
    return EXPECTED_SHARE * thr, p10, p10 + BAND_WIDTH_CAP * thr * WIDTH_SHARE


def _move_frame(X: pd.DataFrame) -> pd.DataFrame:
    d = X[MOVE_FEATURES].astype(float).copy()
    d["asset_id"] = pd.Categorical(d["asset_id"].round().astype("Int64"), categories=[0, 1, 2, 3])
    return d


class GapLGBM:
    SEED = SEED
    TRAINING_DATA_CUTOFF = "fit reads only pack rows available before train_end; no pretrained weights"

    def __init__(self, challenge: int = 2, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> None:
        if challenge != 2:
            raise ValueError("this model enters Task 2 only")
        self.called_horizons = tuple(sorted(int(h) for h in horizons))
        self.pack = None
        self.move_models: dict[int, lgb.LGBMClassifier] = {}
        self.move_floor: dict[int, float] = {}
        self.learner = Learner()
        self._cache_ns: int | None = None
        self._cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ reads
    def _tables(self, asof, daily_since=None) -> dict[str, pd.DataFrame]:
        asof = pd.Timestamp(asof).to_pydatetime()
        daily = self.pack.frame("mcx/mcx_daily", asof).collect(columns=DAILY_COLUMNS)
        daily = daily[daily["asset"].isin(list(THRESHOLD_PCT))]
        if daily_since is not None:
            daily = daily[pd.to_datetime(daily["session_date"]) >= pd.Timestamp(daily_since).tz_localize(None)]
        return {
            "daily": daily.reset_index(drop=True),
            "c1": self.pack.frame("macro/hl_candles_1h", asof).collect(columns=CANDLE_COLUMNS),
            "cd": self.pack.frame("macro/hl_candles_1d", asof).collect(columns=CANDLE_COLUMNS),
            "fu": self.pack.frame("macro/hl_funding", asof).collect(
                columns=["instrument", "time_utc", "funding_rate", "premium", "available_utc"]),
            "usd": self.pack.frame("macro/usdinr", asof).collect(columns=["date", "usdinr_fbil", "available_utc"]),
            "cot": self.pack.frame("macro/cot", asof).collect(
                columns=["asset", "report_date", "available_utc", "open_interest_all",
                         "m_money_positions_long_all", "m_money_positions_short_all"]),
        }

    # ------------------------------------------------------------------ fit
    def fit(self, pack, train_end: datetime) -> dict:
        self.pack = pack
        t = self._tables(train_end)
        chain = pack.frame("labels/chain_daily", pd.Timestamp(train_end).to_pydatetime()).collect(columns=CHAIN_COLUMNS)
        labels = build_labels(chain, horizons=ISSUED_HORIZONS)
        frame = build_frame(labels, t["daily"], t["c1"], t["cd"], t["fu"], t["usd"], t["cot"])
        info = {"spec": SPEC_VERSION, "train_end_utc": pd.Timestamp(train_end).isoformat(), "rows": {}}
        for h in ISSUED_HORIZONS:
            d = frame[(frame["horizon"] == h) & frame["complete"] & ~frame["ambiguous"]].sort_values(["cutoff_utc", "asset"])
            y = (d["label"] != "neither").astype(int).to_numpy()
            dates = pd.to_datetime(d["cutoff_date"])
            w = np.power(0.5, (dates.max() - dates).dt.days.to_numpy(float) / RECENCY_HALF_LIFE_DAYS)
            m = lgb.LGBMClassifier(**MOVE_PARAMS)
            m.fit(_move_frame(d), y, sample_weight=w, categorical_feature=["asset_id"])
            self.move_models[h] = m
            recent = d[dates >= dates.sort_values().unique()[-RECENT_SESSIONS_FOR_QUANTILE]]
            self.move_floor[h] = float(np.quantile(m.predict_proba(_move_frame(recent))[:, 1], MOVE_QUANTILE))
            info["rows"][h] = int(len(d))
        info["move_floor"] = {h: round(v, 6) for h, v in self.move_floor.items()}
        return info

    # ------------------------------------------------------------------ features at the signal instant
    def _state(self, as_of) -> dict[str, dict]:
        t_ns = ns_of(as_of)
        if self._cache_ns == t_ns:
            return self._cache
        ts = pd.Timestamp(as_of).tz_convert("UTC")
        t = self._tables(ts, daily_since=ts.normalize() - pd.Timedelta(days=DAILY_LOOKBACK_DAYS))
        keys = pd.DataFrame({"asset": sorted(HL_SYMBOL), "cutoff_utc": ts,
                             "cutoff_date": pd.Timestamp(ts.date()), "horizon": 0, "label": None,
                             "complete": True, "ambiguous": False})
        feats = build_frame(keys, t["daily"], t["c1"], t["cd"], t["fu"], t["usd"], t["cot"]).set_index("asset")
        prices, _ = price_view(self.pack, as_of, lookback_sessions=10, quotes=True)
        series = {}
        for inst, g in t["c1"].groupby("instrument", sort=True):
            g = g.sort_values("close_utc", kind="stable")
            series[str(inst)] = (to_ns(g["close_utc"]), to_ns(g["available_utc"]), g["close"].to_numpy(float))
        out = {}
        for asset in sorted(HL_SYMBOL):
            g = self._gap_one(prices, series.get(HL_SYMBOL[asset]), asset, as_of, t_ns)
            if "reason" not in g:
                row = feats.loc[[asset]].reset_index()
                g["p_move"] = {h: float(self.move_models[h].predict_proba(_move_frame(row))[:, 1][0]) for h in ISSUED_HORIZONS}
            out[asset] = g
        self._cache_ns, self._cache = t_ns, out
        return out

    @staticmethod
    def _gap_one(prices, series, asset: str, as_of, t_ns: int) -> dict:
        """The gap-v1 measurement, unchanged: entry observation instant to the last candle before the signal."""
        if asset not in prices.assets():
            return {"reason": "no MCX prices for this asset before the signal instant"}
        contract = prices.designated_contract(asset, as_of)
        if contract is None:
            return {"reason": "no designated contract published for this session"}
        quoted = prices.price_at(asset, contract, as_of)
        if quoted is None:
            return {"reason": f"no entry price available for {contract}"}
        _p0, source, p_avail = quoted
        if series is None:
            return {"reason": f"no {HL_SYMBOL[asset]} candles available"}
        anchor_ns = ns_of(p_avail)
        r0 = last_close(series, anchor_ns, strict=False)
        r1 = last_close(series, t_ns, strict=True)
        if r0 is None or r1 is None:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed before the entry observation and the signal"}
        if r1[1] <= r0[1]:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed between the entry observation and the signal"}
        gap_pct = 100.0 * (r1[0] / r0[0] - 1.0)
        return {"gap_pct": gap_pct, "gap_thr": gap_pct / THRESHOLD_PCT[asset], "contract": contract,
                "source": source, "anchor_ns": anchor_ns, "ref0_ns": r0[1], "ref1_ns": r1[1]}

    # ------------------------------------------------------------------ predict
    def predict(self, as_of, asset: str, horizon: int):
        if int(horizon) != self.called_horizons[0]:
            return {"reason": f"model issues horizons {ISSUED_HORIZONS} on the first call at this instant"}
        g = self._state(as_of).get(asset)
        if g is None or "reason" in g:
            return {"reason": (g or {}).get("reason", "asset not covered")}
        if abs(g["gap_thr"]) < MIN_GAP:
            return {"reason": f"{HL_SYMBOL[asset]} moved {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr), below {MIN_GAP} thr"}
        rows = []
        for h in ISSUED_HORIZONS:
            p_move = g["p_move"][h]
            if p_move < self.move_floor[h]:
                continue
            rule_dir = "up" if g["gap_pct"] > 0 else "down"
            direction, note = self.learner.direction(asset, h, rule_dir, g)
            expected, p10, p90 = band(asset)
            evidence = (
                f"{SPEC_VERSION}: {HL_SYMBOL[asset]} {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr) from candle "
                f"{pd.Timestamp(g['ref0_ns'], tz='UTC').isoformat()} (entry {g['source']} of {g['contract']} at "
                f"{pd.Timestamp(g['anchor_ns'], tz='UTC').isoformat()}) to {pd.Timestamp(g['ref1_ns'], tz='UTC').isoformat()}; "
                f"P(move,h{h})={p_move:.3f} >= {self.move_floor[h]:.3f}{note}"
            )
            rows.append({"direction": direction, "horizon": h, "expected_pct": expected, "p10_pct": p10,
                         "p90_pct": p90, "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence})
        if not rows:
            return {"reason": f"gap {g['gap_thr']:+.2f} thr but P(move) below the floor at every horizon"}
        return rows

    # ------------------------------------------------------------------ update
    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        return self.learner.update(matured_outcomes)


def build(challenge: int, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> GapLGBM:
    return GapLGBM(challenge, horizons)
