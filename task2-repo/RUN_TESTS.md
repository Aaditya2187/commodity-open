# Run the Task 2 learning-gain pipeline

From a clone of this repository:

```bash
git lfs install && git lfs pull
# if mcx/mcx_daily.parquet is still a ~130-byte pointer:
#   tar --zstd -xf commodity-open-pack-v2.1.tar.zst

python3.13 -m venv .venv && source .venv/bin/activate
pip install -r task2-repo/requirements-task2.txt --extra-index-url https://download.pytorch.org/whl/cpu
pip install --no-deps -e commodity-open-kit/swing_dataset

cd task2-repo
export PYTHONPATH="$PWD:$PWD/research"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python tests/run_pipeline.py
```

`--quick` runs one setting per learner on 15 sessions of fold F1, then a 1–12 June official smoke instead of the full holdout. `--from-stage N` resumes at stage N (0 checks, 1 tables, 2 sweep, 3 selector, 4 forward, 5 official runs, 6 report).

The sweep writes `research/results/sweep.csv` and skips a design whose folds are already there. One fold at a time: do not run the grid and an official holdout together (CatBoost `bad allocation` / OpenBLAS).

`LEARNER` in `model.py` stays `v3` unless an official holdout run beats gap-night-cat-v3 on the rules in the pipeline report.
