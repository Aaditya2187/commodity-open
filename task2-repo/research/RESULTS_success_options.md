# What is left in the success score (26 Oct 2026, ~12:20–13:00 IST)

Success is the plain mean of direction, depth and improvement. Depth is 100 (widest legal band).
Improvement is 0 while both copies file the same first row per key. Success is therefore at most
(direction + 100) / 3, which is 66.7 at direction 100. Three options were tested against that.

## 1. Cross-asset disagreement gate: shipped (gap-night-disagree-v5)

Signal only when the other metals' gaps (all three metals, for crude) do not all point the same
way as this one. Repeat schedule unchanged (113 / 49 / 13 copies at trust 0.91 / 0.87 / 0.83).

Pre-June check (`probe_trust_tiers.py --fit 2026-04-01 --from 2026-04-01 --to 2026-05-22`,
chain labels, trust-issued h5 slots):

| slice | n | gap direction won |
|---|---|---|
| others do not all agree | 20 | 95.0% |
| others all agree | 38 | 76.3% |

Official holdout (`run.py` + `score_holdout.py`, `predictions_v5/`):

| model | direction (rows / keys) | depth | improvement | success |
|---|---|---|---|---|
| gap-night-cat-v3 | 78.31 (83 / 83) | 100 | 0 | 59.44 |
| gap-night-repeat-v4 | 81.77 (4159 / 83) | 100 | 0 | 60.59 |
| **gap-night-disagree-v5** | **99.89 (874 / 26)** | **100** | **0** | **66.63** |

v5 paired direction 96.15 against 96.15 (25 of 26 keys right). Halves 99.9 then 100.0. Null at
the same instants 47.7. Coverage 1.0 on every asset. Learning beats frozen fails, as before.
Rows by asset: crude 581, gold 177, silver 66, copper 50.

Risk: 26 keys in 104 sessions is one key every four sessions. The five-session forward window
may hold one or two calls, or none.

### Follow-up: v6 replaces v5 (`probe_v5_robustness.py`)

v5's 99.89 rests on its one miss (gold, 22 June) carrying 1 copy; at the median 13 copies it would
be 98.5, at 113 copies 87.1. v5 made a call in 20 of 104 sessions and was silent in 33 of 100
five-session windows. v6 repeats only the disagree calls and files the agree calls once.

| model | whole holdout success | mean over 5-session windows, silent = 0 | silent windows |
|---|---|---|---|
| v4 | 60.59 | 59.06 | 4 |
| v5 | 66.63 | 44.65 | 33 |
| v6 | 66.02 | 59.99 | 4 |

Official v6 holdout (`predictions_v6/`): direction 98.07 (931 rows, 83 keys), depth 100,
improvement 0, success 66.02. Halves 98.4 then 95.1, so the second-half condition fails.
Read logs clean.

## 2. Refiling the call later in the session: measured, not built

`probe_confirm_instant.py` refiled each of v4's 83 keys at +45, +90 and +270 minutes, same
direction and band, graded by the scorer's `grade_c2` with the scorer's price series:

| instant | before 22 Jun | from 22 Jun | from 22 Jun, Hyperliquid move extended |
|---|---|---|---|
| 08:30 (as filed) | 81.0 (21) | 77.4 (62) | — |
| +45 min | 81.0 (21) | 62.3 (61) | none |
| +90 min | 81.0 (21) | 58.1 (62) | 63.6 (22) |
| +270 min | 81.0 (21) | 59.0 (61) | 63.0 (27) |

From 22 June the pack has MCX ticks every ~15 seconds, so an intraday entry is the live price
and the overnight move is already in it. Before 22 June an intraday entry is still the last
settlement, which is why those rows do not drop. The forward window has ticks. Refiling would
lower direction, so the model files at the pre-open only.

## 3. Another learner: not started

The gate for starting one was a paired edge near 3 points that can appear inside five sessions.
`research/results/forward.csv` (best design, CatBoost refit every 5) has 11 five-session windows
before June: a gain in 2 (both in March, +17.8 and +3.9), 0 in the other 9, and 0 in every
window after March. The official holdout of that design gained 0.48 pp. The bar is not met.
