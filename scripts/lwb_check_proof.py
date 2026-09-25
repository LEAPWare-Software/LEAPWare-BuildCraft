#!/usr/bin/env python3
"""CI check `lwb-proof`: every proof/*.json record is well-formed.

Owner directive 7: Proof of Completion on every deliverable. This script
validates every `proof/*.json` file against the shape `proof/schema.json`
documents (a hand-rolled check, not a `jsonschema` dependency — stdlib
only, per the hard rules) plus structural checks a JSON Schema alone
cannot express:

  - `checked_by` must differ from `author` (no self-certified proof).
  - every `commands[]` entry's `exit` must equal its `expect_exit`.
  - `sha256` must look like a real sha256 hex digest (64 hex chars).
  - `commit` must look like a real git SHA (7-40 hex chars).

See proof/README.md for the full record shape and why.

Usage:
    python scripts/lwb_check_proof.py

Stdlib only. Exits 0 and prints "lwb-proof check passed" (or a skipped
message if proof/ has no records) on success; otherwise prints every
failure found (not just the first) and exits 1.

`--reexecute` mode has its own four-way exit contract (REEXECUTE_EXIT_*
below), because "everything checked passed" is not the same claim as
"zero of N commands were even checked", and neither of those is the same
claim as "some digests could not be compared at all":

    0  ALL_MATCHED         every re-executed command matched.
    1  MISMATCH            at least one re-executed command's digest or
                            exit code did not match the record, OR a
                            record contained a malformed `commands[]`
                            entry (missing/non-list/empty/non-string
                            `argv`) that could not be launched at all, OR
                            a re-executed command exceeded its timeout, OR
                            a command's argv resolves to this script
                            itself while marked `verifiable: true` (a
                            self-referencing command may only be
                            legitimately skipped as `verifiable: false`
                            with an enum reason -- pairing self-reference
                            with `verifiable: true` used to be a silent
                            opt-out and is now a failure).
    2  NOTHING_REEXECUTED  zero commands were re-executed (everything was
                            skipped as self-referencing, opted out with
                            `verifiable: false`, or there were no records
                            at all) -- NOT a pass.
    3  UNCOMPARABLE        no MISMATCH occurred, but at least one command's
                            `sanitiser_version` differed from the running
                            `lwb_sanitise.SANITISER_VERSION`, so its digest
                            could not be attributed to a known sanitiser and
                            was never compared.

PRECEDENCE, explicit because two of these can be true in the same run:
MISMATCH (1) always wins over UNCOMPARABLE (3). A digest that is known to
be WRONG is a worse finding than one that could not be checked at all, and
reporting the milder of the two when both are present would hide the
worse one behind it. UNCOMPARABLE, in turn, wins over both ALL_MATCHED and
NOTHING_REEXECUTED: one real pass sitting next to a sanitiser-version-
drifted command must never print the success summary or exit 0 -- a
sanitiser version bump must never silently disable this gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROOF_DIR = REPO_ROOT / "proof"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lwb_sanitise  # noqa: E402

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")

REQUIRED_TOP = ("deliverable", "author", "checked_by", "commit", "commands", "mutations", "unproven")
REQUIRED_COMMAND = ("argv", "exit", "expect_exit", "tail", "sha256")


def _authoritative_pr_from_filename(path: Path):
    """The PR number this record's own FILENAME claims, or None.

    `reviews/<pr>/<file>.json` derives its authoritative PR number from the
    DIRECTORY the record is found under, never from the record's own
    content -- see `lwb_lanes.py::_review_ok`, which exists precisely
    because a record used to be trusted about its own `pr` field and a
    mismatched one went unnoticed. `proof/` has no per-PR directory, but
    this repo's own convention names every PR-tied record after its PR
    number (`7.json` .. `19.json`), so a bare-digit filename stem is
    *compared* against the record's own claim the same way.

    Read that comparison for what it actually is, though: for a file that
    ALREADY EXISTED before this PR, the filename genuinely is external to
    whatever a later edit claims (catches a stale/careless edit). For a
    BRAND NEW file, the filename is exactly as attacker-controlled as the
    `pr` field it is being compared against -- both are written by the
    same author in the same commit. Adversarial review confirmed two
    concrete bypasses this function alone does not catch: a slug-named
    file (`sneaky-slug.json` declaring an old `pr`) and a SELF-CONSISTENT
    fabricated digit filename (`007.json` declaring `"pr": 7` to match).
    This function catches an INCONSISTENT lie, never a self-consistent
    one -- it raises the cost of a careless mismatch, it does not detect
    deliberate, self-consistent fabrication. See
    `check_new_proof_records_declare_pr` for the check that closes that
    gap where a genuinely external number exists (CI, on a `pull_request`
    run) and the honest statement of what happens where it does not.

    Returns `None` for a non-digit stem -- `schema.json` documents
    `deliverable` as "an issue/step number or a short slug", so a
    slug-named file is ordinary and carries no filename-derived authority
    either way.
    """
    stem = path.stem
    return int(stem) if stem.isdigit() else None


def _validate_record(path: Path, data: object) -> list[str]:
    errors: list[str] = []
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        # Not under REPO_ROOT (e.g. a test's own tmp_path proof/ directory,
        # or lwb_handoff.py's PROOF_DIR monkeypatched for a test) -- fall
        # back to the path as given rather than raising; this function's
        # job is validating shape, not enforcing where the file lives.
        rel = path

    if not isinstance(data, dict):
        return [f"{rel}: top-level JSON must be an object"]

    for field in REQUIRED_TOP:
        if field not in data:
            errors.append(f"{rel}: missing required field '{field}'")
    if errors:
        return errors  # further checks assume these fields exist

    if not isinstance(data["deliverable"], str) or not data["deliverable"]:
        errors.append(f"{rel}: 'deliverable' must be a non-empty string")
    if not isinstance(data["author"], str) or not data["author"]:
        errors.append(f"{rel}: 'author' must be a non-empty string")
    if not isinstance(data["checked_by"], str) or not data["checked_by"]:
        errors.append(f"{rel}: 'checked_by' must be a non-empty string")
    elif data["checked_by"] == data.get("author"):
        errors.append(f"{rel}: 'checked_by' equals 'author' — proof cannot be self-certified")

    commit = data["commit"]
    if not isinstance(commit, str) or not COMMIT_RE.match(commit):
        errors.append(f"{rel}: 'commit' does not look like a git SHA: {commit!r}")

    commands = data["commands"]
    if not isinstance(commands, list):
        errors.append(f"{rel}: 'commands' must be a list")
    else:
        for i, cmd in enumerate(commands):
            prefix = f"{rel}: commands[{i}]"
            if not isinstance(cmd, dict):
                errors.append(f"{prefix}: must be an object")
                continue
            for field in REQUIRED_COMMAND:
                if field not in cmd:
                    errors.append(f"{prefix}: missing required field '{field}'")
            if not isinstance(cmd.get("argv"), list) or not cmd.get("argv"):
                errors.append(f"{prefix}: 'argv' must be a non-empty list")
            if not isinstance(cmd.get("exit"), int) or not isinstance(cmd.get("expect_exit"), int):
                errors.append(f"{prefix}: 'exit' and 'expect_exit' must be integers")
            elif cmd["exit"] != cmd["expect_exit"]:
                errors.append(
                    f"{prefix}: exit {cmd['exit']} != expect_exit {cmd['expect_exit']} — "
                    "a proof record cannot record its own failure as proof"
                )
            tail = cmd.get("tail")
            if not isinstance(tail, list) or len(tail) > 10 or not all(isinstance(t, str) for t in tail):
                errors.append(f"{prefix}: 'tail' must be a list of at most 10 strings")
            sha256 = cmd.get("sha256")
            if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
                errors.append(f"{prefix}: 'sha256' does not look like a sha256 hex digest: {sha256!r}")

    if not isinstance(data["mutations"], list) or not all(isinstance(m, str) for m in data["mutations"]):
        errors.append(f"{rel}: 'mutations' must be a list of strings")
    if not isinstance(data["unproven"], list) or not all(isinstance(u, str) for u in data["unproven"]):
        errors.append(f"{rel}: 'unproven' must be a list of strings")

    # acceptance_criteria and tokens are enforced ONLY for records whose
    # typed `pr` is >= 12. Records from PR #11 and earlier (proof/7.json,
    # 8.json, 9.json, 10.json, 11.json) predate both fields and are never
    # rewritten or backfilled to add them: inventing acceptance criteria or
    # token measurements after the fact, for work where they were never
    # captured, would falsify the very records this gate exists to keep
    # honest. See docs/requirements/mission.md quality floor items 1 and the
    # efficiency section.
    pr = data.get("pr")
    path_pr = _authoritative_pr_from_filename(path)

    # This catches an INCONSISTENT self-declared 'pr' against the filename,
    # never a self-consistent fabrication -- see
    # `_authoritative_pr_from_filename`'s docstring for what this can and
    # cannot detect for a BRAND NEW file, and `check_new_proof_records_declare_pr`
    # for the check that uses a genuinely external number (CI, on a
    # `pull_request` run, via `--pr`) to close that gap. When the filename
    # names a PR number and the record's own self-declared 'pr' disagrees
    # with it, that disagreement is itself an error, AND gating uses the
    # STRICTER of the two numbers -- never the self-declared one alone.
    # Found by adversarial review: nothing previously cross-checked a
    # record's self-declared 'pr' against anything outside the record's own
    # content, so an ADDITIONAL record (distinct from whichever one
    # satisfies `check_pr_has_record` for the real PR) could lie about its
    # own 'pr' and sail through `validate_all()`'s field requirements
    # entirely -- the identical shape of the bug PR #19 fixed in
    # `lwb_lanes.py::_review_ok`.
    if isinstance(path_pr, int) and isinstance(pr, int) and pr != path_pr:
        errors.append(
            f"{rel}: record's 'pr' ({pr!r}) does not match its own filename "
            f"({path_pr}) -- a proof record must not self-declare a PR number "
            "that disagrees with the number its filename names"
        )
    effective_pr = max((n for n in (pr, path_pr) if isinstance(n, int)), default=None)

    if isinstance(effective_pr, int) and effective_pr >= 12:
        errors.extend(_validate_acceptance_criteria(rel, data.get("acceptance_criteria")))
        errors.extend(_validate_tokens(rel, data.get("tokens")))
    if isinstance(effective_pr, int) and effective_pr >= VERIFIABILITY_CUTOFF_PR and isinstance(commands, list):
        errors.extend(_validate_verifiability(rel, commands))

    return errors


TOKEN_FIELDS = (
    "total_input",
    "cached_input",
    "uncached_input",
    "output",
    "retries",
    "setup_overhead",
    "tool_overhead",
    "wall_time_seconds",
    "source",
)
ZERO_FORBIDDEN_FIELDS = ("total_input", "output")
# The only two ORIGINS a FRESH CLONE -- on a machine that never had any
# particular plugin installed -- can re-derive. tokens.source must START
# WITH one of these (anchored at position 0, no leading whitespace); detail
# after the origin -- a colon, a parenthetical, derivation notes -- is
# allowed and expected, it is honest provenance, not noise. "spend-ledger"
# and similar named scripts belonged to a plugin the owner is removing: a
# record citing one is unreproducible and unreviewable by anyone else. See
# proof/schema.json's tokens.source description.
ALLOWED_TOKEN_SOURCE_PREFIXES = ("transcript message.usage", "unknown")

# The plan's stated cutoff (docs/maintainers/proof-of-completion-plan.md,
# open blockers 1-3): verifiability fields are enforced only for records
# whose typed `pr` is >= this. Records 7-19 predate the scheme -- two
# different throwaway sanitiser scripts, disagreeing about their own rules
# -- and are never rewritten to add fields that were never captured; see
# proof/README.md.
VERIFIABILITY_CUTOFF_PR = 20

# Closed enum, per the plan's measured table of the ten distinct command
# kinds found in proof/*.json: five re-execute cleanly in CI, three
# cannot, two are conditional. Free text is an advisory rule and this
# repo rejects it -- a reason a validator cannot check is not a check.
ALLOWED_VERIFIABLE_REASONS = (
    "nondeterministic-output",
    "git-range-not-reproducible",
    "needs-repo-secret",
    "needs-build-step",
)


def _argv_has_git_range(argv: list) -> bool:
    """True if `argv` names a git revision range, by any spelling seen (or
    reachable via `argparse`'s own equals-form) in this repo's own proof
    records:

    - a single 'a..b' token (e.g. `--range origin/main..HEAD`);
    - separate `--base`/`--head` flags, space or `=` form (`--base X
      --head Y`, or `--base=X --head=Y` -- `lwb_lanes.py`'s own argparse
      accepts both, and only the space form was detected before, found by
      adversarial review);
    - git's `^ref` exclusion syntax (`git log HEAD ^origin/main`), which
      names a range just as much as `A..B` does.

    `--since=` (a relative-time filter some git commands accept) is
    deliberately NOT treated as a range here: it does not pin a specific
    commit the way `..`/`^`/`--base`+`--head` do, and no command in this
    repo's proof records uses it -- if one ever does, it needs its own
    resolved, dated equivalent, not this field.

    Also NOT detected, and left as a known gap rather than guessed at: git's
    BARE two-revision form with no operator at all, e.g. `git diff
    origin/main HEAD` (equivalent to `origin/main..HEAD` for `diff`/`log`/
    `rev-list`). Catching it needs distinguishing "two revisions" from "one
    revision plus a pathspec" -- `git diff HEAD file.py` is a single
    revision limited to a file, not a range, and looks identical at the
    argv level (a subcommand followed by two plain tokens) without actually
    parsing which tokens resolve to revisions versus paths, which this
    validator does not attempt. No command in this repo's proof records
    uses the bare form today (this repo's own commands all use `--range`,
    `--base`/`--head`, or take no revisions at all) -- if one ever does, it
    needs deliberate handling, not a heuristic that risks flagging an
    ordinary `<rev> <path>` invocation as a range it is not.

    Without resolved shas, CI re-executing any of the DETECTED forms
    resolves a different commit than the one the record proves, and an
    honest record fails -- exactly the failure mode that gets a gate
    switched off."""
    if not isinstance(argv, list):
        return False
    str_args = [a for a in argv if isinstance(a, str)]
    if any(".." in a for a in str_args):
        return True
    if any(a.startswith("^") and len(a) > 1 for a in str_args):
        return True
    has_base = any(a == "--base" or a.startswith("--base=") for a in str_args)
    has_head = any(a == "--head" or a.startswith("--head=") for a in str_args)
    return has_base and has_head


# Same convention as `COMMIT_RE` above: a resolved sha must look like a real
# git object name, never the unresolved symbolic ref itself ('origin/main',
# 'HEAD') -- writing the symbolic ref into resolved_base/resolved_head would
# defeat the field's entire purpose, since CI would be no better off than
# with the original unresolved argv.
RESOLVED_SHA_RE = COMMIT_RE


def _validate_verifiability(rel, commands: list) -> list[str]:
    errors: list[str] = []
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue  # already reported by the base structural check
        argv = cmd.get("argv")
        name = " ".join(argv) if isinstance(argv, list) and all(isinstance(a, str) for a in argv) else repr(argv)
        prefix = f"{rel}: commands[{name!r}]"

        sanitiser_version = cmd.get("sanitiser_version")
        if not isinstance(sanitiser_version, str) or not sanitiser_version:
            errors.append(
                f"{prefix}: missing 'sanitiser_version' -- a digest cannot be attributed "
                "to a known sanitiser without it"
            )

        verifiable = cmd.get("verifiable")
        if not isinstance(verifiable, bool):
            errors.append(f"{prefix}: 'verifiable' must be a boolean")
        elif verifiable is False:
            reason = cmd.get("verifiable_reason")
            if not isinstance(reason, str) or reason not in ALLOWED_VERIFIABLE_REASONS:
                errors.append(
                    f"{prefix}: 'verifiable' is false but 'verifiable_reason' "
                    f"{reason!r} is not one of {ALLOWED_VERIFIABLE_REASONS!r}"
                )

        if _argv_has_git_range(argv):
            resolved_base = cmd.get("resolved_base")
            resolved_head = cmd.get("resolved_head")
            if not isinstance(resolved_base, str) or not RESOLVED_SHA_RE.match(resolved_base):
                errors.append(
                    f"{prefix}: argv names a git revision range but 'resolved_base' "
                    f"{resolved_base!r} does not look like a resolved sha -- the "
                    "UNRESOLVED symbolic ref itself defeats the field's purpose; "
                    "resolve it with e.g. `git rev-parse` before writing the record"
                )
            if not isinstance(resolved_head, str) or not RESOLVED_SHA_RE.match(resolved_head):
                errors.append(
                    f"{prefix}: argv names a git revision range but 'resolved_head' "
                    f"{resolved_head!r} does not look like a resolved sha -- the "
                    "UNRESOLVED symbolic ref itself defeats the field's purpose; "
                    "resolve it with e.g. `git rev-parse` before writing the record"
                )
    return errors


def _validate_acceptance_criteria(rel, criteria) -> list[str]:
    errors: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        errors.append(f"{rel}: 'acceptance_criteria' must be a non-empty list (pr >= 12)")
        return errors
    for i, item in enumerate(criteria):
        prefix = f"{rel}: acceptance_criteria[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        criterion = item.get("criterion")
        if not isinstance(criterion, str) or not criterion:
            errors.append(f"{prefix}: 'criterion' must be a non-empty string")
        met = item.get("met")
        if not isinstance(met, bool):
            errors.append(f"{prefix}: 'met' must be a boolean")
        elif met is False:
            errors.append(f"{prefix}: 'met' is false -- an unmet criterion means the floor was not cleared")
    return errors


def _validate_tokens(rel, tokens) -> list[str]:
    errors: list[str] = []
    if not isinstance(tokens, dict):
        errors.append(f"{rel}: 'tokens' must be an object (pr >= 12)")
        return errors
    for field in TOKEN_FIELDS:
        if field not in tokens:
            errors.append(f"{rel}: 'tokens' missing required field '{field}'")
            continue
        value = tokens[field]
        if field == "source":
            if not isinstance(value, str) or not value.startswith(ALLOWED_TOKEN_SOURCE_PREFIXES):
                errors.append(
                    f"{rel}: tokens.source {value!r} does not begin with a re-derivable origin -- "
                    f"must start with one of {ALLOWED_TOKEN_SOURCE_PREFIXES!r} (detail may follow)"
                )
            continue
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        is_unknown = value == "unknown"
        if not (is_number or is_unknown):
            errors.append(f"{rel}: tokens.{field} must be a number or the string 'unknown'")
        elif field in ZERO_FORBIDDEN_FIELDS and is_number and value == 0:
            errors.append(
                f"{rel}: tokens.{field} is 0 -- almost certainly an unmeasured field recorded as "
                "zero, which the mission forbids; record 'unknown' instead"
            )
    return errors


def validate_all() -> tuple[list[str], int]:
    errors: list[str] = []
    count = 0
    if PROOF_DIR.is_dir():
        for path in sorted(PROOF_DIR.glob("*.json")):
            # schema.json is the shape; exempt.json is the named-gap list
            # (see check_coverage). Neither is a proof record.
            if path.name in ("schema.json", "exempt.json"):
                continue
            count += 1
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{path.relative_to(REPO_ROOT)}: invalid JSON: {exc}")
                continue
            errors.extend(_validate_record(path, data))
    return errors, count


def check_flat_proof_layout() -> list[str]:
    """`proof/` is documented (`proof/README.md`) as a FLAT directory --
    `proof/<id>.json`, nothing nested. Adversarial review found that two
    checks disagreed about the actual shape: `validate_all()` and
    `check_pr_has_record()` use `PROOF_DIR.glob("*.json")`, which is NOT
    recursive, while `check_new_proof_records_declare_pr` finds files via
    `git diff -- proof`, which IS recursive by nature (git diffs the whole
    tree under a pathspec). A record at `proof/sub/20.json` was therefore
    seen and pr-checked by one and completely invisible to the other --
    it could carry no `sanitiser_version`, no `verifiable`, malformed
    `commands[]`, and nothing would ever validate it.

    Rather than making every OTHER check recursive too (silently widening
    scope to match the one check that happened to be recursive by
    accident), a nested `proof/**/*.json` is rejected outright: the flat
    layout is the documented convention, and a nested file is more likely
    an accident (a stray subdirectory) or a deliberate evasion attempt
    than a legitimate structure. This is called unconditionally from
    `main()`, independent of `--pr`/`--coverage`, so a nested file is
    always caught regardless of which other checks happen to run.
    """
    errors: list[str] = []
    if not PROOF_DIR.is_dir():
        return errors
    for path in sorted(PROOF_DIR.rglob("*.json")):
        if path.parent != PROOF_DIR:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: proof/ is a FLAT directory "
                "(proof/<id>.json, see proof/README.md) -- a record nested "
                "under a subdirectory is not a supported layout (it would be "
                "invisible to validate_all()'s non-recursive glob); move it "
                "directly under proof/"
            )
    return errors


SQUASH_SUBJECT_RE = re.compile(r"\(#(\d+)\)\s*$")
EXEMPT_PATH = PROOF_DIR / "exempt.json"


def _landed_deliverables(rev_range: str) -> list[tuple[str, str]]:
    """(sha, subject) for each squash-merge commit in `rev_range`.

    A squash merge is a single-parent commit, so `--merges` finds nothing;
    the convention GitHub writes is a trailing `(#N)` in the subject.
    """
    result = subprocess.run(
        ["git", "log", "--format=%H%x00%s", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    landed = []
    for line in result.stdout.splitlines():
        if "\x00" not in line:
            continue
        sha, subject = line.split("\x00", 1)
        if SQUASH_SUBJECT_RE.search(subject):
            landed.append((sha, subject))
    return landed


def _exempt_shas() -> dict:
    if not EXEMPT_PATH.is_file():
        return {}
    try:
        data = json.loads(EXEMPT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get("merges", {}) if isinstance(data, dict) else {}


def check_coverage(rev_range: str) -> list[str]:
    """Every landed deliverable must HAVE a proof record, not merely be well-formed.

    This is the half directive 7 was missing. `validate_all` checks the
    records that exist; it never asks whether one should exist, so an empty
    `proof/` read as "nothing to prove yet" and the gate could not fail --
    PRs #1 through #5 all merged green with zero records. Historical merges
    are listed in proof/exempt.json with a reason rather than back-filled
    with invented evidence; anything not on that list needs a real record.
    """
    errors: list[str] = []
    proved_commits = set()
    proved_prs = set()
    if PROOF_DIR.is_dir():
        for path in sorted(PROOF_DIR.glob("*.json")):
            if path.name in ("schema.json", "exempt.json"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("commit"), str):
                proved_commits.add(data["commit"])
            # A record is written INSIDE the PR it proves, so it cannot name
            # the squash-merge sha -- that sha does not exist until GitHub
            # creates it at merge time. The PR number is the only identifier
            # available at both moments, so both halves of this check key on
            # it. Without this, every record would be unmatchable post-merge
            # and coverage would fail on work that was properly proven.
            # Typed `pr` only, for the reason spelled out in
            # check_pr_has_record: a digit-string `deliverable` is ordinary
            # usage and collided with unrelated PR numbers.
            if isinstance(data.get("pr"), int):
                proved_prs.add(data["pr"])

    exempt = _exempt_shas()
    for sha, subject in _landed_deliverables(rev_range):
        if sha in exempt or sha[:12] in exempt:
            continue
        match = SQUASH_SUBJECT_RE.search(subject)
        if match and int(match.group(1)) in proved_prs:
            continue
        # `commit` is schema-constrained to 7-40 hex chars, so a prefix test
        # in this direction is enough; the reverse test that used to be here
        # (`c.startswith(sha[:7])`) was dead weight -- it could only match by
        # predicting a future sha -- and it made an empty string match
        # everything if the schema check were ever relaxed.
        if any(len(c) >= 7 and sha.startswith(c) for c in proved_commits):
            continue
        errors.append(
            f"{sha[:12]} ({subject!r}) landed with no proof/*.json record naming its "
            "PR number or commit — owner directive 7: done means committed AND pushed "
            "WITH a proof record. Add one, or list the sha in proof/exempt.json with a "
            "reason."
        )
    return errors


# GitHub's own convention for a bot/App account's login: it always ends in
# `[bot]` (dependabot[bot], renovate[bot], github-actions[bot], the app-name
# form of any GitHub App). This is a DIFFERENT signal from
# `lwb_lanes.py::BOT_AUTHOR_PATTERNS`, which matches the git commit AUTHOR
# EMAIL of each commit in a range. Here there is no commit to inspect yet --
# `check_pr_has_record` runs pre-merge, keyed on the PR's own number, and the
# only bot signal available at that moment is the PR's GITHUB LOGIN
# (`github.event.pull_request.user.login`), which CI already has and this
# module did not previously accept. Anchored at the end (`$`) so a login that
# merely CONTAINS "bot" (e.g. a human-chosen `robot-wrangler`) never matches
# -- only GitHub's own bracketed suffix does.
BOT_LOGIN_RE = re.compile(r"\[bot\]$", re.IGNORECASE)


def is_bot_pr_author(login) -> bool:
    """True when `login` (a GitHub PR author login, not a commit email) is a
    recognized bot/App account by GitHub's own `[bot]` suffix convention.

    Covers `dependabot[bot]` explicitly by the same suffix rule as any other
    bot login (`renovate[bot]`, `github-actions[bot]`, ...) -- there is
    nothing dependabot-specific to special-case. `None`, `""`, and a login
    that merely contains "bot" without the bracketed suffix (e.g. a human
    account named `robot-wrangler`) all return False.
    """
    return isinstance(login, str) and bool(BOT_LOGIN_RE.search(login))


def check_pr_has_record(pr_number: int, pr_author=None, notices: "list[str] | None" = None) -> list[str]:
    """Pre-merge half of directive 7: this PR must carry its own proof record.

    `check_coverage` keys on the `(#N)` squash-merge subject, and GitHub
    fabricates that commit AT MERGE TIME. It does not exist while the PR's
    own CI is running, so running coverage over `base..head` at PR time can
    never find a landed deliverable -- it is a guaranteed no-op. That is how
    this check first shipped, and an independent review of PR #6 caught it:
    the gate meant to stop deliverables merging without proof would itself
    have merged without ever being able to fire.

    So there are two halves, keyed on the two things that actually exist at
    the two moments: the PR NUMBER before the merge (blocking), and the
    COMMIT after it (detective, on push to main).

    `pr_author` (the PR's GitHub login, optional) carries the same exemption
    `lwb_lanes.py`'s module docstring already states for the lane gate ("Bot
    commits are skipped too ... a bot ... cannot write a `reviews/` record,
    so without this every Dependabot PR would fail ... and teach us to merge
    past a red gate"): a Dependabot (or any `[bot]`-suffixed) PR can never
    write a `proof/*.json` record naming its own PR number either -- it has
    no owner directive 7 workflow to run -- so requiring one here is the same
    permanent, unfixable failure the lane gate was already exempted from.
    That reasoning was written for the lane gate only and was never carried
    across to this proof-record gate; this is the missing half. Unlike the
    lane exemption (silent, by design -- see `is_bot_commit`), this one is
    reported: a bot exemption of the PROOF requirement is load-bearing enough
    that it must never look identical to "checked and found a record", so a
    notice is appended to `notices` (if given) naming the PR and the login.
    Bots remain bound by every other check in this file.
    """
    if is_bot_pr_author(pr_author):
        if notices is not None:
            notices.append(
                f"pr-authority: PR #{pr_number} author {pr_author!r} is a recognized bot "
                "account -- exempted from carrying its own proof/*.json record, same "
                "rationale as lwb_lanes.py's BOT_AUTHOR_PATTERNS lane exemption (a bot "
                "cannot write one). Bots remain bound by every other check."
            )
        return []

    errors: list[str] = []
    if not PROOF_DIR.is_dir():
        records = []
    else:
        records = [
            p for p in sorted(PROOF_DIR.glob("*.json"))
            if p.name not in ("schema.json", "exempt.json")
        ]

    for path in records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        # ONLY the typed `pr` integer counts. There used to be a fallback
        # accepting a `deliverable` that happened to be the digits of the PR
        # number, and it was unsound: schema.json documents `deliverable` as
        # "an issue/step number or a short slug", so a small integer is
        # normal, expected usage. A record proving step 6 of some unrelated
        # plan would have silently satisfied PR #6's gate forever, pre- and
        # post-merge, with no relation to its content -- a gate reporting
        # green without checking anything real, the same defect this PR
        # exists to fix. Found by independent review; the first version's own
        # test asserted the broken behaviour as intended.
        if data.get("pr") == pr_number:
            return []

    errors.append(
        f"PR #{pr_number} carries no proof/*.json record for itself. Add one with "
        f"\"pr\": {pr_number} — the typed field, not a deliverable that merely reads "
        f"as \"{pr_number}\". Owner directive 7: done means committed AND pushed WITH "
        "a proof record."
    )
    return errors


def _new_or_changed_proof_paths(rev_range: str):
    """Repo-relative, forward-slash paths (as `git` reports them) of every
    `proof/*.json` file ADDED or MODIFIED in `rev_range`, e.g.
    'origin/main..HEAD'. Returns `None` -- never an empty set -- if the
    `git diff` itself could not be run or failed (no such ref in this
    checkout, git missing, etc.), so a caller can tell "computed, and
    genuinely nothing changed" apart from "could not compute at all" and
    must not treat the latter as if it were the former.
    """
    statuses = _proof_path_statuses(rev_range)
    if statuses is None:
        return None
    return set(statuses)


def _proof_path_statuses(rev_range: str):
    """Like `_new_or_changed_proof_paths`, but keeps the ADDED-vs-MODIFIED
    distinction `check_new_proof_records_declare_pr` needs: an ADDED
    record must declare THIS PR's number, but a MODIFIED one already
    existed on the base branch and is allowed to keep its own -- only
    forbidden from CHANGING it. A plain path set can't carry that
    distinction, hence this separate dict-returning helper alongside the
    older set-returning one (kept for its own direct callers/tests).

    Returns `{relname: status}` where `status` is one of 'A' (added),
    'M' (modified) or 'R' (renamed -- see below), or `None` under the same
    "could not compute at all" conditions as `_new_or_changed_proof_paths`.

    A RENAME is reported by git as a single R-status entry naming both the
    old and new path (`git diff --name-status` prints `R100\told\tnew`
    rather than a separate delete+add). Renaming a proof record does not
    change its content, so on principle a rename+content-preserving-move
    should be free -- but a rename is also the cheapest way to make an old
    record's `pr` value LOOK freshly declared next to unrelated new
    content, and unlike a true MODIFY there is no "base version of this
    exact path" to diff the `pr` field against (the old path is gone).
    Treating it as ADDED is the conservative choice: it costs nothing to a
    legitimate rename (just re-declare the same `pr`, which is what ADDED
    already requires) and it closes the same kind of self-consistent-
    filename bypass `check_new_proof_records_declare_pr`'s docstring
    already documents for brand-new files.
    """
    try:
        result = subprocess.run(
            [
                "git", "diff", "-M", "--name-status", "--diff-filter=ACMR",
                rev_range, "--", "proof",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    statuses: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip("\n")
        if not line:
            continue
        fields = line.split("\t")
        status = fields[0][:1]  # 'A', 'M', or 'R100' -> 'R' (--diff-filter=ACMR: no 'C')
        relname = fields[-1]  # for R this is the NEW path; the old path is fields[1]
        statuses[relname.strip()] = status
    return statuses


def _base_ref(rev_range: str) -> str:
    """The base side of a two-dot `rev_range` ('base..head'), e.g.
    'origin/main' from 'origin/main..HEAD'. `rev_range` is always
    constructed this way by this script's own callers (the
    'origin/main..HEAD' default, or f"{base}..{head}" from --base/--head),
    so a plain split is sufficient -- this is not a general revision-range
    parser.
    """
    base, _, _ = rev_range.partition("..")
    return base


def _read_pr_field_at_ref(ref: str, relname: str):
    """The `pr` field of `proof/<relname>` as it reads at git ref `ref`,
    or `_MISSING` (a sentinel distinct from `None`, which is itself a
    legal-if-wrong value for a JSON field) if the file can't be read at
    that ref at all -- missing from that ref, unreadable git object, not
    valid JSON, or not a JSON object. A caller must fail closed on
    `_MISSING`, never treat it as "the base agrees".
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{relname}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return _MISSING
    if result.returncode != 0:
        return _MISSING
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return _MISSING
    if not isinstance(data, dict):
        return _MISSING
    return data.get("pr")


_MISSING = object()


def check_new_proof_records_declare_pr(
    pr_number: int, rev_range: str = "origin/main..HEAD", notices: "list[str] | None" = None
) -> list[str]:
    """The check that closes the gap `_authoritative_pr_from_filename`
    cannot: for a BRAND NEW proof record, the filename is exactly as
    attacker-controlled as the `pr` field it would be compared against, so
    filename agreement proves nothing about a file created in the same
    commit as its own name. Adversarial review confirmed two concrete
    bypasses this closes: a slug-named file self-declaring a stale `pr`,
    and a SELF-CONSISTENT fabricated digit filename (`007.json` declaring
    `"pr": 7` to match itself).

    The one place a PR number IS genuinely external to every record's own
    content is CI, on a `pull_request` run: `.github/workflows/ci.yml`'s
    `lwb-proof-pr` step already knows `github.event.pull_request.number`
    and passes it as `--pr N` -- no workflow change needed, the number is
    already threaded this far. This function uses that number against
    `rev_range` (default `origin/main..HEAD`, resolvable in this repo's CI
    checkout, which fetches full history), and the two DIFFER by how the
    file changed:

    - ADDED (or RENAMED -- see `_proof_path_statuses`'s docstring for why
      a rename is treated as an add): the record is new, so it must
      self-declare `pr` == `pr_number`. This is the original rule and the
      one that closes the two disclosed bypasses above -- a NEW record's
      filename and `pr` field are both entirely attacker-controlled in
      the same PR, so nothing about the file itself can be trusted.
    - MODIFIED: the record already existed on the base branch (it proves
      SOME earlier PR, not this one) and PR #21's own history is the
      motivating case -- correcting a wrongly-set `verifiable` flag on
      `proof/20.json` without pretending record 20 suddenly proves PR 21.
      Such a record is allowed to keep declaring its original `pr`; what
      it may never do is CHANGE that field, which is checked by reading
      the base version of the same path with `git show <base>:<path>`
      and comparing `pr` fields. If the base version can't be read at all
      (deleted from base, unusual ref, not valid JSON there), this fails
      CLOSED with an explicit error -- never a silent pass, because
      "can't prove it didn't change" is not the same claim as "provably
      unchanged".

    A file unchanged since before this PR is never flagged at all --
    `rev_range` itself excludes it, regardless of what its `pr` says.

    Degrades rather than crashing the whole gate when the diff itself
    cannot be computed (`_proof_path_statuses` returns `None`, e.g. no
    such ref in an unusual checkout): appends a NOTICE to `notices`
    (never silently treated as all-clear) saying every record's `pr` field
    in this run is self-declared and UNVERIFIED against the real PR
    number, and returns no errors -- this is the fail-open case, and it is
    named as such rather than disguised as a passed check.
    """
    if notices is None:
        notices = []
    statuses = _proof_path_statuses(rev_range)
    if statuses is None:
        notices.append(
            f"pr-authority: could not compute '{rev_range}' to find proof/*.json files "
            "new or changed in this PR (no such ref in this checkout?) -- every record's "
            "'pr' field in this run is SELF-DECLARED and UNVERIFIED against the real PR "
            "number; this check did not run"
        )
        return []

    base_ref = _base_ref(rev_range)
    errors: list[str] = []
    for relname in sorted(statuses):
        rel_path = Path(relname)
        if rel_path.name in ("schema.json", "exempt.json"):
            continue
        # A NESTED file (proof/sub/20.json) is `git diff`'s business (it
        # sees the whole tree under the pathspec) but not this function's:
        # `check_flat_proof_layout` is the single authority that rejects a
        # nested proof record outright, and it runs unconditionally from
        # `main()`. Independently pr-checking it here too would let a
        # nested file with a "correct" pr silently pass THIS check while
        # still being rejected by the layout check -- a confusing,
        # inconsistent report for the same file. See
        # docs/maintainers/proof-of-completion-plan.md and
        # check_flat_proof_layout's docstring for the scope-mismatch this
        # avoids re-introducing.
        if rel_path.parent != Path("proof"):
            continue
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue  # deleted in this PR -- nothing left to validate
        try:
            data = json.loads(full_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # already reported by validate_all
        if not isinstance(data, dict):
            continue
        record_pr = data.get("pr")
        status = statuses[relname]
        if status in ("A", "R"):
            if record_pr != pr_number:
                errors.append(
                    f"{relname}: is new in this PR but self-declares 'pr' "
                    f"({record_pr!r}) instead of {pr_number} (this PR's actual number, "
                    "known to CI independent of anything the record or its filename "
                    "claims) -- a NEW record added by a PR must declare that PR's own "
                    "number"
                )
            continue
        # status == "M": the record already existed on the base branch, so
        # it is allowed to keep declaring whatever PR it originally proved
        # -- the motivating case is exactly this: correcting a wrongly-set
        # classification (e.g. `verifiable`) on an existing record without
        # that correction silently reassigning which PR the record proves.
        # What it may NOT do is CHANGE its own `pr` field; check that
        # against the base branch's version of the same path, which is the
        # one place genuinely external to this PR's own content.
        base_pr = _read_pr_field_at_ref(base_ref, relname)
        if base_pr is _MISSING:
            errors.append(
                f"{relname}: modified in this PR but its base version "
                f"('{base_ref}:{relname}') could not be read to verify its 'pr' field "
                "was not changed -- deleted from the base branch, an unreadable git "
                "object, or not valid JSON there; failing closed rather than assuming "
                "it is unchanged"
            )
            continue
        if record_pr != base_pr:
            errors.append(
                f"{relname}: modified in this PR and its 'pr' field changed from "
                f"{base_pr!r} (on '{base_ref}') to {record_pr!r} -- an existing record "
                "may be corrected, but it must keep declaring the PR it originally "
                "proved; a PR that wants to add a NEW record for itself must do so "
                "under a new filename, not by repointing an old one"
            )
    return errors


# `--reexecute` has FOUR distinct exit codes, not three -- see the module
# docstring at the top of this file for the full contract and the
# precedence between MISMATCH and UNCOMPARABLE. Summary:
#   0  REEXECUTE_EXIT_ALL_MATCHED        -- at least one command was
#      re-executed, and every one of them matched (digest and exit code),
#      and nothing was UNCOMPARABLE.
#   1  REEXECUTE_EXIT_MISMATCH           -- at least one re-executed
#      command's digest or exit code did not match the record, timed out,
#      or a record's `commands[]` entry was malformed. Wins over
#      UNCOMPARABLE if both are present in the same run.
#   2  REEXECUTE_EXIT_NOTHING_REEXECUTED -- zero commands were re-executed
#      (every command was skipped as self-referencing, marked
#      verifiable: false, or there were no proof records at all) AND
#      nothing was UNCOMPARABLE either. This is NOT a pass: nothing was
#      checked.
#   3  REEXECUTE_EXIT_UNCOMPARABLE       -- no MISMATCH occurred, but at
#      least one command's `sanitiser_version` differed from the running
#      `lwb_sanitise.SANITISER_VERSION`, so its digest could not be
#      attributed to a known sanitiser and was never compared -- found by
#      independent review of PR #21: previously an UNCOMPARABLE command
#      counted toward neither failures nor the re-executed total, so one
#      real pass next to a sanitiser-version-drifted command still printed
#      the ALL_MATCHED summary at exit 0.
REEXECUTE_EXIT_ALL_MATCHED = 0
REEXECUTE_EXIT_MISMATCH = 1
REEXECUTE_EXIT_NOTHING_REEXECUTED = 2
REEXECUTE_EXIT_UNCOMPARABLE = 3

# Recorded proof commands can legitimately take a while (the full test
# suite, a build step), but a hung or deliberately blocking command must
# not stall the CI job forever -- `continue-on-error: true` only ignores a
# non-zero EXIT, it does not bound wall-clock time (found by independent
# review of PR #21: subprocess.run had no timeout at all). 300s is well
# above every re-executable command actually measured in this repo's own
# proof/*.json while still bounding the job to a finite time.
REEXECUTE_TIMEOUT_SECONDS = 300

# Belt-and-braces recursion guard, alongside (never instead of) the argv
# detection in `_command_resolves_to_self`: every command this function
# re-executes is launched with this env var set to "1". If a launched
# process is ITSELF `lwb_check_proof.py --reexecute` (the argv guard
# failed to catch it, or a proof record somehow launches a wrapper that
# re-invokes this script without naming it in argv at all), `main` refuses
# to do any work rather than recursing. The argv guard is the primary
# defence and must work standalone -- see `_command_resolves_to_self`'s
# docstring -- this is only a second line of defence.
SELF_REEXECUTE_GUARD_ENV = "LWB_CHECK_PROOF_REEXECUTING"


def reexecute_exit_code(report: dict) -> int:
    """The exit code `--reexecute` reports for `report` (as returned by
    `reexecute_verifiable_commands`) -- see the four `REEXECUTE_EXIT_*`
    constants above, and the module docstring, for what each means, why
    they are distinct, and the MISMATCH-over-UNCOMPARABLE precedence.
    """
    if report["failures"]:
        return REEXECUTE_EXIT_MISMATCH
    if report.get("total_uncomparable", 0) > 0:
        return REEXECUTE_EXIT_UNCOMPARABLE
    if report["total_reexecuted"] == 0:
        return REEXECUTE_EXIT_NOTHING_REEXECUTED
    return REEXECUTE_EXIT_ALL_MATCHED


SELF_NAME = "lwb_check_proof"  # module/basename stem, deliberately without ".py"


def _command_resolves_to_self(argv) -> bool:
    """True if `argv` names, invokes, or wraps `lwb_check_proof.py` itself.

    This is the second half of the recursion guard `--reexecute` needs --
    see `reexecute_verifiable_commands`. Every proof record lists
    `lwb_check_proof.py` among its commands (it is one of CI's own gates),
    so re-executing it as an ordinary verifiable command would re-enter
    validation from inside `--reexecute` itself. The FIRST half of the
    guard is that `--reexecute` is an explicit CLI flag that never appears
    in a recorded `argv` (see `tests/test_lwb_check_proof_reexecute.py`),
    so a re-executed command never inherits it and recurses into ITS OWN
    `--reexecute` mode; this function additionally refuses to launch the
    self-referencing command at all, belt and braces, independent of
    whether that first guard holds.

    An independent reviewer of PR #21 CONFIRMED this guard was bypassable:
    the original version compared only `Path(a).name ==
    "lwb_check_proof.py"`, exact-case, against each token -- so
    `['python', 'scripts/LWB_CHECK_PROOF.PY']` was ACTUALLY RE-EXECUTED
    rather than skipped, and it further listed `['python', '-m',
    'lwb_check_proof']`, a `bash -c "..."` wrapper, and a
    `subprocess.run([...])` wrapper as additional live bypasses.

    The fix is deliberately a single broad rule rather than a list of
    special cases for each bypass form: `SELF_NAME` ("lwb_check_proof",
    without the ".py" -- so both the script and the `-m` module spelling
    match the same needle) is looked for, CASE-INSENSITIVELY, as a
    SUBSTRING of every string `argv` token, not just an exact basename
    match on one. This one rule catches every form above without parsing
    argv structure at all:

      - an uppercase or mixed-case filename, anywhere in a path (the
        confirmed bypass) -- substring match is case-insensitive;
      - `-m lwb_check_proof` -- the module name alone is the needle;
      - a `bash -c "... lwb_check_proof.py ..."` / `sh -c` / `cmd /c` /
        `powershell -c "..."` wrapper -- the whole shell command line is
        one argv string token, and the needle appears inside it wherever
        in that line the invocation sits;
      - a `subprocess.run(['python', 'scripts/lwb_check_proof.py'])`
        wrapper passed as an inline `-c` script -- same reasoning, the
        needle appears in the source-code string token.

    Deliberately over-inclusive: a token that merely MENTIONS this
    script's name (in a log message, say) also matches. Erring toward
    catching the self-reference is the correct trade against erring toward
    recursion -- but "matches" no longer means "silently skipped and
    forgotten" on its own. An independent reviewer of PR #21's own
    re-execution logic found that pairing this over-inclusive match with
    `verifiable: true` was a silent opt-out that needed no
    `verifiable_reason` from the closed enum: a command could name this
    script (even just by mentioning it, e.g. inside a `pytest` invocation
    of this very test file) with a deliberately WRONG recorded digest and
    still be treated as skipped rather than compared, and the run still
    exited 0. So the caller (`reexecute_verifiable_commands`) does NOT
    treat every match here as a free pass: a match paired with
    `verifiable: true` is now a FAILURE, and only a match paired with
    anything else (`verifiable: false` with an enum reason, the only
    legitimate way to opt out) is a genuine SKIPPED-SELF, counted in its
    own `total_skipped_self` total. This function only answers "does argv
    resolve to self"; the verifiable-true-means-failure decision lives at
    the call site, not here.
    """
    if not isinstance(argv, list):
        return False
    needle = SELF_NAME.lower()
    return any(isinstance(a, str) and needle in a.lower() for a in argv)


def reexecute_verifiable_commands(records, *, run=subprocess.run) -> dict:
    """Re-run every `commands[]` entry across `records` whose `verifiable`
    is `True`, sanitise its combined stdout+stderr through the CURRENTLY
    RUNNING `lwb_sanitise.sanitise`, and compare the resulting sha256 (and
    exit code) against what the record claims.

    `records` is a list of `(label, data)` pairs -- `label` is whatever the
    caller wants printed (a relative path, in `main`'s real use), `data` is
    a parsed proof record dict. This shape, rather than reading `PROOF_DIR`
    directly, is what lets every guard above be tested without touching
    disk or spawning a real process (`run` is injectable for the same
    reason -- production passes `subprocess.run`, tests pass a spy).

    Five failure modes this function exists to prevent becoming theatre:

    1. Recursion -- every proof record lists `lwb_check_proof.py` among its
       own commands, so blindly re-executing it would re-enter validation
       (and, under an env-gated design, recurse into its own re-execution
       forever). `_command_resolves_to_self` identifies any command naming,
       invoking, or wrapping `lwb_check_proof.py`; such a command is never
       invoked either way, but is only reported `SKIPPED-SELF` (counted in
       `total_skipped_self`) when legitimately opted out as `verifiable:
       false` with an enum reason. A self-referencing command marked
       `verifiable: true` is instead reported as a FAILURE -- found by
       independent review to be a silent opt-out otherwise, needing no
       enum reason at all, that let a deliberately wrong recorded digest
       sail through as a skip rather than a mismatch. On top of that,
       `--reexecute` is a CLI flag that never appears in a recorded
       `argv`, so a re-executed command never inherits it either, and a
       `SELF_REEXECUTE_GUARD_ENV` marker is set on every launched child as
       a belt-and-braces third layer (see `main`).
    2. Sanitiser drift -- a command whose `sanitiser_version` differs from
       `lwb_sanitise.SANITISER_VERSION` is reported `UNCOMPARABLE`, is not
       re-run at all (comparing its digest under different rules would
       prove nothing), and is counted in its OWN `total_uncomparable`
       total -- distinct from both `total_reexecuted` and `failures`, so a
       sanitiser-version bump can never silently look like nothing changed
       (see `reexecute_exit_code`'s `REEXECUTE_EXIT_UNCOMPARABLE`).
    3. Empty is not success -- every record's line and the final `TOTAL`
       line always carry both the re-executed count and the total command
       count, even when the re-executed count is 0, and the TOTAL line
       says so in words (see `reexecute_exit_code`'s
       `REEXECUTE_EXIT_NOTHING_REEXECUTED`). There is no "all verified"
       message anywhere in this function.
    4. Exit codes and timeouts -- a re-run whose exit code differs from the
       recorded `exit` is a failure, checked BEFORE the digest comparison,
       even if the digest happens to match anyway; a re-run that exceeds
       `REEXECUTE_TIMEOUT_SECONDS` is ALSO a failure, naming the command
       and the limit -- never a pass, never a silent skip.
    5. Malformed records -- a `commands[]` entry with no `argv`, a
       non-list `argv`, an empty `argv`, or an `argv` containing a
       non-string element cannot be launched at all. Rather than crashing
       the whole run (the previous behaviour: the traceback took down
       every OTHER record's results along with the bad one), this is
       reported as a FAILURE against just that entry and the run
       continues.

    Returns `{"lines": [...], "failures": [...], "total_commands": M,
    "total_reexecuted": N, "total_uncomparable": U}`. `failures` is empty
    exactly when every attempted re-execution passed (an empty `failures`
    list with `total_reexecuted == 0` is the explicit "0 of N" case above,
    not a claim that anything was verified) -- pass this dict to
    `reexecute_exit_code` for the exit status, which distinguishes all
    FOUR of "nothing was re-executed", "everything re-executed matched",
    "something was uncomparable" and "something mismatched" as different
    values, never conflating any two of them.
    """
    lines: list[str] = []
    failures: list[str] = []
    total_commands = 0
    total_reexecuted = 0
    total_uncomparable = 0
    total_skipped_self = 0
    run_env = {**os.environ, SELF_REEXECUTE_GUARD_ENV: "1"}

    for label, data in records:
        commands = data.get("commands") if isinstance(data, dict) else None
        if not isinstance(commands, list):
            continue
        record_total = len(commands)
        record_reexecuted = 0
        record_lines: list[str] = []

        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            argv = cmd.get("argv")
            name = " ".join(argv) if isinstance(argv, list) and all(isinstance(a, str) for a in argv) else repr(argv)

            if _command_resolves_to_self(argv):
                if cmd.get("verifiable") is True:
                    # Found by independent review: 'verifiable: true' plus
                    # any argv token merely MENTIONING this script's name
                    # was a silent opt-out that needed no
                    # 'verifiable_reason' from the closed enum -- a proof
                    # record could carry a deliberately WRONG digest on a
                    # self-referencing command and still exit 0, because
                    # the command was skipped rather than compared. A
                    # self-referencing command is only legitimately skipped
                    # when it is verifiable: false with an enum reason (see
                    # ALLOWED_VERIFIABLE_REASONS and _validate_verifiability
                    # above, which already enforces that pairing); claiming
                    # verifiable: true on one is now a FAILURE, never a
                    # quiet SKIPPED-SELF.
                    msg = (
                        f"{label}: {name}: self-referencing command is marked "
                        "verifiable: true -- a proof record cannot claim its own "
                        "re-execution as proof; mark it verifiable: false with an "
                        "enum reason instead"
                    )
                    failures.append(msg)
                    record_lines.append(f"    FAIL {name} (self-referencing but verifiable: true)")
                    continue
                total_skipped_self += 1
                record_lines.append(
                    f"    SKIPPED-SELF {name} -- a proof record cannot contain proof of its own re-execution"
                )
                continue

            if cmd.get("verifiable") is not True:
                continue  # not claimed re-executable; not counted as attempted

            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
                msg = f"{label}: {name}: malformed command entry -- 'argv' must be a non-empty list of strings"
                failures.append(msg)
                record_lines.append(f"    FAIL {name} (malformed argv: {argv!r})")
                continue

            sanitiser_version = cmd.get("sanitiser_version")
            if sanitiser_version != lwb_sanitise.SANITISER_VERSION:
                total_uncomparable += 1
                record_lines.append(
                    f"    UNCOMPARABLE {name} -- record sanitiser_version={sanitiser_version!r}, "
                    f"running SANITISER_VERSION={lwb_sanitise.SANITISER_VERSION!r}"
                )
                continue

            record_reexecuted += 1
            total_reexecuted += 1
            try:
                proc = run(
                    argv,
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=REEXECUTE_TIMEOUT_SECONDS,
                    env=run_env,
                )
            except subprocess.TimeoutExpired:
                msg = f"{label}: {name}: exceeded {REEXECUTE_TIMEOUT_SECONDS}s timeout -- treated as a failure"
                failures.append(msg)
                record_lines.append(f"    FAIL {name} (timeout after {REEXECUTE_TIMEOUT_SECONDS}s)")
                continue
            except OSError as exc:
                msg = f"{label}: {name}: could not re-execute: {exc}"
                failures.append(msg)
                record_lines.append(f"    FAIL {name} (could not re-execute: {exc})")
                continue

            combined = proc.stdout + proc.stderr
            sanitised = lwb_sanitise.sanitise(combined)
            digest = hashlib.sha256(sanitised.encode("utf-8")).hexdigest()
            recorded_digest = cmd.get("sha256")
            recorded_exit = cmd.get("exit")

            if proc.returncode != recorded_exit:
                msg = (
                    f"{label}: {name}: exit mismatch -- recorded exit {recorded_exit!r}, "
                    f"re-run exit {proc.returncode!r}"
                )
                failures.append(msg)
                record_lines.append(f"    FAIL {name} (exit {proc.returncode!r} != recorded {recorded_exit!r})")
            elif digest != recorded_digest:
                msg = (
                    f"{label}: {name}: digest mismatch -- recorded sha256 {recorded_digest!r}, "
                    f"re-run sha256 {digest!r}"
                )
                failures.append(msg)
                record_lines.append(f"    FAIL {name} (sha256 {digest} != recorded {recorded_digest})")
            else:
                record_lines.append(f"    PASS {name}")

        total_commands += record_total
        lines.append(f"{label}: {record_reexecuted} of {record_total} commands re-executed")
        lines.extend(record_lines)

    if failures:
        suffix = f" -- MISMATCH: {len(failures)} command(s) did not match"
    elif total_uncomparable > 0:
        suffix = (
            f" -- UNCOMPARABLE: {total_uncomparable} command(s) could not be compared "
            "(sanitiser_version drift), THIS IS NOT A PASS"
        )
    elif total_reexecuted == 0:
        suffix = " -- NOTHING WAS RE-EXECUTED, THIS PROVES NOTHING (not success, not a check)"
    else:
        suffix = " -- ALL RE-EXECUTED COMMANDS MATCHED"
    lines.append(
        f"TOTAL: {total_reexecuted} of {total_commands} commands re-executed, "
        f"{total_uncomparable} uncomparable, {total_skipped_self} skipped-self, "
        f"across {len(records)} records{suffix}"
    )

    return {
        "lines": lines,
        "failures": failures,
        "total_commands": total_commands,
        "total_reexecuted": total_reexecuted,
        "total_uncomparable": total_uncomparable,
        "total_skipped_self": total_skipped_self,
    }


def _load_records_for_reexecute() -> list[tuple[str, dict]]:
    """Every real `proof/*.json` record, as `(relative-path-string, data)`
    pairs -- `reexecute_verifiable_commands`'s disk-facing input. A record
    that fails to parse is skipped here (already reported by
    `validate_all`); this function's only job is to hand back what CAN be
    re-executed.
    """
    records: list[tuple[str, dict]] = []
    if not PROOF_DIR.is_dir():
        return records
    for path in sorted(PROOF_DIR.glob("*.json")):
        if path.name in ("schema.json", "exempt.json"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        try:
            label = str(path.relative_to(REPO_ROOT))
        except ValueError:
            label = str(path)
        records.append((label, data))
    return records


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage",
        dest="rev_range",
        default=None,
        help="post-merge: require a proof record for every squash-merge in base..head",
    )
    parser.add_argument(
        "--pr",
        dest="pr_number",
        type=int,
        default=None,
        help="pre-merge: require a proof record naming this PR number",
    )
    # Paired with --pr: the PR's GitHub login (github.event.pull_request.
    # user.login in CI), not a git commit author email -- a different
    # signal from lwb_lanes.py's commit-email-based bot check. When this
    # names a recognized bot account (is_bot_pr_author), check_pr_has_record
    # exempts that PR from carrying its own proof/*.json record (a bot can
    # never write one) and reports the exemption via a notice rather than
    # silently. Omitted or a non-bot login: no change in behaviour.
    parser.add_argument(
        "--pr-author",
        dest="pr_author",
        default=None,
        help="PR author's GitHub login; a recognized bot (e.g. dependabot[bot]) is "
        "exempted from the --pr proof-record requirement, reported via a notice",
    )
    # Paired with --pr: the base/head to diff for
    # check_new_proof_records_declare_pr's "new or changed in this PR"
    # check. Same base/head reasoning as lwb_check_commit_identity.py and
    # lwb_lanes.py in .github/workflows/ci.yml: pass
    # github.event.pull_request.base.sha / head.sha explicitly, never
    # 'origin/main..HEAD' by default in CI -- a pull_request checkout's
    # HEAD is the synthetic refs/pull/N/merge commit, and origin/main may
    # have moved since the PR branched. Both flags must be given together;
    # with neither, check_new_proof_records_declare_pr falls back to its
    # own 'origin/main..HEAD' default, which is only correct for local,
    # non-CI use (a real checkout of main plus a local branch).
    parser.add_argument("--base", default=None, help="base ref/sha for the pr-authority check")
    parser.add_argument("--head", default=None, help="head ref/sha for the pr-authority check")
    parser.add_argument(
        "--reexecute",
        action="store_true",
        help=(
            "re-run every commands[] entry whose verifiable is true across all "
            "proof/*.json records, sanitise its output, and compare the sha256 "
            "against the recorded digest. Mutually exclusive with every other mode: "
            "run alone, prints a re-execution report, and exits with one of FOUR "
            "distinct codes -- see REEXECUTE_EXIT_ALL_MATCHED (0), "
            "REEXECUTE_EXIT_MISMATCH (1), REEXECUTE_EXIT_NOTHING_REEXECUTED (2), "
            "REEXECUTE_EXIT_UNCOMPARABLE (3) -- 'nothing was re-executed' is never "
            "the same exit code as 'everything re-executed matched', and a "
            "sanitiser-version-drifted command that could not be compared at all "
            "is never the same exit code as either."
        ),
    )
    args = parser.parse_args()

    if args.reexecute:
        if os.environ.get(SELF_REEXECUTE_GUARD_ENV) == "1":
            # Belt-and-braces: this process was itself launched BY a
            # re-execution (see `reexecute_verifiable_commands`, which sets
            # this on every child it spawns). The primary guard is argv
            # detection in `_command_resolves_to_self`, which must -- and
            # does -- work standalone; this is only the second line of
            # defence for a wrapper that hid the self-reference from argv
            # entirely.
            print(
                f"FAIL: refusing to run --reexecute while {SELF_REEXECUTE_GUARD_ENV}=1 is set -- "
                "this process was launched by a re-execution and must not recurse into its own "
                "--reexecute mode"
            )
            return REEXECUTE_EXIT_MISMATCH
        records = _load_records_for_reexecute()
        report = reexecute_verifiable_commands(records)
        for line in report["lines"]:
            print(line)
        for f in report["failures"]:
            print(f"FAIL: {f}")
        return reexecute_exit_code(report)

    errors, count = validate_all()
    errors.extend(check_flat_proof_layout())
    if args.rev_range:
        errors.extend(check_coverage(args.rev_range))
    notices: list[str] = []
    if args.pr_number:
        errors.extend(check_pr_has_record(args.pr_number, pr_author=args.pr_author, notices=notices))
        pr_check_kwargs = {}
        if args.base and args.head:
            pr_check_kwargs["rev_range"] = f"{args.base}..{args.head}"
        errors.extend(
            check_new_proof_records_declare_pr(args.pr_number, notices=notices, **pr_check_kwargs)
        )
    else:
        # No --pr means no authoritative PR number is available to THIS
        # invocation (a local run, the plain `lwb-proof` job on every PR,
        # or the post-merge `--coverage` run on push to main) -- say so
        # rather than silently implying every record's self-declared `pr`
        # was cross-checked against something external. See
        # check_new_proof_records_declare_pr's docstring for the one run
        # (`lwb-proof-pr`, which passes `--pr`) where it genuinely is.
        notices.append(
            "pr-authority: no --pr given -- every record's 'pr' field in this run is "
            "SELF-DECLARED and UNVERIFIED against any number external to the record "
            "itself (only _authoritative_pr_from_filename's filename cross-check ran)"
        )
    for n in notices:
        print(f"NOTICE: {n}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    if count == 0:
        print("lwb-proof check skipped (no proof/*.json records yet)")
    else:
        print(f"lwb-proof check passed ({count} record(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
