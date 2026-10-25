"""Barrier-race labels for Task 2, built from the pack's ``labels/chain_daily`` table.

For every pre-open cutoff since Feb 2021 and each asset, ``chain_daily`` holds the designated
contract's daily path for the next ``horizon`` sessions, roll-normalized to the entry reference
(``w_high``, ``w_low``, ``w_close`` are high/low/settlement divided by the reference price at
the cutoff, chained across a roll).  The scorer's Task 2 test (``scoring2.outcomes.grade_c2`` with
``scoring2.prices.PriceSeries.evaluate_path``) is reproduced here on daily bars:

* ``up`` is realized when ``w_high >= 1 + thr`` is touched on an earlier session than
  ``w_low <= 1 - thr``; inside one session the adverse barrier ranks first, so a bar that touches
  both is a loss for either direction.
* ``down`` symmetrically.
* ``neither`` when no barrier is touched inside the horizon.

Labels for horizons 1..5 come from the h=5 chain, 6..10 from the h=10 chain, 11..20 from h=20.
Before 22 June 2026 the scorer's entry price is the previous settlement, exactly this reference;
from then on it is a captured tick, so holdout labels from this builder differ slightly from the
scorer's own grading (exp 01 measured 1.7% disagreement).  Training stops at 2026-05-31 anyway.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

THRESHOLD_PCT = {"gold": 1.5, "silver": 2.0, "copper": 1.5, "crude": 3.0}
ASSETS = ("gold", "silver", "copper", "crude")
CHAIN_FOR = {h: 5 if h <= 5 else 10 if h <= 10 else 20 for h in range(1, 21)}


def build_labels(chain: pd.DataFrame, horizons=(1, 2, 3, 5, 10)) -> pd.DataFrame:
    """One row per (asset, cutoff_utc, horizon) with the barrier-race outcome.

    Columns: asset, cutoff_utc, cutoff_date, horizon, label (up/down/neither), hit_k (session index
    of the first decisive touch, 1-based, NaN for neither), ambiguous (both barriers in the deciding
    bar), mfe_up_pct / mfe_down_pct (favorable extremes for each direction over the window, in %),
    ret_pct (settlement return at the window end), complete (window has all its sessions in the pack).
    """
    c = chain[chain["asset"].isin(ASSETS)].copy()
    c["cutoff_utc"] = pd.to_datetime(c["cutoff_utc"], utc=True)
    out = []
    for h in horizons:
        base = CHAIN_FOR[h]
        g = c[(c["horizon"] == base) & (c["k"] <= h)].sort_values(["asset", "cutoff_utc", "k"])
        thr = g["asset"].map(THRESHOLD_PCT).to_numpy() / 100.0
        up_hit = g["w_high"].to_numpy() >= 1.0 + thr
        dn_hit = g["w_low"].to_numpy() <= 1.0 - thr
        g = g.assign(up_hit=up_hit, dn_hit=dn_hit)
        rows = []
        for (asset, cutoff), grp in g.groupby(["asset", "cutoff_utc"], sort=False):
            k = grp["k"].to_numpy()
            uh = grp["up_hit"].to_numpy()
            dh = grp["dn_hit"].to_numpy()
            n = len(k)
            first_up = int(k[uh][0]) if uh.any() else None
            first_dn = int(k[dh][0]) if dh.any() else None
            amb = False
            if first_up is None and first_dn is None:
                label, hit = "neither", np.nan
            elif first_dn is None or (first_up is not None and first_up < first_dn):
                label, hit = "up", first_up
            elif first_up is None or first_dn < first_up:
                label, hit = "down", first_dn
            else:  # same session: adverse ranks first for both directions
                label, hit, amb = "neither", first_up, True
            wh = grp["w_high"].to_numpy()
            wl = grp["w_low"].to_numpy()
            rows.append(
                (asset, cutoff, cutoff.date(), h, label, hit, amb,
                 100.0 * (wh.max() - 1.0), 100.0 * (1.0 - wl.min()),
                 100.0 * (float(grp["w_close"].to_numpy()[-1]) - 1.0), n == h)
            )
        out.append(pd.DataFrame(rows, columns=[
            "asset", "cutoff_utc", "cutoff_date", "horizon", "label", "hit_k", "ambiguous",
            "mfe_up_pct", "mfe_down_pct", "ret_pct", "complete"]))
    df = pd.concat(out, ignore_index=True)
    df["cutoff_date"] = pd.to_datetime(df["cutoff_date"])
    return df.sort_values(["horizon", "asset", "cutoff_utc"]).reset_index(drop=True)


def prevailing_null(labels: pd.DataFrame, chain: pd.DataFrame) -> pd.DataFrame:
    """The organizers' always-prevailing-direction null: the sign of the last five sessions' move.

    Computed from the h=5 chain's settlement series of the designated contract: for cutoff t, the
    move from the settlement five sessions before the cutoff to the settlement at the cutoff.
    Returned as a column ``null_dir`` joined on (asset, cutoff_utc).
    """
    c = chain[(chain["horizon"] == 5) & (chain["k"] == 1) & chain["asset"].isin(ASSETS)].copy()
    c["cutoff_utc"] = pd.to_datetime(c["cutoff_utc"], utc=True)
    c = c.sort_values(["asset", "cutoff_utc"])
    c["ref"] = c["denominator"]
    c["ref_5"] = c.groupby("asset")["ref"].shift(5)
    c["null_dir"] = np.where(c["ref"] > c["ref_5"], "up", np.where(c["ref"] < c["ref_5"], "down", "flat"))
    return c[["asset", "cutoff_utc", "null_dir"]]
