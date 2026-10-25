# Memo: Commodity Open 2026 Task 2 (gap-night-cat-v3)

Repository: https://github.com/Aaditya2187/commodity-open; Challenges entered: 2.

## 1. Problem framing

Task 2 asks for a direction call on a barrier race: the asset threshold in the signalled
direction before the threshold against it, within a stated horizon (gold 1.5%, silver 2.0%,
copper 1.5%, crude 3.0%). We signal only when an overnight overseas gap is large enough and
trustworthy enough that the same-side barrier is likely to win within five sessions. `expected_pct`
and the `[p10, p90]` band are fixed multiples of the asset threshold (wide enough to contain every
realized move among directionally right signals, hence depth 100). `invalidation_pct` is set to the
threshold (recorded, not scored). Assets are pooled: one CatBoost trust model, shared gates, no
per-asset direction prior. When the gates fail we write an explicit `no_signal` with a one-line reason.

## 2. Method

**gap-night-cat-v3** (`model.py`, seed 20261025).

| Stage | What |
|---|---|
| B direction | Sign of the Hyperliquid perpetual move from the scorer's entry observation to the 08:30 IST pre-open (experiment 03's stale-entry mechanism). |
| B rule | Signal only if \|gap\| ≥ 0.3 thresholds and Hyperliquid high–low range since the last published MCX settlement ≥ 1.0 thresholds. |
| C trust | CatBoost classifier fitted in `fit` on every gap slot from 2026-02-01 to `train_end` (features in `task2/trust.py`). Threshold keeps the training coverage of the rule. |
| Horizon | 5 only (direction rose with horizon 1→5 on both the Feb–May and holdout slot tables). |
| `update` | `BetaGuard`: per-asset Beta on gap hit rate; never fired on the holdout, so learning and frozen files are byte-identical and improvement is 0. |

No sequence model, no external LLM, no pretrained weights. CatBoost is single-threaded and seeded.

## 3. Signal instants

Pre-open only (08:30 IST), once per asset per session, horizon 5. Coverage is filled with
`no_signal` rows when the rule or the trust filter abstains.

## 4. Data and clocks

Pack reads go only through `PointInTime`: `mcx/mcx_daily`, `labels/chain_daily`,
`macro/hl_candles_1h`, `macro/hl_candles_1d` (and related feature tables listed in
`task2/features.py`). No unvintaged opt-in. No external data. Research slot tables used for
model selection were built with the same client; holdout-based selection is logged in
`commodity-open-kit/template/experiments/HOLDOUT_EXPOSURE.md`.

## 5. Training cutoff

Holdout `fit`: 2026-06-01 03:00 UTC. Forward `fit`: the kit's forward period start (26 Oct 2026
pre-open in kit 2.6.3; CO-0039 draft asks organizers to confirm). Nothing is fitted outside `run.py`.

## 6. Ablation (official scorer, holdout)

| Model | direction (n) | depth | improvement | success |
|---|---|---|---|---|
| gap-lgbm-v1 | 69.09 (275) | 100 | 0 | 56.36 |
| gap-night-v2 | 74.27 (206) | 100 | 0 | 58.09 |
| **gap-night-cat-v3** | **78.31 (83)** | **100** | **0** | **59.44** |
| refit every 5, aux h1–h4 (official, dropped) | 70.84 (415) | 100 | 4.82 | 58.55 |
| prevailing-direction null at v3 instants | 42.2 | — | — | — |

Hard conditions on v3: direction≥60, halves, frozen>null, learning>null, coverage all pass;
learning beats frozen fails (files identical); success≥70 fails.

Learning-loop research (L1 drift, L2 hedge, L3 CatBoost periodic refit on auxiliary horizons,
L4 news sentiment, then the refit/neural/append/blend grid) is in `task2-repo/research/`.
The grid's development winner was CatBoost refit every 5 sessions on auxiliary horizons 1–4.
Its official holdout success is 58.55, below v3, so it was not shipped. `LEARNER` stays `v3`.

## 7. Failure modes

Improvement is structurally near zero: online flips of the gap lose in every feature slice we
tried; the shipped guard never fires. Success is therefore capped near (direction+100)/3 ≈ 59–60.
Copper and short horizons are weaker under the rule alone (hence h5 only). The forward window is
about five scored sessions after a 26 Oct refit, so a paired learning gain there is small-sample
even if `update` receives early deliveries.

## 8. Compute

CPU only (no GPU). `fit` on the holdout cutoff is on the order of one minute; a full holdout
learning run is a few minutes on a 4-core / 16 GB machine. CatBoost `thread_count=1`,
`OMP_NUM_THREADS=1` recommended for byte-identical reruns.

## 9. Reproduction notes

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # installs ./swing_dataset last
python run.py --pack /path/to/v2.1 --challenge 2 --period holdout
python run.py --pack /path/to/v2.1 --challenge 2 --period holdout --frozen
```

Expect byte-identical `predictions/c2_holdout.parquet` and `c2_holdout_frozen.parquet` (they
match each other under the shipped BetaGuard). Official scores are in
`predictions/holdout_scores.json`.
