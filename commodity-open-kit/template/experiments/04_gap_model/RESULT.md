# Experiment 04: single confirmatory holdout run of gap-v1 (2026-10-25)

Spec, pre-registration, model, run.py and tests hashed at 2026-10-25T03:21:57Z, before the run
(`PREREGISTRATION.sha256`). Run once with the pre-registered commands; no reruns. Outputs are in
`holdout_run/`: the signal files, read logs, run.json, `report_2_holdout.json`, `holdout_scores.json`
and the run/score logs.

## Official scorer (`tools/score_holdout.py --challenge 2`), holdout 2026-06-01 to 2026-10-23
| Score | Value | 90% CI |
|---|---|---|
| direction | 58.92 (n=830, 84 episodes) | 54.43–63.37 |
| depth | 100.0 (n=489) | 100–100 |
| improvement | 0.0 | 0–0 |
| success rate | 52.97 (minimum 70) | 51.48–54.46 |
| prevailing-direction null, same instants | 43.49 | |
| baselines' success rate | prevailing 42.3, rv_band 39.5, range_break_vol 39.8 | |

Signals 832 (416 at h3, 416 at h5), invalid 0, unmatured 2, no_signal 0. Coverage 1.000 on all assets.

| Hard condition | Result | Values |
|---|---|---|
| success ≥ 70 | **FAIL** | 52.97 |
| learning beats frozen | **FAIL** (predicted: update is a no-op) | 58.92 vs 58.92, n=830 paired, files byte-identical |
| second half ≥ first half | **FAIL** | 51.45 vs 66.35 (52 + 52 sessions) |
| direction ≥ 60 | **FAIL** | 58.92 |
| frozen beats null | PASS | 58.92 vs 43.49 |
| learning beats null | PASS | 58.92 vs 43.49 |
| coverage ≥ 90% per asset | PASS | 1.000 |
| read log (`repro.check_read_log`, re-derived on the pack) | PASS | 0 violations in both logs, 0 unvintaged reads |

**Holdout minimum: NOT met.** Not prize-eligible.

## Pre-registered confirmation criterion
Direction ≥ 58% and ≥ 8 pp above the null: 58.92% and +15.4 pp. **CONFIRMED** (narrowly on the
58% clause). Per the pre-registration, gap-v1 becomes the model of an honest research submission.

## Things to state in the memo
- Direction fell from 66.3% in the first half to 51.4% in the second. The cause is not established.
  The scorer's entry price switches from settlement to captured ticks from 22 June, within the
  first half. Other possibilities are regime change, basis and data noise. Nothing was tuned on it.
- Pre-holdout (exp 03): 64.7% at h3 and 69.3% at h5. The holdout's pooled 58.9% is lower.
- Depth 100% follows from the maximum allowed band, not from forecasting skill in magnitude.
