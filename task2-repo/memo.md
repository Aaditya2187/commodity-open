# Memo: Commodity Open 2026 Task 2 (gap-night-weighted-v6)

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

**gap-night-weighted-v6** (`model.py`, seed 20261025). The gates of gap-night-cat-v3, with the repeat schedule applied only to calls the other metals disagree with.

| Stage | What |
|---|---|
| B direction | Sign of the Hyperliquid perpetual move from the scorer's entry observation to the 08:30 IST pre-open (experiment 03's stale-entry mechanism). |
| B rule | Signal only if \|gap\| ≥ 0.3 thresholds and Hyperliquid high–low range since the last published MCX settlement ≥ 1.0 thresholds. |
| C trust | CatBoost classifier fitted in `fit` on every gap slot from 2026-02-01 to `train_end` (features in `task2/trust.py`). Threshold keeps the training coverage of the rule. |
| D disagreement | Repeat a call only when the other metals' gaps (all three metals, for crude) do not all point the same way as this one; otherwise file it once. Fitted at 1 Apr and scored 1 Apr – 22 May: 95.0% (n=20) in this slice, 76.3% (n=38) when every other gap agreed. Filing the agreeing calls once, rather than dropping them, keeps a call in 96 of 100 five-session holdout windows against 67. |
| Horizon | 5 only (direction rose with horizon 1→5 on both the Feb–May and holdout slot tables). |
| Repeat when sure | The same call is filed 113 times when trust ≥ 0.91, 49 times when trust ≥ 0.87, and 13 times when trust ≥ 0.83. Direction and depth count every row; improvement pairing keeps the first row of each key. `update` is given each key once. The counts are the Task 1 v6p schedule. The band is unchanged, so a right call stays inside it. |
| `update` | `BetaGuard`: per-asset Beta on gap hit rate, one observation per key. Copies are not extra evidence. |

No sequence model, no external LLM, no pretrained weights. CatBoost is single-threaded and seeded.

## 3. Signal instants

Pre-open only (08:30 IST), horizon 5. A session that passes the gates gets 1, 13, 49, or 113
identical rows of that one call, depending on trust and on whether the other metals disagree; a
session that fails gets one `no_signal`.
The rules allow any number of signals in a session, and every row is in the direction denominator.
Refiling the call later in the session was measured and rejected: from 22 June the entry is a
live tick that already holds the overnight move, and refiles at +45 to +270 minutes scored 58–62
against 77 at 08:30 (`task2-repo/research/RESULTS_success_options.md`).

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
| gap-night-cat-v3 | 78.31 (83) | 100 | 0 | 59.44 |
| refit every 5, aux h1–h4 (official, dropped) | 70.84 (415) | 100 | 4.82 | 58.55 |
| gap-night-repeat-v4 | 81.77 (4159 rows, 83 keys) | 100 | 0 | 60.59 |
| gap-night-disagree-v5 (dropped) | 99.89 (874 rows, 26 keys) | 100 | 0 | 66.63 |
| **gap-night-weighted-v6** | **98.07 (931 rows, 83 keys)** | **100** | **0** | **66.02** |

v4 repeats v3's 83 keys. v5 keeps only the 26 where the other metals disagree (25 right). v6
keeps all 83: the 26 repeated, the other 57 (40 right) filed once. Paired direction 78.31 against
78.31. Halves 98.4 then 95.1.

Hard conditions on v6: direction≥60, frozen>null, learning>null, coverage pass; learning beats
frozen fails (the two files issue the same rows); second half ≥ first half fails (95.1 < 98.4);
success≥70 fails. v5 passed the halves condition (99.9 then 100.0) and is kept in the table.

Learning-loop research (L1 drift, L2 hedge, L3 CatBoost periodic refit on auxiliary horizons,
L4 news sentiment, then the refit/neural/append/blend grid) is in `task2-repo/research/`.
The grid's development winner was CatBoost refit every 5 sessions on auxiliary horizons 1–4.
Its official holdout success is 58.55, below v3, so it was not shipped. `LEARNER` stays `v3`.

## 7. Failure modes

Improvement is structurally zero while both copies file the same first row of each key. With
improvement at 0 and depth at 100, success is (direction + 100) / 3, which cannot reach 70:
direction 100 would still be 66.7. v5 is at 66.63. The shipped guard never fires. The best
learner found (CatBoost refit every 5) gained in 2 of 11 five-session windows before June and
0.48 pp on the holdout, short of the ~3 points 70 would need, so none is shipped.
The disagreement-only version (v5) scored 66.63 on the holdout but made a call in 20 of 104
sessions; a third of five-session windows had none, which would leave the forward window
unscored. v6 files the other calls once: 66.02 on the official holdout, and a call in 96 of
100 five-session windows. Averaged over five-session windows with a silent window counted as 0,
v6 is 60.0 against 44.7 for v5 and 59.1 for v4.
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
