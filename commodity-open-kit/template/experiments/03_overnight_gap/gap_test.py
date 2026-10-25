#!/usr/bin/env python3
"""Experiment 03: sign-of-overnight-overseas-gap rule, pre-holdout only. See PREREGISTRATION.md.

    python experiments/03_overnight_gap/gap_test.py --pack ../../v2.1

Writes results.json, rows_h3.parquet, rows_h5.parquet and learning_feasibility.json next to this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gaplib  # noqa: E402

from swing_dataset.kit import ASSETS, loop  # noqa: E402
from swing_dataset.pack.pit import PointInTime  # noqa: E402
from swing_dataset.scoring2 import THRESHOLD_PCT  # noqa: E402
from swing_dataset.scoring2 import outcomes as O  # noqa: E402
from swing_dataset.scoring2 import signals as SIG  # noqa: E402
from swing_dataset.scoring2.bootstrap import episode_keys  # noqa: E402
from swing_dataset.scoring2.prices import ns_of  # noqa: E402
from swing_dataset.scoring2.score import prevailing_null  # noqa: E402

CUTOFF = pd.Timestamp("2026-06-01 03:00", tz="UTC")
START = date(2026, 2, 19)
HORIZONS = (3, 5)
N_BOOT, SEED, LEVEL = 2000, 0, 0.90
FWD = 5


def signal_rows(gaps: pd.DataFrame, h: int) -> pd.DataFrame:
    g = gaps[gaps["missing"].isna() & (gaps["gap_pct"] != 0)].copy()
    thr = g["asset"].map(THRESHOLD_PCT)
    return pd.DataFrame(
        {
            "asset": g["asset"].to_numpy(),
            "signal_utc": g["signal_utc"].to_numpy(),
            "direction": np.where(g["gap_pct"] > 0, "up", "down"),
            "horizon": h,
            "expected_pct": (2 * thr).to_numpy(),
            "p10_pct": thr.to_numpy(),
            "p90_pct": (5 * thr).to_numpy(),
            "invalidation_pct": thr.to_numpy(),
            "evidence": "sign of overnight xyz perp move since entry-price observation",
        }
    ), g.reset_index(drop=True)


def boot(values: dict[str, np.ndarray], keys: np.ndarray) -> dict:
    """Episode-block bootstrap of means (and of their differences) on one shared draw."""
    uniq, inv = np.unique(keys, return_inverse=True)
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(uniq), size=(N_BOOT, len(uniq)))
    counts = np.stack([np.bincount(d, minlength=len(uniq)) for d in draws])  # (B, episodes)
    n_ep = np.bincount(inv, minlength=len(uniq)).astype(float)
    out = {}
    lo, hi = (1 - LEVEL) / 2, 1 - (1 - LEVEL) / 2
    for name, v in values.items():
        s = np.bincount(inv, weights=v.astype(float), minlength=len(uniq))
        rep = (counts @ s) / (counts @ n_ep)
        out[name] = {"value": round(100 * float(v.mean()), 2),
                     "ci90": [round(100 * float(np.quantile(rep, lo)), 2), round(100 * float(np.quantile(rep, hi)), 2)]}
    if "gap" in values and "null" in values:
        d = values["gap"].astype(float) - values["null"].astype(float)
        s = np.bincount(inv, weights=d, minlength=len(uniq))
        rep = (counts @ s) / (counts @ n_ep)
        out["gap_minus_null_pp"] = {"value": round(100 * float(d.mean()), 2),
                                    "ci90": [round(100 * float(np.quantile(rep, lo)), 2), round(100 * float(np.quantile(rep, hi)), 2)]}
    out["n"], out["episodes"] = int(len(keys)), int(len(uniq))
    return out


def evaluate(pit, prices, gaps, h):
    sig, meta = signal_rows(gaps, h)
    norm = SIG.normalize(sig, 2).signals
    graded = O.grade_c2(norm, prices)
    graded = pd.concat([graded, meta[["gap_pct", "anchor_lag_min", "interval_hours", "p0_source"]]], axis=1)
    graded = graded[graded["scorable"].fillna(False).astype(bool) & ~graded["no_price"].fillna(False).astype(bool)]
    graded = graded.reset_index(drop=True)
    nul = prevailing_null(graded.assign(signal_index=np.arange(len(graded))), prices)
    ng = O.grade_c2(nul, prices).set_index("signal_index")
    graded["null_direction"] = ng["direction"].reindex(range(len(graded))).to_numpy()
    graded["null_realized"] = ng["realized"].reindex(range(len(graded))).to_numpy()
    graded["null_scorable"] = ng["scorable"].reindex(range(len(graded))).to_numpy()
    m = graded[graded["null_scorable"].fillna(False).astype(bool)].reset_index(drop=True)
    m["gap_ok"] = m["realized"].astype(bool)
    m["null_ok"] = m["null_realized"].astype(bool)
    m["keys"] = episode_keys(prices, pd.Timestamp(START, tz="UTC"), h, m["asset"].to_numpy(), m["signal_utc"])
    m["month"] = pd.to_datetime(m["signal_utc"]).dt.strftime("%Y-%m")
    m["week"] = pd.to_datetime(m["signal_utc"]).dt.strftime("%G-W%V")
    m["weekend_anchor"] = pd.to_datetime(m["signal_utc"]).dt.tz_convert("Asia/Kolkata").dt.dayofweek == 0
    m["neither"] = ~m["realized"].astype(bool) & (m["mae_pct"] < m["threshold_pct"] - 1e-9)
    res = {"rows_generated": int(len(sig)), "rows_scorable_and_null_matched": int(len(m)),
           "pooled": boot({"gap": m["gap_ok"].to_numpy(), "null": m["null_ok"].to_numpy()}, m["keys"].to_numpy()),
           "agree_with_null_pct": round(100 * float((m["direction"] == m["null_direction"]).mean()), 1),
           "neither_pct": round(100 * float(m["neither"].mean()), 1),
           "up_signals_pct": round(100 * float((m["direction"] == "up").mean()), 1)}
    res["per_asset"] = {a: boot({"gap": g["gap_ok"].to_numpy(), "null": g["null_ok"].to_numpy()}, g["keys"].to_numpy())
                        for a, g in m.groupby("asset")}
    res["leave_one_asset_out"] = {f"without_{a}": boot({"gap": m.loc[m.asset != a, "gap_ok"].to_numpy(),
                                                        "null": m.loc[m.asset != a, "null_ok"].to_numpy()},
                                                       m.loc[m.asset != a, "keys"].to_numpy()) for a in ASSETS}
    res["monthly"] = {k: {"n": len(g), "gap": round(100 * g.gap_ok.mean(), 1), "null": round(100 * g.null_ok.mean(), 1)}
                      for k, g in m.groupby("month")}
    res["weekly"] = {k: {"n": len(g), "gap": round(100 * g.gap_ok.mean(), 1), "null": round(100 * g.null_ok.mean(), 1)}
                     for k, g in m.groupby("week")}
    res["weekend_vs_weekday_anchor"] = {str(k): {"n": len(g), "gap": round(100 * g.gap_ok.mean(), 1)}
                                        for k, g in m.groupby("weekend_anchor")}
    terc = {}
    for a, g in m.groupby("asset"):
        q = pd.qcut(g["gap_pct"].abs(), 3, labels=["bottom", "middle", "top"])
        t = g.groupby(q, observed=True)["gap_ok"].agg(["size", "mean"])
        terc[a] = {str(k): {"n": int(r["size"]), "direction": round(100 * r["mean"], 1)} for k, r in t.iterrows()}
        terc[a]["abs_gap_cut_pct"] = [round(float(x), 3) for x in g["gap_pct"].abs().quantile([1 / 3, 2 / 3])]
        terc[a]["top_beats_bottom"] = bool(terc[a]["top"]["direction"] > terc[a]["bottom"]["direction"])
    res["terciles_diagnostic"] = terc
    res["gap_stats_pct"] = {a: {"median_abs": round(float(g.gap_pct.abs().median()), 3),
                                "median_abs_over_threshold": round(float((g.gap_pct.abs() / THRESHOLD_PCT[a]).median()), 3)}
                            for a, g in m.groupby("asset")}
    res["anchor_lag_min"] = {"median": float(m.anchor_lag_min.median()), "max": float(m.anchor_lag_min.max())}
    res["interval_hours"] = {"median": float(m.interval_hours.median()), "max": float(m.interval_hours.max())}
    res["p0_sources"] = m["p0_source"].value_counts().to_dict()
    res["signal_utc_range"] = [str(m.signal_utc.min()), str(m.signal_utc.max())]
    pooled = res["pooled"]
    c1 = pooled["gap"]["value"] >= 58.0
    c2 = pooled["gap_minus_null_pp"]["value"] >= 8.0
    c3 = sum(v["top_beats_bottom"] for v in terc.values()) >= 3
    res["screen"] = {"C1_direction_ge_58": bool(c1), "C2_minus_null_ge_8pp": bool(c2),
                     "C3_top_tercile_beats_bottom_ge_3_assets": bool(c3), "pass": bool(c1 and c2 and c3)}
    return res, m


def learning_feasibility(pit, gaps, days):
    """Replay the loop's delivery of the rule's own outcomes with loop.matured_outcomes."""
    out = {}
    for h in (1, 3, 5):
        sig, _ = signal_rows(gaps, h)
        sig["session_date"] = pd.to_datetime(sig["signal_utc"]).dt.tz_convert("Asia/Kolkata").dt.date
        sig = sig[sig["session_date"].isin(days)].sort_values(["signal_utc", "asset"], kind="stable").reset_index(drop=True)
        pos = {d: i for i, d in enumerate(days)}
        sig["day"] = sig["session_date"].map(pos)
        delivered = pd.Series(np.nan, index=sig.index)
        correct = pd.Series(np.nan, index=sig.index)
        pending: list[int] = []
        for k, d in enumerate(days):
            asof = loop.preopen_instant(d)
            if pd.Timestamp(asof) >= CUTOFF:
                break
            if pending:
                frame = sig.loc[pending].drop(columns=["session_date", "day"]).reset_index(drop=True)
                mat = loop.matured_outcomes(pit, asof, frame, 2)
                if len(mat):
                    idx = [pending[j] for j in mat["signal_index"].astype(int)]
                    delivered.loc[idx] = k
                    correct.loc[idx] = mat["realized"].astype(float).to_numpy()
                    done = set(idx)
                    pending = [p for p in pending if p not in done]
            pending.extend(sig.index[sig["day"] == k].tolist())
        sig["delivered_day"], sig["outcome"] = delivered, correct
        sig["delay"] = sig["delivered_day"] - sig["day"]
        # forward-like windows: learner starts at the window start with nothing delivered
        last_day = int(sig.loc[sig["delivered_day"].notna(), "day"].max())
        infl, tot = [], []
        for w0 in range(0, last_day - FWD + 2):
            w = sig[(sig["day"] >= w0) & (sig["day"] < w0 + FWD)]
            n_inf = 0
            for r in w.itertuples():
                prior = w[(w["asset"] == r.asset) & (w["delivered_day"] <= r.day)]
                n_inf += int(len(prior) > 0)
            infl.append(n_inf)
            tot.append(len(w))
        rec = {"signals": int(len(sig)),
               "delay_sessions_distribution_pct": {str(int(k)): round(100 * v, 1) for k, v in
                                                   sig["delay"].value_counts(normalize=True).sort_index().items()},
               "fwd_windows": len(infl),
               "mean_predictions_per_window": round(float(np.mean(tot)), 2),
               "mean_predictions_with_prior_same_asset_outcome": round(float(np.mean(infl)), 2)}
        # adaptable relationship: accuracy conditional on most recent delivered same-asset outcome
        if h in HORIZONS:
            cond = []
            for r in sig.itertuples():
                prev = sig[(sig["asset"] == r.asset) & (sig["delivered_day"] <= r.day)]
                if len(prev) and not np.isnan(r.outcome):
                    last = prev.sort_values(["delivered_day", "day"]).iloc[-1]
                    cond.append((r.asset, r.signal_utc, int(last["outcome"]), int(r.outcome)))
            c = pd.DataFrame(cond, columns=["asset", "signal_utc", "prev_ok", "ok"])
            a = c[c.prev_ok == 1]["ok"].mean()
            b = c[c.prev_ok == 0]["ok"].mean()
            # block bootstrap of the difference by asset-week
            key = c["asset"] + ":" + pd.to_datetime(c["signal_utc"]).dt.strftime("%G-W%V")
            uniq, inv = np.unique(key, return_inverse=True)
            rng = np.random.default_rng(SEED)
            diffs = []
            for _ in range(N_BOOT):
                pick = rng.integers(0, len(uniq), len(uniq))
                cnt = np.bincount(pick, minlength=len(uniq))[inv]
                w1, w0 = cnt * (c.prev_ok == 1), cnt * (c.prev_ok == 0)
                if w1.sum() and w0.sum():
                    diffs.append((w1 * c.ok).sum() / w1.sum() - (w0 * c.ok).sum() / w0.sum())
            rec["conditional_on_last_outcome"] = {
                "n": int(len(c)), "n_prev_correct": int((c.prev_ok == 1).sum()),
                "acc_after_correct": round(100 * float(a), 1), "acc_after_wrong": round(100 * float(b), 1),
                "diff_pp": round(100 * float(a - b), 1),
                "ci90_pp": [round(100 * float(np.quantile(diffs, .05)), 1), round(100 * float(np.quantile(diffs, .95)), 1)],
            }
            ci = rec["conditional_on_last_outcome"]["ci90_pp"]
            rec["learning_mechanism_justified"] = bool(abs(a - b) >= 0.10 and (ci[0] > 0 or ci[1] < 0))
        out[f"h{h}"] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    args = ap.parse_args()
    prereg = (HERE / "PREREGISTRATION.md").read_bytes()
    pit = PointInTime(args.pack)
    prices, _ = loop.price_view(pit, CUTOFF.to_pydatetime())
    days = [d for d in loop.trading_days(pit, loop.preopen_instant(START), START, date(2026, 5, 31))
            if pd.Timestamp(loop.preopen_instant(d)) < CUTOFF]
    gaps = pd.DataFrame([gaplib.gap(pit, prices, a, loop.preopen_instant(d)) for d in days for a in ASSETS])
    results = {
        "preregistration_sha256": hashlib.sha256(prereg).hexdigest(),
        "cutoff_utc": str(CUTOFF),
        "sessions": len(days),
        "gap_rows": int(len(gaps)),
        "missing_reasons": gaps["missing"].fillna("ok").value_counts().to_dict(),
        "zero_gaps": int((gaps["gap_pct"] == 0).sum()),
        "mapping": gaplib.HL_SYMBOL,
        "horizons": {},
    }
    for h in HORIZONS:
        res, m = evaluate(pit, prices, gaps, h)
        results["horizons"][f"h{h}"] = res
        m.drop(columns=["invalid_reasons"], errors="ignore").to_parquet(HERE / f"rows_h{h}.parquet")
    p = [results["horizons"][f"h{h}"]["screen"]["pass"] for h in HORIZONS]
    results["decision"] = "PASS: integrate-candidate" if all(p) else ("collect more evidence" if any(p) else "REJECT")
    lf = learning_feasibility(pit, gaps, days)
    (HERE / "learning_feasibility.json").write_text(json.dumps(lf, indent=2, default=str) + "\n")
    (HERE / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    gaps.to_parquet(HERE / "gaps.parquet")
    print(json.dumps({k: results[k] for k in ("preregistration_sha256", "sessions", "missing_reasons", "decision")}, indent=1))
    for h in HORIZONS:
        r = results["horizons"][f"h{h}"]
        print(f"h{h}", r["screen"], r["pooled"])


if __name__ == "__main__":
    main()
