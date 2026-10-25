#!/usr/bin/env python3
"""Research only: sweeps of the learners in learn_sim.py over auxiliary universes and settings.

    python research/learn_sweep.py L1        # or L2, L3

Settings are chosen on the development folds F2 and F1; HO is printed beside them, not used to choose.
Gate string per fold: direction>=60, frozen>null, learning>frozen, second half>=first, success>=70.
"""
from __future__ import annotations

import sys
from functools import partial

from learn_sim import Drift, Hedge, Refit, show

AUX = ["coreh:1,2", "coreh:1,2,3,4", "noncore:1,2", "noncore:5", "all:1,2", "all:1,2,3,4,5"]


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


if __name__ == "__main__":
    {"L1": l1, "L2": l2, "L3": l3}[sys.argv[1]]()
