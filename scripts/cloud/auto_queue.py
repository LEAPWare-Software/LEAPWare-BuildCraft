#!/usr/bin/env python3
"""Enqueue a pull request into the merge queue, from inside GitHub Actions.

WHY THIS EXISTS, AND WHY IT IS A WORKFLOW RATHER THAN A ROUTINE.

BuildCraft's ruleset requires the merge queue and `allow_auto_merge` is
false, so the only way to land a PR is the GraphQL mutation
`enqueuePullRequest`. A cloud routine cannot call it: **GraphQL is blocked
by the cloud proxy** -- measured by LEAPWare-ShellUX on 2026-09-19, and
the reason `gh pr create`, `gh pr merge`, `gh pr list` and `gh issue
comment` all fail there.

So until this workflow existed, BuildCraft's entire merge path required a
human's laptop. A cloud routine could do every piece of the work and then
be unable to land it. That is the single dependency that kept the product
tied to one machine.

A GitHub Actions job has no such problem: it runs INSIDE GitHub, so
nothing is proxied. See D27 in `docs/requirements/decisions.md`.

THE READINESS TEST, AND WHY IT IS SIMPLER THAN THE ONE SHELLUX USES.

ShellUX parses reviewer comments to decide whether a PR may land. We do
not need to, and parsing comments would be strictly worse here: this
repository's gates ALREADY ENCODE READINESS.

  * `lwb-lanes` fails unless the PR carries an independent review record
    under `reviews/<pr>/` whose `reviewer_id` differs from the commit
    author and whose `reviewer_was_dispatched_by_author` is false.
  * `lwb-proof-pr` fails unless the PR carries `proof/<pr>.json`.
  * the test matrix, the leak scan and the rest are required contexts.

So "every required check is green" already means "an independent reviewer
signed this and the evidence exists". Re-deriving that from comment text
would add a second, weaker source of truth that could disagree with the
first -- and a second place for it to rot. The gate is the evidence.

THE ENQUEUE IS PINNED TO A SPECIFIC COMMIT. If anything is pushed between
the check passing and this job running, the mutation fails rather than
landing an unreviewed head. The merge queue then re-runs every required
check before merging, so this job cannot land anything the ruleset would
refuse -- it can only ask.

WHAT THIS DELIBERATELY WILL NOT DO: it never merges directly, never
force-merges, never bypasses the queue, and never acts on a draft or a PR
whose checks are absent rather than green. An ABSENT check is not a
passing one; see `_all_required_checks_green`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

REPO = os.environ.get("LWB_REPO", "LEAPWare-Software/LEAPWare-BuildCraft")

# Exit codes, distinct so a caller can tell the outcomes apart. "Not ready"
# is NOT a failure -- it is the normal case on most runs.
EXIT_ENQUEUED = 0
EXIT_NOT_READY = 0
EXIT_ERROR = 1


def _run(args: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout, result.stderr


def _api(path: str) -> Optional[Any]:
    """REST GET via gh. Returns None on any failure -- callers must treat
    None as "could not check", never as "checked and found nothing"."""
    code, out, err = _run(["gh", "api", path])
    if code != 0:
        print(f"NOTICE: gh api {path} exited {code}: {err.strip()[:200]}")
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"NOTICE: gh api {path} returned non-JSON")
        return None


def required_contexts() -> Optional[List[str]]:
    """The contexts the branch ruleset actually requires.

    Read from the repository rather than hardcoded, because a hardcoded
    list silently stops protecting whatever is added to the ruleset later.
    Returns None if it cannot be determined -- which must block, not pass.
    """
    rules = _api(f"repos/{REPO}/rules/branches/main")
    if rules is None:
        return None
    contexts: List[str] = []
    for rule in rules:
        if rule.get("type") == "required_status_checks":
            params = rule.get("parameters") or {}
            for check in params.get("required_status_checks") or []:
                ctx = check.get("context")
                if ctx:
                    contexts.append(ctx)
    return contexts


def _all_required_checks_green(sha: str, required: List[str]) -> Tuple[bool, str]:
    """True only if every required context is present AND successful.

    An ABSENT check is not a passing one. This repository has documented
    eight instances of a check that was not running being mistaken for a
    check that was passing -- including an unparseable workflow that
    produced no run at all rather than a red one.
    """
    runs = _api(f"repos/{REPO}/commits/{sha}/check-runs?per_page=100")
    if runs is None:
        return False, "could not read check runs"

    by_name: Dict[str, str] = {}
    for run in runs.get("check_runs", []):
        name = run.get("name")
        if not name:
            continue
        status = run.get("status")
        conclusion = run.get("conclusion")
        by_name[name] = conclusion if status == "completed" else f"pending({status})"

    missing = [c for c in required if c not in by_name]
    if missing:
        return False, f"required checks absent (not merely failing): {', '.join(sorted(missing))}"

    bad = [f"{c}={by_name[c]}" for c in required if by_name[c] != "success"]
    if bad:
        return False, f"required checks not green: {', '.join(sorted(bad))}"

    return True, f"all {len(required)} required checks green"


def enqueue(pr_number: int, sha: str) -> bool:
    """Ask the merge queue to take this PR, pinned to `sha`.

    GraphQL works here because Actions runs inside GitHub. The same call
    from a cloud routine fails at the proxy, which is the whole reason
    this file exists.
    """
    node = _api(f"repos/{REPO}/pulls/{pr_number}")
    if node is None or "node_id" not in node:
        print("FAIL: could not read the pull request's node id")
        return False

    query = (
        "mutation($pr:ID!,$sha:GitObjectID!){"
        " enqueuePullRequest(input:{pullRequestId:$pr,expectedHeadOid:$sha})"
        " { mergeQueueEntry { position state } } }"
    )
    code, out, err = _run(
        [
            "gh", "api", "graphql",
            "-f", f"query={query}",
            "-f", f"pr={node['node_id']}",
            "-f", f"sha={sha}",
        ]
    )
    if code != 0:
        print(f"FAIL: enqueue rejected: {err.strip()[:400]}")
        return False
    print(f"ENQUEUED: #{pr_number} at {sha[:8]} -- {out.strip()[:200]}")
    return True


def main() -> int:
    pr_number_raw = os.environ.get("LWB_PR_NUMBER", "").strip()
    if not pr_number_raw.isdigit():
        print("FAIL: LWB_PR_NUMBER is not set to a number")
        return EXIT_ERROR
    pr_number = int(pr_number_raw)

    pr = _api(f"repos/{REPO}/pulls/{pr_number}")
    if pr is None:
        print("FAIL: could not read the pull request")
        return EXIT_ERROR

    if pr.get("state") != "open":
        print(f"NOT READY: #{pr_number} is {pr.get('state')}, not open")
        return EXIT_NOT_READY
    if pr.get("draft"):
        print(f"NOT READY: #{pr_number} is a draft")
        return EXIT_NOT_READY
    if pr.get("base", {}).get("ref") != "main":
        print(f"NOT READY: #{pr_number} does not target main")
        return EXIT_NOT_READY

    sha = pr.get("head", {}).get("sha")
    if not sha:
        print("FAIL: could not read the head sha")
        return EXIT_ERROR

    required = required_contexts()
    if required is None:
        print("FAIL: could not read the branch ruleset, so readiness cannot be determined")
        return EXIT_ERROR
    if not required:
        print("FAIL: the ruleset lists NO required checks -- refusing to enqueue on no evidence")
        return EXIT_ERROR

    green, why = _all_required_checks_green(sha, required)
    print(f"#{pr_number} at {sha[:8]}: {why}")
    if not green:
        return EXIT_NOT_READY

    return EXIT_ENQUEUED if enqueue(pr_number, sha) else EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
