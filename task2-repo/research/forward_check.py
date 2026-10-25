#!/usr/bin/env python3
"""Replay the chosen design on every 5-session window from 2 Mar 2026 through mid-October.

The forward window refits at its first session and scores about five sessions, and only h1/h2
outcomes mature inside it, so the auxiliary universe is ``coreh:1,2``. Windows that cross 1 June
are skipped. Writes ``research/results/forward.csv`` and ``forward.md``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import learn_sim as S

OUT_CSV = Path("research/results/forward.csv")
OUT_MD = Path("research/results/forward.md")
AUX = "coreh:1,2"


def _choice() -> tuple[str, str, dict]:
    path = Path("research/results/selection.json")
    if path.exists():
        payload = json.loads(path.read_text())
        block = payload.get("ship") or payload.get("best")
        if block:
            return str(block["learner"]), dict(block.get("params") or {}), str(block.get("design"))
    return "refit", {"every": 5, "news": False}, "refit_e5_fallback"


def _windows() -> list[pd.Timestamp]:
    days = sorted(set(S.KEYS["pre"]["session_date"]).union(S.KEYS["holdout"]["session_date"]))
    days = [d for d in days if pd.Timestamp("2026-03-02") <= d <= pd.Timestamp("2026-10-16")]
    return days


def main() -> int:
    learner, params, design = _choice()
    days = _windows()
    rows = []
    june = pd.Timestamp("2026-06-01")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if OUT_CSV.exists():
        OUT_CSV.unlink()
    for i in range(0, max(0, len(days) - 4), 5):
        window = days[i : i + 5]
        if window[0] < june <= window[-1]:
            continue
        # a hole between the pre table and the holdout is not one window
        if (window[-1] - window[0]).days > 14:
            continue
        r = S.replay("W", S.Online(learner, **params), AUX, start=window[0], max_sessions=5)
        r["gates"] = S.gates(r)
        r.update({"design": design, "learner": learner, "params": json.dumps(params, sort_keys=True),
                  "aux": AUX, "window_start": str(pd.Timestamp(window[0]).date()),
                  "window_end": str(pd.Timestamp(window[-1]).date())})
        rows.append(r)
        pd.DataFrame([{
            "design": design, "learner": learner, "window_start": r["window_start"], "window_end": r["window_end"],
            "n": r["n"], "D": r["D"], "F": r["F"], "gain": r["gain"], "success": r["success"], "gates": r["gates"],
        }]).to_csv(OUT_CSV, mode="a", header=not OUT_CSV.exists() or OUT_CSV.stat().st_size == 0, index=False)
        print(f"{r['window_start']} n={r['n']:3d} D={r['D']:5.1f} gain={r['gain']:+5.2f} S={r['success']:5.1f} [{r['gates']}]", flush=True)
    n = len(rows)
    if n == 0:
        text = "# Forward check\n\nNo windows.\n"
    else:
        gain = pd.Series([r["gain"] for r in rows])
        direc = pd.Series([r["D"] for r in rows])
        succ = pd.Series([r["success"] for r in rows])
        text = "\n".join([
            "# Forward check",
            "",
            f"Design `{design}` learner `{learner}` params `{json.dumps(params, sort_keys=True)}` aux `{AUX}`.",
            f"Windows: {n} (5 sessions, stride 5, 2 Mar 2026 through 16 Oct 2026, none crossing 1 June).",
            "",
            f"- share with gain > 0: {100 * (gain > 0).mean():.1f}%",
            f"- mean gain: {gain.mean():+.2f} pp",
            f"- share with direction >= 60 and success >= 70: {100 * ((direc >= 60) & (succ >= 70)).mean():.1f}%",
            "",
        ])
    OUT_MD.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
