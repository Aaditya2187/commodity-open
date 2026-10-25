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
