# Phase 2: LightGBM walk-forward (2026-10-25)

LightGBM 4.6.0, built from the official v4.6.0 tag (commit d02a01ac) with its pinned Eigen 3147391d,
deterministic=True, num_threads=1, seed 20261025. Labels: barrier race (asset threshold up before
threshold down within h sessions; "neither" counts as a miss, as the scorer does). 57 point-in-time
features. Purged expanding-window folds (purge h + 5 business days). No holdout data used.

## Every slot signalled, 3-class model, 1-year recency half-life

| Test block | h3 LGBM | h3 null | h5 LGBM | h5 null |
|---|---|---|---|---|
| 2023 H1 | 33.8 | 31.8 | 43.2 | 43.8 |
| 2023 H2 | 21.7 | 25.8 | 27.1 | 37.7 |
| 2024 H1 | 22.9 | 27.7 | 33.0 | 38.7 |
| 2024 H2 | 34.7 | 36.0 | 45.9 | 44.2 |
| 2025 H1 | 33.3 | 30.8 | 43.2 | 40.5 |
| 2025 H2 | 33.1 | 34.7 | 43.2 | 44.2 |
| 2026 Jan-May | 42.5 | 45.5 | 45.0 | 49.8 |

Gap rule on the 280 Feb-May 2026 rows where the overseas gap exists: 64.3 (h3), 68.9 (h5).

## Variants, Jan-May 2026 block

| Variant | h3 | h5 |
|---|---|---|
| Binary up/down on decided rows, all features | 40.6 | 46.9 |
| Per-asset binary models | 40.3 | 44.1 |
| Gap-era only (train to 10 Apr), small feature set, 3 seeds | 53.3 vs gap 60.7 | 55.7 vs gap 67.9 |
| Gap-era only (train to 30 Apr) | 56.7 vs gap 61.9 | 61.1 vs gap 69.0 |

When the gap-era LightGBM disagrees with the gap's sign it is right 18-31% of the time.

## Reading
Phase 2 gate fails: LightGBM does not beat the prevailing-direction null on 2021-2026 daily features,
and on gap-era rows it is worse than the sign of the gap alone. The predictive information at h3/h5
is concentrated in the overnight overseas move, which has ~280 pre-holdout rows.
