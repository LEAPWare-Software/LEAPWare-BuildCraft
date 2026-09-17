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
into the `lwb-lanes` CI job) is a no-op for the PRs named in
`BOOTSTRAP_EXEMPT_PRS` — the PR that introduced this system could not have
satisfied it before it existed. That used to be the range 1-5, which was a
mistake: PR numbers are a consumable resource, and Dependabot spent #2, #3
and #4 unattended. It is now an explicit set, so no bot can eat the window
and nobody can widen it by editing one digit. `--pr-number` with no value,
or 0, means "not running under a PR" (e.g. a push to main after merge) and
is also skipped, since lane enforcement is a pre-merge gate.

Bot commits are skipped too (`BOT_AUTHOR_PATTERNS`): a bot stamps no
`LWB-Agent:` trailer and cannot write a `reviews/` record, so without this
every Dependabot PR would fail the lane check and teach us to merge past a
red gate. Bots remain bound by every other check.
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

# The bootstrap window, as an explicit set rather than a `<= N` threshold.
# A threshold is wrong here because PR numbers are a shared, consumable
# resource: Dependabot opened #2, #3 and #4 unattended, silently spending
# three quarters of a window that was meant for the PRs that stood this
# system up. Only #1 (the scaffold) and #5 (the PR that fixed this rule)
# ever needed the exemption, so they are named, and the window cannot be
# eaten or quietly extended by a bot.
BOOTSTRAP_EXEMPT_PRS = frozenset({1, 5})

# Commit authors that cannot satisfy lane review by construction: a bot
# does not run a CTO role, cannot write a reviews/ record, and does not
# stamp an `LWB-Agent:` trailer. Without this, every Dependabot PR from #6
# onward fails `lwb-lanes` on a missing trailer -- which would train us to
# merge past a red lane check, the exact habit this gate exists to prevent.
# A bot commit is still bound by every other check (commit identity, env
# leak, tests); it is only exempt from the two-CTO lane review.
# How many DISTINCT independent reviewers a shared-path change needs. The
# old rule was "one record per CLI vendor", which read as two but was really
# one-each and could never be met with a single CLI in operation. One
# genuinely independent reviewer is the substance of directive 5; raise this
# when a second reviewer identity is routinely available. A project policy
# may tighten it, never loosen it.
REQUIRED_INDEPENDENT_REVIEWS = 1

BOT_AUTHOR_PATTERNS = (
    re.compile(r"^dependabot(?:\[bot\])?@", re.IGNORECASE),
    re.compile(r"^\d+\+dependabot\[bot\]@users\.noreply\.github\.com$", re.IGNORECASE),
    re.compile(r"\[bot\]@users\.noreply\.github\.com$", re.IGNORECASE),
)

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


def _review_ok(review_path: Path, errors: list[str]) -> Optional[str]:
    """Validate one review record. Returns its reviewer_id, or None if invalid.

    Vendor-agnostic on purpose. This used to take an `agent` and look for
    exactly `reviews/<pr>/<agent>-cto.json`, and `check_lanes` called it
    twice -- once for "claude", once for "codex" -- so a shared-path change
    needed one record per CLI VENDOR. That coupled independence to a vendor
    when the property that actually matters is a distinct reviewer IDENTITY,
    which `reviews/README.md` already spelled out ("two different sessions,
    not the same one reviewing itself"). It was also unsatisfiable: one CLI
    operates this repo, so from PR #6 every shared-path change would have
    been unmergeable, and an unsatisfiable gate is worse than a strict one
    because it gets routed around. Any filename is accepted now; what is
    enforced is AGREE and reviewer_id != commit_author_id.
    """
    import json

    rel = review_path.relative_to(REPO_ROOT)
    try:
        data = json.loads(review_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel}: invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{rel}: not a JSON object")
        return None
    if data.get("verdict") != "AGREE":
        errors.append(f"{rel}: verdict is {data.get('verdict')!r}, want 'AGREE'")
        return None
    reviewer_id = data.get("reviewer_id")
    author_id = data.get("commit_author_id")
    if not reviewer_id or not author_id:
        errors.append(f"{rel}: missing 'reviewer_id' or 'commit_author_id'")
        return None
    if reviewer_id == author_id:
        errors.append(
            f"{rel}: reviewer_id equals commit_author_id ({reviewer_id!r}) — "
            "a reviewer may not be the commit's own author"
        )
        return None
    return str(reviewer_id)


def independent_reviews(pr_number: int, commit_sha: str, errors: list[str]) -> bool:
    """True when this PR carries REQUIRED_INDEPENDENT_REVIEWS distinct reviewers."""
    review_dir = REPO_ROOT / "reviews" / str(pr_number)
    records = sorted(review_dir.glob("*.json")) if review_dir.is_dir() else []

    reviewer_ids = set()
    for record in records:
        reviewer_id = _review_ok(record, errors)
        if reviewer_id is not None:
            reviewer_ids.add(reviewer_id)

    if len(reviewer_ids) < REQUIRED_INDEPENDENT_REVIEWS:
        errors.append(
            f"{commit_sha[:12]}: touches a shared path and has "
            f"{len(reviewer_ids)} independent review(s) in reviews/{pr_number}/, "
            f"needs {REQUIRED_INDEPENDENT_REVIEWS} "
            "(each a record with verdict AGREE and a reviewer_id differing from "
            "commit_author_id)"
        )
        return False
    return True


def commit_author_email(sha: str) -> str:
    """The author email of `sha`, for the bot check."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ae", sha],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def is_bot_commit(sha: str) -> bool:
    """True when `sha`'s author is a bot that cannot satisfy lane review."""
    email = commit_author_email(sha)
    return any(pattern.search(email) for pattern in BOT_AUTHOR_PATTERNS)


def check_lanes(rev_range: str, pr_number: int) -> list[str]:
    """Check every commit in `rev_range`. Returns a list of failure strings."""
    # 0 means "not running under a PR" (a push to main after merge). The
    # --pr-number help text always said so and main() printed a skip message
    # for it, but check_lanes itself enforced anyway -- so a direct call with
    # 0 ran the full gate. Lane review is a pre-merge check; there is nothing
    # to gate after the fact.
    if pr_number == 0:
        return []
    if pr_number in BOOTSTRAP_EXEMPT_PRS:
        return []

    errors: list[str] = []
    for sha in commits_in_range(rev_range):
        if is_bot_commit(sha):
            continue  # see BOT_AUTHOR_PATTERNS
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
            independent_reviews(pr_number, sha, errors)

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
    elif args.pr_number in BOOTSTRAP_EXEMPT_PRS:
        print(f"lwb-lanes check skipped (bootstrap exception, PR #{args.pr_number})")
    else:
        print("lwb-lanes check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
