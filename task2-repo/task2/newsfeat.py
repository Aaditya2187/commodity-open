"""Headline sentiment at one pre-open, read through PointInTime.

Same lexicon as ``research/news_feats.py``. A slot's score is the trust-weighted mean of headlines
admitted before the signal: ``night`` from the entry anchor to the signal, ``day`` the 24 hours
before the signal. The table is collected once per as-of instant and reused across assets.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

UP = {"rise", "rises", "rising", "rose", "gain", "gains", "gained", "rally", "rallies", "rallied", "surge", "surges",
      "surged", "jump", "jumps", "jumped", "climb", "climbs", "climbed", "soar", "soars", "soared", "higher", "high",
      "highs", "record", "bullish", "rebound", "rebounds", "rebounded", "advance", "advances", "advanced", "firm",
      "firms", "firmer", "boost", "boosts", "spike", "spikes", "strengthens", "strong", "upbeat", "up"}
DOWN = {"fall", "falls", "fell", "falling", "drop", "drops", "dropped", "decline", "declines", "declined", "slump",
        "slumps", "slumped", "plunge", "plunges", "plunged", "slide", "slides", "slid", "tumble", "tumbles", "tumbled",
        "sink", "sinks", "sank", "lower", "low", "lows", "bearish", "weaken", "weakens", "weaker", "retreat",
        "retreats", "loss", "losses", "ease", "eases", "eased", "slip", "slips", "slipped", "crash", "down", "weak"}
WORD = re.compile(r"[a-z]+")
_CACHE: dict = {"ns": None, "by": None}


def _score(title: str) -> float:
    w = WORD.findall(str(title).lower())
    u, d = sum(x in UP for x in w), sum(x in DOWN for x in w)
    return np.nan if u + d == 0 else (u - d) / (u + d)


def _load(pack, as_of) -> dict:
    ns = int(pd.Timestamp(as_of).value)
    if _CACHE["ns"] == ns and _CACHE["by"] is not None:
        return _CACHE["by"]
    t = pack.frame("pack/news/news_rows", pd.Timestamp(as_of).to_pydatetime()).collect(
        columns=["asset", "original_title", "trust_weight", "fetched_utc", "available_utc", "clock_quality"])
    t = t[t["asset"].notna()].copy()
    if len(t) == 0:
        by = {}
    else:
        q = t["clock_quality"].astype(str)
        adm = pd.to_datetime(t["available_utc"], utc=True).where(q == "published", pd.to_datetime(t["fetched_utc"], utc=True))
        t["admit_ns"] = pd.DatetimeIndex(adm).as_unit("ns").asi8
        t["s"] = t["original_title"].map(_score)
        t = t[t["s"].notna()].sort_values("admit_ns")
        by = {a: (g["admit_ns"].to_numpy(), g["s"].to_numpy(float), g["trust_weight"].to_numpy(float)) for a, g in t.groupby("asset")}
    _CACHE["ns"] = ns
    _CACHE["by"] = by
    return by


def scores(pack, as_of, asset: str, anchor_ns: int, signal_ns: int) -> tuple[float, float]:
    """Return ``(news_night, news_day)``. Missing headlines score 0."""
    by = _load(pack, as_of)
    ns, s, w = by.get(asset, (np.array([], np.int64), np.array([]), np.array([])))
    out = []
    for t0 in (int(anchor_ns), int(signal_ns) - 24 * 3600 * 10**9):
        i0, i1 = np.searchsorted(ns, t0, side="right"), np.searchsorted(ns, int(signal_ns), side="left")
        out.append(float(np.average(s[i0:i1], weights=w[i0:i1])) if i1 > i0 else 0.0)
    return out[0], out[1]
