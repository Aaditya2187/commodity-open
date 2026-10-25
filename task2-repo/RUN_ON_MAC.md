# Running gap-lgbm on your Mac

The kit's point-in-time client needs pyarrow, which only your Mac environment has, so the official
run happens there. From a terminal:

```bash
cd ~/Desktop/CommodityOpenLatest
source commodity-open-kit/.venv/bin/activate
pip install lightgbm==4.6.0            # needs normal internet; on macOS also: brew install libomp

cd task2-repo
cp ../commodity-open-kit/template/run.py .       # byte-identical copy, do not edit
export SWING_PACK_ROOT=~/Desktop/CommodityOpenLatest/v2.1

# quick check on one fortnight first (a minute or two)
python run.py --pack $SWING_PACK_ROOT --challenge 2 --period holdout --from 2026-06-01 --to 2026-06-12

# full holdout, learning and frozen copies
python run.py --pack $SWING_PACK_ROOT --challenge 2 --period holdout
python run.py --pack $SWING_PACK_ROOT --challenge 2 --period holdout --frozen
python ../commodity-open-kit/tools/validate_submission.py predictions/c2_holdout.parquet --pack $SWING_PACK_ROOT
python ../commodity-open-kit/tools/score_holdout.py --pack $SWING_PACK_ROOT --predictions predictions/ --challenge 2
```

Note: this full holdout run is a confirmatory look at the holdout. Log it in
`experiments/HOLDOUT_EXPOSURE.md` before running it, and do not tune MIN_GAP or MOVE_QUANTILE on it.

`research/` holds code that reads parquet files directly (pqread.py) and must not be imported by
model.py; reproduce.py would list it for review. Older copies of pqread.py and validate.py are
still in `task2/` from an earlier step; move them into `research/` or delete them.
