"""Task 2 model "gap-night-cat": overseas-gap direction, overnight-range rule, CatBoost trust filter.

A. **Direction.** The sign of the Hyperliquid perpetual's move from the scorer's entry observation
   to the pre-open (experiment 03's stale-entry-price mechanism), measured exactly as gap-v1 did.
B. **Rule.** Only slots with |gap| >= MIN_GAP thresholds and a Hyperliquid high-low range since the
   last MCX settlement was published (``hl_night_range``) of at least NIGHT_RANGE_MIN thresholds.
C. **Trust filter (CatBoost).** ``fit`` visits every pre-open from TRUST_FROM to ``train_end``
   through the point-in-time client, computes the same features ``predict`` computes
   (``task2.trust``), labels each slot with |gap| >= MIN_GAP by whether the gap direction won the
   barrier race within the horizon (``labels/chain_daily``, complete windows only), and fits a
   CatBoost classifier. Its threshold keeps the share of training slots the rule keeps. A slot is
   signalled when it passes B and C; otherwise a ``no_signal`` row with the reason.
D. **Horizon 5 only.** Direction rose with the horizon at every step from 1 to 5 in both periods
   below (fewer windows end with neither barrier touched); the forward window scores h <= 5.

Measured on research slot tables (research/models_eval.py, research/RESULTS_gap_night_cat_v3.md):
CatBoost fitted on 20 Feb - 22 May and applied to the holdout, h5: 77.8 on 81 signals, against
75.7 for the rule alone; fitted on the holdout and applied to 20 Feb - 22 May: 83.5 against 80.3.

``update`` (learning copy only): see ``task2.learner``. Both copies apply the same rule and filter,
so learning and frozen files share every key.

Reads go only through the client handed to ``fit``; CatBoost is seeded and single-threaded.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime

import numpy as np
import pandas as pd

from swing_dataset.kit.loop import price_view, session_bounds, trading_days
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

from task2.features import build_frame
from task2.labels import build_labels
from task2.learner import Learner
from task2.trust import TrustModel, slot_features

SPEC_VERSION = "gap-night-cat-v3"
SEED = 20261025
ISSUED_HORIZONS = (5,)
# Defaults stay on v3. The pipeline may override them with TASK2_LEARNER / TASK2_LEARNER_PARAMS / TASK2_AUX
# without editing this file. A design that clears the official bar is written back into these three constants.
LEARNER = "v3"
LEARNER_PARAMS: dict = {}
AUX_HORIZONS = (1, 2, 3, 4)


def resolve_runtime():
    learner = os.environ.get("TASK2_LEARNER", LEARNER)
    if "TASK2_LEARNER_PARAMS" in os.environ:
        params = json.loads(os.environ.get("TASK2_LEARNER_PARAMS") or "{}")
    else:
        params = dict(LEARNER_PARAMS)
    aux_env = os.environ.get("TASK2_AUX")
    if aux_env is None:
        aux = tuple(int(h) for h in AUX_HORIZONS)
    else:
        aux = tuple(int(x) for x in aux_env.split(",") if x.strip())
    spec = "gap-night-cat-v3" if learner == "v3" else f"gap-night-learn-v4-{learner}"
    return learner, params, aux, spec


def _finite(value, default=0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def path_vector(c1: pd.DataFrame, instrument: str, g: dict, thr: float) -> list[float]:
    """Last 12 hourly log returns, most recent first, in thresholds. Zeros when the path is missing."""
    zeros = [0.0] * 12
    if c1 is None or len(c1) == 0 or "ref0_ns" not in g:
        return zeros
    s = c1[c1["instrument"] == instrument].sort_values("close_utc", kind="stable")
    if len(s) == 0:
        return zeros
    close_ns = to_ns(s["close_utc"])
    i0 = int(np.searchsorted(close_ns, g["ref0_ns"], side="left"))
    i1 = int(np.searchsorted(close_ns, g["ref1_ns"], side="left"))
    if i0 >= len(s) or i1 >= len(s) or close_ns[i0] != g["ref0_ns"] or close_ns[i1] != g["ref1_ns"] or i1 <= i0:
        return zeros
    px = s["close"].to_numpy(float)
    lr = np.diff(np.log(px[max(0, i1 - 12) : i1 + 1])) * 100.0 / thr
    if not np.isfinite(lr).all():
        return zeros
    lr = np.concatenate([np.full(12 - len(lr), 0.0), lr])
    return [float(lr[-1 - k]) for k in range(12)]


def outcome_y(row) -> int | None:
    """+1 up-first, -1 down-first, 0 neither/ambiguous, None when the row cannot be labelled."""
    if bool(row.get("no_price", False)) or row.get("realized") is None:
        return None
    direction = str(row.get("direction"))
    realized = bool(row.get("realized"))
    if realized and direction == "up":
        return 1
    if realized and direction == "down":
        return -1
    ambiguous = bool(row.get("ambiguous", False))
    mae = row.get("mae_pct")
    thr = THRESHOLD_PCT.get(str(row.get("asset")))
    if (not realized) and (not ambiguous) and mae is not None and thr is not None and float(mae) >= thr:
        return -1 if direction == "up" else 1
    return 0
MIN_GAP = 0.3  # thresholds; chosen on 2026-02-20..2026-05-29 (experiment 03 window), pre-holdout
NIGHT_RANGE_MIN = 1.0  # thresholds; chosen on 2026-02-20..2026-05-22 and the holdout together
TRUST_FROM = date(2026, 2, 1)  # Hyperliquid candles start on 2026-02-19; earlier sessions have no gap
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


class GapNightCat:
    SEED = SEED
    TRAINING_DATA_CUTOFF = "fit reads only pack rows available before train_end; no pretrained weights"

    def __init__(self, challenge: int = 2, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> None:
        if challenge != 2:
            raise ValueError("this model enters Task 2 only")
        self.called_horizons = tuple(sorted(int(h) for h in horizons))
        self.pack = None
        self.trust = TrustModel(SEED)
        self.learner = Learner()
        self.learner_name, self.learner_params, self.aux_horizons, self.spec = resolve_runtime()
        self.online = None
        self._issued: dict[tuple, dict] = {}
        self._sessions_seen = 0
        self._seen_asof = None
        if self.learner_name != "v3":
            from task2.online import make

            self.online = make(self.learner_name, **self.learner_params)
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
        end = pd.Timestamp(train_end)
        chain = pack.frame("labels/chain_daily", end.to_pydatetime()).collect(columns=CHAIN_COLUMNS)
        labels = build_labels(chain, horizons=ISSUED_HORIZONS)
        labels = labels[labels["complete"]]
        outcome = {(a, int(pd.Timestamp(c).value)): lab for a, c, lab in zip(labels["asset"], labels["cutoff_utc"], labels["label"])}
        label_map: dict[tuple, int] = {}
        if self.online is not None:
            lab_all = build_labels(chain, horizons=(1, 2, 3, 4, 5))
            lab_all = lab_all[lab_all["complete"]]
            label_map = {
                (a, int(pd.Timestamp(c).value), int(h)): (1 if lab == "up" else -1 if lab == "down" else 0)
                for a, c, h, lab in zip(lab_all["asset"], lab_all["cutoff_utc"], lab_all["horizon"], lab_all["label"])
            }
        bounds = session_bounds(pack, end.to_pydatetime(), TRUST_FROM, end.date())
        rows, won, kept = [], [], []
        online_rows: list[dict] = []
        for day_i, day in enumerate(trading_days(pack, end.to_pydatetime(), TRUST_FROM, end.date()), start=1):
            instant = bounds[day][0]
            if pd.Timestamp(instant) >= end:
                break
            instant_ns = int(pd.Timestamp(instant).value)
            for asset, g in self._state(instant).items():
                label = outcome.get((asset, instant_ns))
                if "reason" not in g and label is not None and abs(g["gap_thr"]) >= MIN_GAP:
                    rows.append(g["trust"])
                    won.append(label == ("up" if g["gap_thr"] > 0 else "down"))
                    kept.append(g["night_range"] >= NIGHT_RANGE_MIN)
                if label_map and "reason" not in g:
                    base = self._feat_base(asset, g)
                    for h in (1, 2, 3, 4, 5):
                        y = label_map.get((asset, instant_ns, h))
                        if y is None:
                            continue
                        online_rows.append({**base, "h": h, "y": y, "gidx": day_i, "asset": asset})
        self._cache_ns, self._cache = None, {}
        info = {"spec": self.spec, "train_end_utc": end.isoformat(), "min_gap": MIN_GAP,
                "night_range_min": NIGHT_RANGE_MIN, "horizons": list(ISSUED_HORIZONS)}
        info["trust"] = self.trust.fit(rows, np.array(won, bool), float(np.mean(kept)) if kept else 0.0)
        if self.online is not None:
            frame = pd.DataFrame(online_rows)
            self.online.fit(frame)
            info["online"] = {"learner": self.learner_name, "train_rows": int(len(frame)), "params": self.learner_params}
        self._cache_ns, self._cache = None, {}
        self._issued = {}
        self._sessions_seen = 0
        self._seen_asof = None
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
                row = feats.loc[asset]
                g["night_range"] = float(row["hl_night_range"]) if "hl_night_range" in feats.columns else float("nan")
                g["vol_20"] = float(row["vol_20"])
                g["signal_ns"] = t_ns
                g["f_ret_5"] = _finite(row["ret_5"]) if "ret_5" in feats.columns else 0.0
                g["f_ret_20"] = _finite(row["ret_20"]) if "ret_20" in feats.columns else 0.0
                g["f_hl_night_pos"] = _finite(row["hl_night_pos"]) if "hl_night_pos" in feats.columns else 0.0
                g["f_dist_ma_20"] = _finite(row["dist_ma_20"]) if "dist_ma_20" in feats.columns else 0.0
                if self._wants_path():
                    g["path"] = path_vector(t["c1"], HL_SYMBOL[asset], g, THRESHOLD_PCT[asset])
                if self._wants_news():
                    from task2.newsfeat import scores as news_scores

                    g["news_night"], g["news_day"] = news_scores(self.pack, as_of, asset, g["anchor_ns"], t_ns)
            out[asset] = g
        for asset, f in slot_features(out, t["c1"], HL_SYMBOL, THRESHOLD_PCT).items():
            out[asset]["trust"] = f
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

    def _wants_news(self) -> bool:
        feats = getattr(self.online, "feats", ()) or ()
        return "news_night" in feats or "news_day" in feats

    def _wants_path(self) -> bool:
        feats = getattr(self.online, "feats", ()) or ()
        return any(str(name).startswith("path_") for name in feats)

    def _feat_base(self, asset: str, g: dict) -> dict:
        base = {
            "asset": asset,
            "gap_thr": _finite(g.get("gap_thr")),
            "f_ret_5": _finite(g.get("f_ret_5")),
            "f_ret_20": _finite(g.get("f_ret_20")),
            "f_hl_night_pos": _finite(g.get("f_hl_night_pos")),
            "f_dist_ma_20": _finite(g.get("f_dist_ma_20")),
            "news_night": _finite(g.get("news_night")),
            "news_day": _finite(g.get("news_day")),
        }
        path = g.get("path") or [0.0] * 12
        for i, value in enumerate(path):
            base[f"path_{i}"] = _finite(value)
        return base

    def _remember(self, asset: str, signal_ns: int, horizon: int, g: dict) -> None:
        if self.online is None:
            return
        feat = self._feat_base(asset, g)
        feat["h"] = int(horizon)
        self._issued[(asset, int(signal_ns), int(horizon))] = feat

    # ------------------------------------------------------------------ predict
    def predict(self, as_of, asset: str, horizon: int):
        if self.online is not None:
            mark = int(pd.Timestamp(as_of).value)
            if mark != self._seen_asof:
                self._sessions_seen += 1
                self._seen_asof = mark
        if int(horizon) != self.called_horizons[0]:
            return {"reason": f"model issues horizons {ISSUED_HORIZONS} on the first call at this instant"}
        g = self._state(as_of).get(asset)
        if g is None or "reason" in g:
            return {"reason": (g or {}).get("reason", "asset not covered")}
        name = HL_SYMBOL[asset]
        if abs(g["gap_thr"]) < MIN_GAP:
            return {"reason": f"{name} moved {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr), below {MIN_GAP} thr"}
        if not g["night_range"] >= NIGHT_RANGE_MIN:
            return {"reason": f"{name} overnight range {g['night_range']:.2f} thr, below {NIGHT_RANGE_MIN} thr"}
        p_trust = self.trust.score(g["trust"])
        if p_trust < self.trust.threshold:
            return {"reason": f"{name} gap {g['gap_thr']:+.2f} thr, trust {p_trust:.3f} below {self.trust.threshold:.3f}"}
        rule_dir = "up" if g["gap_pct"] > 0 else "down"
        rows = []
        signal_ns = int(g.get("signal_ns") or ns_of(as_of))
        for h in ISSUED_HORIZONS:
            direction, note = self.learner.direction(asset, h, rule_dir, g)
            expected, p10, p90 = band(asset)
            evidence = (
                f"{self.spec}: {name} {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr) from candle "
                f"{pd.Timestamp(g['ref0_ns'], tz='UTC').isoformat()} (entry {g['source']} of {g['contract']} at "
                f"{pd.Timestamp(g['anchor_ns'], tz='UTC').isoformat()}) to {pd.Timestamp(g['ref1_ns'], tz='UTC').isoformat()}; "
                f"overnight range {g['night_range']:.2f} thr; trust {p_trust:.3f} >= {self.trust.threshold:.3f}{note}"
            )
            rows.append({"direction": direction, "horizon": h, "expected_pct": expected, "p10_pct": p10,
                         "p90_pct": p90, "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence})
            self._remember(asset, signal_ns, h, g)
        if self.online is not None:
            for h in self.aux_horizons:
                if h in ISSUED_HORIZONS:
                    continue
                feat = self._feat_base(asset, g)
                feat["h"] = int(h)
                p_up = float(self.online.proba(feat))
                direction = "up" if p_up >= 0.5 else "down"
                expected, p10, p90 = band(asset)
                evidence = (
                    f"{self.spec}: aux h{h} p(up)={p_up:.3f}; {name} gap {g['gap_thr']:+.2f} thr; "
                    f"overnight range {g['night_range']:.2f} thr"
                )
                rows.append({"direction": direction, "horizon": int(h), "expected_pct": expected, "p10_pct": p10,
                             "p90_pct": p90, "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence})
                self._remember(asset, signal_ns, h, g)
        return rows

    # ------------------------------------------------------------------ update
    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        info = self.learner.update(matured_outcomes)
        if self.online is None or matured_outcomes is None or len(matured_outcomes) == 0:
            return info
        rows = []
        ordered = matured_outcomes.sort_values(["signal_utc", "asset", "horizon"], kind="stable")
        for _, matured in ordered.iterrows():
            y = outcome_y(matured)
            if y is None:
                continue
            key = (str(matured["asset"]), ns_of(matured["signal_utc"]), int(matured["horizon"]))
            feat = self._issued.get(key)
            if feat is None:
                continue
            row = dict(feat)
            row["y"] = int(y)
            rows.append(row)
        if rows:
            self.online.update(pd.DataFrame(rows), self._sessions_seen)
            if isinstance(info, dict):
                info = dict(info)
                info["online_rows"] = len(rows)
        return info


def build(challenge: int, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> GapNightCat:
    return GapNightCat(challenge, horizons)
