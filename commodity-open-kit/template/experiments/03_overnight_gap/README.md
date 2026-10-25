# Experiment 03: overnight overseas gap (pre-holdout, 20 Feb – 29 May 2026)

Pre-registration: `PREREGISTRATION.md` (sha256 `a666837451f73ef5aec9a97572ef82046457bc10564d9a81525e1109d811abf8`,
hash recorded in `PREREGISTRATION.sha256` before the evaluation script existed, and again in `results.json`).

```
cd commodity-open-kit/template
../.venv/bin/python experiments/03_overnight_gap/test_units.py --pack ../../v2.1      # 5 tests
../.venv/bin/python experiments/03_overnight_gap/gap_test.py --pack ../../v2.1        # results.json, learning_feasibility.json, rows_h3/h5.parquet, gaps.parquet
../.venv/bin/python experiments/03_overnight_gap/posthoc_mechanism.py ../../v2.1      # posthoc.json (NOT part of the screen)
```

## Screen (pre-registered)
| | direction (90% CI) | matched null | diff pp (90% CI) | C1 ≥58 | C2 ≥8pp | C3 terciles ≥3/4 | pass |
|---|---|---|---|---|---|---|---|
| h=3 (n=275, 94 episodes) | 64.7 (59.7–69.7) | 45.5 | +19.3 (13.2–25.1) | ✔ | ✔ | ✔ (4th: silver ✘) | **✔** |
| h=5 (n=274, 58 episodes) | 69.3 (65.3–73.4) | 49.3 | +20.1 (15.0–24.9) | ✔ | ✔ | ✘ (copper, silver ✘) | **✘** |

**Pre-registered decision: COLLECT MORE EVIDENCE**, because exactly one horizon passed.

## Post-hoc mechanism checks (no selection)
- Placebo (the perp move over the 9h before the entry observation, already contained in p0): 40.4% at h3 and 42.3% at h5.
  This is below the null, so the effect is not generic momentum.
- The next MCX open moves from p0 in the direction of the gap in 83–90% of cases (corr 0.69–0.81, slope 0.32–0.68).
  This is consistent with the stale-entry-price mechanism.

## Learning feasibility
Delivery delays come from `loop.matured_outcomes` on the rule's own signals. In a 5-session window,
about 13–14 of 20 predictions have an earlier matured same-asset outcome at h3/h5, and 16 of 20 with h=1 probes.
Accuracy after a correct vs a wrong last outcome: h3 63.8 vs 68.8 (diff −5.0, 90% CI −16.3 to +5.7);
h5 68.6 vs 72.9 (diff −4.3, CI −17.5 to +8.3). **No learning mechanism is justified.**
