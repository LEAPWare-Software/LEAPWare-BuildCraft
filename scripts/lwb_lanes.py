#!/usr/bin/env python3
"""Lane classification shared by the `lwb-lanes` CI check and the in-repo
session lane hooks (`scripts/lwb_check_lane_write.py`).

Owner directive 5: "Codex works only on the Codex part, Claude only on the
Claude part. Shared parts may be changed by either CLI only after the
CTO/CIO role on each CLI adversarially checks and agrees; the owner is not
in that loop."

Lane membership (literal, per the D1b brief):
  - claude lane: `plugins/claude/`, `adapters/claude/`, any directory
    literally named `claude` under `tests/` (e.g. `tests/adapters/fixtures/claude/`).
  - codex lane: `plugins/codex/`, `adapters/codex/`, any directory literally
    named `codex` under `tests/`.
  - shared: `core/`, `scripts/`, `.github/`, `docs/`, `proof/`, `reviews/`,
    `tests/`, `HANDOFF.md`, `AGENTS.md`, `CLAUDE.md`, `README.md`.

`tests/` is shared, with the lane-owned subtrees and filename patterns
below carved out of it. It has to be: a test covering a shared script
(`tests/test_lwb_check_proof.py`, say) previously classified as "other" —
in neither lane and not on the shared list — which meant NEITHER CLI was
allowed to write it, so a shared script could not be given a test at all.
Lane patterns are therefore matched before the shared prefixes.

One extension beyond the literal glob, documented here rather than left
implicit: a test module directly named `test_claude_*` or `*_claude_*`
under `tests/` (not inside a `claude/` subdirectory) is also classified as
the claude lane, and likewise `test_codex_*` / `*_codex_*` for codex — this
repo already has `tests/adapters/test_claude_hook_io.py` and
`tests/adapters/test_codex_hook_io.py` sitting directly under `tests/adapters/`,
not under a `claude/`/`codex/` subdirectory, and the literal glob alone
would strand them in neither lane nor the shared list.

Bootstrap exception: lane enforcement (this module's `check_lanes`, wired
into the `lwb-lanes` CI job) is a no-op for PR numbers 1-5 — the PR that
introduced this system could not have satisfied it before it existed. PR 6
onward is enforced. `--pr-number` with no value, or 0, means "not running
under a PR" (e.g. a push to main after merge) and is also skipped, since
lane enforcement is a pre-merge PR gate, not a post-merge one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENTS = ("claude", "codex", "human")

SHARED_PREFIXES = (
    "core/",
    "scripts/",
    ".github/",
    "docs/",
    "proof/",
    "reviews/",
    # `tests/` is shared so that a test covering a shared script is writable
    # by either CLI (under two-CTO review). Without it, a file such as
    # `tests/test_lwb_check_proof.py` classified as "other" — in no lane and
    # not shared — so NEITHER CLI could touch it. Lane-owned subtrees inside
    # `tests/` still win: see classify_path's ordering.
    "tests/",
)
SHARED_FILES = ("HANDOFF.md", "AGENTS.md", "CLAUDE.md", "README.md")

BOOTSTRAP_LAST_EXEMPT_PR = 5

TRAILER_RE = re.compile(r"^LWB-Agent:\s*(claude|codex|human)\s*$", re.MULTILINE)


def classify_path(path: str) -> str:
    """Return "claude", "codex", "shared", or "other" for a repo-relative path."""
    posix = path.replace("\\", "/")

    # Lane-specific patterns are checked BEFORE the shared prefixes, because
    # `tests/` is shared as a whole while `tests/**/claude/**` and
    # `tests/**/*_claude_*` inside it still belong to the claude lane. No
    # shared prefix other than `tests/` can match a lane pattern, so the
    # order is a no-op for the rest.
    for agent in ("claude", "codex"):
        if posix.startswith(f"plugins/{agent}/") or posix.startswith(f"adapters/{agent}/"):
            return agent
        parts = posix.split("/")
        if posix.startswith("tests/") and agent in parts:
            return agent
        filename = parts[-1]
        if posix.startswith("tests/") and (
            filename.startswith(f"test_{agent}_") or f"_{agent}_" in filename
        ):
            return agent

    for prefix in SHARED_PREFIXES:
        if posix.startswith(prefix):
            return "shared"
    if posix in SHARED_FILES:
        return "shared"

    return "other"


def commit_agent(sha: str) -> Optional[str]:
    """The `LWB-Agent:` trailer value for `sha`, or None if missing/invalid."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B", sha],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    m = TRAILER_RE.search(result.stdout)
    return m.group(1) if m else None


def commit_files(sha: str) -> list[str]:
    # --root: a root commit (no parent, e.g. the first commit of a fresh
    # test repo) otherwise shows no files at all under plain diff-tree.
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def commits_in_range(rev_range: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _review_ok(pr_number: int, agent: str, commit_sha: str, errors: list[str]) -> bool:
    review_path = REPO_ROOT / "reviews" / str(pr_number) / f"{agent}-cto.json"
    if not review_path.is_file():
        errors.append(f"{commit_sha[:12]}: missing required review {review_path.relative_to(REPO_ROOT)}")
        return False
    import json

    try:
        data = json.loads(review_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{review_path}: invalid JSON: {exc}")
        return False
    if data.get("verdict") != "AGREE":
        errors.append(f"{review_path}: verdict is {data.get('verdict')!r}, want 'AGREE'")
        return False
    if data.get("reviewer_agent") != agent:
        errors.append(f"{review_path}: reviewer_agent is {data.get('reviewer_agent')!r}, want {agent!r}")
        return False
    reviewer_id = data.get("reviewer_id")
    author_id = data.get("commit_author_id")
    if not reviewer_id or not author_id:
        errors.append(f"{review_path}: missing 'reviewer_id' or 'commit_author_id'")
        return False
    if reviewer_id == author_id:
        errors.append(
            f"{review_path}: reviewer_id equals commit_author_id ({reviewer_id!r}) — "
            "a reviewer may not be the commit's own author"
        )
        return False
    return True


def check_lanes(rev_range: str, pr_number: int) -> list[str]:
    """Check every commit in `rev_range`. Returns a list of failure strings."""
    if pr_number <= BOOTSTRAP_LAST_EXEMPT_PR:
        return []

    errors: list[str] = []
    for sha in commits_in_range(rev_range):
        agent = commit_agent(sha)
        if agent is None:
            errors.append(f"{sha[:12]}: missing or invalid 'LWB-Agent:' trailer")
            continue
        if agent == "human":
            continue  # the owner's own commits are unrestricted

        files = commit_files(sha)
        touches_shared = False
        for f in files:
            cls = classify_path(f)
            if cls == "shared":
                touches_shared = True
            elif cls != agent:
                errors.append(
                    f"{sha[:12]} (LWB-Agent: {agent}): touches '{f}', outside the "
                    f"{agent} lane and not a shared path"
                )

        if touches_shared:
            _review_ok(pr_number, "claude", sha, errors)
            _review_ok(pr_number, "codex", sha, errors)

    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base ref, e.g. origin/main")
    parser.add_argument("--head", default="HEAD", help="head ref (default HEAD)")
    parser.add_argument(
        "--pr-number", type=int, default=0, help="PR number (0 = not a PR, skip enforcement)"
    )
    args = parser.parse_args()

    errors = check_lanes(f"{args.base}..{args.head}", args.pr_number)
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    if args.pr_number == 0:
        print("lwb-lanes check skipped (not running under a PR)")
    elif args.pr_number <= BOOTSTRAP_LAST_EXEMPT_PR:
        print(f"lwb-lanes check skipped (bootstrap exception, PR #{args.pr_number})")
    else:
        print("lwb-lanes check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
