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

A reviewer filing their own AGREE/DISAGREE record under `reviews/<pr>/`
(or `proof/<pr>.json`) commits it under their own git identity, which is
neither LEAPWare nor a bot -- and force-push is denied in this repo, so a
commit flagged here permanently fails that PR. `--pr-number` (mirroring
`lwb_lanes.py`'s own flag) exempts a commit from this check when it is
"record-only" for THAT pr -- every file it touches lives under
`reviews/<pr-number>/` or is exactly `proof/<pr-number>.json` -- reusing
`lwb_lanes._is_record_only_commit` rather than a second, separately
maintained copy of that definition. `--pr-number 0` (the default, "no PR
context") means the exemption never applies, so omitting the flag keeps
this check exactly as strict as before.

Usage:
    python scripts/lwb_check_commit_identity.py [--base <ref>] [--head <ref>] [--pr-number <n>]

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

# Reuse the shared-path definition of a "record-only" commit rather than
# duplicating it: `scripts/lwb_lanes.py` already has to answer this same
# question for the `lwb-lanes` gate, and a second, separately-maintained
# copy here would drift from it silently.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from lwb_lanes import _is_record_only_commit  # noqa: E402

ALLOWED_HUMAN = ("LEAPWare", "leapware@outlook.com")

# A GitHub bot commits as "<name>[bot] <NNNNNNN+name[bot]@users.noreply.github.com>"
# (Dependabot's own shape, seen in this repo's own history) or the plainer
# "<name>[bot] <name@users.noreply.github.com>" some other GitHub bots use.
BOT_NAME = re.compile(r"^[\w.\-]+\[bot\]$")
BOT_EMAIL = re.compile(r"^(?:\d+\+)?[\w.\-]+\[bot\]@users\.noreply\.github\.com$")


def _authors(rev_range: str, pr_number: int) -> list[tuple[str, str]]:
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
        # A reviewer's own record-only commit for THIS pr (see module
        # docstring) is not an identity violation -- skip it before it
        # ever reaches the allow-list check below.
        if _is_record_only_commit(sha, pr_number):
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


def check(rev_range: str, pr_number: int = 0) -> list[str]:
    findings = []
    for name, email in _authors(rev_range, pr_number):
        if not _is_allowed(name, email):
            findings.append(f"{name} <{email}>")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="base ref, e.g. origin/main")
    parser.add_argument("--head", default="HEAD", help="head ref (default HEAD)")
    parser.add_argument(
        "--pr-number",
        type=int,
        default=0,
        help="PR number (0 = no PR context, record-only exemption never applies)",
    )
    args = parser.parse_args()

    rev_range = f"{args.base}..{args.head}" if args.base else "-500"
    findings = check(rev_range, args.pr_number)
    if findings:
        for f in findings:
            print(f"FAIL: commit author not LEAPWare or an allow-listed bot: {f}")
        return 1
    print("lwb-commit-identity check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
