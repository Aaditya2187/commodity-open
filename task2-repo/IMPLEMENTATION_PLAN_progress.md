# Task 2 implementation plan: what we followed and how far we got

Status as of Sun 25 Oct 2026, 19:00 IST. The submission window closes Mon 26 Oct, 17:00 IST.
The full plan is in the claude.ai doc *Task 2 Implementation Plan*; this file tracks progress against it.

## The plan

Build a tree-first learning system inside the kit's `fit` / `predict` / `update` contract.

- **Labels:** barrier-race labels (the asset threshold up before the threshold down within h sessions), graded the way the scorer grades.
- **Features:** point-in-time features from every pack table, read only through `PointInTime`.
- **Core model:** LightGBM, with a short-window GRU and a kNN analog added only if they improve the blend.
- **Learning:** the learning copy differs from the frozen copy only through `update`.
- **Benchmark:** gap-v1, the overnight overseas-gap rule (58.9% direction on the holdout).
- **Validation:** purged walk-forward on 2021 – May 2026, scored like the official scorer, plus one confirmatory holdout run per pre-registered model.

| Phase | What | Gate to pass | Status |
|---|---|---|---|
| 0 | Data foundation: labels, point-in-time features, leakage rules | Labels match the scorer; no look-ahead | ✅ Done |
| 1 | Baselines and validation harness | Harness reproduces the null and gap-rule numbers | ✅ Done |
| 2 | LightGBM core | Beats the gap rule in the Feb–May 2026 block | ❌ Failed, design pivoted (below) |
| 2b | Gap-centred hybrid (the pivot) | Beats the gap rule pre-holdout | ✅ Passed (80.2% vs 74.6% at matched coverage) |
| 3 | Online learning loop in `update` | Paired gain > 0 in session replay | ❌ Not met: +0.00 pp best |
| — | Official holdout run (learning + frozen), automated | Run, validate, score, read-log check | 🔄 In progress: building pyarrow from source |
| 4 | Add-ons: CatBoost, GRU, kNN, depth and news features | Each must improve the blend | ⏸ Not started |
| 5 | Freeze and package: memo, `reproduce.py`, `submit.py` | Byte-identical reproduction | ⏸ Not started |

## Phase by phase

### Phase 0: data foundation ✅
- `task2/labels.py`: barrier-race labels for h ∈ {1, 2, 3, 5, 10}, 2021 to 23 Oct 2026. 29,465 rows from `labels/chain_daily`, using the scorer's tie rule.
  - Check: the holdout h5 split (48 down, 46 up, 6 neither) matches experiment 01 within 1 point.
- `task2/features.py`: 57 point-in-time features (MCX daily, cross-asset, Hyperliquid gap/candles/funding, USD/INR, COT).
  - Check: the gap rule recomputed from these features gives 64.3 at h3 and 68.9 at h5 before the holdout, matching experiment 03.
- Finding: the overseas features exist only from Feb 2026 (about 280 rows per horizon before the holdout). No long overseas history exists in the pack for gold, silver or copper.

### Phase 1: harness ✅
- `research/validate.py`: 7 purged expanding-window folds (2023 H1 to Jan–May 2026), purge h + 5 business days. Reports direction, the null, the gap rule on the same rows, halves and coverage.

### Phase 2: LightGBM as the direction model ❌
LightGBM 4.6.0 was built from Microsoft's official source tag because PyPI is blocked here.

| Jan–May 2026 block | h3 | h5 |
|---|---|---|
| LightGBM, 57 features | 42.5 | 45.0 |
| Variants (binary, per-asset, gap-era only) | 40–57 | 44–61 |
| Prevailing null | 45.5 | 49.8 |
| Gap rule | 61–64 | 68–69 |

LightGBM sat at or below the null in 2023–2025 as well. The daily features carry no direction signal at h3 or h5; the only signal is the overnight gap.

### Phase 2b: the pivot to a gap-centred hybrid ✅
- **Stage A (LightGBM):** P(either barrier is hit within h), trained on 2021–2026. AUC 0.59–0.72 in 6 of 7 blocks.
- **Stage B:** direction = sign of the gap.
- **Stage C:** signal only if abs(gap) ≥ 0.3 thresholds and stage A's P(move) ≥ its 25th percentile on training; otherwise `no_signal`.

| Pre-holdout, 5 rolling chunks | Direction | Coverage |
|---|---|---|
| Every gap row | 66.8 | 100% |
| abs(gap) ≥ 0.3 | 74.6 | 66% |
| **Hybrid** | **80.2** (h3 85.5, h5 77.3) | **50%** |

It was better in all 5 chunks. Caveat: it was 1 of 8 variants tried on the same 560 rows. A LightGBM "trust" model was tried for stage C and did worse (70.9–74.2).

Packaged as `model.py` (`gap-lgbm-v1`) on the kit's interface and smoke-tested at about 0.5 s per session.

### Phase 3: learning in `update` ❌
| Policy (session replay, 296 signals) | Paired gain |
|---|---|
| Per-asset Beta guard (shipped) | +0.00 pp (never fires) |
| Faster guard | −1.69 pp |
| Online logistic, three settings | −1.0 to −5.1 pp |

This agrees with experiments 02, 03 and 06. Qualifying needs about +4 to +5 pp on both periods, so this is the blocking gate.

### Official holdout run 🔄
- `autoeval.py`: runs the template `run.py` (learning + frozen), `validate_submission.py`, `score_holdout.py`, the read-log check, and appends to `PROGRESS.md`.
- Blocker: the kit needs pyarrow, which can't be installed here. pyarrow 25.0.1 is being built from Apache's GitHub tag; its dependencies are built and Arrow C++ is compiling.
- Before the run, it must be logged in `HOLDOUT_EXPOSURE.md` as a confirmatory look, with no tuning on its result.

## What's left, in order
1. Finish the pyarrow build, then the automated full holdout run with scores and gates.
2. Decide on the learning gate, the only route to success ≥ 70. Nothing tested so far gives a gain.
3. Clean and package the repository: pin `lightgbm==4.6.0`, remove the stale files, write the memo, run `reproduce.py`, then `submit.py`.
4. Phase 4 add-ons (depth and news features into stage A or C, kNN, GRU), after the deadline or if time allows.
