#!/usr/bin/env python3
"""Make and check the git bundle a team submits, and print what to paste into the form.

    python tools/submit.py --ticket CO-00XX --tasks 1
    python tools/submit.py --ticket CO-00XX --tasks 1,2 --out ~/CO-00XX.bundle

Run it in the top directory of your repository, on the commit you want scored. It writes one file
containing the whole repository at that commit, verifies the file git just wrote, confirms the commit
is in it, and prints the commit hash and the file's sha256. Upload the file, paste the hash.

Nothing here needs the network and nothing leaves the machine. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

TICKET = re.compile(r"^CO-\d{4}$")


def run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def git(*argv: str) -> str:
    done = run("git", *argv)
    if done.returncode != 0:
        raise SystemExit(f"submit: git {' '.join(argv)} failed:\n{done.stderr.strip() or done.stdout.strip()}")
    return done.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", required=True, help="your ticket number, for example CO-0023")
    parser.add_argument("--tasks", default="1", help="the task or tasks you are entering: 1, 2 or 1,2")
    parser.add_argument("--out", help="where to write the bundle (default: ./TICKET.bundle)")
    args = parser.parse_args(argv)

    if not TICKET.match(args.ticket):
        raise SystemExit(f"submit: {args.ticket!r} is not a ticket number of the form CO-0000")
    tasks = {t.strip() for t in args.tasks.split(",") if t.strip()}
    if not tasks or not tasks <= {"1", "2"}:
        raise SystemExit(f"submit: --tasks takes 1, 2 or 1,2, not {args.tasks!r}")

    if run("git", "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise SystemExit("submit: this is not a git repository; run it at the top of your project")

    top = Path(git("rev-parse", "--show-toplevel"))
    commit = git("rev-parse", "HEAD")
    if not commit:
        raise SystemExit("submit: the repository has no commit yet")
    subject = git("log", "-1", "--format=%s")

    # What the rules require the repository to hold at the commit that is run.
    missing = [name for name in ("run.py", "requirements.txt") if run("git", "cat-file", "-e", f"HEAD:{name}").returncode != 0]
    if "run.py" in missing:
        raise SystemExit(f"submit: {top}/run.py is not in commit {commit[:12]}; the organizers run run.py, so commit it first")
    warnings = []
    if "requirements.txt" in missing:
        warnings.append("requirements.txt is not in the repository: pin your dependencies there, as RULES.md section 7 asks")
    for soft in ("memo.md", "predictions"):
        if run("git", "cat-file", "-e", f"HEAD:{soft}").returncode != 0:
            warnings.append(f"{soft} is not in the repository: RULES.md section 7 asks for it")
    dirty = [line for line in run("git", "status", "--porcelain", "--untracked-files=no").stdout.splitlines() if line.strip()]
    if dirty:
        warnings.append(
            f"{len(dirty)} tracked file(s) have uncommitted changes and are NOT in the bundle: "
            + ", ".join(line[2:].strip() for line in dirty[:5])
            + (" ..." if len(dirty) > 5 else "")
        )

    out = Path(args.out).expanduser() if args.out else Path.cwd() / f"{args.ticket}.bundle"
    if out.exists():
        print(f"submit: replacing the existing {out}")
        out.unlink()
    git("bundle", "create", str(out), "HEAD")

    verified = run("git", "bundle", "verify", str(out))
    if verified.returncode != 0:
        raise SystemExit(f"submit: git cannot verify the bundle it just wrote:\n{verified.stderr.strip()}")
    heads = {}
    for line in git("bundle", "list-heads", str(out)).splitlines():
        sha, _, name = line.partition(" ")
        heads[name.strip()] = sha
    if heads.get("HEAD") != commit:
        raise SystemExit(
            f"submit: the bundle's HEAD is {heads.get('HEAD')}, not this repository's {commit}; "
            "run this again at the top of the repository you mean to submit"
        )

    digest = hashlib.sha256()
    with out.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    size = out.stat().st_size

    print()
    print("The bundle is ready. Upload this file through the submission link:")
    print(f"  file    {out}")
    print(f"  bytes   {size:,}")
    print(f"  sha256  {digest.hexdigest()}")
    print()
    print("Paste these into the form:")
    print(f"  ticket  {args.ticket}")
    print(f"  task(s) {','.join(sorted(tasks))}")
    print(f"  commit  {commit}")
    print()
    print(f"The commit is {commit[:12]} ({subject}).")
    for warning in warnings:
        print(f"  note: {warning}")
    print()
    print("The link checks the bundle again when it arrives and shows you a receipt. Keep this file until")
    print("the verdicts: the last upload before Mon 26 Oct 2026, 5 pm IST is the one that counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
