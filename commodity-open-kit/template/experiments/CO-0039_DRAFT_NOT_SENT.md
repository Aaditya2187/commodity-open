# DRAFT, NOT SENT: ticket CO-0039, clarification of forward-window run arguments (Task 2)

**Subject:** CO-0039: exact forward-window arguments and forward `fit` cutoff for Task 2

Hello organizers,

We are finalizing our Task 2 submission (kit 2.6.3, pack v2.1) and would like to confirm three
details of the forward run so that our repository behaves as intended. We will not change our
training-cutoff policy until we hear back.

1. **Exact arguments.** Which `--from`, `--to` and `--train-end` values (if any) will
   `tools/forward_run.py` pass to `run.py --challenge 2 --period forward`, for both the learning
   and the `--frozen` runs? In particular, will the final scored file come from a run with
   `--to 2026-11-02` on a pack built after that session?

2. **Forward fit data.** RULES §5 says that on the forward window `fit` happens "at its first
   session". May `fit(pack, train_end)` in the forward run use every pack row available before
   that forward `train_end` (that is, including June–October 2026 data), for both the learning
   copy and the frozen copy? Or must the forward fit stay capped at the holdout cutoff of
   2026-06-01 03:00 UTC?

3. **26 vs 27 October.** In kit 2.6.3, `swing_dataset.kit.loop.PERIODS["forward"]` starts on
   2026-10-26 (fit at its 08:30 IST pre-open). RULES and `forward_run.py` describe the scored
   sessions as Tue 27 Oct to Mon 2 Nov. How should teams treat 26 October?
   - Will the forward run start on 26 or 27 October?
   - If it starts on 26 October, are signals issued on 26 October excluded from scoring?
   - Can outcomes of those 26 October signals reach `update()` before the scored sessions begin?
   - Which `--test-start` will the scorer use?

Thank you,
[team name]
