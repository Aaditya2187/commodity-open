# Experiment 06: online logistic learner (ologit). Configurations and criteria, frozen before scoring

Written 2026-10-25 ~16:15 IST, after a fit-only smoke test (weights printed, nothing scored).

## Fixed for every configuration
- Features (each available before the 08:30 IST pre-open, read through PointInTime):
  - overseas gap / threshold, anchored at the entry-price trade, capped at the last session close;
  - trailing 5-session move / threshold;
  - trailing 20-session move / threshold;
  - intercept.
  - All clipped to [-3, 3]. No other scaling (the threshold units are fixed constants).
- Schedule: every pre-open, all four assets, horizons 3 and 5 issued, no abstention.
  Band [0.999 thr, +12 thr], expected 2 thr.
- Starting state: a Laplace logistic fit per horizon, prior N(0, 1), on decided labels known
  before train_end. Learning and frozen start from the same fit (tested by state digest).
- Update target: up-first (1) or down-first (0), derived from the delivered row (`realized`,
  `direction`, `mae_pct` ≥ threshold). Rows where neither barrier was hit, or with an ambiguous bar,
  are skipped. Feedback = only what `loop.matured_outcomes` delivers.
- Update rule: online Newton (Laplace) step with forgetting factor LAMBDA.
- Frozen comparator: the identical model with `--frozen` (update never called).

## Configurations (the only two scored in round 1)
- C1: LAMBDA = 1.00. No forgetting; pure Bayesian accumulation.
- C2: LAMBDA = 0.95. Memory of about 20 labels per horizon (about one week of four assets); can track drift.

## Development folds (pre-holdout; labels resolve before 2026-06-01)
- F1: train_end 2026-04-01 03:00 UTC; scored window 2026-04-01 to 2026-05-22.
- F2: train_end 2026-03-16 03:00 UTC; scored window 2026-03-16 to 2026-05-22.

F2 contains F1's window, so the folds are not independent. Both reuse the Feb–May period already
used by exp 03 (not fresh). Run with the template's run.py (`--from/--to/--train-end`), scored by
`tools/score_holdout.py --challenge 2 --from --to`.

## Primary endpoint
Paired learning gain = scorer's paired learning direction − paired frozen direction, in pp.

## Decision per configuration
- **PASS**: gain ≥ +2.0 pp on F1 and on F2.
- **FAIL**: gain ≤ 0 on either fold.
- **INCONCLUSIVE**: anything else.

If both configurations pass, select the one with the larger minimum-fold gain; on a tie, C1.
Sample size: report n paired per fold. If fewer than 150 paired rows, the result is INCONCLUSIVE at best.

## Revisions and stopping
At most two further rounds. Each must be driven by an observed failure and written below before it
is scored. The official holdout is run only for the selected configuration, once, and is labelled
EXPLORATORY (it has been inspected before). It cannot change the selection.

## Revision log
(appended before each revision is scored)

### Revision R1 (written 2026-10-25 before scoring R1; round 1 results logged in attempts.jsonl)
Observed failure: C1 FAIL (F1 −1.01 pp, F2 +2.30), C2 FAIL (F1 −4.05, F2 −1.79). Weight traces show
that updates mainly move the intercept (C2: about −0.2 → +1.0; the learning copy issues 52–54% ups
vs 37–42% for frozen) and the gap weight (1.5–1.9 → 2.0–3.0). Direction flips concentrate on
small-gap keys, where the intercept decides, and these flips were net wrong (F+L− > L+F− in 3 of 4
runs). Intercept drift is the drift-learning mechanism exp 02 already rejected.

R1 (the single revision): update ONLY the gap coefficient (one-dimensional online Newton on the
gap weight with intercept, m5 and m20 held at their fitted values), LAMBDA = 1.0. Rationale: the
mechanism that could be learnable is the strength of overseas-gap pass-through. Recent drift is not.
Same folds, same PASS/FAIL/INCONCLUSIVE rule.
Expectation, stated before scoring: fewer flips, and a gain near 0. If R1 fails, development stops
here. No second revision is planned unless R1 shows a broken update path.

### Holdout run (written before running): R1 is INCONCLUSIVE (F1 +0.68, F2 +2.55); no configuration PASSED. R1 is run once on the official holdout as EXPLORATORY evidence for the gates table only. This is not a selection by passing criteria and not confirmation. No further revisions.
