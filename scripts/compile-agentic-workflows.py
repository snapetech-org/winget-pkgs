#!/usr/bin/env python3
"""Compile WinGet gh-aw sources and restore per-job private JIT labels.

`runs-on-slim` is a workflow-wide setting in gh-aw. The broker also needs a
unique job label for each generated job, so this wrapper adds that label after
compilation without editing the compiler-owned job graph or other metadata.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED_GH_AW_VERSION = "v0.88.7"
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?(?:\r?\n)?$")
RUNS_ON = re.compile(r"^    runs-on:\s*(.*?)\s*(?:\r?\n)?$")


def gh_aw_version() -> str:
    result = subprocess.run(
        ["gh", "aw", "version"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    )
    match = re.search(r"\b(v\d+\.\d+\.\d+)\b", result.stdout + result.stderr)
    if not match:
        raise RuntimeError("could not determine gh-aw compiler version")
    return match.group(1)


def selected_workflows(names: list[str]) -> list[str]:
    available = {p.stem for p in WORKFLOWS.glob("*.md")}
    if not names:
        return sorted(available)
    selected = [Path(name).stem for name in names]
    unknown = sorted(set(selected) - available)
    if unknown:
        raise ValueError("unknown gh-aw workflow(s): " + ", ".join(unknown))
    if len(set(selected)) != len(selected):
        raise ValueError("workflow list contains duplicate names")
    return selected


def patch_lock(path: Path) -> int:
    raw = path.read_bytes().decode("utf-8")
    lines = raw.splitlines(keepends=True)
    jobs_line = next((i for i, line in enumerate(lines) if line.rstrip("\r\n") == "jobs:"), None)
    if jobs_line is None:
        raise RuntimeError(f"{path.name}: missing jobs mapping")

    headers = [
        (i, match.group(1))
        for i, line in enumerate(lines[jobs_line + 1 :], jobs_line + 1)
        if (match := JOB_HEADER.match(line))
    ]
    if not headers:
        raise RuntimeError(f"{path.name}: generated workflow has no jobs")

    changed = 0
    matched_jobs = 0
    for index, (start, job_id) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(lines)
        runs_on_idx = next(
            (i for i in range(start + 1, end) if RUNS_ON.match(lines[i])), None
        )
        if runs_on_idx is None:
            raise RuntimeError(f"{path.name}:{job_id}: missing generated runs-on")
        match = RUNS_ON.match(lines[runs_on_idx])
        assert match is not None
        expression = match.group(1)
        if '"group":"ng-shared-main-jit"' not in expression:
            raise RuntimeError(f"{path.name}:{job_id}: unexpected runner group")
        if '"ng-main-run-{0}"' not in expression:
            raise RuntimeError(f"{path.name}:{job_id}: missing run-scoped private label")
        expected = f'"gha-{{0}}-{job_id}"'
        occurrences = expression.count(expected)
        if occurrences > 1:
            raise RuntimeError(f"{path.name}:{job_id}: duplicate job-scoped label")
        if occurrences == 0:
            anchor = '"ng-main-run-{0}"'
            position = expression.index(anchor) + len(anchor)
            expression = expression[:position] + "," + expected + expression[position:]
            newline = "\r\n" if lines[runs_on_idx].endswith("\r\n") else "\n"
            lines[runs_on_idx] = f"    runs-on: {expression}{newline}"
            changed += 1
        matched_jobs += 1

    if matched_jobs != len(headers):
        raise RuntimeError(f"{path.name}: not every generated job has private JIT routing")
    if changed:
        path.write_bytes("".join(lines).encode("utf-8"))
    return matched_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflows", nargs="*", help="gh-aw workflow IDs (default: all .md sources)")
    args = parser.parse_args()

    version = gh_aw_version()
    if version != EXPECTED_GH_AW_VERSION:
        raise RuntimeError(
            f"expected gh-aw {EXPECTED_GH_AW_VERSION}, found {version}; "
            "install the pinned compiler before regenerating locks"
        )

    workflows = selected_workflows(args.workflows)
    subprocess.run(
        ["gh", "aw", "compile", "--no-check-update", *workflows],
        cwd=ROOT,
        check=True,
    )

    total_jobs = 0
    for workflow in workflows:
        lock = WORKFLOWS / f"{workflow}.lock.yml"
        if not lock.is_file():
            raise RuntimeError(f"compiler did not generate {lock.name}")
        total_jobs += patch_lock(lock)
    print(
        f"gh-aw {version}: compiled {len(workflows)} workflow(s); "
        f"verified private group 10 and per-job run labels on {total_jobs} jobs"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"compile-agentic-workflows: {exc}", file=sys.stderr)
        raise SystemExit(1)
