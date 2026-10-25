#!/usr/bin/env python3
"""Research only: direction, count and halves of candidate abstention rules on slot files.

    python research/eval_rules.py research/slots_pre.parquet research/slots_holdout.parquet

Direction is the gap direction's realized rate over the slots a rule issues, the scorer's ruler.
Halves split the period's sessions by count, as the scorer does.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd


def prep(path: str) -> pd.DataFrame:
    s = pd.read_parquet(path)
    s = s[s["gap_thr"].notna()].copy()
    sg = np.sign(s["gap_thr"].to_numpy())
    up, dn = s["realized_up"].astype(bool).to_numpy(), s["realized_down"].astype(bool).to_numpy()
    s["hit"] = np.where(sg > 0, up, dn)
    s["abs_gap"] = s["gap_thr"].abs()
    s["ret5_al"] = s["f_ret_5"] * sg
    s["ret20_al"] = s["f_ret_20"] * sg
    s["last3_al"] = s["f_hl_gap_last3"] * sg
    s["pm_ok"] = s["p_move"] >= s["move_floor"]
    n_sessions = s["session_idx"].max() + 1
    s["half"] = np.where(s["session_idx"] < n_sessions // 2, 1, 2)
    return s


RULES = {
    "current (|gap|>=0.3, P(move))": lambda s: (s.abs_gap >= 0.3) & s.pm_ok,
    "|gap|>=0.3 only": lambda s: s.abs_gap >= 0.3,
    "|gap|>=0.4, P(move)": lambda s: (s.abs_gap >= 0.4) & s.pm_ok,
    "|gap|>=0.5, P(move)": lambda s: (s.abs_gap >= 0.5) & s.pm_ok,
    "|gap|>=0.5": lambda s: s.abs_gap >= 0.5,
    "current, ret5 aligned <= 0.5": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.ret5_al <= 0.5),
    "current, ret5 aligned <= 1.0": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.ret5_al <= 1.0),
    "current, ret20 aligned <= 1.0": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.ret20_al <= 1.0),
    "current, |gap| >= ret5 aligned": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.abs_gap >= s.ret5_al),
    "current, last3 aligned >= 0": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.last3_al >= 0),
    "current, night_range >= 0.5": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.f_hl_night_range >= 0.5),
    "current, h5 only": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.horizon == 5),
    "current, h3 only": lambda s: (s.abs_gap >= 0.3) & s.pm_ok & (s.horizon == 3),
}


def report(s: pd.DataFrame, mask: pd.Series) -> str:
    x = s[mask.fillna(False).to_numpy(bool)]
    if not len(x):
        return "n=0"
    h1, h2 = x[x.half == 1].hit, x[x.half == 2].hit
    return (f"n={len(x):4d} dir={100 * x.hit.mean():5.1f} halves={100 * h1.mean() if len(h1) else np.nan:5.1f}/"
            f"{100 * h2.mean() if len(h2) else np.nan:5.1f}")


def main() -> None:
    frames = {p: prep(p) for p in sys.argv[1:]}
    for name, rule in RULES.items():
        print(f"{name:34s} " + " | ".join(f"{p.split('/')[-1].split(chr(92))[-1][:14]}: {report(s, rule(s))}" for p, s in frames.items()))


if __name__ == "__main__":
    main()
