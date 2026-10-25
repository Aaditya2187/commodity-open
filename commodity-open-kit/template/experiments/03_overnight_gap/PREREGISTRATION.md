# Experiment 03: pre-registration (frozen before any result was computed)

Written 2026-10-25, before `gap_test.py` was written or run. `gap_test.py` records this file's
sha256 in `results.json`. If the file is edited after the run, the hashes will not match.

## Hypothesis
At the 08:30 IST pre-open, the scorer's entry price `p0` is the last MCX observation available
(before 22 June 2026 that is always the previous session's settlement, published at that session's
evening close). Overseas trading between that observation and the pre-open shifts the price
relative to `p0`. So the sign of the overseas move over that interval predicts which threshold
barrier is hit first.

## Rule (no fitted parameters)
- `anchor_utc` = the `price_available_utc` that `PriceSeries.price_at` returns for the scorer's own
  designated contract, i.e. the instant of the entry-price observation.
- `ref0` = close of the last Hyperliquid 1h candle (`macro/hl_candles_1h`) with
  `close_utc <= anchor_utc`. `ref1` = close of the last candle with `close_utc < signal_utc`.
  Both are read through PointInTime at `signal_utc`, so `available_utc < signal_utc` is enforced.
- Mapping: gold→`xyz:GOLD`, silver→`xyz:SILVER`, copper→`xyz:COPPER`, crude→`xyz:CL`.
- `gap = ref1/ref0 - 1`. Direction = up if gap > 0, down if gap < 0. A zero or missing gap means
  no signal (counted and reported).
- Expected/band are fixed placeholders. Depth is not evaluated here.

## Keys
Every MCX session pre-open from the first one with an anchor candle (≈ 2026-02-20) for all four
assets. The asset must have a designated contract. Horizons 3 and 5 are evaluated separately.
A row is evaluated only if it is `scorable` under `grade_c2` with prices built from rows available
before **2026-06-01 03:00 UTC**. Every pack read happens at or before that instant.

## Comparator
The official `scoring2.score.prevailing_null` is applied to exactly the same evaluated rows and
graded with `grade_c2`.

## Screening criteria, applied to each horizon separately
- C1: pooled direction ≥ 58%.
- C2: pooled direction minus matched-null direction ≥ 8 percentage points.
- C3: for at least 3 of 4 assets, direction in the top |gap| tercile > direction in the bottom
  tercile (terciles within asset, over that horizon's evaluated keys). This is diagnostic only and
  not a deployable selection rule.

## How the criteria combine across horizons
- **PASS / integrate-candidate**: h=3 and h=5 both pass C1, C2 and C3.
- **Collect more evidence**: exactly one horizon passes all three.
- **Reject**: neither horizon passes all three.

Passing does not establish the competition's ≥60% direction gate or any learning requirement.

## Reported, but not part of the screen
- 90% episode-block bootstrap intervals: blocks of h sessions per asset (`bootstrap.episode_keys`),
  2000 resamples, seed 0. Covers direction, null, and the difference.
- Per asset, per calendar month, per ISO week, leave-one-asset-out, weekend vs weekday anchors,
  anchor staleness (minutes between `anchor_utc` and the `ref0` candle close), basis notes.

## Learning feasibility, pre-declared
- Use the rule's own h=3 and h=5 signals with `loop.matured_outcomes` (daily-bar view, as the loop
  does) at each actual pre-open. Count, in every 5-session window, the predictions that have at
  least one earlier matured outcome (same asset) at decision time.
- Adaptable-relationship test: compare per-asset accuracy of the rule conditional on the most
  recent matured outcome of the same asset being correct vs incorrect. A learning mechanism is
  proposed only if the difference is ≥ 10 pp and its 90% block-bootstrap interval excludes 0.
  Otherwise none is proposed.

## Forbidden after seeing results
Choosing an asset, horizon, sign inversion, date window, gap cutoff or any parameter, and relaxing
any criterion above.
