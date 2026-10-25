#!/usr/bin/env python3
"""Research only: sweeps of the learners in learn_sim.py over auxiliary universes and settings.

    python research/learn_sweep.py L1        # or L2, L3
    python research/learn_sweep.py grid      # writes research/results/sweep.csv
    python research/learn_sweep.py grid --quick

``grid`` skips a (design, aux) that already has every requested fold, so a crash can resume.
Settings are chosen on the development folds F2 and F1; HO is recorded beside them, not used to choose.
Gate string per fold: direction>=60, frozen>null, learning>frozen, second half>=first, success>=70.
"""
from __future__ import annotations

import sys
from functools import partial

from learn_sim import Drift, Hedge, Refit, run_design, show

AUX = ["coreh:1,2", "coreh:1,2,3,4", "noncore:1,2", "noncore:5", "all:1,2", "all:1,2,3,4,5"]
GRID_AUX = ["coreh:1,2,3,4", "coreh:1,2", "noncore:5", "all:1,2"]
FOLDS = ("F2", "F1", "HO")


def l1():
    for aux in AUX:
        for half in (5, 20, 80):
            for pool in (0.0, 20.0):
                show(f"L1 drift half={half} pool={pool}", partial(Drift, half=half, pool=pool), aux)


def l2():
    for aux in AUX:
        for eta in (0.3, 1.0):
            for gamma in (0.9, 0.98):
                show(f"L2 hedge eta={eta} g={gamma}", partial(Hedge, eta=eta, gamma=gamma), aux)
        show("L2 hedge mom/rev/drift only", partial(Hedge, eta=1.0, gamma=0.95, experts=("mom5", "rev5", "mom20", "drift")), aux)


def l3():
    for aux in AUX:
        for kind in ("logit", "cat"):
            for every in (5, 15):
                show(f"L3 refit {kind} every={every}", partial(Refit, kind=kind, every=every), aux)


def _grid_points() -> list[tuple[str, str, dict]]:
    points = []
    for every in (5, 10):
        for news in (False, True):
            name = f"refit_e{every}" + ("_news" if news else "")
            points.append((name, "refit", {"every": every, "news": news}))
    for k in (1, 3):
        for lr in (3e-4, 1e-3):
            for news in (False, True):
                tag = f"{lr:.0e}".replace("+0", "").replace("+", "")
                name = f"mlp_k{k}_lr{tag}" + ("_news" if news else "")
                points.append((name, "neural", {"kind": "mlp", "k": k, "lr": lr, "news": news}))
    points.append(("gru_k3_lr3e-4", "neural", {"kind": "gru", "k": 3, "lr": 3e-4, "news": False}))
    for every in (5, 10):
        for alpha in (0.5, 0.8):
            points.append((f"append_e{every}_a{alpha}", "append", {"every": every, "alpha": alpha}))
    for w in (0.5, 0.7):
        points.append((f"blend_w{w}", "blend", {"w_refit": w, "every": 5, "k": 3, "lr": 3e-4, "news": False}))
    return points


def grid(quick: bool = False) -> None:
    if quick:
        points = [
            ("refit_e5", "refit", {"every": 5, "news": False}),
            ("mlp_k1_lr3e-4", "neural", {"kind": "mlp", "k": 1, "lr": 3e-4, "news": False}),
            ("gru_k3_lr3e-4", "neural", {"kind": "gru", "k": 3, "lr": 3e-4, "news": False}),
            ("append_e5_a0.5", "append", {"every": 5, "alpha": 0.5}),
            ("blend_w0.5", "blend", {"w_refit": 0.5, "every": 5, "k": 3, "lr": 3e-4}),
        ]
        for design, learner, params in points:
            run_design(design, learner, params, "coreh:1,2,3,4", folds=("F1",),
                       csv_path="research/results/sweep_quick.csv", max_sessions=15)
        return
    for design, learner, params in _grid_points():
        for aux in GRID_AUX:
            run_design(design, learner, params, aux, folds=FOLDS, csv_path="research/results/sweep.csv")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "grid":
        grid(quick="--quick" in sys.argv)
    else:
        {"L1": l1, "L2": l2, "L3": l3}[cmd]()
