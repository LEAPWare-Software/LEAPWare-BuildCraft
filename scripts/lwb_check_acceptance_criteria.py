#!/usr/bin/env python3
r"""CI check `lwb-acceptance-criteria`: acceptance criteria must predate work.

Quality-floor item 1, closed by D24 (`docs/requirements/decisions.md`):
*"nothing records or timestamps acceptance criteria before work starts --
so it is verified by the reviewer reading the PR's own chronology. Closing
that is required work, not an accepted gap."* Every other floor item grades
work AFTER the fact; this is the one item that stops an agent choosing the
target after seeing where the arrow landed, and D24's own analysis is that
every evidence source we control can be forged -- a committed file, a git
commit timestamp, commit order, an agent's own attestation. THE DECISION:
*"work starts with a GitHub issue stating what done means, and the gate
compares GitHub's own creation timestamp against the first commit of the
deliverable. We cannot forge GitHub's clock. The evidence is external by
construction."* This script is that gate, run at CI time (never at hook
time -- it needs `gh`/network, which `approach.md` section 8 and D17
forbid the `PreToolUse` hook boundary from touching).

D24 named two design gaps and refused to hand-wave them: *"Not yet
designed, and not to be hand-waved when it is: what counts as 'the first
commit of a deliverable' when a branch is merged forward or a deliverable
spans branches; and what happens to work that legitimately begins before
its scope is known. Both need answering before the rule is written, and
neither is answered here."* This script answers both.

## Gap 1: "the first commit of a deliverable" when a branch is merged forward

**Answer: the earliest entry in `git log --first-parent <base>..<head>
--reverse --format=%H`.**

`<base>..<head>` alone (no `--first-parent`) already excludes every commit
reachable from `<base>` -- that is ordinary git range semantics, nothing
`--first-parent` adds. So this repo's own recurring pattern -- a
conductor routine merging `origin/main` forward into a deliverable branch
to resolve a conflict, something its own PR history (see PR #58, #51, #62
comments) does constantly -- causes no confusion on that count alone:
`origin/main`'s own commits, wherever `origin/main` has since moved to,
are reachable from `<base>` and never appear as range members, merged
forward or not.

What plain `git log <base>..<head> --reverse` (no `--first-parent`) gets
wrong is different, and it is exactly what this repo's own
`resolve_reviewable_head` in `scripts/lwb_lanes.py` already had to fix
once (its own `--first-parent` correction, tracked as this repo's PR
#63, superseding a gap PR #56 left open): a merge commit has TWO parents,
and plain `git log` walks BOTH -- the mainline the merge landed on AND
whatever was merged in -- in commit-DATE order, not branch-topology
order. A genuine side branch created and merged WITHIN the deliverable
(not `origin/main` forward-merged in, but a feature branch the deliverable
itself merges) leaves commits in the `<base>..<head>` range that are not
on the deliverable's own mainline at all, and if that side branch's
commits happen to carry an earlier author/commit date than the
deliverable's true first commit -- entirely possible, since dates are
whatever the machine that made them says -- plain date-ordered traversal
can present the side commit as "first" under `--reverse`. `--first-parent`
closes this the same way it closed it in `resolve_reviewable_head`: it
walks only the mainline parent at every step, so the walk never descends
into a side branch's own history at all, and the earliest entry after
`--reverse` is therefore the deliverable branch's own true first commit,
regardless of what any side branch's commit dates say. Reused here rather
than rediscovered, per that PR's own reasoning.

The one case this does not and cannot cover, said plainly rather than
hand-waved: a deliverable whose FIRST real commit is itself a side-branch
merge (i.e. the very start of the work was assembled from a branch made
before the tracking issue existed and merged in as the opening act). No
git-log shape distinguishes that from an honest merge later in the same
branch's life; disambiguating it needs authorial intent, not topology.

## Gap 2: work that legitimately begins before its scope is known

**Answer: `docs/requirements/acceptance_exempt.json`,** a small,
append-only, reviewed list. Real work sometimes has to start (a spike, an
incident fix, a scoping investigation) before an issue can be written
naming what "done" means for it -- D24 accepts that cost explicitly
("every deliverable opens with an issue, every time, with no exception
that can be argued into existence later") while still needing a release
valve for the honest case, or the very first time it is hit, the rule
gets bypassed by force rather than by a reviewable exception. Each entry
matches a PR number or a branch name (or both -- see below) and carries a
non-empty `reason`; a match is reported `EXEMPT`, never `FAIL`, regardless
of whether an issue is even linked. The file ships with zero entries.
Adding one is a shared-path change under this repo's own review discipline
(`CLAUDE.md`) -- a visible, reviewable act, not a silent opt-out, which is
the same design this repo already uses for `proof/exempt.json`.

## What this script does, in order

1. Loads and validates `docs/requirements/acceptance_exempt.json`. A
   malformed entry (both `pr` and `branch` null, a missing/empty `reason`,
   wrong types) is a loud `CONFIG_ERROR` -- never silently ignored, and
   never treated as "no exemptions".
2. Checks whether `--pr`/the resolved branch name matches an exemption.
   A match is reported `EXEMPT` immediately, before anything else runs --
   an exemption is a blanket opt-out, so it does not matter whether the
   commit range or `gh` would even resolve.
3. Resolves the deliverable's first commit per Gap 1 above. `--base` not
   resolvable, `--head` not resolvable, or the resolved range containing
   zero commits (including `--base` and `--head` resolving to the same
   commit) is `NO_RANGE` -- distinct from both `PASS` and `FAIL`, because
   "nothing to check" is not the same claim as either.
4. Fetches the PR body via `gh api repos/{owner}/{repo}/pulls/{pr}` (REST
   only -- this proxy environment blocks GraphQL, exactly like the rest of
   this repo's tooling) and searches it, case-insensitively, for GitHub's
   standard closing-keyword syntax: `(close[sd]?|fix(es|ed)?|resolve[sd]?)
   \s+#(\d+)`. The first match wins; no match is `NO_ISSUE_REFERENCE`
   (a `FAIL` variant, since the deliverable is not exempted at this point).
5. Fetches the linked issue via `gh api repos/{owner}/{repo}/issues/{n}`
   for its `created_at`, and compares it against the first commit's AUTHOR
   date (`git log -1 --format=%aI`, not commit date, which a rebase can
   change without the author's knowledge). Issue timestamp <= first-commit
   timestamp is `PASS`; issue timestamp after the first commit is `FAIL`,
   naming both timestamps and the gap.
6. Any `gh` failure at any point -- missing executable, timeout, non-zero
   exit for any reason -- is `UNVERIFIABLE`, distinctly, never folded into
   a pass or a fail.

## Deliberately NOT distinguished: why a `gh` 404 and a network failure
report the same `UNVERIFIABLE`

`gh api` exits non-zero for a missing PR/issue exactly as it does for an
expired token, no network, or a rate limit. This script does not try to
tell those apart by pattern-matching `gh`'s stderr text -- that is exactly
the brittle, ad-hoc string-sniffing this repo's own gates
(`lwb_check_state_claims.py`'s "KNOWN EVASIONS" section) have learned not
to lean on for anything that matters. Every `gh` failure, whatever its
cause, is `UNVERIFIABLE` with the raw `gh` stderr printed alongside it, so
a human reading the CI log can tell the difference even though the script
itself does not try to.

`--pr` not given at all (and the deliverable not exempted) is a DIFFERENT
thing from a `gh` failure and is reported as `CONFIG_ERROR`, not
`UNVERIFIABLE`: it is an operator/wiring problem this invocation controls
(the caller did not pass a PR number), not GitHub's clock failing to
answer -- folding the two together would hide a broken CI wiring behind
the same label this script uses for "GitHub was unreachable".

## A known, already-documented CI limitation this script inherits rather
than fixes

Every step in `.github/workflows/ci.yml` that already calls `gh`
(`lwb-check-state-claims`, `lwb-proof-pr`, `lwb-proof-reexecute`) sets no
`GH_TOKEN`/`GITHUB_TOKEN` at all -- checked directly against the live
file, not assumed. `docs/maintainers/proof-of-completion-plan.md` already
names the consequence for the state-claims gate: *"CI stayed green only
because the runner's gh is unauthenticated."* This script's own CI step
matches that existing convention exactly rather than quietly fixing it on
the side (repo-wide `gh` auth in CI is a shared-path change of its own,
orthogonal to this deliverable, and needs its own review) -- so, as wired
today, this step will very likely report `UNVERIFIABLE` on every real PR
run until that separate gap is closed. It is still worth shipping
report-only: the plumbing, the exemption mechanism, and the comparison
logic are all real and independently testable, and a wired but
currently-`UNVERIFIABLE` gate is the honest, visible state to ship rather
than a silently-never-armed one.

## HONEST SCOPE -- what this does NOT check

- **Only a linked GitHub issue counts.** A requirements doc, a Slack
  thread, or a design note written before work started is not detected;
  D24's own decision is specifically to anchor on GitHub's clock, so
  anything not on GitHub is out of scope by design, not by oversight.
- **The issue's TEXT is never read.** A one-line placeholder issue passes
  exactly as well as a fully-specified one -- this checks WHEN acceptance
  criteria were recorded, never WHETHER they are any good. That judgement
  is a reviewer's job, not a script's.
- **Report-only.** This ships warn/report-only, per D9 (a judgement about
  whether a PR body's closing-keyword match is the RIGHT issue, or whether
  an exemption's reason is honest, is exactly the kind of call D9 reserves
  for a human, not a fact a script can certify) and per this repo's own
  discipline of landing a new gate quiet before arming it (see
  `core/lwb_core/rules/lwb_proof_required.py`'s docstring, "Ship quiet,
  collect evidence from the ledger, then arm"). Arming this to block is a
  deliberate, separate follow-up, not attempted here.
- **A single closing-keyword match is trusted as-is.** GitHub itself
  requires the keyword to sit in the PR/issue's DEFAULT branch base for
  the auto-close behaviour to fire; this script does not replicate that
  additional constraint and matches the pattern anywhere in the body.

Usage:
    python scripts/lwb_check_acceptance_criteria.py --pr <N>
        [--base origin/main] [--head HEAD] [--branch <name>]
        [--repo-path .] [--gh-repo OWNER/REPO]

Stdlib only. Prints one `OUTCOME: message` line and returns one of six
exit codes -- see `ACCEPTANCE_EXIT_*` below -- never a plain boolean.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

DEFAULT_GH_REPO = "LEAPWare-Software/LEAPWare-BuildCraft"
EXEMPT_RELATIVE_PATH = Path("docs") / "requirements" / "acceptance_exempt.json"

GH_TIMEOUT_SECONDS = 20

# ---------------------------------------------------------------------------
# Exit codes. Mirrors scripts/lwb_check_proof.py's REEXECUTE_EXIT_* pattern:
# distinct constants for distinct claims, never a single boolean. Per the
# brief this implements ("mirror the pattern: 0 for pass/exempt, non-zero
# and DISTINCT for each other outcome"), PASS and EXEMPT share exit code 0
# -- neither should ever block a merge -- but the printed OUTCOME tag still
# distinguishes them textually (see Outcome below), because "acceptance
# criteria were verified" and "this deliverable opted out of verification"
# are different claims even when neither should fail a build.
# ---------------------------------------------------------------------------
ACCEPTANCE_EXIT_PASS = 0
ACCEPTANCE_EXIT_FAIL = 1
ACCEPTANCE_EXIT_UNVERIFIABLE = 2
ACCEPTANCE_EXIT_NO_RANGE = 3
ACCEPTANCE_EXIT_CONFIG_ERROR = 4


class Outcome(str, Enum):
    PASS = "PASS"
    EXEMPT = "EXEMPT"
    FAIL = "FAIL"
    NO_ISSUE_REFERENCE = "NO_ISSUE_REFERENCE"
    UNVERIFIABLE = "UNVERIFIABLE"
    NO_RANGE = "NO_RANGE"
    CONFIG_ERROR = "CONFIG_ERROR"


_OUTCOME_EXIT_CODE: dict[Outcome, int] = {
    Outcome.PASS: ACCEPTANCE_EXIT_PASS,
    Outcome.EXEMPT: ACCEPTANCE_EXIT_PASS,
    Outcome.FAIL: ACCEPTANCE_EXIT_FAIL,
    Outcome.NO_ISSUE_REFERENCE: ACCEPTANCE_EXIT_FAIL,
    Outcome.UNVERIFIABLE: ACCEPTANCE_EXIT_UNVERIFIABLE,
    Outcome.NO_RANGE: ACCEPTANCE_EXIT_NO_RANGE,
    Outcome.CONFIG_ERROR: ACCEPTANCE_EXIT_CONFIG_ERROR,
}


@dataclass
class Result:
    outcome: Outcome
    message: str

    @property
    def exit_code(self) -> int:
        return _OUTCOME_EXIT_CODE[self.outcome]

    def render(self) -> str:
        return f"{self.outcome.value}: {self.message}"


# GitHub's own closing-keyword syntax (case-insensitive; the first match in
# the body wins on multiple matches, per this script's brief).
_CLOSING_KEYWORD_RE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?)\s+#(\d+)"
)


# ---------------------------------------------------------------------------
# git helpers -- every one takes `repo: Path` explicitly (never a module-
# level REPO_ROOT constant) so a test can point this at a throwaway tmp_path
# repo exactly the way tests/test_lwb_check_state_claims.py and
# tests/test_lwb_lanes.py do, with no monkeypatching of module globals.
# ---------------------------------------------------------------------------


def _run_git(argv: list[str], repo: Path) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", *argv],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _rev_parse(repo: Path, ref: str) -> str | None:
    result = _run_git(["rev-parse", ref], repo)
    if result is None or result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def _first_parent_commits(repo: Path, base_sha: str, head_sha: str) -> list[str] | None:
    """The `--first-parent` walk this whole script is built around -- see
    the module docstring's "Gap 1" section for why this flag, and not plain
    `git log base..head`, is the correct tool."""
    result = _run_git(
        ["log", "--first-parent", f"{base_sha}..{head_sha}", "--reverse", "--format=%H"],
        repo,
    )
    if result is None or result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line.strip()]


def _commit_author_date(repo: Path, sha: str) -> str | None:
    result = _run_git(["log", "-1", "--format=%aI", sha], repo)
    if result is None or result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def _current_branch(repo: Path) -> str | None:
    """The branch name for `acceptance_exempt.json`'s `branch` matching.

    `$GITHUB_HEAD_REF` first -- GitHub Actions sets this on `pull_request`
    events to the PR's real branch name, which is what an author actually
    wrote into the exemption file; the checkout itself is typically a
    detached synthetic merge ref, so asking git directly would answer
    'HEAD' (nothing) in exactly the CI context this matters most in. Falls
    back to `git rev-parse --abbrev-ref HEAD` for local/non-Actions use,
    and to None (no branch-based match attempted) if that also resolves to
    a detached 'HEAD'."""
    env_branch = os.environ.get("GITHUB_HEAD_REF")
    if env_branch:
        return env_branch
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    if result is None or result.returncode != 0:
        return None
    name = result.stdout.strip()
    if not name or name == "HEAD":
        return None
    return name


def resolve_first_commit(
    repo: Path, base: str, head: str
) -> tuple[str | None, str | None, Result | None]:
    """Resolve the deliverable's first commit and its author date.

    Returns `(first_commit_sha, first_commit_author_date_iso, None)` on
    success, or `(None, None, Result(Outcome.NO_RANGE, ...))` naming
    exactly why -- `--base` unresolvable, `--head` unresolvable, or the
    resolved range containing zero commits (including `--base` and
    `--head` resolving to the same commit) -- per this script's brief:
    "a DISTINCT, clearly named outcome, never silently PASS or silently
    FAIL."
    """
    base_sha = _rev_parse(repo, base)
    if base_sha is None:
        return None, None, Result(
            Outcome.NO_RANGE, f"--base {base!r} does not resolve in this repository"
        )
    head_sha = _rev_parse(repo, head)
    if head_sha is None:
        return None, None, Result(
            Outcome.NO_RANGE, f"--head {head!r} does not resolve in this repository"
        )
    if base_sha == head_sha:
        return None, None, Result(
            Outcome.NO_RANGE,
            f"--base and --head both resolve to {base_sha} -- the range is empty, "
            "nothing to check",
        )
    commits = _first_parent_commits(repo, base_sha, head_sha)
    if commits is None:
        return None, None, Result(
            Outcome.NO_RANGE,
            f"'git log --first-parent {base_sha}..{head_sha}' could not be run",
        )
    if not commits:
        return None, None, Result(
            Outcome.NO_RANGE,
            f"the first-parent range {base_sha}..{head_sha} contains no commits -- "
            "nothing to check",
        )
    first_sha = commits[0]
    author_date = _commit_author_date(repo, first_sha)
    if author_date is None:
        return None, None, Result(
            Outcome.NO_RANGE,
            f"could not read the author date of first commit {first_sha}",
        )
    return first_sha, author_date, None


# ---------------------------------------------------------------------------
# docs/requirements/acceptance_exempt.json
# ---------------------------------------------------------------------------


def load_exemptions(repo: Path) -> tuple[list[dict] | None, str | None]:
    """Load and validate `docs/requirements/acceptance_exempt.json`.

    Returns `(entries, None)` on success (an empty list if the file is
    missing entirely, matching "ships with zero entries" -- a repo that
    simply hasn't added the file yet is not a config error), or
    `(None, reason)` for ANY malformed entry -- rejected loudly, never
    silently dropped or silently treated as "no exemptions", per this
    script's brief.
    """
    path = repo / EXEMPT_RELATIVE_PATH
    if not path.is_file():
        return [], None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"{EXEMPT_RELATIVE_PATH}: could not be read: {exc}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{EXEMPT_RELATIVE_PATH}: not valid JSON: {exc}"
    if not isinstance(data, list):
        return None, (
            f"{EXEMPT_RELATIVE_PATH}: top-level JSON must be an array, "
            f"got {type(data).__name__}"
        )

    validated: list[dict] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            return None, f"{EXEMPT_RELATIVE_PATH}[{i}]: entry must be an object"
        pr = entry.get("pr")
        branch = entry.get("branch")
        reason = entry.get("reason")
        if pr is not None and (isinstance(pr, bool) or not isinstance(pr, int)):
            return None, f"{EXEMPT_RELATIVE_PATH}[{i}]: 'pr' must be an integer or null, got {pr!r}"
        if branch is not None and not (isinstance(branch, str) and branch):
            return None, (
                f"{EXEMPT_RELATIVE_PATH}[{i}]: 'branch' must be a non-empty string or null, "
                f"got {branch!r}"
            )
        if pr is None and branch is None:
            return None, (
                f"{EXEMPT_RELATIVE_PATH}[{i}]: both 'pr' and 'branch' are null -- an "
                "exemption must match something"
            )
        if not isinstance(reason, str) or not reason.strip():
            return None, f"{EXEMPT_RELATIVE_PATH}[{i}]: 'reason' must be a non-empty string, got {reason!r}"
        validated.append({"pr": pr, "branch": branch, "reason": reason})
    return validated, None


def _find_exemption(
    exemptions: list[dict], pr_number: int | None, branch: str | None
) -> dict | None:
    for entry in exemptions:
        if entry["pr"] is not None and pr_number is not None and entry["pr"] == pr_number:
            return entry
        if entry["branch"] is not None and branch is not None and entry["branch"] == branch:
            return entry
    return None


# ---------------------------------------------------------------------------
# gh
# ---------------------------------------------------------------------------


def _gh_api_json(path: str, *, timeout: int = GH_TIMEOUT_SECONDS) -> tuple[dict | None, str | None]:
    """Run `gh api <path>` and parse the JSON response.

    Returns `(data, None)` on success, or `(None, reason)` for ANY
    failure -- missing executable, timeout, non-zero exit (auth, network,
    404, rate limit -- deliberately not distinguished; see the module
    docstring). `reason` always carries `gh`'s own stderr verbatim so a
    human reading CI output can tell the difference even though this
    function does not try to.
    """
    try:
        result = subprocess.run(
            ["gh", "api", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, "the 'gh' executable is not installed on this machine"
    except subprocess.TimeoutExpired:
        return None, f"'gh api {path}' timed out after {timeout}s"
    if result.returncode != 0:
        stderr = result.stderr.strip() or "(no stderr captured)"
        return None, f"'gh api {path}' exited {result.returncode}: {stderr}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"'gh api {path}' did not return valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, f"'gh api {path}' returned a JSON {type(data).__name__}, not an object"
    return data, None


def find_closing_issue(pr_body: str) -> int | None:
    """The issue number of the FIRST GitHub closing-keyword match in
    `pr_body`, or None if there is none. Multiple matches: the first one
    (by position in the text) wins, per this script's brief."""
    match = _CLOSING_KEYWORD_RE.search(pr_body or "")
    return int(match.group(1)) if match else None


def _parse_iso8601(value: str) -> datetime:
    """Parse a `git log %aI` or GitHub API `created_at` timestamp.

    Both are ISO 8601 with a timezone; GitHub's own form ends in a literal
    `Z`, which `datetime.fromisoformat` only accepts natively from Python
    3.11 -- this repo's CI matrix (`.github/workflows/ci.yml`) still runs
    3.10, so the trailing `Z` is rewritten to `+00:00` by hand rather than
    relying on a stdlib behaviour this repo does not yet require."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no timezone offset")
    return dt


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------


def check_acceptance_criteria(
    *,
    repo: Path,
    base: str,
    head: str,
    pr_number: int | None,
    branch: str | None,
    gh_repo: str,
) -> Result:
    exemptions, exempt_error = load_exemptions(repo)
    if exempt_error is not None:
        return Result(Outcome.CONFIG_ERROR, exempt_error)

    matched = _find_exemption(exemptions, pr_number, branch)
    if matched is not None:
        which = (
            f"pr={matched['pr']}" if matched["pr"] is not None else f"branch={matched['branch']!r}"
        )
        return Result(
            Outcome.EXEMPT,
            f"exempted in {EXEMPT_RELATIVE_PATH} ({which}): {matched['reason']}",
        )

    if pr_number is None:
        return Result(
            Outcome.CONFIG_ERROR,
            "no --pr given and this deliverable is not exempted -- cannot look up a "
            f"linked issue without a PR number to fetch the PR body from (see "
            f"{EXEMPT_RELATIVE_PATH} for the legitimate way to skip this check)",
        )

    first_sha, first_author_date, range_result = resolve_first_commit(repo, base, head)
    if range_result is not None:
        return range_result

    pr_data, gh_error = _gh_api_json(f"repos/{gh_repo}/pulls/{pr_number}")
    if gh_error is not None:
        return Result(Outcome.UNVERIFIABLE, f"could not fetch PR #{pr_number}: {gh_error}")

    body = pr_data.get("body") or ""
    issue_number = find_closing_issue(body)
    if issue_number is None:
        return Result(
            Outcome.NO_ISSUE_REFERENCE,
            f"PR #{pr_number}'s body names no GitHub closing keyword "
            "(close[sd]?/fix(es|ed)?/resolve[sd]? #N) -- D24 requires a linked issue "
            f"whose creation timestamp anchors when work started, and this deliverable "
            f"is not listed in {EXEMPT_RELATIVE_PATH}",
        )

    issue_data, gh_error = _gh_api_json(f"repos/{gh_repo}/issues/{issue_number}")
    if gh_error is not None:
        return Result(
            Outcome.UNVERIFIABLE,
            f"PR #{pr_number} references issue #{issue_number}, but it could not be "
            f"fetched: {gh_error}",
        )

    issue_created_raw = issue_data.get("created_at")
    if not issue_created_raw:
        return Result(
            Outcome.UNVERIFIABLE,
            f"issue #{issue_number} carries no 'created_at' in the gh api response",
        )

    try:
        issue_created = _parse_iso8601(issue_created_raw)
        commit_authored = _parse_iso8601(first_author_date)
    except ValueError as exc:
        return Result(Outcome.UNVERIFIABLE, f"could not parse a timestamp for comparison: {exc}")

    gap = abs(commit_authored - issue_created)
    if issue_created <= commit_authored:
        return Result(
            Outcome.PASS,
            f"issue #{issue_number} created {issue_created_raw}, first commit {first_sha} "
            f"authored {first_author_date} ({gap} later) -- acceptance criteria existed "
            "before work started",
        )
    return Result(
        Outcome.FAIL,
        f"issue #{issue_number} created {issue_created_raw}, AFTER first commit "
        f"{first_sha}'s author date {first_author_date} (issue postdates the first "
        f"commit by {gap}) -- acceptance criteria did not exist before work started",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="origin/main", help="base ref (default: origin/main)")
    parser.add_argument("--head", default="HEAD", help="head ref (default: HEAD)")
    parser.add_argument(
        "--pr",
        dest="pr_number",
        type=int,
        default=None,
        help="the PR number whose body is searched for a closing-keyword issue reference",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help=(
            "branch name for docs/requirements/acceptance_exempt.json 'branch' matching "
            "(default: $GITHUB_HEAD_REF, else the local repo's current branch)"
        ),
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        dest="repo_path",
        help="local git repository root (default: current directory)",
    )
    parser.add_argument(
        "--gh-repo",
        default=DEFAULT_GH_REPO,
        help="owner/repo slug for gh api calls (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo_path).resolve()
    branch = args.branch if args.branch is not None else _current_branch(repo)

    result = check_acceptance_criteria(
        repo=repo,
        base=args.base,
        head=args.head,
        pr_number=args.pr_number,
        branch=branch,
        gh_repo=args.gh_repo,
    )
    print(result.render())
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
