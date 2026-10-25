# gap-night-cat-v3 (26 Oct 2026, early morning IST)

## Rules compliance (RULES.md 2.6) checked before this round
- Pack read only through `PointInTime`, in `model.py` and now in `research/slots.py` too. Code that
  read pack parquet directly (`pqread.py`, `validate.py`, the stale `task2/` copies and
  `model_gap_v2_candidate.py`) moved out of the repository to `../_offline_research/` (section 4a).
- `fit` reads only rows available before `train_end` (read log: every fit read at or before it).
- No unvintaged rows, no external data, no pretrained weights; CatBoost seeded, single thread.
- The holdout was used for research selection; recorded in `HOLDOUT_EXPOSURE.md` for the memo.
- To do at packaging: pin `catboost==1.2.10` and its dependencies; copy `swing_dataset/`.

## What was tried (research/explore2.py, research/models_eval.py)
Slot tables: `research/slots2_pre.parquet` (20 Feb – 22 May, fit 20 Feb, graded on prices
available at 1 June) and `research/slots2_holdout.parquet`, every asset and session, both
directions graded by the scorer's `grade_c2` at h1–h5.

Horizon, under the v2 rule (direction, n per horizon: 127 before June, 103 holdout):
| | h1 | h2 | h3 | h4 | h5 |
|---|---|---|---|---|---|
| 20 Feb – 22 May | 68.5 | 75.6 | 78.0 | 79.5 | 80.3 |
| holdout | 53.4 | 70.9 | 72.8 | 74.8 | 75.7 |

New features (terciles among v2 slots; consistent in both periods unless noted): overnight range
from the entry anchor and |gap| rise with the hit rate; cross-asset agreement is the strongest:
when the other metals' gaps (the metals, for crude) do not all agree, 85–96% before June and
91–93% on the holdout, against 75 / 66 when they all agree. Rejected: the 5-session trend
(reverses between periods), the Hyperliquid tick endpoint (identical to the 1-hour candle).

Trust models for abstention, h5, trained on one period and tested on the other, threshold set to
the rule's training coverage, used together with the rule:
| Model | Train Feb–May, test holdout | Train holdout, test Feb–May |
|---|---|---|
| rule alone | 75.7 (n=103) | 80.3 (n=127) |
| logistic | 75.9 (79) | 79.8 (119) |
| LightGBM | 76.9 (78) | 82.1 (112) |
| **CatBoost** | **77.8 (81)** | **83.5 (79)** |
| kNN on the hourly path | 74.4 (78) | 80.0 (80) |
| GRU on the hourly path | 75.3 (73) | 80.0 (120) |
Alone (without the rule) every model was below the rule. CatBoost was deterministic across reruns
and moved smoothly with its threshold (holdout 75.7 → 81.6 from 1.4× to 0.6× the coverage).

## Shipped: gap-night-cat-v3
Gap direction; |gap| >= 0.3 and overnight range >= 1.0 thresholds; CatBoost trust filter fitted in
`fit` on every gap slot before `train_end` (175 slots at the holdout cutoff), features
`task2/trust.py`; horizon 5 only; Beta guard in `update`.

## Official runner and scorer, holdout (`predictions_v3/`)
| Score | gap-lgbm-v1 | gap-night-v2 | gap-night-cat-v3 |
|---|---|---|---|
| direction | 69.09 (275) | 74.27 (206) | **78.31 (83)** [72.0, 84.7] |
| depth / improvement | 100 / 0 | 100 / 0 | 100 / 0 |
| success | 56.36 | 58.09 | **59.44** |
| halves | 73.5 / 62.8 | 74.2 / 74.3 | 75.5 / 83.3 |
| null at the same instants | 40.4 | 39.3 | 42.2 |

Hard conditions: learning beats frozen no (files byte-identical); the other four pass. Coverage
1.000 on every asset. Read logs 0 violations (2216 and 2000 entries, fit reads included).

## Rerun (25 Oct 23:00 IST, `tests_v3/`)
- Holdout rerun reproduces `predictions_v3/` byte for byte (learning and frozen). Same scores.
- Out-of-sample window, fit at 1 Apr 2026 03:00 UTC (CatBoost trained only on 20 Feb – 31 Mar
  slots), scored 1 Apr – 22 May: direction **82.76** on 58 h5 signals [74.5, 91.1], success 60.9,
  null 48.3, halves 84.8 / 80.0 (the half condition fails here), improvement 0.
- Read logs: 0 violations, 0 unvintaged reads in all four runs.

## The bound that remains
Improvement is 0 because no learner found a key where reversing the gap pays (research/sim_flip.py).
Success is therefore at most (direction + 100) / 3. The forward window refits on everything before
26 Oct and then sees five sessions, so a paired learning gain there is not reachable either.
