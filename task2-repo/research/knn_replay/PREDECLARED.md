# gap-lgbm-knn-v1: pre-holdout replay, declared before it runs (25 Oct 2026, evening IST)

## What is tested
`task2.learner.AnalogLearner` in place of the Beta guard. Everything else in `model.py` is
gap-lgbm-v1 unchanged (MIN_GAP 0.3, MOVE_QUANTILE 0.25, horizons 3 and 5, band, stage-A LightGBM).

Fixed settings, one configuration, no search:
- Library: per asset and horizon; rows with |hl_gap| >= 0.3 thresholds and a complete window before
  `train_end`, plus the learning copy's own matured signals. Features `hl_gap`, `vol_20`, `ret_5`.
  The target is whether the gap's own direction won the barrier race; `neither` and an ambiguous
  bar count as misses.
- Distance: Euclidean on features scaled by the library's own standard deviation.
- K = 21, at least 11 rows to vote, flip when at least 65% of the nearest rows missed.

## Window
Official `run.py` (byte-identical template copy), learning and `--frozen`:
`--train-end 2026-02-20T03:00:00+00:00 --from 2026-02-20 --to 2026-05-22`.
The plan said 20 Feb to 29 May. The scored window ends 22 May so that every h5 outcome resolves
before 1 June, so no holdout price is graded. Scored with `tools/score_holdout.py --challenge 2
--from 2026-02-20 --to 2026-05-22 --no-baselines`.

The overseas history starts in February 2026, so the fitted library is close to empty at 20 Feb.
The frozen copy is therefore close to the plain gap rule, and the learning copy builds its library
from its own outcomes. That is the question being asked: does the run's own outcome history
improve the gap direction on the same keys.

## Decision (one run, no reruns except to fix a crash that produced no output)
- KEEP the kNN if the paired gain (scorer's paired learning direction minus paired frozen
  direction) is greater than 0 and learning direction >= frozen direction.
- Otherwise put the Beta guard back (`Learner = BetaGuard`).
- Reported in any case: paired gain, both directions, flip counts (learning right and frozen wrong,
  and the reverse), per asset and per horizon, read-log check.

The holdout is not opened by this replay. A holdout run of a kept kNN is one confirmatory look,
logged in `HOLDOUT_EXPOSURE.md` before it runs, and nothing is chosen from it.
