# Packaging status (26 Oct 2026, ~01:40 IST)

Ship-or-stop kept **gap-night-cat-v3**. Official holdout (reconfirmed here):

| direction | depth | improvement | success | hard: learn>frozen |
|---|---|---|---|---|
| 78.3 (n=83) | 100 | 0 | 59.4 | FAIL (files identical) |

`tools/reproduce.py --challenge 2` → **REPRODUCED** (byte-identical learning and frozen).

## Done here
- Root submission surface: `run.py`, `model.py`, `task2/`, `requirements.txt` (pins catboost + lightgbm), `swing_dataset/`, `memo.md`, `LICENSE`, `predictions/`
- Research notes: `task2-repo/research/RESULTS_L4.md`, `RESULTS_aux_mix_ship.md`
- Commits on Cursor `origin/main`: `456b7e5` (latest)

## You still need (before 17:00 IST)

1. **Push to GitHub** (no GitHub credentials in this VM):
   ```bash
   git push github main
   ```
2. **Submit bundle** with your registration ticket:
   ```bash
   python commodity-open-kit/tools/submit.py --ticket CO-00XX --tasks 2
   ```
   Upload the printed bundle + commit hash through the organizers' link.
3. Optional: email `CO-0039_DRAFT_NOT_SENT.md` if you still want forward-run clarification.
