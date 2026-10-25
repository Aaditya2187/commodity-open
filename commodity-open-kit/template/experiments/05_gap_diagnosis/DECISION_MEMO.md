# Decision memo: Task 2 qualification feasibility (2026-10-25, 09:10 IST)

Deadline: Mon 26 Oct 2026, 17:00 IST (README.md:25, RULES.md:123,140). That leaves about 32 hours.
Scorer: kit 2.6.3 `swing_dataset/scoring2`. Paths below are relative to `swing_dataset/swing_dataset/`.

## 1. Score formula (Confirmed Fact)
- direction = mean of `realized` over scorable rows (score.py:512, 551–555). Realized means the
  threshold was hit before the opposite threshold (outcomes.py:167). "Neither" and invalid rows
  count as not realized; scorable = decided or window complete (outcomes.py:174).
- depth = mean of `in_band` over realized rows (score.py:556–560; outcomes.py:171). Bounded by 100.
- improvement = clip(10 × (paired learning direction − paired frozen direction) in pp, 0, 100)
  (score.py:573–581, 688–691, `IMPROVEMENT_MULTIPLIER` __init__.py:77). Paired means identical
  (asset, signal_utc, horizon) keys, scorable in both files, first row per key (score.py:485–498).
- success = unrounded plain mean of the three (score.py:593–598). Minimum 70 (__init__.py:43).
- Hard conditions (score.py:628–635):
  - learning beats frozen: paired, strictly greater;
  - second half ≥ first half: learning direction, window session dates split by count (score.py:195–201, 606–612);
  - direction ≥ 60 (__init__.py:47);
  - frozen beats null at frozen instants (holdout only, score.py:~776);
  - learning beats null.
- Coverage: per asset, at least 90% of sessions have a valid signal or no_signal row; every asset
  must meet it (score.py:135–191, __init__.py:49).
- Reconciliation with gap-v1: 489/830 = 58.9157; 489/489 = 100; paired 58.9157 − 58.9157 → 0;
  (58.9157 + 100 + 0)/3 = 52.9719. This matches report_2_holdout.json exactly.

## 2. Qualification arithmetic (Confirmed Fact)
- success ≥ 70 ⇔ D + Dep + I ≥ 210. With D ≤ 100 and Dep ≤ 100, I ≥ 10, so a paired gain of at least 1.0 pp is needed even at D = 100.
- **Any model whose learning copy equals its frozen copy is capped at (D + 100)/3 < 70 unless D > 110, which is impossible.**
- With Dep = 100: D = 60 needs a gain of ≥ 5.0 pp; D = 65 needs ≥ 4.5 pp; D = 70 needs ≥ 4.0 pp.
- Moving gap-v1 from 58.9 to 60 gives (60 + 100)/3 = 53.3. That is not enough.
- The hard gate needs any gain > 0; success needs a gain of about 4–5 pp. Both must hold in both periods.
- Improvement counts only paired keys. Abstaining, or issuing extra keys, cannot create gain. Only
  direction changes on keys shared with frozen can.

## 3. Timing and update contract
- Confirmed Fact:
  - Holdout fit at 2026-06-01 03:00 UTC (loop.py:116; RULES.md:104: a Task 2 model "learns only through update").
  - `update` runs at each pre-open, before `predict`, never when frozen (loop.py:481–492).
  - It delivers rows decided on daily bars (`price_view` without quotes, loop.py:261; settled
    loop.py:266), once, and drops them from pending (loop.py:485–486).
  - `no_price` rows are withheld (loop.py:487).
  - Fields: signal columns + `p0, price_source, contract_id, window_end_utc, window_complete, bars,
    ambiguous, mfe_pct, mae_pct, realized, in_band, scorable, unmatured, no_price` (outcomes.py:55).
  - Early-decided rows carry partial `mfe_pct`.
- Confirmed Fact: forward fit is at the 26 Oct pre-open in the kit (loop.py:117). The scored sessions run 27 Oct – 2 Nov.
- Needs Verification (CO-0039): which data a forward fit may use, and the 26 vs 27 Oct start.
- Confirmed Fact, a timing defect in gap-v1:
  - On 41 of 416 holdout keys (June–July), the scorer's entry price is a tick *captured* at
    08:29 IST, so gap-v1's anchor became 08:29 and its gap covered only one hour.
  - 160 tick anchors are 23:59 IST captures, about 29 minutes after the trade.
  - Zero read-log violations did not catch this, because it is a semantic error, not a look-ahead.
- Needs Verification: whether that 08:29 `ltp` is the previous night's last trade (stale).
  `exch_trade_time_utc` exists only from 14 July.

## 4. Diagnosis (diag_table.json, task1_catch_bound.json)
- Reused data: 2021 – May 2026 daily (exp 02 and earlier research); 20 Feb – 29 May 2026 gap rows
  (exp 03); the holdout (template, logistic, exp 01, exp 04). **No untouched development period exists for the gap rule.**
- Strongly Supported (development, reused): the gap beats the null by about 18–20 pp in both
  chronological blocks and for both gap signs.
- EXPLORATORY (holdout):
  - The second-half drop is broad: both gap signs, and the null drops too (h3 46.6 → 35.7; h5 49.5 → 42.0).
  - The gap's lead over the null persists in the second half (h3 +13.5 [6.9, 19.7]; h5 +11.6 [1.8, 21.5]).
  - The bottom dev-defined |gap| tercile is about 50% (no edge); the top tercile is 71–75%.
  - Truncated-interval rows are not worse (n = 41).
- Uncertain: whether the second half is a harder market or a weaker signal. This does **not** justify reversal.
- Strongly Supported: no outcome-driven adaptation has evidence.
  - Exp 02 drift learners: gain about 0 pp, worse than frozen in most windows.
  - Exp 03: accuracy after a wrong outcome minus after a correct one is +4 to +5 pp, with intervals that include 0.
- Strongly Supported: the forward window has about 40 paired keys (20 per horizon). One key = 2.5 pp, so a 5 pp gain is 2 keys, which is indistinguishable from noise.
- Option C (Task 1, allowed by RULES.md:128,155):
  - Confirmed Fact: pre-open-only signals can catch at most **77.4%** of the 230 holdout swings, even with oracle direction.
  - Task 1 success ≥ 70 with correctness and depth near 65 needs catch ≥ 80, above that bound.
  - Intraday instants would need tick features, which have no pre-holdout development data.

## 5. Recommendation
**No next forecasting experiment is justified for qualification.**
- A: no evidence of an adaptable relationship, and abstention cannot raise the paired gain.
- B: new information can raise D but cannot create a learning gain. The usable sources start in June or July (holdout only).
- C: blocked by the catch bound above.

Remaining options are not qualification paths:
1. Submit an honest non-qualifying research entry (gap-v1 as a benchmark, defects disclosed).
2. A fix-only gap-v2 (trade-time anchor) for research value, after verifying the stale `ltp`.
3. Do not submit Task 2.
