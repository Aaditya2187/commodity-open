# Experiment 04: pre-registration of the single confirmatory holdout run

Frozen before the holdout run. `PREREGISTRATION.sha256` holds the hashes of this file, SPEC.md,
submission/model.py and submission/run.py, written before the run.

## Exactly what runs, and only once
With K=/Users/_navyagoyal_/Desktop/CommodityOpenLatest, E=$K/commodity-open-kit/template/experiments/04_gap_model:
```
cd $E/submission
python run.py --pack $K/v2.1 --challenge 2 --period holdout --out $E/holdout_run
python run.py --pack $K/v2.1 --challenge 2 --period holdout --frozen --out $E/holdout_run
python $K/commodity-open-kit/tools/score_holdout.py --pack $K/v2.1 --predictions $E/holdout_run --challenge 2
```
(Default `--horizons`. The model issues 3 and 5 itself.) The run is not repeated with any change to
the model, band, horizons, assets or dates. A rerun is allowed only to reproduce byte-identical
files, or to fix a crash that produced no output. Any such rerun is logged.

## Predictions declared now
- learning and frozen files identical → `learning_beats_frozen` FALSE, improvement 0.
- success therefore ≈ (direction + depth) / 3 < 70 → success condition FALSE.
- depth ≈ 100% (band contains every mfe ≥ threshold up to 13 thresholds).

## Confirmation criterion (official scorer output, all scored h ≤ 20 rows, i.e. both horizons together)
- **CONFIRMED** if direction ≥ 58% AND direction − the scorer's prevailing-direction null ≥ 8 pp.
  Then gap-v1 becomes the model of an honest research submission.
- **NOT CONFIRMED** otherwise. Then we fall back to the template baseline for the submission and
  report gap-v1 as a failed confirmation in the memo.

Every hard condition is reported exactly as `score_holdout.py` prints it, whatever the outcome.
No per-asset, per-horizon or sub-period result is used to change anything.
