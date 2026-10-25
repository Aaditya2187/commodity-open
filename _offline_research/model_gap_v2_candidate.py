"""Task 2 model gap-v2: overseas-gap direction with magnitude abstention and a per-asset online guard.

Mechanism (experiment 03, pre-registered): at the 08:30 IST pre-open the scorer's entry price is
the last MCX observation (the previous settlement, or a captured tick), which is stale relative to
overseas trading since then. The Hyperliquid perpetual's move over that interval says where the
MCX price will open relative to the entry price, so it says which barrier of the Task 2 race is
closer. Direction = sign of the gap.

What is new relative to gap-v1 (``experiments/04_gap_model``):

1. **Magnitude abstention.** The edge grows steeply with the size of the gap in threshold units
   (pre-holdout Feb-May 2026: bottom tercile 52-57%, top tercile 82-85%). A signal is issued only
   when ``|gap| >= MIN_GAP`` thresholds; otherwise a ``no_signal`` row records the reason, which
   satisfies the coverage floor of section 5. ``MIN_GAP`` was chosen on the pre-holdout window
   only (0.3 gives 70.1% at h3 and 74.3% at h5 on 67% of slots) and is identical in both copies,
   so the learning and frozen files share every key and the improvement score is measured on all
   of them.
2. **Anchor fix.** The entry observation's instant is capped at the last session close, so a tick
   captured at 08:29 IST (41 holdout keys in gap-v1) no longer shortens the overnight window to one
   hour.
3. **Online per-asset guard (the learning).** ``update`` receives the run's own graded signals and
   keeps, per asset, an exponentially forgotten Beta posterior of the gap rule's hit rate. If the
   posterior mean of an asset falls below ``FLIP_BELOW`` with at least ``MIN_EVIDENCE`` effective
   outcomes, that asset's direction is inverted until the posterior recovers above ``UNFLIP_ABOVE``.
   The rationale is the basis risk named in experiment 05: copper's perpetual tracks COMEX while
   MCX copper tracks LME, and the pass-through can break. NOT YET CHECKED: whether the guard trips
   on the pre-holdout window, and whether it produces any paired gain there. Until a session
   replay measures that, this file is an unvalidated candidate, not a submission.

STATUS: exploratory side branch derived from the gap-v1 benchmark. It is not the tree-first plan
in the implementation doc; keep it only as a benchmark variant.

Everything is read through the ``PointInTime`` client handed to ``fit``. No randomness.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

SPEC_VERSION = "gap-v2"
SEED = 20261025
TRAINING_DATA_CUTOFF = "none: no parameters are fitted from pack rows; MIN_GAP chosen on 2026-02-20..2026-05-29"
ISSUED_HORIZONS = (3, 5)
HL_TABLE = "macro/hl_candles_1h"
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
CANDLE_COLUMNS = ["instrument", "close_utc", "close", "available_utc"]
PRICE_LOOKBACK_SESSIONS = 10
#: Abstain below this gap size, in asset thresholds. Pre-holdout choice; identical in both copies.
MIN_GAP = 0.3
#: Band: [0.999 thr, 0.999 thr + 12 thr), just inside BAND_WIDTH_CAP. A realized row has mfe >= thr.
P10_SHARE = 0.999
WIDTH_SHARE = 1.0 - 1e-9
#: expected_pct in thresholds: the pre-holdout median mfe of realized gap signals, ~2 thresholds.
EXPECTED_SHARE = 2.0
#: Online guard. Prior Beta(PRIOR_HITS, PRIOR_MISSES) per asset = 0.65 with the weight of 20 outcomes.
PRIOR_HITS, PRIOR_MISSES = 13.0, 7.0
FORGET = 0.5 ** (1.0 / 30.0)  # half-life of 30 outcomes
MIN_EVIDENCE = 20.0  # effective outcomes (after forgetting) before the guard may act
FLIP_BELOW = 0.40
UNFLIP_ABOVE = 0.50
IST_SESSION_CLOSE_UTC_HOUR = 18  # 23:30 IST; a tick captured after this belongs to the next morning


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


def capped_anchor_ns(p_avail, as_of) -> int:
    """The entry observation's instant, capped at the previous session's close.

    A settlement is published after the close, so it is unchanged. A tick captured in the
    pre-open minutes (08:29 IST) is moved back to the previous close: the price it carries is the
    last trade, which happened before that close, and the overnight overseas move since then is
    what the rule measures.
    """
    a = pd.Timestamp(p_avail)
    s = pd.Timestamp(as_of)
    prev_close = (s.tz_convert("UTC").normalize() - pd.Timedelta(days=1)).replace(hour=IST_SESSION_CLOSE_UTC_HOUR)
    if a > prev_close and a.tz_convert("UTC").date() == s.tz_convert("UTC").date():
        a = prev_close
    return ns_of(a)


class AssetGuard:
    """Exponentially forgotten Beta posterior of the gap rule's hit rate for one asset."""

    def __init__(self) -> None:
        self.hits = PRIOR_HITS
        self.misses = PRIOR_MISSES
        self.flipped = False
        self.n_seen = 0

    def observe(self, realized_for_rule: bool) -> None:
        self.hits *= FORGET
        self.misses *= FORGET
        if realized_for_rule:
            self.hits += 1.0
        else:
            self.misses += 1.0
        self.n_seen += 1
        evidence = self.hits + self.misses - (PRIOR_HITS + PRIOR_MISSES) * FORGET ** self.n_seen
        mean = self.hits / (self.hits + self.misses)
        if not self.flipped and evidence >= MIN_EVIDENCE and mean < FLIP_BELOW:
            self.flipped = True
        elif self.flipped and mean > UNFLIP_ABOVE:
            self.flipped = False

    def state(self) -> dict:
        return {"hits": round(self.hits, 4), "misses": round(self.misses, 4), "flipped": self.flipped, "n": self.n_seen}


class GapForecasterV2:
    SEED = SEED
    TRAINING_DATA_CUTOFF = TRAINING_DATA_CUTOFF

    def __init__(self, challenge: int = 2, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> None:
        if challenge != 2:
            raise ValueError("this model enters Task 2 only")
        self.called_horizons = tuple(sorted(int(h) for h in horizons))
        self.pack = None
        self._cache_ns: int | None = None
        self._cache: dict[str, dict] = {}
        self.guards = {a: AssetGuard() for a in HL_SYMBOL}
        self.updates_received = 0
        self.update_log: list[dict] = []

    # ------------------------------------------------------------------ fit
    def fit(self, pack, train_end: datetime) -> dict:
        self.pack = pack
        return {"spec": SPEC_VERSION, "fitted_parameters": 0, "min_gap_thresholds": MIN_GAP,
                "train_end_utc": pd.Timestamp(train_end).isoformat(), "issued_horizons": list(ISSUED_HORIZONS)}

    # ------------------------------------------------------------------ features
    def _gaps(self, as_of) -> dict[str, dict]:
        t_ns = ns_of(as_of)
        if self._cache_ns == t_ns:
            return self._cache
        prices, _ = price_view(self.pack, as_of, lookback_sessions=PRICE_LOOKBACK_SESSIONS, quotes=True)
        frame = self.pack.frame(HL_TABLE, pd.Timestamp(as_of).to_pydatetime()).collect(columns=CANDLE_COLUMNS)
        series = {}
        for inst, g in frame.groupby("instrument", sort=True):
            g = g.sort_values("close_utc", kind="stable")
            series[str(inst)] = (to_ns(g["close_utc"]), to_ns(g["available_utc"]), g["close"].to_numpy(float))
        out = {}
        for asset, inst in sorted(HL_SYMBOL.items()):
            out[asset] = self._gap_one(prices, series.get(inst), asset, as_of, t_ns)
        self._cache_ns, self._cache = t_ns, out
        return out

    @staticmethod
    def _gap_one(prices, series, asset: str, as_of, t_ns: int) -> dict:
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
        anchor_ns = capped_anchor_ns(p_avail, as_of)
        r0 = last_close(series, anchor_ns, strict=False)
        r1 = last_close(series, t_ns, strict=True)
        if r0 is None or r1 is None:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed before the entry observation and the signal"}
        if r1[1] <= r0[1]:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed between the entry observation and the signal"}
        gap_pct = 100.0 * (r1[0] / r0[0] - 1.0)
        gap_thr = gap_pct / THRESHOLD_PCT[asset]
        if abs(gap_thr) < MIN_GAP:
            return {"reason": f"{HL_SYMBOL[asset]} moved {gap_pct:+.3f}% ({gap_thr:+.2f} thresholds) since the entry "
                              f"observation, below the {MIN_GAP} threshold minimum"}
        return {"gap_pct": gap_pct, "gap_thr": gap_thr, "contract": contract, "source": source,
                "anchor_ns": anchor_ns, "ref0_ns": r0[1], "ref1_ns": r1[1]}

    # ------------------------------------------------------------------ predict
    def predict(self, as_of, asset: str, horizon: int):
        if int(horizon) != self.called_horizons[0]:
            return {"reason": f"gap rule issues horizons {ISSUED_HORIZONS} on the first call at this instant"}
        g = self._gaps(as_of).get(asset)
        if g is None or "reason" in g:
            return {"reason": (g or {}).get("reason", "asset not covered")}
        rule_dir = "up" if g["gap_pct"] > 0 else "down"
        guard = self.guards[asset]
        direction = ("down" if rule_dir == "up" else "up") if guard.flipped else rule_dir
        expected, p10, p90 = band(asset)
        evidence = (
            f"{SPEC_VERSION}: {HL_SYMBOL[asset]} moved {g['gap_pct']:+.3f}% ({g['gap_thr']:+.2f} thr) from the candle "
            f"closing {pd.Timestamp(g['ref0_ns'], tz='UTC').isoformat()} (entry {g['source']} of {g['contract']} "
            f"observed {pd.Timestamp(g['anchor_ns'], tz='UTC').isoformat()}) to the candle closing "
            f"{pd.Timestamp(g['ref1_ns'], tz='UTC').isoformat()}"
            + ("; guard inverted the rule" if guard.flipped else "")
        )
        return [
            {"direction": direction, "horizon": h, "expected_pct": expected, "p10_pct": p10, "p90_pct": p90,
             "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence}
            for h in ISSUED_HORIZONS
        ]

    # ------------------------------------------------------------------ update
    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        """Feed each settled outcome to its asset's guard, in signal order, once."""
        self.updates_received += len(matured_outcomes)
        if matured_outcomes is None or not len(matured_outcomes):
            return {"updates_received": self.updates_received, "state_changed": False}
        rows = matured_outcomes.sort_values(["signal_utc", "asset", "horizon"], kind="stable")
        before = {a: g.flipped for a, g in self.guards.items()}
        for _, r in rows.iterrows():
            if not bool(r.get("scorable", True)) or bool(r.get("no_price", False)):
                continue
            asset = str(r["asset"])
            inverted = "guard inverted" in str(r.get("evidence", ""))
            realized = bool(r["realized"])
            # the guard tracks the *rule's* hit rate: an inverted row that was realized means the rule missed
            self.guards[asset].observe(realized != inverted)
        changed = any(before[a] != g.flipped for a, g in self.guards.items())
        self.update_log.append({"n": int(len(rows)), "last_signal_utc": str(rows["signal_utc"].iloc[-1]),
                                "guards": {a: g.state() for a, g in self.guards.items()}})
        return {"updates_received": self.updates_received, "state_changed": changed,
                "guards": {a: g.state() for a, g in self.guards.items()}}


def build(challenge: int, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> GapForecasterV2:
    return GapForecasterV2(challenge, horizons)
