# gap-night-v2 (25 Oct 2026, late evening IST)

The holdout was used to choose this model, together with the 20 Feb – 22 May 2026 period. The
team lifted the one-look rule for this round; the holdout scores below are therefore not
out-of-sample. The forward window (27 Oct – 2 Nov) is the only unseen test.

## What changed from gap-lgbm-v1
- New abstention: signal only when Hyperliquid's high-low range since the last MCX settlement was
  published (`hl_night_range`) is at least 1.0 asset thresholds. Unchanged: |gap| >= 0.3 thresholds.
- The LightGBM P(move) gate is off (`MOVE_FILTER = False`). Before June it removed one signal; on
  the holdout it removed every copper signal from August.
- Direction, band, horizons (3 and 5) and the Beta guard in `update` are unchanged.

## Official runner and scorer, holdout 1 June – 23 Oct 2026 (`predictions_v2/`)
| Score | gap-lgbm-v1 | gap-night-v2 |
|---|---|---|
| direction | 69.09 (n=275) | **74.27** (n=206) [68.1, 80.5] |
| depth | 100 | 100 |
| improvement | 0 | 0 |
| success | 56.36 | **58.09** |
| null at the same instants | 40.36 | 39.3 |
| halves | 73.5 / 62.8 (fail) | 74.2 / 74.3 (**pass**) |

Hard conditions: learning beats frozen **no** (files byte-identical); second half >= first **yes**;
direction >= 60 yes; frozen beats null yes; learning beats null yes. Coverage 1.000 on every asset.
Read logs: 0 violations, 0 unvintaged reads (1381 and 1147 entries).

## Evidence for the rule (research/eval_rules.py on research/slots_pre.parquet and slots_holdout.parquet)
| Night range >= | 20 Feb – 22 May: n / direction | Holdout: n / direction (halves) |
|---|---|---|
| (none, v1) | 343 / 72.6 | 275 / 69.1 (73.5 / 62.8) |
| 1.0 | 254 / 79.1 | 206 / 74.3 (74.2 / 74.3) |
| 1.1 | 232 / 79.7 | 164 / 75.6 |
| 1.2 | 210 / 80.5 | 144 / 76.4 |
| 1.3 | 192 / 81.8 | 116 / 77.6 |

Rejected: aligning with the 5-session trend (holdout 77.6 but 20 Feb – 22 May down to 65.9–67.6).

## Why improvement stays at 0 (research/sim_flip.py)
Improvement only moves when the learning copy changes direction on a key both copies issue. Over
all 832 holdout gap slots the opposite barrier wins at most ~30% of the time in any feature
tercile, while the gap direction wins 65–70%. Online learners refitted every session on delivered
outcomes (logistic on 6–60 features, on the new June/July sources, per asset) flipped at a loss:
best +4 keys of 832 (+0.5 pp), richer feature sets −5 to −13 pp. The Hyperliquid tick, Trading
Economics, COMEX delayed and SHFE/INE gaps are each wrong 70–100% of the time when they disagree
with the candle gap. With improvement at 0, success is capped at (direction + 100) / 3.
