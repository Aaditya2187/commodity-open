# gap-lgbm-knn-v1 pre-holdout replay: result (25 Oct 2026, evening IST)

Settings and decision rule: `PREDECLARED.md`, written before the run. Harness: `replay.py`.
Outputs: `run/` (signal files, read logs, scorer report, `summary.json`).

The first attempt crashed in `fit` before writing any signal: at 20 Feb the pack has no overseas
gap rows, so the fit frame had no `hl_gap` column. `AnalogLearner.fit` now returns an empty library
in that case. The run was then made once.

## Official scorer, 20 Feb to 22 May 2026 (pre-holdout)
| | Learning | Frozen |
|---|---|---|
| direction (paired, n = 343) | 72.59 | 72.59 |
| paired gain | 0.00 pp | |
| depth | 98.39 | |
| improvement | 0.0 | |
| success | 57.00 | |
| null at the same instants | 50.15 | |
| halves | 74.16 then 70.91 | |

Keys where the two copies differ: 0. Read logs: 0 violations in both.
Per asset (both copies): copper 55.95, crude 78.05, gold 69.86, silver 83.65.
Per horizon: h3 70.35, h5 74.85.

## Why the vote never fired (in-process check of the update path, same window)
`update` received 330 matured outcomes and appended all 330 (13 signals were still unmatured at the
end). Final library sizes 33–51 per asset and horizon. The gap's own hit rate in the library:
copper 54–64, gold 69–79, crude 80, silver 84. The highest share of missed neighbours at any
library point was 0.62 (copper h3), against the declared 0.65. Crude and silver never exceeded 0.33.

So the update path works. There is no neighbourhood of past gaps where the gap direction loses
often enough to be reversed. This agrees with experiments 02, 03, 06 and Phase 3.

## Decision
**REVERT to BetaGuard**, as declared. The 0.65 vote is not lowered after seeing 0.62; that would be
a search on this window. The holdout was not opened for this model.
