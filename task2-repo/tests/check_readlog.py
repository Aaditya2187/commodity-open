#!/usr/bin/env python3
"""Check a signal file's point-in-time read log.

    python tests/check_readlog.py --pack ../v2.1 --signals predictions/c2_holdout.parquet \
        --train-end 2026-06-01T03:00:00+00:00
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from swing_dataset.kit import repro


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--train-end", required=True, help="ISO-8601 fit instant with offset")
    args = parser.parse_args(argv)
    log_path = repro.read_log_for(args.signals)
    if not log_path.exists():
        print(f"missing {log_path}")
        return 1
    entries = repro.load_read_log(log_path)
    decisions = repro.load_predictions(args.signals)
    train_end = datetime.fromisoformat(args.train_end)
    report = repro.check_read_log(entries, decisions, train_end, pack=args.pack)
    print(json.dumps({k: report[k] for k in report if k != "violations"}, default=str))
    for item in report.get("violations") or []:
        print(f"violation: {item}")
    print("read log", "ok" if report.get("ok") else "PROBLEM", f"({report.get('entries', len(entries))} entries)")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
