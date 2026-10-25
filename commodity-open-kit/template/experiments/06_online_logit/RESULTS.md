# Experiment 06: online logistic learner (ologit). Results (2026-10-25, ~17:00 IST)

Deadline Mon 26 Oct 17:00 IST (README.md:25). Research stops by Mon 11:00 IST so the final six
hours go to reproduction and packaging. gap-v1, template/model.py, template/run.py and the
baselines are untouched; `submission/run.py` is a byte-identical copy of the template's.

## Gate table (verified in scoring2/score.py and __init__.py; see 05_gap_diagnosis/DECISION_MEMO.md)
| Item | Exact rule |
|---|---|
| direction | realized / scorable signals. Realized = threshold before opposite threshold within h; "neither" and invalid rows count as failures |
| depth | in_band / realized. Band ≤ 12 thresholds |
| improvement | clip(10 × (paired learning − paired frozen direction, pp), 0, 100). Paired = same (asset, signal_utc, horizon), scorable in both |
| success | plain mean of the three, unrounded; must be ≥ 70 |
| hard gates | learning > frozen (paired, strict); second half ≥ first half (session dates split by count); direction ≥ 60; frozen > null (holdout); learning > null |
| coverage | ≥ 90% of sessions per asset with a signal or no_signal row |
| periods | holdout (fit 2026-06-01 03:00 UTC) AND forward 27 Oct – 2 Nov (fit at its first session, 26 Oct in kit; CO-0039 unresolved). Each must pass independently; forward scores h ≤ 5 only |
| labels | update() at each pre-open, before predict, with outcomes decided on daily bars by rows available before that pre-open; delivered once; partial mfe if decided early |
| arithmetic | success ≥ 70 ⇒ D + Dep + I ≥ 210. With Dep = 100: D = 60 needs a 5.0 pp paired gain, D = 65 needs 4.5 pp. Zero gain caps success at (D + 100)/3 < 70 |
| interface | build/fit/predict/update via the template's run.py; deterministic; Python 3.13 CPU. Runs take ~10–40 s |

## Candidate
Per-horizon (3, 5) logistic P(up first | decided) on [intercept, overseas gap, 5-session move,
20-session move], all in threshold units and clipped. Laplace fit with prior N(0, 1) on decided
pre-open labels before train_end. Online-Newton updates from delivered outcomes. The overseas gap
anchor is capped at the last session close, which fixes the gap-v1 08:29 snapshot defect.

1. Why it might predict direction: a stale entry price at the pre-open (exp 03 mechanism).
2. Why updates might help: the fit has few labels (~100–250), so the pass-through weight is
   shrunk by the prior; drift in the base rate.
3. Why it might fail: base-rate drift was already rejected (exp 02); a few dozen labels a week is noise.

## Required tests: 10/10 pass (`tests/test_ologit.py`)
- identical initial state digests;
- updates change the state digest;
- every delivered label's signal precedes the update cutoff, and the outcome was decided on available data;
- the update log records the latest label signal and window end;
- a no-op update reproduces the frozen file exactly;
- identical keys in both files;
- zero read-log violations;
- byte-identical reruns;
- nanosecond units;
- training labels precede train_end.

## Results (official run.py + shipped scorer; every attempt in attempts.jsonl)
| Run | Learning | Frozen | Paired gain pp (n) | Null | Improvement | Success | Halves 1st/2nd | Flips: L right & F wrong / F right & L wrong | Pre-declared verdict |
|---|---|---|---|---|---|---|---|---|---|
| C1 λ=1.00 F1 | 62.50 | 63.51 | −1.01 (296) | 45.6 | 0 | 54.2 | 66.0/59.2 | 9 / 12 | FAIL |
| C1 F2 | 64.80 | 62.50 | +2.30 (392) | 49.7 | 23.0 | 62.6 | 68.8/61.0 | 31 / 22 | |
| C2 λ=0.95 F1 | 59.46 | 63.51 | −4.05 (296) | 45.6 | 0 | 53.2 | 64.6/54.6 | 14 / 26 | FAIL |
| C2 F2 | 60.71 | 62.50 | −1.79 (392) | 49.7 | 0 | 53.6 | 66.1/55.5 | 36 / 43 | |
| R1 gap-only F1 | 64.19 | 63.51 | +0.68 (296) | 45.6 | 6.8 | 57.0 | 65.3/63.2 | 2 / 0 | INCONCLUSIVE |
| R1 F2 | 65.05 | 62.50 | +2.55 (392) | 49.7 | 25.5 | 63.5 | 65.6/64.5 | 12 / 2 | |
| **R1 HOLDOUT (EXPLORATORY)** | 56.39 [51.9, 60.8] | 56.14 | +0.24 (830) | 43.5 | 2.4 [0, 7.3] | **52.9** | 64.4/48.3 | 4 / 2 | not confirmation |

Development folds reuse the Feb–May period of exp 03 and overlap (F2 ⊃ F1). Depth was 100 and
coverage 1.00 for every asset in every run, and all read logs had 0 violations.

R1 holdout hard gates:

| Gate | Result |
|---|---|
| learning > frozen | ✔ (+0.24 pp, 2 net keys) |
| second half ≥ first | ✘ |
| direction ≥ 60 | ✘ |
| frozen > null | ✔ |
| learning > null | ✔ |
| success ≥ 70 | ✘ |
| coverage | ✔ |

Per asset (holdout, learning/frozen): copper 43.8/43.8, crude 62.5/61.5, gold 54.9/54.9, silver 64.4/64.4.

## Conclusions
- **Confirmed Fact:** no configuration meets the direction or learning-gain gates. The best
  paired gain was +2.55 pp on a development fold and +0.24 pp on the holdout; about 4.5–5 pp is needed in both periods.
- **Confirmed Fact:** full-weight updates (C1, C2) learn base-rate drift through the intercept, and
  the resulting flips are net wrong (worse with forgetting).
- **Strongly Supported:** gap-only updates make few flips and those are mostly right (14 vs 2 on
  development; 4 vs 2 on the holdout). This looks like the shrunk pass-through weight being relaxed
  as data arrive. It is real but small, and shrinks as the initial fit has more data (holdout fit
  has about 240 labels; the forward fit may have more).
- **Strongly Supported:** the ologit frozen copy (56.1%) is weaker than gap-v1 (58.9%) on the
  holdout. The intercept and momentum terms cost accuracy relative to the gap sign alone.
- **Uncertain:** the cause of the holdout second-half decline (both copies and the null fall).
- **Needs Verification:** forward fit data scope (CO-0039).

Per the pre-declared stopping rule, development stops here: one revision used, R1 inconclusive.
Not prize-eligible.

## Reproduce (from commodity-open-kit/template)
```
../.venv/bin/python experiments/06_online_logit/tests/test_ologit.py --pack ../../v2.1
for c in C1 C2 R1; do for f in F1 F2; do ../.venv/bin/python experiments/06_online_logit/evaluate.py --pack ../../v2.1 --config $c --fold $f; done; done
../.venv/bin/python experiments/06_online_logit/evaluate.py --pack ../../v2.1 --config R1 --fold HOLDOUT
```
Outputs: `runs/<config>_<fold>/` (signals, read logs, update_log.jsonl, report_2_holdout.json,
summary.json), plus `attempts.jsonl`.
