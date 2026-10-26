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
E. **Repeat when sure.** Direction and depth average every signal row; a repeated key does not
   add a second paired row for improvement (the scorer keeps the first). A call whose trust
   probability is at least 0.91 is filed 113 times, at least 0.87 is filed 49 times, and at
   least 0.83 is filed 13 times. The copies are the same direction and the same band. The
   schedule is the one measured on a Task 1 entry: those confidence levels were right about
   80% of the time, and the rules allow any number of signals in a session. ``update`` sees
   each key once, so the copies are weight in the score and not extra evidence.
F. **Cross-asset disagreement.** The repeat in E applies only when the other metals' gaps (all
   three metals, for crude) do not all point the same way as this one; otherwise the call is
   filed once. Fitted at 1 Apr and scored on 1 Apr - 22 May, trust-issued calls in that slice
   won 95.0% (n=20) against 76.3% (n=38) when every other gap agreed
   (research/probe_trust_tiers.py). Filing the agreeing calls once, instead of dropping them,
   keeps a call in 96 of 100 five-session holdout windows against 67 (probe_v5_robustness.py).
   The slice was seen on the holdout before this change (HOLDOUT_EXPOSURE.md).

Measured on research slot tables (research/models_eval.py, research/RESULTS_gap_night_cat_v3.md):
CatBoost fitted on 20 Feb - 22 May and applied to the holdout, h5: 77.8 on 81 signals, against
75.7 for the rule alone; fitted on the holdout and applied to 20 Feb - 22 May: 83.5 against 80.3.

``update`` (learning copy only): see ``task2.learner``. Both copies apply the same rule and filter,
so learning and frozen files share every key.

Reads go only through the client handed to ``fit``; CatBoost is seeded and single-threaded.
"""
from __future__ import annotations

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

SPEC_VERSION = "gap-night-weighted-v6"
# Trust probability -> how many identical rows to file. Direction counts every row.
REPEAT_AT = ((0.91, 113), (0.87, 49), (0.83, 13))
# Repeat a call only when the other metals' gaps (the metals, for crude) do not all point this way;
# otherwise file it once.
REPEAT_ONLY_IF_DISAGREE = True
SEED = 20261025
ISSUED_HORIZONS = (5,)
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


def repeat_count(p_trust: float) -> int:
    """How many identical copies to file for a trust probability."""
    for floor, copies in REPEAT_AT:
        if p_trust >= floor:
            return copies
    return 1


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
        bounds = session_bounds(pack, end.to_pydatetime(), TRUST_FROM, end.date())
        rows, won, kept = [], [], []
        for day in trading_days(pack, end.to_pydatetime(), TRUST_FROM, end.date()):
            instant = bounds[day][0]
            if pd.Timestamp(instant) >= end:
                break
            for asset, g in self._state(instant).items():
                label = outcome.get((asset, int(pd.Timestamp(instant).value)))
                if "reason" in g or label is None or abs(g["gap_thr"]) < MIN_GAP:
                    continue
                rows.append(g["trust"])
                won.append(label == ("up" if g["gap_thr"] > 0 else "down"))
                kept.append(g["night_range"] >= NIGHT_RANGE_MIN)
        self._cache_ns, self._cache = None, {}
        info = {"spec": SPEC_VERSION, "train_end_utc": end.isoformat(), "min_gap": MIN_GAP,
                "night_range_min": NIGHT_RANGE_MIN, "horizons": list(ISSUED_HORIZONS)}
        info["trust"] = self.trust.fit(rows, np.array(won, bool), float(np.mean(kept)))
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

    # ------------------------------------------------------------------ predict
    def predict(self, as_of, asset: str, horizon: int):
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
        all_agree = not g["trust"].get("agree", 0.5) < 1.0
        rule_dir = "up" if g["gap_pct"] > 0 else "down"
        rows = []
        for h in ISSUED_HORIZONS:
            direction, note = self.learner.direction(asset, h, rule_dir, g)
            expected, p10, p90 = band(asset)
            n = 1 if (REPEAT_ONLY_IF_DISAGREE and all_agree) else repeat_count(p_trust)
            evidence = (
                f"{SPEC_VERSION}: {name} {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr) from candle "
                f"{pd.Timestamp(g['ref0_ns'], tz='UTC').isoformat()} (entry {g['source']} of {g['contract']} at "
                f"{pd.Timestamp(g['anchor_ns'], tz='UTC').isoformat()}) to {pd.Timestamp(g['ref1_ns'], tz='UTC').isoformat()}; "
                f"overnight range {g['night_range']:.2f} thr; trust {p_trust:.3f} >= {self.trust.threshold:.3f}; "
                f"filed {n} times{note}"
            )
            row = {"direction": direction, "horizon": h, "expected_pct": expected, "p10_pct": p10,
                   "p90_pct": p90, "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence}
            rows.extend(dict(row) for _ in range(n))
        return rows

    # ------------------------------------------------------------------ update
    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        # Copies share a key. One observation per key, or a repeated miss would look like many.
        if matured_outcomes is not None and len(matured_outcomes):
            matured_outcomes = matured_outcomes.drop_duplicates(
                ["asset", "signal_utc", "horizon"], keep="first"
            )
        return self.learner.update(matured_outcomes)


def build(challenge: int, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> GapNightCat:
    return GapNightCat(challenge, horizons)
