#!/usr/bin/env python3
"""CI check `lwb-hosted-runners`: every workflow job runs on a GitHub-hosted runner.

This repo's CI must never depend on a self-hosted runner (a specific
machine, a specific owner's laptop, or anything not reproducible by a
fresh GitHub-hosted VM). Scans every `.github/workflows/*.yml` /
`*.yaml` file and fails if any job's `runs-on` value, or any entry in a
`runs-on` list, is not one of the known hosted labels below.

Recognized hosted labels (GitHub-hosted runners, per GitHub's own
documentation): the `-latest` aliases, and every versioned label GitHub
currently publishes for `ubuntu`, `windows`, and `macos`. A `runs-on`
built from a matrix expression (e.g. `${{ matrix.os }}`) is resolved
against that job's own `strategy.matrix` values instead of the literal
expression string, so a matrix-driven job is checked the same way a
literal one is.

This is a plain-text/YAML-shape scan, not a full YAML parser with GitHub
Actions expression semantics -- it uses the standard library's `yaml`-free
line scanning deliberately (no third-party dependency under `scripts/`
either), so it recognizes the common shapes this repo's own workflows use
and fails LOUD (non-zero, with the offending file/job) rather than
silently passing on a shape it cannot parse.

Usage:
    python scripts/lwb_check_hosted_runners.py

Stdlib only. Exits 0 and prints "lwb-hosted-runners check passed" on
success; otherwise prints every finding and exits 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

_HOSTED_OS = {"ubuntu", "windows", "macos"}
# e.g. "ubuntu-latest", "windows-2022", "macos-14" -- GitHub's own hosted
# runner label shapes. A trailing "-latest" or a numeric/short version
# after the OS name is accepted; anything else is flagged.
_HOSTED_LABEL_RE = re.compile(
    r"^(?:" + "|".join(_HOSTED_OS) + r")-(?:latest|\d[\w.]*)$"
)

_JOB_HEADER_RE = re.compile(r"^  (\S[^:]*):\s*$")
_RUNS_ON_SCALAR_RE = re.compile(r"^\s*runs-on:\s*(\S.*?)\s*$")
_RUNS_ON_LIST_START_RE = re.compile(r"^\s*runs-on:\s*\[(.*)\]\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*-\s*(\S.*?)\s*$")
_MATRIX_OS_RE = re.compile(r"^\s*os:\s*\[(.*)\]\s*$")
_MATRIX_EXPR_RE = re.compile(r"^\$\{\{\s*matrix\.os\s*\}\}$")


def _split_list(raw: str) -> list[str]:
    return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]


def _find_workflow_files() -> list[Path]:
    if not WORKFLOWS_DIR.is_dir():
        return []
    return sorted(
        p
        for p in WORKFLOWS_DIR.iterdir()
        if p.is_file() and p.suffix in {".yml", ".yaml"}
    )


def _check_file(path: Path) -> list[str]:
    findings: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    rel = path.relative_to(REPO_ROOT).as_posix()

    current_job: str | None = None
    matrix_os: list[str] | None = None
    in_runs_on_list = False
    runs_on_list_items: list[str] = []

    def _resolve_and_check(job: str, value: str) -> None:
        value = value.strip().strip("'\"")
        if _MATRIX_EXPR_RE.match(value):
            if matrix_os is None:
                findings.append(
                    f"{rel}: job '{job}' runs-on uses matrix.os but no "
                    f"strategy.matrix.os was found in that job"
                )
                return
            for candidate in matrix_os:
                if not _HOSTED_LABEL_RE.match(candidate):
                    findings.append(
                        f"{rel}: job '{job}' matrix os '{candidate}' is not a "
                        f"recognized GitHub-hosted runner label"
                    )
            return
        if not _HOSTED_LABEL_RE.match(value):
            findings.append(
                f"{rel}: job '{job}' runs-on '{value}' is not a recognized "
                f"GitHub-hosted runner label"
            )

    for raw_line in lines:
        header_match = _JOB_HEADER_RE.match(raw_line)
        if header_match and not raw_line.strip().startswith("-"):
            # A new top-level-under-`jobs:` key. This is a coarse heuristic
            # (two-space indent) matching this repo's own workflow style.
            current_job = header_match.group(1).strip()
            matrix_os = None
            in_runs_on_list = False
            runs_on_list_items = []
            continue

        matrix_match = _MATRIX_OS_RE.match(raw_line)
        if matrix_match and current_job:
            matrix_os = _split_list(matrix_match.group(1))
            continue

        list_start = _RUNS_ON_LIST_START_RE.match(raw_line)
        if list_start and current_job:
            for item in _split_list(list_start.group(1)):
                _resolve_and_check(current_job, item)
            continue

        scalar_match = _RUNS_ON_SCALAR_RE.match(raw_line)
        if scalar_match and current_job:
            value = scalar_match.group(1)
            if value == "":
                in_runs_on_list = True
                runs_on_list_items = []
                continue
            _resolve_and_check(current_job, value)
            continue

        if in_runs_on_list:
            item_match = _LIST_ITEM_RE.match(raw_line)
            if item_match:
                _resolve_and_check(current_job, item_match.group(1))
                continue
            in_runs_on_list = False

    return findings


def check() -> list[str]:
    findings: list[str] = []
    for path in _find_workflow_files():
        findings.extend(_check_file(path))
    return findings


def main() -> int:
    findings = check()
    if findings:
        for f in findings:
            print(f"FAIL: {f}")
        return 1
    print("lwb-hosted-runners check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
