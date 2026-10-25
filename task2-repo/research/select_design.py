#!/usr/bin/env python3
"""Choose a learning design from research/results/sweep.csv.

A design qualifies only when both F2 and F1 have gain > 0, direction >= 60 and frozen > null.
Qualifiers are ranked by the lower of the two development success rates. The holdout is reported
and is not used to choose. Only ``coreh:*`` universes, and only learners the model can run
(refit, neural, append, blend), can ship. Missing folds are skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SWEEP = Path("research/results/sweep.csv")
OUT_JSON = Path("research/results/selection.json")
OUT_MD = Path("research/results/SELECTION.md")
SHIP_LEARNERS = {"refit", "neural", "append", "blend"}


def _num(row, key, default=0.0) -> float:
    try:
        value = float(row[key])
    except (TypeError, ValueError, KeyError):
        return default
    if value != value:  # NaN
        return default
    return value


def _fold_blob(row) -> dict:
    return {
        "n": int(_num(row, "n")),
        "D": _num(row, "D"),
        "F": _num(row, "F"),
        "gain": _num(row, "gain"),
        "success": _num(row, "success"),
        "null": _num(row, "null"),
        "h1": _num(row, "h1"),
        "h2": _num(row, "h2"),
        "gates": "" if "gates" not in row or pd.isna(row["gates"]) else str(row["gates"]),
    }


def _passes(blob: dict) -> bool:
    return blob["gain"] > 0 and blob["D"] >= 60 and blob["F"] > blob["null"]


def _pack(design: str, rows: pd.DataFrame) -> dict:
    one = rows.iloc[0]
    params = one["params"]
    try:
        params = json.loads(params) if isinstance(params, str) else dict(params)
    except json.JSONDecodeError:
        params = {"raw": str(params)}
    folds = {}
    for _, row in rows.iterrows():
        folds[str(row["fold"])] = _fold_blob(row)
    return {
        "design": design,
        "learner": str(one["learner"]),
        "params": params,
        "aux": str(one["aux"]),
        "folds": folds,
    }


def main() -> int:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if not SWEEP.exists():
        payload = {"best": None, "ship": None, "qualified": 0, "note": f"missing {SWEEP}"}
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
        OUT_MD.write_text(f"# Selection\n\nNo sweep file at `{SWEEP}`.\n")
        print(payload["note"])
        return 0
    df = pd.read_csv(SWEEP)
    if df.empty or "design" not in df.columns:
        payload = {"best": None, "ship": None, "qualified": 0, "note": "sweep is empty"}
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
        OUT_MD.write_text("# Selection\n\nSweep is empty.\n")
        print(payload["note"])
        return 0
    df = df.drop_duplicates(["design", "aux", "fold"], keep="last")
    ranked = []
    for (design, aux), rows in df.groupby(["design", "aux"], sort=False):
        have = {str(f): rows[rows["fold"].astype(str) == f].iloc[-1] for f in rows["fold"].astype(str).unique()}
        if "F2" not in have or "F1" not in have:
            continue
        f2, f1 = _fold_blob(have["F2"]), _fold_blob(have["F1"])
        if not (_passes(f2) and _passes(f1)):
            continue
        packed = _pack(str(design), rows)
        packed["dev_min_success"] = min(f2["success"], f1["success"])
        packed["dev_mean_success"] = (f2["success"] + f1["success"]) / 2
        ranked.append(packed)
    ranked.sort(key=lambda p: (-p["dev_min_success"], -p["dev_mean_success"], p["design"], p["aux"]))
    best = ranked[0] if ranked else None
    shipable = [p for p in ranked if str(p["aux"]).startswith("coreh:") and p["learner"] in SHIP_LEARNERS]
    ship = shipable[0] if shipable else None
    payload = {"best": best, "ship": ship, "qualified": len(ranked), "shipable": len(shipable)}
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    lines = ["# Selection", "", "Holdout folds are reported and were not used to rank.", ""]
    lines.append(f"Qualified designs: {len(ranked)}. Shipable (`coreh:*`): {len(shipable)}.")
    lines.append("")
    if best is None:
        lines.append("No design passed F2 and F1 (gain > 0, direction >= 60, frozen > null).")
    else:
        lines.append(f"Best: `{best['design']}` learner `{best['learner']}` aux `{best['aux']}` "
                     f"(min dev success {best['dev_min_success']:.2f}).")
    if ship is None:
        lines.append("Ship: none.")
    else:
        lines.append(f"Ship: `{ship['design']}` learner `{ship['learner']}` aux `{ship['aux']}` "
                     f"params `{json.dumps(ship['params'], sort_keys=True)}`.")
    lines += ["", "| design | aux | learner | dev min S | F2 D/gain/S | F1 D/gain/S | HO D/gain/S |",
              "|---|---|---|---|---|---|---|"]
    for p in ranked[:12]:
        def cell(fold):
            b = p["folds"].get(fold)
            if not b:
                return "—"
            return f"{b['D']:.1f} / {b['gain']:+.2f} / {b['success']:.1f}"
        lines.append(f"| {p['design']} | {p['aux']} | {p['learner']} | {p['dev_min_success']:.1f} | {cell('F2')} | {cell('F1')} | {cell('HO')} |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(OUT_MD.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
