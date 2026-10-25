#!/usr/bin/env python3
"""Research only: horizon choice and new overnight-path features on both periods (slots2_*.parquet)."""
from __future__ import annotations

import numpy as np
import pandas as pd

H = (1, 2, 3, 4, 5)


def load(path: str) -> pd.DataFrame:
    s = pd.read_parquet(path)
    s = s[s["gap_thr"].notna()].copy()
    sg = np.sign(s["gap_thr"].to_numpy())
    for h in H:
        s[f"hit_h{h}"] = np.where(sg > 0, s[f"real_up_h{h}"], s[f"real_down_h{h}"]).astype(bool)
        s[f"opp_h{h}"] = np.where(sg > 0, s[f"real_down_h{h}"], s[f"real_up_h{h}"]).astype(bool)
    s["abs_gap"] = s["gap_thr"].abs()
    s["last1_al"] = s["last1"] * sg
    s["last3_al"] = s["last3"] * sg
    s["pos_al"] = (s["pos_anchor"] - 0.5) * sg
    s["ret5_al"] = s["f_ret_5"] * sg
    n = s["session_idx"].max() + 1
    s["half"] = np.where(s["session_idx"] < n // 2, 1, 2)
    return s


P, Hd = load("research/slots2_pre.parquet"), load("research/slots2_holdout.parquet")
base = lambda s: (s.abs_gap >= 0.3) & (s.night_range >= 1.0)


def d(s, m, h):
    x = s[m]
    return f"{len(x):3d} {100 * x[f'hit_h{h}'].mean():5.1f} ({100 * x[x.half == 1][f'hit_h{h}'].mean():4.1f}/{100 * x[x.half == 2][f'hit_h{h}'].mean():4.1f})"


print("== v2 rule, by horizon: n dir (half1/half2)")
for h in H:
    print(f"h{h}: pre {d(P, base(P), h)} | holdout {d(Hd, base(Hd), h)}")
print("h3+h5 pooled: pre %.1f | holdout %.1f" % (
    100 * np.r_[P[base(P)].hit_h3, P[base(P)].hit_h5].mean(), 100 * np.r_[Hd[base(Hd)].hit_h3, Hd[base(Hd)].hit_h5].mean()))

print("\n== new features among v2 issued, tercile hit rate (h3,h5 pooled): pre | holdout")
for c in ["nr_anchor", "eff", "pos_al", "last1_al", "last3_al", "n_hours", "abs_gap", "night_range", "ret5_al", "f_vol_20", "f_hl_vol_20d"]:
    out = []
    for s in (P, Hd):
        x = s[base(s)]
        v = x[c].to_numpy(float)
        q = np.nanquantile(v, [1 / 3, 2 / 3])
        bins = [v <= q[0], (v > q[0]) & (v <= q[1]), v > q[1]]
        hr = [100 * np.r_[x.hit_h3[b], x.hit_h5[b]].mean() for b in bins]
        out.append(" ".join(f"{r:5.1f}" for r in hr) + f" [q {q[0]:.2f},{q[1]:.2f}]")
    print(f"{c:12s} pre {out[0]} | holdout {out[1]}")

print("\n== cross-asset: other assets' gap sign agreement (v2 issued)")
for s, name in ((P, "pre"), (Hd, "holdout")):
    piv = s.pivot_table(index="session_idx", columns="asset", values="gap_thr")
    x = s[base(s)].copy()
    sg = np.sign(x.gap_thr.to_numpy())
    agree = []
    for r, g in zip(x.itertuples(), sg):
        others = piv.loc[r.session_idx].drop(r.asset)
        metals = [a for a in ("gold", "silver", "copper") if a != r.asset] if r.asset != "crude" else []
        o = others[metals] if metals else others
        agree.append(np.nanmean(np.sign(o.to_numpy()) == g) if o.notna().any() else np.nan)
    x["agree"] = agree
    for lo, hi in ((-0.01, 0.34), (0.34, 0.67), (0.67, 1.01)):
        b = (x.agree > lo) & (x.agree <= hi)
        print(f"{name}: agree in ({lo:.2f},{hi:.2f}] n={b.sum():3d} dir={100 * np.r_[x.hit_h3[b], x.hit_h5[b]].mean():5.1f}")

print("\n== tick endpoint (holdout only): gap from hl_quotes vs candle gap")
x = Hd[base(Hd) & Hd.gap_hlq.notna()]
same = np.sign(x.gap_hlq) == np.sign(x.gap_thr)
print("n", len(x), "sign agrees", round(same.mean(), 3))
for c, lo in (("gap_hlq", 0.3), ("gap_hlq", 0.5)):
    m = x[c].abs() >= lo
    hit = np.where(np.sign(x[c]) > 0, x.real_up_h5, x.real_down_h5)[m]
    print(f"|{c}|>={lo}: n={m.sum()} h5 dir by tick sign {100 * hit.mean():.1f} vs candle {100 * x.hit_h5[m].mean():.1f}")
