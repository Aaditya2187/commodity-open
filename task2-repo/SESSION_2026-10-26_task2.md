# Commodity Open 2026, Task 2: session log, 26 Oct 2026 (morning IST)

Submission closes **Mon 26 Oct 2026, 17:00 IST**. Research stopped after ship-or-stop; packaging in progress.

## Setup (this cloud VM)
- Cloned `https://github.com/Aaditya2187/commodity-open.git`; `git lfs pull` restored pack (~4 MB `mcx_daily.parquet`).
- Python 3.13.17 via `uv`; `.venv` with template requirements + `lightgbm==4.6.0` + `catboost==1.2.10` + editable `swing_dataset`.
- Smoke: `run.py ... --from 2026-06-01 --to 2026-06-12` → `result: VALID`.

## Research completed
1. **L4 news** — FAILED. See `task2-repo/research/RESULTS_L4.md`.
2. **Aux-mix** — selected `coreh:1,2,3,4` / cat every=5 on F2&F1; HO success 60.6. See `RESULTS_aux_mix_ship.md`.
3. **Ship-or-stop** — keep **gap-night-cat-v3** (direction 78.3, success 59.4, improvement 0).

## Afternoon (this Windows machine)
4. **Repeat when sure (v4)** — trust ≥ 0.91/0.87/0.83 filed 113/49/13 times. Holdout 81.77 / 60.59.
5. **Disagreement gate (v5)** — 99.89 / 66.63, but silent in 33% of five-session windows.
6. **Weighted (v6, shipped)** — repeat only when the other metals disagree, file the rest once. Holdout direction 98.07, depth 100, improvement 0, success 66.02. Halves 98.4 / 95.1 (fails).
7. Later-instant refile and further learners measured and rejected. See `task2-repo/research/RESULTS_success_options.md`.

## Packaging
- `requirements.txt`, `swing_dataset/`, `memo.md`, `LICENSE`, `predictions/` (from v3) at repo root and under `task2-repo/`.
- Next: regenerate holdout learning+frozen, `reproduce.py`, then `submit.py` with the team ticket.
