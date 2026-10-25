#!/usr/bin/env python3
"""Frozen-vs-learning harness: run.py (learning + --frozen) -> shipped scorer -> disagreement table.

    python experiments/06_online_logit/evaluate.py --pack ../../v2.1 --config C1 --fold F1
    python experiments/06_online_logit/evaluate.py --pack ../../v2.1 --config C2 --fold HOLDOUT

Writes runs/<config>_<fold>/ with the signal files, read logs, update log, scorer report and
summary.json, and appends a line to attempts.jsonl (every attempt, failures included).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from swing_dataset.kit import loop, repro
from swing_dataset.pack.pit import PointInTime
from swing_dataset.scoring2 import outcomes as O
from swing_dataset.scoring2 import signals as SIG

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[2]
CONFIGS = {"C1": {"OLOGIT_LAMBDA": "1.0"}, "C2": {"OLOGIT_LAMBDA": "0.95"},
           "R1": {"OLOGIT_LAMBDA": "1.0", "OLOGIT_UPDATE_MASK": "gap"}}
FOLDS = {
    "F1": {"train_end": "2026-04-01T03:00:00+00:00", "from": "2026-04-01", "to": "2026-05-22"},
    "F2": {"train_end": "2026-03-16T03:00:00+00:00", "from": "2026-03-16", "to": "2026-05-22"},
    "HOLDOUT": {"train_end": None, "from": None, "to": None},  # official holdout, EXPLORATORY
}
KEY = ["asset", "signal_utc", "horizon"]


def sh(cmd, env, log):
    t = time.perf_counter()
    with open(log, "w") as fh:
        rc = subprocess.call(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT)
    return rc, round(time.perf_counter() - t, 1)


def disagreements(pack: Path, out: Path, start, end) -> dict:
    pit = PointInTime(pack)
    prices, _ = loop.price_view(pit, datetime(2026, 10, 24, 6, tzinfo=UTC), quotes=True)
    frames = {}
    for kind, stem in (("learning", "c2_holdout"), ("frozen", "c2_holdout_frozen")):
        d = pd.read_parquet(out / f"{stem}.parquet")
        s = d[d["signal_utc"].notna()].reset_index(drop=True)
        if start is not None:
            s = s[(s["signal_utc"] >= pd.Timestamp(start, tz="UTC")) &
                  (s["signal_utc"] <= pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))].reset_index(drop=True)
        g = O.grade_c2(SIG.normalize(s, 2).signals, prices)
        g = g[g["scorable"].fillna(False).astype(bool)]
        frames[kind] = g.set_index(KEY)[["direction", "realized"]]
    j = frames["learning"].join(frames["frozen"], lsuffix="_l", rsuffix="_f", how="inner")
    j["ok_l"], j["ok_f"] = j["realized_l"].astype(bool), j["realized_f"].astype(bool)
    diff = j[j["direction_l"] != j["direction_f"]]
    res = {"paired": int(len(j)), "direction_differs": int(len(diff)),
           "learning_right_frozen_wrong": int((diff.ok_l & ~diff.ok_f).sum()),
           "frozen_right_learning_wrong": int((~diff.ok_l & diff.ok_f).sum()),
           "both_wrong_when_differ": int((~diff.ok_l & ~diff.ok_f).sum()),
           "learning_direction": round(100 * j.ok_l.mean(), 3), "frozen_direction": round(100 * j.ok_f.mean(), 3)}
    jr = j.reset_index()
    res["per_asset"] = {a: {"n": int(len(g)), "learning": round(100 * g.ok_l.mean(), 1), "frozen": round(100 * g.ok_f.mean(), 1),
                            "differs": int((g.direction_l != g.direction_f).sum())} for a, g in jr.groupby("asset")}
    res["per_horizon"] = {str(h): {"n": int(len(g)), "learning": round(100 * g.ok_l.mean(), 1), "frozen": round(100 * g.ok_f.mean(), 1),
                                   "differs": int((g.direction_l != g.direction_f).sum())} for h, g in jr.groupby("horizon")}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--config", required=True, choices=sorted(CONFIGS))
    ap.add_argument("--fold", required=True, choices=sorted(FOLDS))
    ap.add_argument("--submission", type=Path, default=HERE / "submission")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    pack = a.pack.resolve()
    fold = FOLDS[a.fold]
    out = HERE / "runs" / f"{a.config}_{a.fold}{a.tag}"
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **CONFIGS[a.config], "OLOGIT_UPDATE_LOG": str(out / "update_log.jsonl")}
    (out / "update_log.jsonl").unlink(missing_ok=True)
    narrow = []
    if fold["from"]:
        narrow = ["--from", fold["from"], "--to", fold["to"], "--train-end", fold["train_end"]]
    py = sys.executable
    timings = {}
    for frozen in (False, True):
        cmd = [py, str(a.submission / "run.py"), "--pack", str(pack), "--challenge", "2", "--period", "holdout",
               "--out", str(out), *narrow] + (["--frozen"] if frozen else [])
        rc, secs = sh(cmd, env, out / ("run_frozen.log" if frozen else "run_learning.log"))
        timings["frozen" if frozen else "learning"] = secs
        if rc != 0:
            raise SystemExit(f"run.py failed ({'frozen' if frozen else 'learning'}); see {out}")
    score_cmd = [py, str(KIT / "tools" / "score_holdout.py"), "--pack", str(pack), "--predictions", str(out),
                 "--challenge", "2", "--no-baselines"] + (["--from", fold["from"], "--to", fold["to"]] if fold["from"] else [])
    rc, secs = sh(score_cmd, env, out / "score.log")
    timings["score"] = secs
    rep = json.loads((out / "report_2_holdout.json").read_text())
    reads = {}
    for stem in ("c2_holdout", "c2_holdout_frozen"):
        man = json.loads((out / f"{stem}.run.json").read_text())
        decisions = pd.read_parquet(out / f"{stem}.parquet")
        te = pd.Timestamp(man["fit"]["train_end_utc"]).to_pydatetime()
        chk = repro.check_read_log(repro.load_read_log(out / f"{stem}.readlog.jsonl"), decisions, te, pack)
        reads[stem] = {"ok": chk["ok"], "entries": chk["entries"], "violations": len(chk["violations"])}
    ul = [json.loads(l) for l in (out / "update_log.jsonl").read_text().splitlines()] if (out / "update_log.jsonl").exists() else []
    s = rep["scores"]
    summary = {
        "config": a.config, "fold": a.fold, "label": "EXPLORATORY (inspected holdout)" if a.fold == "HOLDOUT" else "development (reused Feb–May period)",
        "window": rep["window"], "direction": s["direction"], "depth": s["depth"], "improvement": s["improvement"],
        "success_rate": s["success_rate"], "paired": rep["paired_direction"],
        "paired_gain_pp": None if rep["paired_direction"]["learning"] is None else round(rep["paired_direction"]["learning"] - rep["paired_direction"]["frozen"], 3),
        "frozen_direction_all": rep["frozen"]["direction"], "null": rep["prevailing_direction_null"]["direction_at_entry_instants"],
        "halves": rep["halves"], "hard_conditions": rep["hard_conditions"],
        "coverage": {k: v["share"] for k, v in rep["coverage"]["per_asset"].items()},
        "award_conditions": rep.get("award_conditions"),
        "disagreements": disagreements(pack, out, fold["from"], fold["to"]),
        "read_logs": reads, "updates": {"calls": len(ul), "labels_used": sum(u["used"] for u in ul),
                                        "labels_skipped": sum(u["skipped"] for u in ul)},
        "fit": json.loads((out / "c2_holdout.run.json").read_text())["fit"], "seconds": timings,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with open(HERE / "attempts.jsonl", "a") as fh:
        fh.write(json.dumps({"utc": datetime.now(UTC).isoformat(), "config": a.config, "fold": a.fold, "tag": a.tag,
                             "paired_gain_pp": summary["paired_gain_pp"], "direction": s["direction"]["value"],
                             "frozen": rep["frozen"]["direction"], "n_paired": rep["paired_direction"]["n"]}) + "\n")
    d = summary["disagreements"]
    print(f"{a.config} {a.fold}: learning {s['direction']['value']:.2f} frozen {rep['frozen']['direction']:.2f} "
          f"gain {summary['paired_gain_pp']} pp (n={rep['paired_direction']['n']}) null {summary['null']:.2f} "
          f"success {s['success_rate']['value']:.2f} halves {rep['halves']['first_half_direction']:.1f}/{rep['halves']['second_half_direction']:.1f} "
          f"| differ {d['direction_differs']} L+F- {d['learning_right_frozen_wrong']} F+L- {d['frozen_right_learning_wrong']} "
          f"| reads ok {all(r['ok'] for r in reads.values())} | {timings}")


if __name__ == "__main__":
    main()
