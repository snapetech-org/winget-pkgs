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
KEY_LINE = re.compile(r"^( *)([A-Za-z0-9_-]+):(?:\s*(.*))?$")


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


def mapping_block(lines: list[str], indent: int, key: str) -> list[str] | None:
    start = None
    for index, line in enumerate(lines):
        match = KEY_LINE.match(line)
        if match and len(match.group(1)) == indent and match.group(2) == key:
            start = index
            break
    if start is None:
        return None
    result = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() and not line.lstrip().startswith("#"):
            current_indent = len(line) - len(line.lstrip(" "))
            if current_indent <= indent:
                break
        result.append(line)
    return result


def markdown_frontmatter(source: Path) -> list[str]:
    parts = source.read_text().split("---", 2)
    if len(parts) != 3:
        raise RuntimeError(f"{source.name}: missing YAML frontmatter")
    return parts[1].splitlines()


def run_name(lines: list[str]) -> str | None:
    start = None
    initial = ""
    for index, line in enumerate(lines):
        match = KEY_LINE.match(line)
        if match and not match.group(1) and match.group(2) == "run-name":
            start = index
            initial = match.group(3) or ""
            if initial.strip() in {">", ">-", ">+", "|", "|-", "|+"}:
                initial = ""
            break
    if start is None:
        return None
    pieces = [initial.strip()] if initial.strip() else []
    for line in lines[start + 1 :]:
        if line.strip() and not line.lstrip().startswith("#") and not line.startswith((" ", "\t")):
            break
        if line.strip():
            pieces.append(line.strip())
    return " ".join(" ".join(pieces).split())


def private_only_options(block: list[str]) -> bool:
    for index, line in enumerate(block):
        match = re.match(r"^\s{8}options:\s*(.*?)\s*(?:#.*)?$", line)
        if not match:
            continue
        inline = match.group(1)
        if inline:
            values = inline.strip("[] ").split(",")
            return [value.strip().strip("\"'") for value in values] == ["private"]
        values = []
        for item in block[index + 1 :]:
            if item.strip() and len(item) - len(item.lstrip(" ")) <= 8:
                break
            option = re.match(r"^\s{10}-\s*(.*?)\s*(?:#.*)?$", item)
            if option:
                values.append(option.group(1).strip().strip("\"'"))
        return values == ["private"]
    return False


def verify_manual_dispatch(source: Path, lock: Path) -> None:
    source_lines = markdown_frontmatter(source)
    lock_lines = lock.read_text().splitlines()
    source_dispatch = mapping_block(source_lines, 2, "workflow_dispatch")
    if source_dispatch is None:
        return
    lock_dispatch = mapping_block(lock_lines, 2, "workflow_dispatch")
    if lock_dispatch is None:
        raise RuntimeError(f"{lock.name}: compiler dropped workflow_dispatch")

    for key in ("action", "runner_pool"):
        source_input = mapping_block(source_dispatch, 6, key)
        lock_input = mapping_block(lock_dispatch, 6, key)
        if source_input is None or lock_input is None:
            raise RuntimeError(f"{source.name}/{lock.name}: missing dispatch input {key}")
        required = re.compile(r"^\s{8}required:\s*true\s*(?:#.*)?$")
        if not any(required.match(line) for line in source_input):
            raise RuntimeError(f"{source.name}: dispatch input {key} must be required")
        if not any(required.match(line) for line in lock_input):
            raise RuntimeError(f"{lock.name}: compiled dispatch input {key} is not required")

    source_pool = mapping_block(source_dispatch, 6, "runner_pool") or []
    lock_pool = mapping_block(lock_dispatch, 6, "runner_pool") or []
    if not private_only_options(source_pool):
        raise RuntimeError(f"{source.name}: runner_pool options must be private only")
    if not private_only_options(lock_pool):
        raise RuntimeError(f"{lock.name}: compiled runner_pool options are not private only")

    source_name = run_name(source_lines)
    compiled_name = run_name(lock_lines)
    if not source_name or not compiled_name:
        raise RuntimeError(f"{source.name}/{lock.name}: missing run-name contract")
    if source_name != compiled_name:
        raise RuntimeError(f"{lock.name}: compiler changed the source run-name contract")
    for value in ("inputs.action", "inputs.runner_pool"):
        if value not in source_name or value not in compiled_name:
            raise RuntimeError(f"{source.name}/{lock.name}: run-name must include {value}")


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
    if changed:
        path.write_bytes("".join(lines).encode("utf-8"))
    return len(headers)


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
        source = WORKFLOWS / f"{workflow}.md"
        lock = WORKFLOWS / f"{workflow}.lock.yml"
        if not lock.is_file():
            raise RuntimeError(f"compiler did not generate {lock.name}")
        total_jobs += patch_lock(lock)
        verify_manual_dispatch(source, lock)
    print(
        f"gh-aw {version}: compiled {len(workflows)} workflow(s); "
        f"verified private group 10 and per-job run labels on {total_jobs} jobs, "
        "plus every applicable manual action/pool contract"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"compile-agentic-workflows: {exc}", file=sys.stderr)
        raise SystemExit(1)
