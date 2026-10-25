# Holdout (1 June – 23 October 2026) exposure log

Every look at holdout-period outcomes made during model research, for the memo.

| When (IST) | What was seen | Used to choose anything? |
|---|---|---|
| before 24 Oct | Official holdout scores of the template baseline, the incremental logistic candidate (with and without cutoff). See team notes. | The logistic candidate was rejected partly on these. |
| 24 Oct, exp 01 | Holdout per-asset base rates of up-first/down-first/neither at h=1,2,3,5. Pooled h5: up 44.6, down 48.9, neither 6.5. Per asset: crude up-first 60.6 vs down 36.5; gold down 60.2 vs up 35.0; silver down 56.7 vs up 40.4; copper 42.3/42.3. Matched null at h5: 45.8. Realized-MFE distribution in threshold units (max 7.85). Outcome delivery delays with `loop.matured_outcomes`. Daily-vs-tick label disagreement (1.7%). | Delivery-delay figures were used to reason about forward learnability. The MFE range supports the band-width argument; that argument also follows from the definition (realized ⇒ mfe ≥ threshold). No direction, asset tilt or parameter has been chosen from these rates. Any per-asset direction prior is now off-limits. |
| 25 Oct, exp 03 | Nothing from the holdout. All reads at 2026-06-01 03:00 UTC. | — |
| 25 Oct, exp 04 tests | Smoke window 1–8 July: entry prices, contracts and keys only, no outcomes. | No. |
| 25 Oct, exp 05 | Holdout breakdown of gap-v1 by asset, half, gap sign, |gap| tercile, entry source (exploratory), and the Task 1 catch bound. | No. |
| 25 Oct ~17:00 IST, exp 06 | One exploratory holdout run of ologit R1, after development stopped (R1 inconclusive). | No. |
| 25 Oct 03:22 UTC, exp 04 | ONE pre-registered official holdout run of frozen gap-v1 and its score (see 04_gap_model/RESULT.md). | Only the pre-registered confirm/fallback decision. |
| 25 Oct 19:10 IST, gap-lgbm-v1 smoke | Official run.py + scorer on 1-12 Jun only (10 sessions): direction 76.3 on 38 signals, null 42.1, improvement 0. Pipeline check of the automated harness. | No. Model was fully specified (MIN_GAP 0.3, MOVE_QUANTILE 0.25, guard constants) before this run. |
| 25 Oct 19:15 IST, gap-lgbm-v1 confirmatory | ONE full holdout run (learning + frozen) of the pre-specified gap-lgbm-v1, official run.py + scorer, logged here before it ran. | Only to report. No parameter, horizon, asset or threshold may be chosen from it. |
| 25 Oct evening, gap-lgbm-v1 confirmatory result | That run, scored once. Direction 69.09 (n=275, 60 episodes), depth 100, improvement 0, success 56.36. Halves 73.46 then 62.83. Null at the same instants 40.36. Learning and frozen files byte-identical. Read logs clean. | No. Reported only. |
| 25 Oct late evening, gap-night-v2 selection | The team lifted the one-look rule. Full holdout slot table (every asset, session, h3/h5, both directions graded) used with 20 Feb – 22 May to test online flip learners (none gained) and abstention rules; the night-range >= 1.0 threshold was chosen on both periods. Official run: direction 74.27, success 58.09, halves 74.2 / 74.3. | **Yes**: NIGHT_RANGE_MIN and MOVE_FILTER. Holdout scores of gap-night-v2 are in-sample. |
| 26 Oct early morning, gap-night-cat-v3 | Slot tables with horizons 1–5 and new path/cross-asset features on both periods; trust models trained on 20 Feb – 22 May and tested on the holdout (and the reverse). Official run: direction 78.31 on 83 h5 signals, success 59.44, halves 75.5 / 83.3. | **Yes**: horizon 5 only and the choice of CatBoost among five models. The CatBoost model itself is fitted only on data before `train_end`. |

Rules adopted after the gap-lgbm-v1 exposure: no per-asset direction prior, no horizon or asset
selection using holdout outcomes, and at most one confirmatory holdout run of a fully pre-specified
model. The team lifted the last of these on 25 Oct late evening (gap-night-v2 row); the first two
still hold for gap-night-v2, whose rule is the same for every asset and horizon.
| 26 Oct ~01:20 IST, L4 news | Univariate news-dir rates on holdout + L3/L4 learner replay on HO only (news features zero before June). | **No** for shipping. News is anti-predictive vs gap; L4 gain identical to L3 (+0.96) or worse. |
| 26 Oct ~01:30 IST, aux-mix | L3 cat every∈{3,5,10} × aux universes; select on F2&F1 all gates, confirm HO. apply_core diagnostic. | **Yes (selection):** best aux remains coreh:1,2,3,4 every=5. HO success 60.6 still fails ≥70. Ship-or-stop → keep v3. |
