# Pipeline report

# Selection

Holdout folds are reported and were not used to rank.

Qualified designs: 35. Shipable (`coreh:*`): 21.

Best: `refit_e5` learner `refit` aux `coreh:1,2,3,4` (min dev success 82.76).
Ship: `refit_e5` learner `refit` aux `coreh:1,2,3,4` params `{"every": 5, "news": false}`.

| design | aux | learner | dev min S | F2 D/gain/S | F1 D/gain/S | HO D/gain/S |
|---|---|---|---|---|---|---|
| refit_e5 | coreh:1,2,3,4 | refit | 82.8 | 76.0 / +11.06 / 92.0 | 75.9 / +7.24 / 82.8 | 72.0 / +0.96 / 60.6 |
| refit_e5_news | coreh:1,2,3,4 | refit | 82.8 | 76.0 / +11.06 / 92.0 | 75.9 / +7.24 / 82.8 | 72.0 / +0.96 / 60.6 |
| blend_w0.7 | coreh:1,2,3,4 | blend | 78.2 | 75.1 / +9.57 / 90.3 | 75.9 / +5.86 / 78.2 | 72.0 / +0.96 / 60.6 |
| refit_e10 | coreh:1,2,3,4 | refit | 77.7 | 71.7 / +6.81 / 79.9 | 74.5 / +5.86 / 77.7 | 72.0 / +0.96 / 60.6 |
| refit_e10_news | coreh:1,2,3,4 | refit | 77.7 | 71.7 / +6.81 / 79.9 | 74.5 / +5.86 / 77.7 | 72.0 / +0.96 / 60.6 |
| append_e5_a0.5 | coreh:1,2,3,4 | append | 76.4 | 73.8 / +8.94 / 87.7 | 74.1 / +5.52 / 76.4 | 72.0 / +0.96 / 60.6 |
| append_e5_a0.8 | coreh:1,2,3,4 | append | 76.4 | 73.8 / +8.94 / 87.7 | 74.1 / +5.52 / 76.4 | 72.0 / +0.96 / 60.6 |
| blend_w0.7 | coreh:1,2 | blend | 75.3 | 74.5 / +8.51 / 86.5 | 74.1 / +5.17 / 75.3 | 69.1 / +0.80 / 59.0 |
| refit_e5 | coreh:1,2 | refit | 74.9 | 74.5 / +9.22 / 88.9 | 73.0 / +5.17 / 74.9 | 69.1 / +0.80 / 59.0 |
| refit_e5_news | coreh:1,2 | refit | 74.9 | 74.5 / +9.22 / 88.9 | 73.0 / +5.17 / 74.9 | 69.1 / +0.80 / 59.0 |
| refit_e10 | coreh:1,2 | refit | 74.9 | 73.8 / +8.51 / 86.3 | 73.0 / +5.17 / 74.9 | 69.1 / +0.80 / 59.0 |
| refit_e10_news | coreh:1,2 | refit | 74.9 | 73.8 / +8.51 / 86.3 | 73.0 / +5.17 / 74.9 | 69.1 / +0.80 / 59.0 |

# Forward check

Design `refit_e5` learner `refit` params `{"every": 5, "news": false}` aux `coreh:1,2`.
Windows: 30 (5 sessions, stride 5, 2 Mar 2026 through 16 Oct 2026, none crossing 1 June).

- share with gain > 0: 6.7%
- mean gain: +0.72 pp
- share with direction >= 60 and success >= 70: 6.7%

## v3 holdout

- direction 78.3132530120482
- depth 100.0
- improvement 0.0
- success 59.437751004016064
- paired learning 78.3132530120482 frozen 78.3132530120482 n=83
- halves 75.47169811320755 then 83.33333333333334
- hard conditions failing: ['learning_beats_frozen', 'success_rate_at_least_minimum']

## ship holdout

- direction 70.8433734939759
- depth 100.0
- improvement 4.819277108433773
- success 58.55421686746988
- paired learning 70.8433734939759 frozen 70.36144578313252 n=415
- halves 68.67924528301886 then 74.66666666666667
- hard conditions failing: ['success_rate_at_least_minimum']

v3 rerun identical: True
ship rerun identical: True

## Decision

Official holdout of `refit_e5` (aux horizons 1–4 on core sessions, CatBoost refit every 5) has success **58.55**, below gap-night-cat-v3's **59.44**. Learning direction is above frozen, direction stays above 60, frozen beats the null, and the second half is above the first. Success does not clear 59.4, so `LEARNER` stays `"v3"`. The 1 Apr–22 May fold of the same candidate scores success 68.74 and is not used to override the holdout.
