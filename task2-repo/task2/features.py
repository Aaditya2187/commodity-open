"""Point-in-time features at each pre-open cutoff, from the pack's daily and macro tables.

Every feature at cutoff ``t`` (08:30 IST = 03:00 UTC) is computed from rows whose
``available_utc`` is strictly before ``t``.  For the research frame the tables are read whole and
filtered by availability per cutoff; the submission model computes the same quantities from the
``PointInTime`` client's frame at the signal instant, so the two agree by construction.

Feature groups
  mcx:    returns, volatility, range position, volume and open-interest state of the designated
          series (volume-leader contract, roll-adjusted by ratio chaining)
  xs:     cross-asset ratio z-scores and rolling correlations
  hl:     overnight overseas gap (gap-v1), overnight range, perp daily returns, funding
  fx:     USD/INR level changes
  cot:    managed-money net positioning and its percentile
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .labels import ASSETS, THRESHOLD_PCT

HL_SYMBOL = {"gold": "xyz:GOLD", "silver": "xyz:SILVER", "copper": "xyz:COPPER", "crude": "xyz:CL"}
COT_ASSET = {"gold": "gold", "silver": "silver", "copper": "copper", "crude": "crude"}
CUTOFF_UTC_HOUR = 3


def _cutoff(session_dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(session_dates)
    return (d + pd.Timedelta(hours=CUTOFF_UTC_HOUR)).dt.tz_localize("UTC")


# ----------------------------------------------------------------------------- MCX daily
def continuous_series(daily: pd.DataFrame) -> pd.DataFrame:
    """Per asset and session: the volume-leader contract's OHLC/settlement, roll-adjusted log return,
    and asset-wide volume and open interest. Rows carry the session's own ``available_utc``."""
    d = daily[daily["asset"].isin(ASSETS)].copy()
    d["session_date"] = pd.to_datetime(d["session_date"])
    d = d[d["settlement"].notna()]
    agg = d.groupby(["asset", "session_date"]).agg(
        volume_all=("volume_lots", "sum"), oi_all=("open_interest", "sum"), available_utc=("available_utc", "max")
    ).reset_index()
    lead = d.sort_values(["asset", "session_date", "volume_lots"], ascending=[True, True, False]) \
            .groupby(["asset", "session_date"], as_index=False).first()
    lead = lead[["asset", "session_date", "contract_id", "open", "high", "low", "close", "settlement", "volume_lots", "open_interest"]]
    out = lead.merge(agg, on=["asset", "session_date"]).sort_values(["asset", "session_date"]).reset_index(drop=True)
    # roll-adjusted return: when the leader changes, use the new contract's own previous settlement
    prev_settle_same = d.set_index(["asset", "session_date", "contract_id"])["settlement"]
    rets = np.full(len(out), np.nan)
    for i in range(1, len(out)):
        if out.at[i, "asset"] != out.at[i - 1, "asset"]:
            continue
        cid = out.at[i, "contract_id"]
        prev_date = out.at[i - 1, "session_date"]
        key = (out.at[i, "asset"], prev_date, cid)
        base = prev_settle_same.get(key, np.nan) if cid != out.at[i - 1, "contract_id"] else out.at[i - 1, "settlement"]
        if pd.notna(base) and base > 0:
            rets[i] = np.log(out.at[i, "settlement"] / base)
    out["logret"] = rets
    out["roll"] = out["contract_id"] != out.groupby("asset")["contract_id"].shift(1)
    return out


def mcx_features(cs: pd.DataFrame) -> pd.DataFrame:
    """Features for the cutoff *after* each session row (the row is the last available bar)."""
    g = cs.sort_values(["asset", "session_date"]).copy()
    thr = g["asset"].map(THRESHOLD_PCT) / 100.0
    r = g["logret"]
    grp = g.groupby("asset")
    f = pd.DataFrame({"asset": g["asset"], "session_date": g["session_date"]})
    for n in (1, 2, 5, 10, 20, 60):
        f[f"ret_{n}"] = grp["logret"].transform(lambda s: s.rolling(n, min_periods=n).sum()) / thr
    for n in (5, 20, 60):
        f[f"vol_{n}"] = grp["logret"].transform(lambda s: s.rolling(n, min_periods=n).std()) / thr
    pk = np.log(g["high"] / g["low"]) ** 2 / (4 * np.log(2))
    f["parkinson_5"] = np.sqrt(pk.groupby(g["asset"]).transform(lambda s: s.rolling(5, min_periods=3).mean())) / thr
    f["parkinson_20"] = np.sqrt(pk.groupby(g["asset"]).transform(lambda s: s.rolling(20, min_periods=10).mean())) / thr
    f["vol_ratio_5_60"] = f["vol_5"] / f["vol_60"]
    hi20 = grp["high"].transform(lambda s: s.rolling(20, min_periods=10).max())
    lo20 = grp["low"].transform(lambda s: s.rolling(20, min_periods=10).min())
    f["range_pos_20"] = (g["settlement"] - lo20) / (hi20 - lo20)
    f["range_width_20"] = (hi20 - lo20) / g["settlement"] / thr
    for n in (20, 50):
        ma = grp["settlement"].transform(lambda s: s.rolling(n, min_periods=n // 2).mean())
        f[f"dist_ma_{n}"] = (g["settlement"] / ma - 1.0) / thr
    f["day_range"] = (g["high"] - g["low"]) / g["settlement"] / thr
    f["close_loc"] = (g["settlement"] - g["low"]) / (g["high"] - g["low"]).replace(0, np.nan)
    f["gap_open"] = np.log(g["open"] / grp["settlement"].shift(1)) / thr
    v = g["volume_all"].astype(float)
    f["vol_z_20"] = (v - v.groupby(g["asset"]).transform(lambda s: s.rolling(20, min_periods=10).mean())) / \
                    v.groupby(g["asset"]).transform(lambda s: s.rolling(20, min_periods=10).std())
    oi = g["oi_all"].astype(float)
    f["oi_chg_1"] = oi.groupby(g["asset"]).pct_change(1)
    f["oi_chg_5"] = oi.groupby(g["asset"]).pct_change(5)
    f["price_oi_quadrant"] = np.sign(r) * np.sign(f["oi_chg_1"])
    f["roll"] = g["roll"].astype(float)
    f["available_utc"] = g["available_utc"]
    return f


def cross_asset_features(cs: pd.DataFrame) -> pd.DataFrame:
    px = cs.pivot(index="session_date", columns="asset", values="settlement").sort_index().ffill()
    lr = cs.pivot(index="session_date", columns="asset", values="logret").sort_index()
    out = pd.DataFrame(index=px.index)
    for a, b in (("gold", "silver"), ("copper", "gold"), ("crude", "gold"), ("copper", "crude")):
        ratio = np.log(px[a] / px[b])
        z = (ratio - ratio.rolling(60, min_periods=30).mean()) / ratio.rolling(60, min_periods=30).std()
        out[f"ratio_z_{a}_{b}"] = z
        out[f"corr20_{a}_{b}"] = lr[a].rolling(20, min_periods=10).corr(lr[b])
    for a in ASSETS:
        others = [b for b in ASSETS if b != a]
        out[f"others_ret5_{a}"] = sum(lr[b].rolling(5, min_periods=5).sum() / (THRESHOLD_PCT[b] / 100) for b in others) / 3
    return out.reset_index()


# ----------------------------------------------------------------------------- overseas / macro
def _searchsorted_last(sorted_ns: np.ndarray, t_ns: int, strict: bool) -> int:
    return int(np.searchsorted(sorted_ns, t_ns, side="left" if strict else "right")) - 1


def hl_features(keys: pd.DataFrame, cs: pd.DataFrame, candles_1h: pd.DataFrame, candles_1d: pd.DataFrame,
                funding: pd.DataFrame) -> pd.DataFrame:
    """Per (asset, cutoff_utc): the overnight gap and perp state, all from rows available before the cutoff.

    ``keys`` carries asset, cutoff_utc. The anchor for the gap is the availability instant of the
    last MCX daily row before the cutoff (settlement publication), as gap-v1 does before the tick
    feed starts; the research frame stops before the tick feed, so this is exact for training.
    """
    anchor = cs[["asset", "session_date", "available_utc"]].copy()
    anchor["available_utc"] = pd.to_datetime(anchor["available_utc"], utc=True)
    rows = []
    c1 = candles_1h.copy()
    c1["close_ns"] = pd.DatetimeIndex(pd.to_datetime(c1["close_utc"], utc=True)).as_unit("ns").asi8
    c1["avail_ns"] = pd.DatetimeIndex(pd.to_datetime(c1["available_utc"], utc=True)).as_unit("ns").asi8
    cd = candles_1d.copy()
    cd["avail_ns"] = pd.DatetimeIndex(pd.to_datetime(cd["available_utc"], utc=True)).as_unit("ns").asi8
    fu = funding.copy()
    fu["avail_ns"] = pd.DatetimeIndex(pd.to_datetime(fu["available_utc"], utc=True)).as_unit("ns").asi8
    series_1h = {k: g.sort_values("close_ns") for k, g in c1.groupby("instrument")}
    series_1d = {k: g.sort_values("avail_ns") for k, g in cd.groupby("instrument")}
    series_fu = {k: g.sort_values("avail_ns") for k, g in fu.groupby("instrument")}
    anchors = {k: g.sort_values("available_utc") for k, g in anchor.groupby("asset")}
    for asset, cutoff in zip(keys["asset"], keys["cutoff_utc"]):
        t_ns = int(pd.Timestamp(cutoff).as_unit("ns").value)
        rec = {"asset": asset, "cutoff_utc": cutoff}
        inst = HL_SYMBOL[asset]
        thr = THRESHOLD_PCT[asset]
        s = series_1h.get(inst)
        an = anchors.get(asset)
        if s is not None and an is not None and len(s):
            a_ns = an["available_utc"].to_numpy().astype("datetime64[ns]").astype(np.int64)
            ia = int(np.searchsorted(a_ns, t_ns, side="left")) - 1
            if ia >= 0:
                anchor_ns = int(a_ns[ia])
                cl = s["close_ns"].to_numpy()
                av = s["avail_ns"].to_numpy()
                px = s["close"].to_numpy(float)
                hi = s["high"].to_numpy(float)
                lo = s["low"].to_numpy(float)
                i0 = _searchsorted_last(cl, anchor_ns, strict=False)
                while i0 >= 0 and av[i0] > anchor_ns:
                    i0 -= 1
                i1 = _searchsorted_last(cl, t_ns, strict=True)
                while i1 >= 0 and av[i1] >= t_ns:
                    i1 -= 1
                if i0 >= 0 and i1 > i0:
                    rec["hl_gap"] = 100.0 * (px[i1] / px[i0] - 1.0) / thr
                    seg_hi = hi[i0 + 1 : i1 + 1].max()
                    seg_lo = lo[i0 + 1 : i1 + 1].min()
                    rec["hl_night_range"] = 100.0 * (seg_hi / seg_lo - 1.0) / thr
                    rec["hl_night_pos"] = (px[i1] - seg_lo) / (seg_hi - seg_lo) if seg_hi > seg_lo else 0.5
                    rec["hl_gap_hours"] = (cl[i1] - cl[i0]) / 3.6e12
                    # last 3 candles momentum vs full gap
                    j = max(i0, i1 - 3)
                    rec["hl_gap_last3"] = 100.0 * (px[i1] / px[j] - 1.0) / thr
        d = series_1d.get(inst)
        if d is not None and len(d):
            av = d["avail_ns"].to_numpy()
            k = int(np.searchsorted(av, t_ns, side="left")) - 1
            if k >= 1:
                cl = d["close"].to_numpy(float)
                rec["hl_ret_1d"] = 100.0 * (cl[k] / cl[k - 1] - 1.0) / thr
                if k >= 5:
                    rec["hl_ret_5d"] = 100.0 * (cl[k] / cl[k - 5] - 1.0) / thr
                if k >= 20:
                    rec["hl_vol_20d"] = 100.0 * np.std(np.diff(np.log(cl[k - 20 : k + 1]))) / thr
        f = series_fu.get(inst)
        if f is not None and len(f):
            av = f["avail_ns"].to_numpy()
            k = int(np.searchsorted(av, t_ns, side="left")) - 1
            if k >= 0:
                fr = f["funding_rate"].to_numpy(float)
                rec["funding_last"] = fr[k] * 1e4
                rec["funding_mean_24"] = fr[max(0, k - 23) : k + 1].mean() * 1e4
                rec["premium_last"] = f["premium"].to_numpy(float)[k] * 1e4
        rows.append(rec)
    return pd.DataFrame(rows)


def fx_features(keys: pd.DataFrame, usdinr: pd.DataFrame) -> pd.DataFrame:
    u = usdinr.copy()
    u["avail_ns"] = pd.DatetimeIndex(pd.to_datetime(u["available_utc"], utc=True)).as_unit("ns").asi8
    u = u.sort_values("avail_ns")
    av = u["avail_ns"].to_numpy()
    px = u["usdinr_fbil"].to_numpy(float)
    rows = []
    for asset, cutoff in zip(keys["asset"], keys["cutoff_utc"]):
        t_ns = int(pd.Timestamp(cutoff).as_unit("ns").value)
        k = int(np.searchsorted(av, t_ns, side="left")) - 1
        rec = {"asset": asset, "cutoff_utc": cutoff}
        if k >= 5:
            rec["inr_chg_1"] = 100.0 * (px[k] / px[k - 1] - 1.0)
            rec["inr_chg_5"] = 100.0 * (px[k] / px[k - 5] - 1.0)
            rec["inr_stale_days"] = (t_ns - av[k]) / 8.64e13
        rows.append(rec)
    return pd.DataFrame(rows)


def cot_features(keys: pd.DataFrame, cot: pd.DataFrame) -> pd.DataFrame:
    c = cot[cot["asset"].isin(ASSETS)].copy()
    c["avail_ns"] = pd.DatetimeIndex(pd.to_datetime(c["available_utc"], utc=True)).as_unit("ns").asi8
    c["mm_net"] = c["m_money_positions_long_all"] - c["m_money_positions_short_all"]
    c["mm_net_oi"] = c["mm_net"] / c["open_interest_all"]
    c = c.sort_values(["asset", "report_date", "avail_ns"]).drop_duplicates(["asset", "report_date"], keep="first")
    by = {a: g.sort_values("avail_ns") for a, g in c.groupby("asset")}
    rows = []
    for asset, cutoff in zip(keys["asset"], keys["cutoff_utc"]):
        t_ns = int(pd.Timestamp(cutoff).as_unit("ns").value)
        rec = {"asset": asset, "cutoff_utc": cutoff}
        g = by.get(asset)
        if g is not None:
            av = g["avail_ns"].to_numpy()
            k = int(np.searchsorted(av, t_ns, side="left")) - 1
            if k >= 1:
                net = g["mm_net_oi"].to_numpy(float)
                rec["cot_mm_net_oi"] = net[k]
                rec["cot_mm_chg_1w"] = net[k] - net[k - 1]
                lo = max(0, k - 156)
                rec["cot_mm_pct_3y"] = (net[lo : k + 1] <= net[k]).mean()
                rec["cot_age_days"] = (t_ns - av[k]) / 8.64e13
        rows.append(rec)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- assembly
def build_frame(labels: pd.DataFrame, daily: pd.DataFrame, candles_1h, candles_1d, funding, usdinr, cot) -> pd.DataFrame:
    """Labels joined with every feature group on (asset, cutoff_utc)."""
    cs = continuous_series(daily)
    mf = mcx_features(cs)
    # the cutoff that each session row feeds: the next session's pre-open = first cutoff after available_utc
    keys = labels[["asset", "cutoff_utc", "cutoff_date"]].drop_duplicates().sort_values(["asset", "cutoff_utc"])
    mf["available_utc"] = pd.to_datetime(mf["available_utc"], utc=True)
    merged = []
    for asset, k in keys.groupby("asset"):
        f = mf[mf["asset"] == asset].sort_values("available_utc")
        m = pd.merge_asof(k.sort_values("cutoff_utc"), f.drop(columns=["asset"]), left_on="cutoff_utc",
                          right_on="available_utc", direction="backward", allow_exact_matches=False)
        merged.append(m)
    X = pd.concat(merged, ignore_index=True)
    X["staleness_sessions"] = (X["cutoff_date"] - X["session_date"]).dt.days
    xs = cross_asset_features(cs)
    X = pd.merge_asof(X.sort_values("session_date"), xs.sort_values("session_date"), on="session_date", direction="backward")
    X = X.sort_values(["asset", "cutoff_utc"]).reset_index(drop=True)
    k2 = X[["asset", "cutoff_utc"]]
    for part in (hl_features(k2, cs, candles_1h, candles_1d, funding), fx_features(k2, usdinr), cot_features(k2, cot)):
        X = X.merge(part, on=["asset", "cutoff_utc"], how="left")
    X["asset_id"] = X["asset"].map({a: i for i, a in enumerate(ASSETS)})
    X["dow"] = X["cutoff_date"].dt.dayofweek
    return labels.merge(X.drop(columns=["cutoff_date"]), on=["asset", "cutoff_utc"], how="left")


FEATURE_COLUMNS = [
    "ret_1", "ret_2", "ret_5", "ret_10", "ret_20", "ret_60", "vol_5", "vol_20", "vol_60", "parkinson_5", "parkinson_20",
    "vol_ratio_5_60", "range_pos_20", "range_width_20", "dist_ma_20", "dist_ma_50", "day_range", "close_loc", "gap_open",
    "vol_z_20", "oi_chg_1", "oi_chg_5", "price_oi_quadrant", "roll", "staleness_sessions",
    "ratio_z_gold_silver", "corr20_gold_silver", "ratio_z_copper_gold", "corr20_copper_gold", "ratio_z_crude_gold",
    "corr20_crude_gold", "ratio_z_copper_crude", "corr20_copper_crude",
    "others_ret5_gold", "others_ret5_silver", "others_ret5_copper", "others_ret5_crude",
    "hl_gap", "hl_night_range", "hl_night_pos", "hl_gap_hours", "hl_gap_last3", "hl_ret_1d", "hl_ret_5d", "hl_vol_20d",
    "funding_last", "funding_mean_24", "premium_last", "inr_chg_1", "inr_chg_5", "inr_stale_days",
    "cot_mm_net_oi", "cot_mm_chg_1w", "cot_mm_pct_3y", "cot_age_days", "asset_id", "dow",
]
