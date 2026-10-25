#!/usr/bin/env python3
"""Run the learning-gain pipeline from task2-repo/.

    python tests/run_pipeline.py
    python tests/run_pipeline.py --quick
    python tests/run_pipeline.py --from-stage 3

Stages:
0 imports and the data pack, 1 slot tables if missing, 2 sweep, 3 selector, 4 forward check,
5 official run.py (v3, and the ship design when it has no news features), 6 the report.
Logs land in research/results/logs/. The learning and frozen copies of one fold start together.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
PACK = REPO / "v2.1"
PY = sys.executable
LOGS = ROOT / "research" / "results" / "logs"
RESULTS = ROOT / "research" / "results"


def env(extra: dict | None = None) -> dict:
    e = os.environ.copy()
    e["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "research"), e.get("PYTHONPATH", "")])
    e["OMP_NUM_THREADS"] = "1"
    e["OPENBLAS_NUM_THREADS"] = "1"
    e["MKL_NUM_THREADS"] = "1"
    e.pop("TASK2_LEARNER", None)
    e.pop("TASK2_LEARNER_PARAMS", None)
    e.pop("TASK2_AUX", None)
    if extra:
        e.update(extra)
    return e


def run(cmd: list[str], log_name: str, extra_env: dict | None = None, cwd: Path = ROOT) -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    path = LOGS / log_name
    print(f"== {log_name}: {' '.join(cmd)}", flush=True)
    with path.open("w") as handle:
        proc = subprocess.run(cmd, cwd=cwd, env=env(extra_env), stdout=handle, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        tail = path.read_text(errors="replace")[-2000:]
        print(tail, flush=True)
        raise SystemExit(f"{log_name} exited {proc.returncode}")
    return proc.returncode


def run_pair(out: Path, log_stem: str, extra: list[str], extra_env: dict | None = None) -> None:
    """Start the learning copy and the frozen copy together."""
    out.mkdir(parents=True, exist_ok=True)
    base = [PY, "run.py", "--pack", str(PACK), "--challenge", "2", "--period", "holdout", "--out", str(out)]
    LOGS.mkdir(parents=True, exist_ok=True)
    procs = []
    handles = []
    for frozen, name in ((False, "learn"), (True, "frozen")):
        cmd = base + extra + (["--frozen"] if frozen else [])
        handle = (LOGS / f"{log_stem}_{name}.log").open("w")
        handles.append(handle)
        print(f"== {log_stem} {name}", flush=True)
        procs.append(subprocess.Popen(cmd, cwd=ROOT, env=env(extra_env), stdout=handle, stderr=subprocess.STDOUT))
    codes = [p.wait() for p in procs]
    for handle in handles:
        handle.close()
    if any(codes):
        raise SystemExit(f"{log_stem} failed: {codes}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage0() -> None:
    if sys.version_info[:2] != (3, 13):
        raise SystemExit(f"need Python 3.13, have {sys.version}")
    import catboost  # noqa: F401
    import lightgbm  # noqa: F401
    import pandas  # noqa: F401
    import pyarrow  # noqa: F401
    from swing_dataset.pack.pit import PointInTime  # noqa: F401
    daily = PACK / "mcx" / "mcx_daily.parquet"
    if not daily.exists() or daily.stat().st_size < 100_000:
        raise SystemExit(f"{daily} is missing or still an LFS pointer ({daily.stat().st_size if daily.exists() else 0} bytes)")
    print("stage 0 ok", sys.version.split()[0], "pack", daily.stat().st_size, flush=True)


def stage1() -> None:
    need = {
        "research/deliveries.py": ROOT / "research" / "labels_daily.parquet",
        "research/news_feats.py": ROOT / "research" / "news_holdout.parquet",
    }
    slots = [
        ("research/slots2_pre.parquet", ["--train-end", "2026-02-20T03:00:00+00:00", "--from", "2026-02-20", "--to", "2026-05-22",
                                         "--grade-asof", "2026-06-01T03:00:00+00:00", "--out", "research/slots2_pre.parquet"]),
        ("research/slots2_holdout.parquet", ["--from", "2026-06-01", "--to", "2026-10-23",
                                             "--grade-asof", "2026-10-24T06:00:00+00:00", "--out", "research/slots2_holdout.parquet"]),
    ]
    if not (ROOT / "research" / "labels_daily.parquet").exists():
        run([PY, "research/deliveries.py", "--pack", str(PACK)], "01_labels.log")
    if not (ROOT / "research" / "news_holdout.parquet").exists():
        run([PY, "research/news_feats.py", "--pack", str(PACK)], "01_news.log")
    for name, args in slots:
        if not (ROOT / name).exists():
            run([PY, "research/slots.py", "--pack", str(PACK), *args], "01_" + Path(name).stem + ".log")
    print("stage 1 ok", flush=True)


def _has_news(params: dict) -> bool:
    if params.get("news"):
        return True
    feats = params.get("feats") or []
    return any(str(f).startswith("news_") for f in feats)


def _aux_horizons(aux: str) -> str:
    # coreh:1,2,3,4 -> 1,2,3,4
    return aux.split(":", 1)[1] if ":" in aux else aux


def stage5(quick: bool) -> dict:
    """Official runs. Returns a dict the report stage prints."""
    summary: dict = {"v3": {}, "ship": None}
    holdout_extra = ["--from", "2026-06-01", "--to", "2026-06-12"] if quick else []
    apr_extra = ["--train-end", "2026-04-01T03:00:00+00:00", "--from", "2026-04-01", "--to", "2026-05-22"]
    v3_out = RESULTS / "official" / "v3"
    run_pair(v3_out / "holdout", "05_v3_holdout", holdout_extra)
    if not quick:
        run_pair(v3_out / "pre_apr", "05_v3_apr", apr_extra)
    for tag, folder, score_extra in (("holdout", v3_out / "holdout", holdout_extra), ("pre_apr", v3_out / "pre_apr", ["--from", "2026-04-01", "--to", "2026-05-22"])):
        if not (folder / "c2_holdout.parquet").exists():
            continue
        run([PY, str(REPO / "commodity-open-kit" / "tools" / "score_holdout.py"), "--pack", str(PACK),
             "--predictions", str(folder), "--challenge", "2", "--no-baselines", "--out", str(folder), *score_extra],
            f"05_v3_score_{tag}.log")
        train_end = "2026-04-01T03:00:00+00:00" if tag == "pre_apr" else "2026-06-01T03:00:00+00:00"
        for stem in ("c2_holdout", "c2_holdout_frozen"):
            run([PY, "tests/check_readlog.py", "--pack", str(PACK), "--signals", str(folder / f"{stem}.parquet"),
                 "--train-end", train_end], f"05_v3_readlog_{tag}_{stem}.log")
    first = sha256(v3_out / "holdout" / "c2_holdout.parquet")
    rerun = v3_out / "holdout_rerun"
    run_pair(rerun, "05_v3_rerun", holdout_extra, extra_env=None)
    # frozen is started too; the hash that matters is the learning file
    second = sha256(rerun / "c2_holdout.parquet")
    summary["v3"] = {"holdout_dir": str(v3_out / "holdout"), "rerun_identical": first == second,
                     "sha256": first}
    selection_path = RESULTS / "selection.json"
    if not selection_path.exists():
        return summary
    selection = json.loads(selection_path.read_text())
    ship = selection.get("ship")
    summary["ship_block"] = ship
    if not ship:
        return summary
    if ship.get("learner") not in {"refit", "neural", "append", "blend"} or _has_news(ship.get("params") or {}):
        summary["ship_skipped"] = "news features or a learner the official runner does not execute"
        return summary
    ship_env = {
        "TASK2_LEARNER": ship["learner"],
        "TASK2_LEARNER_PARAMS": json.dumps(ship.get("params") or {}),
        "TASK2_AUX": _aux_horizons(str(ship.get("aux") or "coreh:1,2,3,4")),
    }
    ship_out = RESULTS / "official" / "ship"
    run_pair(ship_out / "holdout", "05_ship_holdout", holdout_extra, ship_env)
    if not quick:
        run_pair(ship_out / "pre_apr", "05_ship_apr", apr_extra, ship_env)
    for tag, folder, score_extra in (("holdout", ship_out / "holdout", holdout_extra), ("pre_apr", ship_out / "pre_apr", ["--from", "2026-04-01", "--to", "2026-05-22"])):
        if not (folder / "c2_holdout.parquet").exists():
            continue
        run([PY, str(REPO / "commodity-open-kit" / "tools" / "score_holdout.py"), "--pack", str(PACK),
             "--predictions", str(folder), "--challenge", "2", "--no-baselines", "--out", str(folder), *score_extra],
            f"05_ship_score_{tag}.log")
        train_end = "2026-04-01T03:00:00+00:00" if tag == "pre_apr" else "2026-06-01T03:00:00+00:00"
        for stem in ("c2_holdout", "c2_holdout_frozen"):
            run([PY, "tests/check_readlog.py", "--pack", str(PACK), "--signals", str(folder / f"{stem}.parquet"),
                 "--train-end", train_end], f"05_ship_readlog_{tag}_{stem}.log")
    h1 = sha256(ship_out / "holdout" / "c2_holdout.parquet")
    rerun = ship_out / "holdout_rerun"
    run_pair(rerun, "05_ship_rerun", holdout_extra, ship_env)
    summary["ship"] = {"holdout_dir": str(ship_out / "holdout"), "rerun_identical": h1 == sha256(rerun / "c2_holdout.parquet"),
                       "sha256": h1, "learner": ship["learner"], "params": ship.get("params"), "aux": ship.get("aux")}
    return summary


def _scores(folder: Path) -> dict:
    path = folder / "holdout_scores.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    block = (data.get("challenges") or {}).get("2") or {}
    report = {}
    report_path = folder / "report_2_holdout.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
    return {"scores": block.get("scores") or {}, "conditions": block.get("award_conditions") or {},
            "diagnostics": block.get("diagnostics") or {}, "report": report}


def stage6(official: dict) -> None:
    lines = ["# Pipeline report", ""]
    sel = RESULTS / "SELECTION.md"
    if sel.exists():
        lines.append(sel.read_text().strip())
        lines.append("")
    fwd = RESULTS / "forward.md"
    if fwd.exists():
        lines.append(fwd.read_text().strip())
        lines.append("")
    for label, folder in (("v3 holdout", Path(official.get("v3", {}).get("holdout_dir", ""))),
                          ("ship holdout", Path((official.get("ship") or {}).get("holdout_dir", "")))):
        if not folder or not str(folder) or folder == Path("."):
            continue
        sc = _scores(folder)
        if not sc:
            continue
        scores = sc["scores"]
        def val(name):
            block = scores.get(name) or {}
            return block.get("value")
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- direction {val('direction')}")
        lines.append(f"- depth {val('depth')}")
        lines.append(f"- improvement {val('improvement')}")
        lines.append(f"- success {val('success_rate')}")
        report = sc.get("report") or {}
        paired = report.get("paired_direction") or {}
        halves = report.get("halves") or {}
        if paired:
            lines.append(f"- paired learning {paired.get('learning')} frozen {paired.get('frozen')} n={paired.get('n')}")
        if halves:
            lines.append(f"- halves {halves.get('first_half_direction')} then {halves.get('second_half_direction')}")
        cond = sc["conditions"]
        hard = (cond.get("hard_conditions") or report.get("hard_conditions") or {})
        failing = [k for k, v in hard.items() if v is False]
        if cond.get("success_rate_at_least_minimum") is False:
            failing.append("success_rate_at_least_minimum")
        lines.append(f"- hard conditions failing: {failing or 'none'}")
        lines.append("")
    if official.get("v3"):
        lines.append(f"v3 rerun identical: {official['v3'].get('rerun_identical')}")
    if official.get("ship"):
        lines.append(f"ship rerun identical: {official['ship'].get('rerun_identical')}")
    if official.get("ship_skipped"):
        lines.append(f"ship official run skipped: {official['ship_skipped']}")
    text = "\n".join(lines) + "\n"
    (RESULTS / "PIPELINE_REPORT.md").write_text(text)
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--from-stage", type=int, default=0)
    args = parser.parse_args()
    os.chdir(ROOT)
    start = args.from_stage
    official: dict = {}
    if start <= 0:
        stage0()
    if start <= 1:
        stage1()
    if start <= 2:
        cmd = [PY, "research/learn_sweep.py", "grid"] + (["--quick"] if args.quick else [])
        run(cmd, "02_sweep.log")
    if start <= 3:
        run([PY, "research/select_design.py"], "03_select.log")
    if start <= 4:
        run([PY, "research/forward_check.py"], "04_forward.log")
    if start <= 5:
        official = stage5(args.quick)
        (RESULTS / "official_summary.json").write_text(json.dumps(official, indent=2, default=str) + "\n")
    else:
        path = RESULTS / "official_summary.json"
        if path.exists():
            official = json.loads(path.read_text())
    if start <= 6:
        stage6(official)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
