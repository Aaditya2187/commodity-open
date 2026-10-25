#!/usr/bin/env python3
"""Pre-holdout replay of gap-lgbm-knn-v1: official run.py (learning + --frozen), shipped scorer, flips.

    python research/knn_replay/replay.py --pack ../v2.1

Settings and the keep/drop rule are in PREDECLARED.md, written before this ran. Outputs go to
research/knn_replay/run/: both signal files, read logs, the scorer report and summary.json.
Flips are graded on prices available at 2026-06-01 03:00 UTC, so no holdout price is read.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from swing_dataset.kit import loop, repro
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import outcomes as O
from swing_dataset.scoring2 import signals as SIG

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KIT = REPO.parent / "commodity-open-kit"
TRAIN_END = "2026-02-20T03:00:00+00:00"
START, END = "2026-02-20", "2026-05-22"
GRADE_ASOF = datetime(2026, 6, 1, 3, tzinfo=UTC)
KEY = ["asset", "signal_utc", "horizon"]


def flips(pack: Path, out: Path) -> dict:
    prices, _ = loop.price_view(PointInTime(pack), GRADE_ASOF, quotes=True)
    frames = {}
    for kind, stem in (("learning", "c2_holdout"), ("frozen", "c2_holdout_frozen")):
        d = pd.read_parquet(out / f"{stem}.parquet")
        s = d[d["signal_utc"].notna()].reset_index(drop=True)
        g = O.grade_c2(SIG.normalize(s, 2).signals, prices)
        g = g[g["scorable"].fillna(False).astype(bool)]
        frames[kind] = g.set_index(KEY)[["direction", "realized"]]
    j = frames["learning"].join(frames["frozen"], lsuffix="_l", rsuffix="_f", how="inner")
    j["ok_l"], j["ok_f"] = j["realized_l"].astype(bool), j["realized_f"].astype(bool)
    diff = j[j["direction_l"] != j["direction_f"]]
    jr = j.reset_index()

    def block(g):
        return {"n": int(len(g)), "learning": round(100 * g.ok_l.mean(), 2), "frozen": round(100 * g.ok_f.mean(), 2),
                "differs": int((g.direction_l != g.direction_f).sum())}

    return {"paired": int(len(j)), "direction_differs": int(len(diff)),
            "learning_right_frozen_wrong": int((diff.ok_l & ~diff.ok_f).sum()),
            "frozen_right_learning_wrong": int((~diff.ok_l & diff.ok_f).sum()),
            "both_wrong_when_differ": int((~diff.ok_l & ~diff.ok_f).sum()),
            "learning_direction": round(100 * j.ok_l.mean(), 3), "frozen_direction": round(100 * j.ok_f.mean(), 3),
            "per_asset": {a: block(g) for a, g in jr.groupby("asset")},
            "per_horizon": {str(h): block(g) for h, g in jr.groupby("horizon")}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    a = ap.parse_args()
    pack = a.pack.resolve()
    out = HERE / "run"
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONWARNINGS": "ignore"}
    py = sys.executable
    base = [py, str(REPO / "run.py"), "--pack", str(pack), "--challenge", "2", "--period", "holdout", "--out", str(out),
            "--train-end", TRAIN_END, "--from", START, "--to", END]
    procs = []
    for frozen in (False, True):
        log = open(out / ("run_frozen.log" if frozen else "run_learning.log"), "w")
        procs.append((subprocess.Popen(base + (["--frozen"] if frozen else []), cwd=REPO, env=env,
                                       stdout=log, stderr=subprocess.STDOUT), log, frozen))
    for p, log, frozen in procs:
        rc = p.wait()
        log.close()
        if rc != 0:
            raise SystemExit(f"run.py failed ({'frozen' if frozen else 'learning'}); see {out}")
    with open(out / "score.log", "w") as log:
        rc = subprocess.call([py, str(KIT / "tools" / "score_holdout.py"), "--pack", str(pack), "--predictions", str(out),
                              "--challenge", "2", "--no-baselines", "--from", START, "--to", END],
                             cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    if rc != 0:
        raise SystemExit(f"scoring failed; see {out / 'score.log'}")
    rep = json.loads((out / "report_2_holdout.json").read_text())
    reads = {}
    for stem in ("c2_holdout", "c2_holdout_frozen"):
        man = json.loads((out / f"{stem}.run.json").read_text())
        decisions = pd.read_parquet(out / f"{stem}.parquet")
        te = pd.Timestamp(man["fit"]["train_end_utc"]).to_pydatetime()
        chk = repro.check_read_log(repro.load_read_log(out / f"{stem}.readlog.jsonl"), decisions, te, pack)
        reads[stem] = {"ok": chk["ok"], "entries": chk["entries"], "violations": len(chk["violations"])}
    s, paired = rep["scores"], rep["paired_direction"]
    gain = None if paired["learning"] is None else round(paired["learning"] - paired["frozen"], 3)
    keep = gain is not None and gain > 0 and paired["learning"] >= paired["frozen"]
    summary = {
        "window": rep["window"], "direction": s["direction"], "depth": s["depth"], "improvement": s["improvement"],
        "success_rate": s["success_rate"], "paired": paired, "paired_gain_pp": gain,
        "frozen_direction_all": rep["frozen"]["direction"],
        "null": rep["prevailing_direction_null"]["direction_at_entry_instants"],
        "halves": rep["halves"], "hard_conditions": rep["award_conditions"]["hard_conditions"],
        "flips": flips(pack, out), "read_logs": reads,
        "fit": json.loads((out / "c2_holdout.run.json").read_text())["fit"],
        "decision": "KEEP kNN" if keep else "REVERT to BetaGuard",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    f = summary["flips"]
    print(f"learning {paired['learning']} frozen {paired['frozen']} gain {gain} pp (n={paired['n']}) "
          f"null {summary['null']} success {s['success_rate']['value']} "
          f"halves {rep['halves']['first_half_direction']}/{rep['halves']['second_half_direction']} | "
          f"differ {f['direction_differs']} L+F- {f['learning_right_frozen_wrong']} F+L- {f['frozen_right_learning_wrong']} | "
          f"reads ok {all(r['ok'] for r in reads.values())} | {summary['decision']}")


if __name__ == "__main__":
    main()
