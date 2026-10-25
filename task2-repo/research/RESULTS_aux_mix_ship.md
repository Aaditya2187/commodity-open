# Aux-mix selection and ship-or-stop (26 Oct 2026, ~01:30 IST)

## Selection rule (pre-registered for this look)

Choose `(kind, every, aux)` on **F2 and F1 only**: all five hard-condition characters in
`learn_sim.gates` must be `Y` on both folds (`dir≥60`, frozen>null, learn>frozen, halves, success≥70).
Then **confirm** on HO without further selection. Learner fixed to L3 CatBoost Refit (best family
from `sweep_L3.txt`). Logged in `HOLDOUT_EXPOSURE.md`.

## Dev-passing configs

| Config | aux | F2 S / gates | F1 S / gates | HO D | HO gain | HO S | HO gates |
|---|---|---|---|---|---|---|---|
| cat every=5 | coreh:1,2,3,4 | 92.0 YYYYY | 82.8 YYYYY | 72.0 | +0.96 | 60.6 | YYYY. |
| cat every=10 | coreh:1,2,3,4 | 79.9 YYYYY | 77.7 YYYYY | 72.0 | +0.96 | 60.6 | YYYY. |
| cat every=10 | coreh:1,2,3 | 91.7 YYYYY | 76.6 YYYYY | 70.8 | +0.90 | 59.9 | YYYY. |

No other aux (`coreh:1,2`, `coreh:3,4`, `noncore:*`) cleared both F2 and F1.

## apply_core probe (not selected; diagnostic)

Flipping core keys as well as aux: HO gain rises only to **+1.20** (S=61.4). Still fails success≥70.

## Forward-window feasibility

Kit forward fit is 26 Oct pre-open; scored sessions are ~27 Oct–2 Nov (≤5 sessions, h≤5).
On HO analog with `coreh:1,2,3,4`, deliver delays are short (median 1 session on the daily-label
index), so `update` can fire inside a 5-session window. That does **not** create a path to
holdout success≥70: the best confirmed HO success remains 60.6. A forward paired gain, even if
real, cannot rescue a holdout that misses the minimum (RULES §4 / §4a).

CO-0039 draft (forward args / fit data / 26 vs 27 Oct) remains in
`commodity-open-kit/template/experiments/CO-0039_DRAFT_NOT_SENT.md` if useful to send.

## Ship-or-stop

**STOP research. Keep gap-night-cat-v3.** No design passes F2, F1 **and** HO with success≥70
while keeping a strong frozen copy. Official holdout of v3 stays: direction 78.3 / depth 100 /
improvement 0 / success 59.4. Package v3 for submission.
