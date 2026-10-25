"""The learning layer used by ``update`` (learning copy only; the frozen copy never calls it).

Per asset, an exponentially forgotten Beta posterior of the gap rule's hit rate on the run's own
graded signals. If the posterior mean falls below FLIP_BELOW with at least MIN_EVIDENCE effective
outcomes, that asset's direction is inverted until the mean recovers above UNFLIP_ABOVE.

Measured before the holdout (session replay of Feb 20 - May 29 2026, 296 filtered signals, delivery
at the pre-open after each outcome settles): the guard never fires, so the paired gain is 0.00 pp.
Faster guards and online logistic re-weighting all lost 1-5 pp there by inverting correct calls.
This layer is therefore a safety switch for a broken overseas pass-through, not a source of gain.
"""
from __future__ import annotations

import pandas as pd

PRIOR_HITS, PRIOR_MISSES = 13.0, 7.0
FORGET = 0.5 ** (1.0 / 30.0)
MIN_EVIDENCE = 20.0
FLIP_BELOW = 0.40
UNFLIP_ABOVE = 0.50
INVERTED_TAG = "; learner inverted the gap direction"


class _Guard:
    def __init__(self) -> None:
        self.hits, self.misses, self.n, self.flipped = PRIOR_HITS, PRIOR_MISSES, 0, False

    def observe(self, rule_right: bool) -> None:
        self.hits = self.hits * FORGET + (1.0 if rule_right else 0.0)
        self.misses = self.misses * FORGET + (0.0 if rule_right else 1.0)
        self.n += 1
        evidence = self.hits + self.misses - (PRIOR_HITS + PRIOR_MISSES) * FORGET ** self.n
        mean = self.hits / (self.hits + self.misses)
        if not self.flipped and evidence >= MIN_EVIDENCE and mean < FLIP_BELOW:
            self.flipped = True
        elif self.flipped and mean > UNFLIP_ABOVE:
            self.flipped = False

    def state(self) -> dict:
        return {"hits": round(self.hits, 6), "misses": round(self.misses, 6), "n": self.n, "flipped": self.flipped}


class Learner:
    def __init__(self) -> None:
        self.guards: dict[str, _Guard] = {}
        self.received = 0

    def _g(self, asset: str) -> _Guard:
        return self.guards.setdefault(asset, _Guard())

    def direction(self, asset: str, horizon: int, rule_dir: str, info: dict) -> tuple[str, str]:
        if self._g(asset).flipped:
            return ("down" if rule_dir == "up" else "up"), INVERTED_TAG
        return rule_dir, ""

    def update(self, matured: pd.DataFrame) -> dict:
        n = 0 if matured is None else len(matured)
        self.received += n
        if not n:
            return {"received": self.received, "state_changed": False}
        before = {a: g.flipped for a, g in self.guards.items()}
        for _, r in matured.sort_values(["signal_utc", "asset", "horizon"], kind="stable").iterrows():
            if bool(r.get("no_price", False)) or r.get("realized") is None:
                continue
            inverted = INVERTED_TAG in str(r.get("evidence", ""))
            self._g(str(r["asset"])).observe(bool(r["realized"]) != inverted)
        changed = any(before.get(a, False) != g.flipped for a, g in self.guards.items())
        return {"received": self.received, "state_changed": changed,
                "guards": {a: g.state() for a, g in sorted(self.guards.items())}}
