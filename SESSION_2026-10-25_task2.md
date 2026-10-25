# Commodity Open 2026, Task 2: session log, 25 Oct 2026

Submission window closes **Mon 26 Oct 2026, 17:00 IST**.

## 1. What was done, in order

1. **Research review.** Read the two research documents (11 competition solutions). Takeaways: tree models carry most strong entries; short input windows beat long ones; simple baselines place well; nothing covers news or macro vintages.
2. **Implementation plan doc.** Wrote *Task 2 Implementation Plan* (claude.ai doc), first from the research alone.
3. **Rules and pack read.** Read `RULES.md` 2.6, the kit's `scoring2` code, the template, and experiments 01–06 in `template/experiments/`. Key facts:
   - The target is a **barrier race**: the asset threshold up before the threshold down, within h sessions (gold 1.5%, silver 2.0%, copper 1.5%, crude 3.0%). A "neither" outcome counts as a miss.
   - Scores are direction, depth and improvement (10 × the paired gain of learning over frozen). Success is their plain mean and must be at least 70.
   - There are five hard gates, including learning > frozen, direction ≥ 60, second half ≥ first half, and frozen > null.
   - With depth at 100, qualifying needs **direction + improvement ≥ 110**, i.e. roughly a 4–5 pp paired learning gain.
4. **Plan rewritten twice.** First as "submit gap-v1 honestly". The user rejected that: gap-v1 is a benchmark only. Then rewritten as a tree-first implementation adapted to the rules.
5. **Phase 0–1 built** (`task2-repo/task2/`):
   - `labels.py`: barrier-race labels for 2021 to 23 Oct 2026, from `labels/chain_daily`, using the scorer's tie rule (the adverse barrier ranks first inside a bar). 29,465 rows. The holdout split matches exp 01 within 1 point.
   - `features.py`: 57 point-in-time features from MCX daily, cross-asset, Hyperliquid, USD/INR and COT. The overseas features exist only from Feb 2026 (about 12% of rows).
   - `research/validate.py`: purged expanding walk-forward folds, 7 test blocks from 2023 to May 2026.
6. **LightGBM installed** (non-negotiable per the user). PyPI, conda and GitLab are blocked from both machines, so I built **LightGBM 4.6.0 from Microsoft's v4.6.0 tag**, with its pinned Eigen commit 3147391d from the PX4 GitHub mirror. It is deterministic: two fits give identical output.
7. **Phase 2 result: LightGBM as the direction model fails.** See section 2.
8. **Direction chosen: gap-centred hybrid.** Stage A is a LightGBM move model, stage B is the gap direction, stage C is abstention. Packaged as `model.py`.
9. **Learning layer tested.** Session replay before the holdout: no learner gives a positive gain.
10. **Automation started.** Built `autoeval.py`, which runs `run.py` (learning + frozen), validates, scores with the official scorer, checks read logs and writes `PROGRESS.md`. The kit needs pyarrow, so I'm building **pyarrow 25.0.1 from Apache's GitHub tag** (with zstd, snappy, thrift, boost headers, rapidjson and xsimd built from source). This build is in progress.

## 2. Results (all before the holdout, no holdout tuning)

### LightGBM as a direction model (Jan–May 2026 test block)
| Setup | h3 | h5 |
|---|---|---|
| 3-class, 57 features | 42.5 | 45.0 |
| Binary up/down | 40.6 | 46.9 |
| Per-asset models | 40.3 | 44.1 |
| Gap-era rows only, 3 seeds | 53–57 | 56–61 |
| Prevailing-direction null | 45.5 | 49.8 |
| Gap rule alone | 61–64 | 68–69 |

In the 2023–2025 blocks LightGBM is at or below the null throughout. When LightGBM overrules the gap's sign, it is right 18–31% of the time.

### Stage A: LightGBM "will either barrier be hit" model
AUC is 0.59–0.72 in 6 of 7 test blocks, and it beats a constant forecast's Brier score in every block. The exception is 2026 h5 (AUC 0.48), where 90% of slots move anyway.

### Stage C: when to signal (560 gap-era rows, 20 Feb – 29 May 2026, 5 rolling test chunks)
| Rule | Direction | Share of slots signalled |
|---|---|---|
| Every gap row | 66.8 | 100% |
| LightGBM trust model | 70.9–74.2 | 61–66% |
| Logistic on abs(gap) | 73.6 | 62% |
| abs(gap) ≥ 0.3 thresholds | 74.6 | 66% |
| **abs(gap) ≥ 0.3 and stage-A P(move) ≥ 25th percentile of training** | **80.2** | **50%** |

By horizon: h3 goes from 72.3 to 85.5 (35% of slots); h5 from 76.9 to 77.3 (65%). The filter is better in all 5 chunks. Caveat: it was 1 of 8 variants tried on the same 560 rows.

### Learning layer (session replay, 296 filtered signals)
| Policy | Paired gain |
|---|---|
| Per-asset Beta guard (shipped) | +0.00 pp (never fires) |
| Faster guard | −1.69 pp |
| Online logistic, three settings | −1.0 to −5.1 pp |

**The learning > frozen gate is still unsolved.**

## 3. The model as it stands: `gap-lgbm-v1`
- **fit:** builds labels and features from pack rows available before `train_end` and trains one stage-A LightGBM per horizon (h3, h5).
- **predict (08:30 IST pre-open):**
  - Direction is the sign of the Hyperliquid move since the scorer's entry observation (gap-v1's measurement, unchanged).
  - It signals only if abs(gap) ≥ 0.3 thresholds and P(move) ≥ the training floor; otherwise it writes a `no_signal` row with the reason.
- **update:** a per-asset guard that reverses an asset's direction only if its hit rate collapses (a safety switch).
- **Reads:** only through `PointInTime`. LightGBM runs deterministic and single-threaded.
- **Smoke test** on a stand-in client: about 0.5 s per session; signals and reasons look sane.

## 4. Files (in `~/Desktop/CommodityOpenLatest/task2-repo/`)
| File | What |
|---|---|
| `model.py` | gap-lgbm-v1 submission model |
| `task2/labels.py`, `features.py`, `learner.py` | model package |
| `research/validate.py`, `pqread.py`, `RESULTS_lightgbm_phase2.md` | research only (pqread reads files directly, so it must not ship) |
| `RUN_ON_MAC.md` | manual run commands (superseded by automation) |
| `model_gap_v2_candidate.py`, `task2/pqread.py`, `task2/validate.py` | stale copies: move or delete |

Plan doc: *Task 2 Implementation Plan* (claude.ai artifact).

## 5. Status and next steps
- [x] pyarrow 25.0.1 is installed (Python 3.13 venv). The pack's parquet files were Git LFS pointers; the real `v2.1` archive was extracted before the run.
- [x] Full holdout run, learning + frozen; validate; official scorer; read-log check. Success 56.36, direction 69.09, depth 100, improvement 0. Minimum not met. Scores are in `task2-repo/predictions/holdout_scores.json`.
- [x] Logged in `HOLDOUT_EXPOSURE.md` before the run. The result was recorded after scoring. No tuning on it.
- [ ] Learning-gain problem: still no mechanism with evidence. The shipped guard never fired, so the two files are byte-identical.
- [ ] Repository packaging: pin `lightgbm==4.6.0`, run `reproduce.py`, write the memo, `submit.py`.
- [ ] Optional: send CO-0039 (the forward-run arguments question) to the organizers.

## 6. Environment notes
- The cloud workspace reaches only GitHub (git). PyPI, conda and GitLab are blocked. Allowing **pypi.org** and **files.pythonhosted.org** in claude.ai Settings → Capabilities would remove the source builds.
- The Mac's Terminal is click-only for Claude; the kit's Mac venv has pyarrow but no LightGBM.
