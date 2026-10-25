"""Task 2 overnight-gap forecaster: frozen specification v1 (see ../SPEC.md).

At each 08:30 IST pre-open, the scorer's entry price p0 for an asset is the last MCX observation
available: a tick captured before the pre-open, or the previous session's settlement. The direction
is the sign of the Hyperliquid xyz perpetual move from the instant of that observation to the
signal instant. Nothing is fitted. ``update`` records what it receives and changes nothing, so the
learning run and the frozen run issue identical rows (stated in the memo).

Pack reads go only through the PointInTime client handed to ``fit``. Timestamps are compared as
nanosecond integers, converted explicitly from the pack's microsecond columns.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from swing_dataset.kit.loop import price_view
from swing_dataset.scoring2 import BAND_WIDTH_CAP, THRESHOLD_PCT
from swing_dataset.scoring2.prices import ns_of

SPEC_VERSION = "gap-v1"
SEED = 20261025  # nothing draws a random number; recorded for the run manifest
ISSUED_HORIZONS = (3, 5)
HL_TABLE = "macro/hl_candles_1h"
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
CANDLE_COLUMNS = ["instrument", "close_utc", "close", "available_utc"]
PRICE_LOOKBACK_SESSIONS = 10
#: Band [P10_SHARE * threshold, P10 + 12 thresholds), just inside BAND_WIDTH_CAP. A realized signal
#: has mfe >= threshold by definition, so a band below the threshold would only waste width.
P10_SHARE = 0.999
WIDTH_SHARE = 1.0 - 1e-9
EXPECTED_SHARE = 2.0  # fixed placeholder for expected_pct, in thresholds; not fitted


def to_ns(values) -> np.ndarray:
    """Nanoseconds since epoch for a tz-aware datetime column, whatever unit it is stored in."""
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ns").asi8


def last_close(series: tuple[np.ndarray, np.ndarray, np.ndarray], t_ns: int, *, strict: bool):
    """(close, close_ns) of the last candle closed at/before t_ns (before, if strict) and available by then."""
    close_ns, avail_ns, px = series
    i = int(np.searchsorted(close_ns, t_ns, side="left" if strict else "right")) - 1
    while i >= 0 and (avail_ns[i] > t_ns or (strict and avail_ns[i] >= t_ns)):
        i -= 1
    return None if i < 0 else (float(px[i]), int(close_ns[i]))


def band(asset: str) -> tuple[float, float, float]:
    thr = THRESHOLD_PCT[asset]
    p10 = P10_SHARE * thr
    return EXPECTED_SHARE * thr, p10, p10 + BAND_WIDTH_CAP * thr * WIDTH_SHARE


class GapForecaster:
    SEED = SEED
    TRAINING_DATA_CUTOFF = "none: no parameters are fitted; no pretrained weights"

    def __init__(self, challenge: int = 2, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> None:
        if challenge != 2:
            raise ValueError("this model enters Task 2 only")
        # The model issues ISSUED_HORIZONS whatever run.py asks for (its default is 5,10), on the
        # first horizon it is called with at each instant, so every run issues the same rows.
        self.called_horizons = tuple(sorted(int(h) for h in horizons))
        self.pack = None
        self._cache_ns: int | None = None
        self._cache: dict[str, dict] = {}
        self.updates_received = 0

    def fit(self, pack, train_end: datetime) -> dict:
        self.pack = pack
        return {"spec": SPEC_VERSION, "fitted_parameters": 0, "train_end_utc": pd.Timestamp(train_end).isoformat(),
                "issued_horizons": list(ISSUED_HORIZONS)}

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
        anchor_ns = ns_of(p_avail)
        r0 = last_close(series, anchor_ns, strict=False)
        r1 = last_close(series, t_ns, strict=True)
        if r0 is None or r1 is None:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed before the entry observation and the signal"}
        if r1[1] <= r0[1]:
            return {"reason": f"no {HL_SYMBOL[asset]} candle closed between the entry observation and the signal"}
        gap = 100.0 * (r1[0] / r0[0] - 1.0)
        if gap == 0.0:
            return {"reason": f"{HL_SYMBOL[asset]} unchanged since the entry observation"}
        return {"gap_pct": gap, "contract": contract, "source": source, "anchor_ns": anchor_ns,
                "ref0_ns": r0[1], "ref1_ns": r1[1]}

    def predict(self, as_of, asset: str, horizon: int):
        if int(horizon) != self.called_horizons[0]:
            return {"reason": f"gap rule issues horizons {ISSUED_HORIZONS} on the first call at this instant"}
        g = self._gaps(as_of).get(asset)
        if g is None or "reason" in g:
            return {"reason": (g or {}).get("reason", "asset not covered")}
        direction = "up" if g["gap_pct"] > 0 else "down"
        expected, p10, p90 = band(asset)
        evidence = (
            f"{SPEC_VERSION}: {HL_SYMBOL[asset]} moved {g['gap_pct']:+.3f}% from the candle closing "
            f"{pd.Timestamp(g['ref0_ns'], tz='UTC').isoformat()} (entry {g['source']} of {g['contract']} "
            f"observed {pd.Timestamp(g['anchor_ns'], tz='UTC').isoformat()}) to the candle closing "
            f"{pd.Timestamp(g['ref1_ns'], tz='UTC').isoformat()}"
        )
        return [
            {"direction": direction, "horizon": h, "expected_pct": expected, "p10_pct": p10, "p90_pct": p90,
             "invalidation_pct": THRESHOLD_PCT[asset], "evidence": evidence}
            for h in ISSUED_HORIZONS
        ]

    def update(self, matured_outcomes: pd.DataFrame) -> dict:
        # Frozen by specification: experiment 03 found no outcome-conditional relationship to adapt.
        self.updates_received += len(matured_outcomes)
        return {"updates_received": self.updates_received, "state_changed": False}


def build(challenge: int, horizons: tuple[int, ...] = ISSUED_HORIZONS) -> GapForecaster:
    return GapForecaster(challenge, horizons)
