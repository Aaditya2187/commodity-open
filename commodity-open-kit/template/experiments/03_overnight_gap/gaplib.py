"""Point-in-time overseas-gap helpers for experiment 03. Every timestamp is compared in nanoseconds."""

from __future__ import annotations

import numpy as np
import pandas as pd

from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2.prices import ns_of

HL_TABLE = "macro/hl_candles_1h"
HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
CANDLE_COLUMNS = ["instrument", "open_utc", "close_utc", "close", "trade_count", "available_utc"]


def to_ns(values) -> np.ndarray:
    """Nanoseconds since epoch for any tz-aware datetime column, whatever its stored unit."""
    idx = pd.DatetimeIndex(pd.to_datetime(values, utc=True))
    return idx.as_unit("ns").asi8


def candles(pit: PointInTime, asof) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per instrument: (close_ns, available_ns, close price), sorted, from rows available before asof."""
    frame = pit.frame(HL_TABLE, pd.Timestamp(asof).to_pydatetime()).collect(columns=CANDLE_COLUMNS)
    out = {}
    for inst, g in frame.groupby("instrument", sort=True):
        g = g.sort_values("close_utc", kind="stable")
        out[str(inst)] = (to_ns(g["close_utc"]), to_ns(g["available_utc"]), g["close"].to_numpy(float))
    return out


def last_close(series, t_ns: int, *, strict: bool) -> tuple[float, int] | None:
    """Close of the last candle whose close is <= t_ns (or < t_ns if strict) AND available by then."""
    close_ns, avail_ns, px = series
    side = "left" if strict else "right"
    i = int(np.searchsorted(close_ns, t_ns, side=side)) - 1
    while i >= 0 and (avail_ns[i] > t_ns or (strict and avail_ns[i] >= t_ns)):
        i -= 1
    if i < 0:
        return None
    return float(px[i]), int(close_ns[i])


def gap(pit: PointInTime, prices, asset: str, signal_utc) -> dict:
    """The overseas move from the scorer's entry-price observation to the signal instant."""
    t_ns = ns_of(signal_utc)
    contract = prices.designated_contract(asset, signal_utc)
    rec = {"asset": asset, "signal_utc": pd.Timestamp(signal_utc), "contract": contract}
    if contract is None:
        return rec | {"missing": "no designated contract"}
    quoted = prices.price_at(asset, contract, signal_utc)
    if quoted is None:
        return rec | {"missing": "no entry price"}
    p0, source, p_avail = quoted
    anchor_ns = ns_of(p_avail)
    series = candles(pit, signal_utc).get(HL_SYMBOL[asset])
    if series is None:
        return rec | {"missing": "no candles", "p0_source": source}
    r0 = last_close(series, anchor_ns, strict=False)
    r1 = last_close(series, t_ns, strict=True)
    rec |= {"p0": p0, "p0_source": source, "anchor_utc": pd.Timestamp(anchor_ns, tz="UTC")}
    if r0 is None or r1 is None:
        return rec | {"missing": "no candle before anchor or signal"}
    rec |= {
        "ref0": r0[0], "ref1": r1[0],
        "anchor_lag_min": (anchor_ns - r0[1]) / 6e10,
        "signal_lag_min": (t_ns - r1[1]) / 6e10,
        "interval_hours": (r1[1] - r0[1]) / 3.6e12,
        "gap_pct": 100.0 * (r1[0] / r0[0] - 1.0),
        "missing": None,
    }
    return rec
