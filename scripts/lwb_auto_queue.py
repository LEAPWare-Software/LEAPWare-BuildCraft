#!/usr/bin/env python3
"""`lwb-auto-queue`: decide, from inside GitHub Actions, whether a PR may enter
the merge queue -- and (only when armed) enqueue it.

WHY THIS EXISTS, AND WHY IT IS A WORKFLOW RATHER THAN A ROUTINE
--------------------------------------------------------------
This repository disables repo-level auto-merge and requires a merge queue, so
the only way in is the GraphQL mutation `enqueuePullRequest`
(`docs/maintainers/session-protocol.md`). A cloud routine cannot run it:
GraphQL is blocked by the cloud proxy, which is why `gh pr create`,
`gh pr merge`, `gh pr list` and `gh issue comment` all fail there.

A GitHub Actions job runs *inside* GitHub, so no proxy sits between it and the
API. That is the mechanical reason. The better reason is that the thing doing
the enqueue should be the thing that can already see the checks: an outside
caller has to ask, a workflow already knows.

Adapted from LEAPWare-ShellUX's `scripts/cloud/auto-queue.mjs`, NOT copied.
Three things differ, each measured against this repository:

  1. ShellUX calls `gh pr merge --squash --auto`. That CANNOT work here:
     this repo's `allow_auto_merge` is false, and `gh pr merge --squash`
     fails with "Auto merge is not allowed for this repository"
     (`docs/maintainers/session-protocol.md`). So the armed path is the
     `enqueuePullRequest` mutation instead.
  2. ShellUX's readiness test is a reviewer comment on the PR. This repo's
     merge gate is `proof/<pr>.json` plus an independent review record under
     `reviews/<pr>/`, so readiness is tested against those files at the PR
     head, not against a comment.
  3. Required checks are not hardcoded. They are read live from the branch
     ruleset, so this script cannot drift away from what actually gates main.

THIS SHIPS DISABLED. The enqueue is refused unless the repository variable
`LWB_AUTO_QUEUE` is exactly `armed`. That variable does not exist, so every
run is a dry run that prints its decision and changes nothing. Arming it is
the owner's action, after an audit.

WHAT THIS IS NOT. It is a scheduling convenience, not an integrity control.
Every routine posts under the owner's own login, and `reviewer_id` is a
self-attested string (D16, D20). This script can tell that a review record
exists, is `AGREE`, names a different identity and points at this exact head.
It cannot tell whether the identity was genuinely independent.

Usage:
  python scripts/lwb_auto_queue.py --probe
  python scripts/lwb_auto_queue.py --pr N [--expected-head SHA]

Exits 0 when it reached a decision (ready or not ready) and 1 only when it
could NOT decide -- an unreachable API, an unreadable record. "I could not
check" never shares an exit code with "I checked and found nothing".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO = os.environ.get("GITHUB_REPOSITORY", "LEAPWare-Software/LEAPWare-BuildCraft")

# The one switch that arms the mutation. Sourced from the repository variable
# `vars.LWB_AUTO_QUEUE`, which does not exist -- so the armed path is
# unreachable until the owner creates it deliberately.
ARM_VALUE = "armed"
ARM_ENV = "LWB_AUTO_QUEUE"

# Kept in step with scripts/lwb_lanes.py::REQUIRED_INDEPENDENT_REVIEWS. It is
# duplicated rather than imported because this script must run against a PR's
# records while the workflow has the DEFAULT branch checked out (see the
# workflow's comment on why it never checks out PR code), and a mismatch is
# caught by tests/test_lwb_auto_queue.py.
REQUIRED_INDEPENDENT_REVIEWS = 1

EXIT_DECIDED = 0
EXIT_COULD_NOT_CHECK = 1


class CouldNotCheck(Exception):
    """Raised when a fact needed for the decision could not be read at all."""


def _gh(args: list[str], *, allow_fail: bool = False) -> str:
    proc = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        if allow_fail:
            return ""
        raise CouldNotCheck(
            f"`gh {' '.join(args)}` exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()[:400]}"
        )
    return proc.stdout


def _gh_json(args: list[str]) -> object:
    raw = _gh(args)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise CouldNotCheck(f"`gh {' '.join(args)}` did not return JSON: {exc}") from exc


def _contents_json(path: str, ref: str) -> object | None:
    """Read a JSON file from the repo at `ref` over REST. None when absent.

    The content is parsed as DATA and never executed. That distinction is the
    whole reason the workflow can look at a pull request's files while running
    the default branch's code.
    """
    raw = _gh(
        ["api", f"repos/{REPO}/contents/{path}?ref={ref}", "--jq", ".content"],
        allow_fail=True,
    )
    if not raw.strip():
        return None
    import base64

    try:
        return json.loads(base64.b64decode(raw.strip()).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise CouldNotCheck(f"{path}@{ref} is not readable JSON: {exc}") from exc


def _list_dir(path: str, ref: str) -> list[str]:
    raw = _gh(
        ["api", f"repos/{REPO}/contents/{path}?ref={ref}", "--jq", ".[].name"],
        allow_fail=True,
    )
    return [line.strip() for line in raw.splitlines() if line.strip()]


# --------------------------------------------------------------------------
# readiness
# --------------------------------------------------------------------------


def required_contexts() -> list[str]:
    """The required status checks, read live from the branch ruleset."""
    rulesets = _gh_json(["api", f"repos/{REPO}/rulesets"])
    contexts: list[str] = []
    for entry in rulesets:  # type: ignore[union-attr]
        detail = _gh_json(["api", f"repos/{REPO}/rulesets/{entry['id']}"])
        for rule in detail.get("rules", []):  # type: ignore[union-attr]
            if rule.get("type") == "required_status_checks":
                params = rule.get("parameters", {})
                contexts += [
                    c["context"] for c in params.get("required_status_checks", [])
                ]
    if not contexts:
        raise CouldNotCheck(
            "no required_status_checks rule found in any ruleset -- refusing to "
            "treat 'no required checks' as 'all checks passed'"
        )
    return sorted(set(contexts))


def check_conclusions(sha: str) -> dict[str, str]:
    """Map check-name -> conclusion for a commit. Paginated."""
    raw = _gh(
        [
            "api",
            "--paginate",
            f"repos/{REPO}/commits/{sha}/check-runs?per_page=100",
            "--jq",
            ".check_runs[] | [.name, (.conclusion // \"pending\")] | @tsv",
        ]
    )
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if "\t" in line:
            name, conclusion = line.split("\t", 1)
            # Latest run for a name wins; the API returns newest first.
            out.setdefault(name.strip(), conclusion.strip())
    return out


def review_records(pr: int, head: str) -> tuple[int, list[str]]:
    """Count review records at `head` that satisfy the independence gate."""
    problems: list[str] = []
    names = _list_dir(f"reviews/{pr}", head)
    if not names:
        return 0, [f"no review records under reviews/{pr}/ at {head[:12]}"]
    good = 0
    for name in names:
        if not name.endswith(".json"):
            continue
        record = _contents_json(f"reviews/{pr}/{name}", head)
        if not isinstance(record, dict):
            problems.append(f"reviews/{pr}/{name} is not a JSON object")
            continue
        verdict = record.get("verdict")
        reviewer = str(record.get("reviewer_id", ""))
        author = str(record.get("commit_author_id", ""))
        reviewed = str(record.get("reviewed_commit", ""))
        if verdict != "AGREE":
            problems.append(f"reviews/{pr}/{name}: verdict is {verdict!r}, not AGREE")
            continue
        if not reviewer or reviewer == author:
            problems.append(
                f"reviews/{pr}/{name}: reviewer_id does not differ from commit_author_id"
            )
            continue
        if not head.startswith(reviewed):
            problems.append(
                f"reviews/{pr}/{name}: reviewed_commit {reviewed[:12]} is not this head"
            )
            continue
        good += 1
    return good, problems


def readiness(pr: int, expected_head: str | None) -> tuple[bool, str, list[str]]:
    """Return (ready, head_sha, reasons-it-is-not-ready)."""
    data = _gh_json(["api", f"repos/{REPO}/pulls/{pr}"])
    assert isinstance(data, dict)
    head = data["head"]["sha"]
    reasons: list[str] = []

    if data.get("state") != "open":
        reasons.append(f"PR is {data.get('state')}, not open")
    if data.get("draft"):
        reasons.append("PR is a draft")
    if data.get("base", {}).get("ref") != "main":
        reasons.append(f"PR targets {data.get('base', {}).get('ref')!r}, not main")
    if expected_head and expected_head != head:
        reasons.append(
            f"head moved: expected {expected_head[:12]}, found {head[:12]}"
        )

    conclusions = check_conclusions(head)
    for context in required_contexts():
        got = conclusions.get(context)
        if got is None:
            reasons.append(f"required check {context!r} has not reported")
        elif got != "success":
            reasons.append(f"required check {context!r} is {got}")

    proof = _contents_json(f"proof/{pr}.json", head)
    if proof is None:
        reasons.append(f"no proof record at proof/{pr}.json")
    elif not isinstance(proof, dict) or proof.get("pr") != pr:
        reasons.append(f"proof/{pr}.json does not declare pr == {pr}")
    elif proof.get("checked_by") == proof.get("author"):
        reasons.append(f"proof/{pr}.json is self-certified (checked_by == author)")

    good, problems = review_records(pr, head)
    reasons += problems
    if good < REQUIRED_INDEPENDENT_REVIEWS:
        reasons.append(
            f"{good} of {REQUIRED_INDEPENDENT_REVIEWS} independent review "
            f"record(s) satisfied at this head"
        )

    return (not reasons), head, reasons


# --------------------------------------------------------------------------
# the armed path, and the probe that stands in for it while disabled
# --------------------------------------------------------------------------


def enqueue(pr: int, head: str) -> None:
    """Enqueue the PR. Only ever reached when explicitly armed."""
    node_id = _gh(
        [
            "api",
            "graphql",
            "-f",
            "query=query($o:String!,$n:String!,$p:Int!){repository(owner:$o,name:$n)"
            "{pullRequest(number:$p){id}}}",
            "-F",
            f"o={REPO.split('/')[0]}",
            "-F",
            f"n={REPO.split('/')[1]}",
            "-F",
            f"p={pr}",
            "--jq",
            ".data.repository.pullRequest.id",
        ]
    ).strip()
    if not node_id:
        raise CouldNotCheck("could not resolve the pull request node id")
    out = _gh(
        [
            "api",
            "graphql",
            "-f",
            "query=mutation($id:ID!,$head:GitObjectID!){enqueuePullRequest(input:"
            "{pullRequestId:$id,expectedHeadOid:$head}){mergeQueueEntry{position state}}}",
            "-F",
            f"id={node_id}",
            "-F",
            f"head={head}",
        ]
    )
    print(f"ENQUEUED: {out.strip()}")


def probe() -> int:
    """Report what this runner can actually reach. Writes nothing.

    This exists because the disabled state means the mutation itself is never
    executed, so the claim "the merge path works from Actions" would otherwise
    rest on nothing. The probe measures every step of that path except the
    mutation, and says plainly that the mutation is the unmeasured one.
    """
    print(f"repo: {REPO}")
    ok = True

    try:
        login = _gh(["api", "user", "--jq", ".login"]).strip()
        print(f"REST  ok   : authenticated as {login or '(app token, no user)'}")
    except CouldNotCheck as exc:
        print(f"REST  note : {exc}")

    try:
        contexts = required_contexts()
        print(f"REST  ok   : {len(contexts)} required check(s) read from the ruleset")
        for c in contexts:
            print(f"             - {c}")
    except CouldNotCheck as exc:
        ok = False
        print(f"REST  FAIL : {exc}")

    try:
        out = _gh(
            [
                "api",
                "graphql",
                "-f",
                "query=query{viewer{login}}",
                "--jq",
                ".data.viewer.login",
            ]
        ).strip()
        print(f"GQL   ok   : graphql reachable from this runner (viewer={out or 'n/a'})")
    except CouldNotCheck as exc:
        ok = False
        print(f"GQL   FAIL : {exc}")

    try:
        out = _gh(
            [
                "api",
                "graphql",
                "-f",
                "query=query{__type(name:\"Mutation\"){fields{name}}}",
                "--jq",
                '[.data.__type.fields[].name] | index("enqueuePullRequest")',
            ]
        ).strip()
        found = out not in ("", "null")
        print(
            f"GQL   {'ok   ' if found else 'FAIL '}: enqueuePullRequest mutation "
            f"{'present' if found else 'NOT present'} in the schema this token sees"
        )
        ok = ok and found
    except CouldNotCheck as exc:
        ok = False
        print(f"GQL   FAIL : {exc}")

    print(
        "UNMEASURED : the enqueuePullRequest mutation is never executed by a "
        "probe. Reaching the schema is not the same as being permitted to "
        "enqueue, and this script does not claim it is."
    )
    return EXIT_DECIDED if ok else EXIT_COULD_NOT_CHECK


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", type=int, help="pull request number")
    parser.add_argument("--expected-head", help="refuse to act if the head moved")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="report what this runner can reach; decide nothing, write nothing",
    )
    args = parser.parse_args()

    if args.probe:
        return probe()
    if not args.pr:
        print("nothing to do: no --pr and no --probe")
        return EXIT_DECIDED

    try:
        ready, head, reasons = readiness(args.pr, args.expected_head)
    except CouldNotCheck as exc:
        print(f"COULD NOT CHECK: {exc}")
        return EXIT_COULD_NOT_CHECK

    print(f"PR #{args.pr} at {head}")
    if ready:
        print("READY: every required check is green and the merge gate is satisfied")
    else:
        print("NOT READY:")
        for reason in reasons:
            print(f"  - {reason}")

    armed = os.environ.get(ARM_ENV, "") == ARM_VALUE
    if not armed:
        print(
            f"DRY RUN: {ARM_ENV} is not {ARM_VALUE!r}, so nothing was enqueued. "
            "This is the shipped state."
        )
        return EXIT_DECIDED
    if not ready:
        return EXIT_DECIDED
    try:
        enqueue(args.pr, head)
    except CouldNotCheck as exc:
        print(f"COULD NOT CHECK: {exc}")
        return EXIT_COULD_NOT_CHECK
    return EXIT_DECIDED


if __name__ == "__main__":
    sys.exit(main())
