# Phase 2 results (2026-10-25), all pre-holdout

## LightGBM direction model, every slot signalled (Jan-May 2026 block)
| | h3 | h5 |
|---|---|---|
| 3-class, 57 features | 42.5 | 45.0 |
| binary up/down | 40.6 | 46.9 |
| per-asset | 40.3 | 44.1 |
| gap-era only (3 seeds) | 53-57 | 56-61 |
| prevailing null | 45.5 | 49.8 |
| gap rule | 61-64 | 68-69 |
2023-2025 blocks: LightGBM at or below the null. Rejected as a direction model.

## Stage A: LightGBM P(either barrier hit within h), 2021-2026 walk-forward
AUC 0.59-0.72 in 6 of 7 blocks at both horizons (2026 h5: 0.48, base rate 90%). Beats constant Brier in every block.

## Stage C: abstention on gap-era rows (Feb 20 - May 29 2026, 5 rolling chunks, 560 rows)
| rule | direction | coverage |
|---|---|---|
| all gap rows | 66.8 | 100% |
| LightGBM trust model (several feature sets) | 70.9-74.2 | 61-66% |
| logistic on abs(gap) | 73.6 | 62% |
| abs(gap) >= 0.3 thr | 74.6 | 66% |
| abs(gap) >= 0.3 and stage-A P(move) >= train q25 | 80.2 | 50% |
By horizon: h3 72.3 -> 85.5 (cov 66 -> 35%); h5 76.9 -> 77.3. Better in all 5 chunks.
Selection caveat: one of 8 variants tried on the same 560 rows.

## Learning layer replay (296 filtered signals, delivery at next pre-open after settlement)
| policy | paired gain pp |
|---|---|
| per-asset Beta guard (default, shipped) | +0.00 (never fires) |
| faster guard | -1.69 |
| online logistic lr 0.3 / 1.0 / weak prior | -1.35 / -5.07 / -1.01 |
No learner produced a positive gain. The learning > frozen gate remains unsolved.
