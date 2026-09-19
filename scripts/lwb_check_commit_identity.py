#!/usr/bin/env python3
"""CI check: every commit author is LEAPWare, or an allow-listed GitHub bot.

This repo's commit identity is `LEAPWare <leapware@outlook.com>` (owner
directive 10). A GitHub-managed bot (Dependabot today; more may be added by
GitHub itself later) commits under its own `<name>[bot]` account and a
`@users.noreply.github.com` email -- that is GitHub's own identity, not a
human's, and is explicitly allowed here. Any OTHER author name/email is
flagged: it is either a real, non-LEAPWare human identity (which does not
belong in this repo's history per owner directive 10) or a bot this list
has not reviewed yet.

A commit whose changed files are ALL under `reviews/` or `proof/` (pure
record-keeping -- e.g. a reviewer filing their own AGREE record) is exempt
from this check via the same `_is_record_only_commit` test `lwb_lanes.py`
uses to compute the reviewable head. Before this exemption existed, a
reviewer's own record-only commit landing under any identity other than
exactly `LEAPWare <leapware@outlook.com>` permanently failed this gate for
the whole branch -- and since force-push is denied here, that could not be
fixed in place, only worked around by re-cutting the entire PR from a clean
commit. `lwb_lanes.resolve_reviewable_head` already carried this same
exemption for the freshness check; `_authors` here had it not, which was
the asymmetry actually driving that pattern. This does not touch owner
directive 10 for anything that changes code: any code-changing commit must
still be authored as LEAPWare.

Usage:
    python scripts/lwb_check_commit_identity.py [--base <ref>] [--head <ref>]

With no arguments, checks every commit reachable from HEAD (bounded to the
last 500 to keep this cheap; raise the bound if this repo's history ever
needs it). `--base`/`--head` restrict the scan to `base..head`, e.g. a PR's
own new commits.

Stdlib only. Exits 0 and prints "lwb-commit-identity check passed" on
success; otherwise prints every offending author and exits 1.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# lwb_lanes.py lives in this same directory (scripts/); imported for
# `_is_record_only_commit` rather than duplicating that logic here, so the
# definition of "record-only" can never drift between the two checks that
# both depend on it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lwb_lanes import _is_record_only_commit  # noqa: E402

ALLOWED_HUMAN = ("LEAPWare", "leapware@outlook.com")

# A GitHub bot commits as "<name>[bot] <NNNNNNN+name[bot]@users.noreply.github.com>"
# (Dependabot's own shape, seen in this repo's own history) or the plainer
# "<name>[bot] <name@users.noreply.github.com>" some other GitHub bots use.
BOT_NAME = re.compile(r"^[\w.\-]+\[bot\]$")
BOT_EMAIL = re.compile(r"^(?:\d+\+)?[\w.\-]+\[bot\]@users\.noreply\.github\.com$")


def _authors(rev_range: str) -> list[tuple[str, str]]:
    """Distinct (name, email) pairs among non-record-only commits in
    `rev_range`. A commit whose changed files are ALL under `reviews/` or
    `proof/` is skipped via `_is_record_only_commit` -- see the module
    docstring for why. `%H` is included in the log format (previously
    only `%an\\t%ae`) because that test needs the commit sha; it is split
    off `line` below and not otherwise used.
    """
    result = subprocess.run(
        ["git", "log", "--format=%H\t%an\t%ae", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    seen: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, rest = line.partition("\t")
        name, _, email = rest.partition("\t")
        if _is_record_only_commit(sha):
            continue
        pair = (name, email)
        if pair not in seen:
            seen.append(pair)
    return seen


def _is_allowed(name: str, email: str) -> bool:
    if (name, email) == ALLOWED_HUMAN:
        return True
    if BOT_NAME.match(name) and BOT_EMAIL.match(email):
        return True
    return False


def check(rev_range: str) -> list[str]:
    findings = []
    for name, email in _authors(rev_range):
        if not _is_allowed(name, email):
            findings.append(f"{name} <{email}>")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="base ref, e.g. origin/main")
    parser.add_argument("--head", default="HEAD", help="head ref (default HEAD)")
    args = parser.parse_args()

    rev_range = f"{args.base}..{args.head}" if args.base else "-500"
    findings = check(rev_range)
    if findings:
        for f in findings:
            print(f"FAIL: commit author not LEAPWare or an allow-listed bot: {f}")
        return 1
    print("lwb-commit-identity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
