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
    # `.claude/` and `.codex/` are the CLIs' own contributor-side config.
    # `.claude/settings.json` registers the PreToolUse lane hook, and
    # `.claude/agents/` holds the role definitions a cloud routine dispatches
    # -- a routine only sees agents committed on the branch it checks out, so
    # they have to be tracked. They are SHARED, not lane-owned, for the same
    # reason `.gitignore` is: a file whose whole purpose is to govern what the
    # enforcement does cannot be owned by the agent it enforces against. Put
    # `.claude/` in the claude lane and the claude agent could rewrite the
    # hook that constrains it with no independent review. Before this entry
    # both trees classified as "other" -- in no lane and not shared -- so
    # NEITHER CLI could touch its own config at all, which is what blocked
    # `.claude/agents/` from ever landing.
    ".claude/",
    ".codex/",
)
# Root files that belong to no single CLI's lane. `.gitignore` is here
# because a change to it is repo-wide by construction -- PR #16 added
# `graphify-out/` to it to keep artifacts carrying the operator's username
# out of a PUBLIC repo, and the lane gate rejected that commit as being
# outside the claude lane. A file whose whole purpose is to govern what the
# whole repo tracks cannot sensibly belong to one lane; it is shared, and
# therefore needs independent review like any other shared path.
SHARED_FILES = (
    "HANDOFF.md",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    ".gitignore",
)

# The bootstrap window, as an explicit set rather than a `<= N` threshold.
# A threshold is wrong here because PR numbers are a shared, consumable
# resource: Dependabot opened #2, #3 and #4 unattended, silently spending
# three quarters of a window that was meant for the PRs that stood this
# system up. Only #1 (the scaffold) and #5 (the PR that fixed this rule)
# ever needed the exemption, so they are named, and the window cannot be
# eaten or quietly extended by a bot.
BOOTSTRAP_EXEMPT_PRS = frozenset({1, 5})

# The PR number from which a reviews/<pr>/*.json record must carry a
# PARSEABLE identity in both reviewer_id and commit_author_id, per the
# "<role>-<model>-<session-token>-<date>" format below. Records 7-18 predate
# this format -- they were measured (not guessed) to be free-form strings
# that do not fit it, and rewriting them to fit would be editing evidence
# to suit a validator, which is the falsification this whole change exists
# to stop. It is a NAMED constant, not a "pr >= N" literal scattered through
# the code, following the same precedent as scripts/lwb_check_proof.py's
# acceptance_criteria/tokens cutoff at PR #12.
REVIEWER_ID_FORMAT_CUTOFF_PR = 19

# "<role-and-model>-<session-token>-<date>", parsed from the RIGHT: the
# trailing "-YYYY-MM-DD" is the date, the segment before that (up to the
# next dash) is the session-token, and everything left over is
# role-and-model -- hyphens and all. This used to require role, model and
# session-token to each be a single dash-free segment
# ("<role>-<model>-<session-token>-<date>", parsed left to right), which
# hard-failed real identifiers this repo actually uses: "lw-verifier" (this
# repo's own agent name) and "claude-sonnet-5" (a real model id) both
# contain hyphens. That pushed authors toward writing degraded ids purely
# to satisfy the validator -- the exact falsification pressure this format
# exists to remove, just relocated to id construction. Parsing from the
# right instead means role and model no longer need to be told apart at
# all; only the date (fixed shape, unambiguous) and the session-token
# (the segment adjacent to it, for PARSING an individual id into its three
# fields) need to be isolated. NOTE: parsing an id's own session-token
# field this way is still correct and used for the format check below --
# but comparing two ids' session-token FIELDS this way, to detect a shared
# identity, is not (see _shared_long_segment): an appended suffix segment
# shifts which field sits "next to" the date without changing what the
# two ids actually share, and this repo's own PRs 15-17 self-review has
# its shared token NOT adjacent to the date at all.
_DATE_SUFFIX_RE = re.compile(r"-(\d{4}-\d{2}-\d{2})$")
# A session-token must not itself be shaped like a date -- covers both the
# hyphenated form (impossible here in practice, since a token is defined as
# a single dash-free segment by construction) and a compact 8-digit
# YYYYMMDD, so a token cannot smuggle in a second, disguised date field.
_DATE_SHAPED_RE = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")

# Below this length, a hyphen-delimited segment shared between two ids is
# not evidence of anything -- a real session or dispatch token is long: this
# very session's own token is 8 hex characters ("f8da3f9e"), and the
# per-dispatch ids already sitting in reviews/7 through reviews/13 run 17
# characters ("ac5ffd6d6cde8a968"). A short coincidental fragment ("9999",
# "v2", "sonnet") turns up between two UNRELATED ids often enough that
# flagging it would block a legitimate review -- the failure mode that gets
# a gate disabled. 8 is the floor observed in this repo's own real session
# token, not an arbitrary round number.
#
# KNOWN RESIDUAL, found by the independent review of PR #19 and left open
# deliberately rather than discovered later: a shared token SHORTER than
# this goes undetected. That is not hypothetical here -- reviews/schema.json
# accepts a 7-character git short sha as a legitimate identifier, so a
# future record mirroring that house style would produce a real 7-character
# shared token that clears this floor cleanly. A UUID's later groups are
# 4 characters and likewise clear it. Lowering the floor reopens the
# false-positive problem this constant exists to fix -- two unrelated ids
# sharing "9999" would block a legitimate review -- and no value closes
# both. The trade is recorded here rather than resolved, because the cost
# of a missed accidental self-review is a weaker audit trail, while the
# cost of a false positive is a gate someone switches off.
MIN_SHARED_SEGMENT_LENGTH = 8

# How many DISTINCT independent reviewers a shared-path change needs. The
# old rule was "one record per CLI vendor", which read as two but was really
# one-each and could never be met with a single CLI in operation. One
# genuinely independent reviewer is the substance of directive 5; raise this
# when a second reviewer identity is routinely available. A project policy
# may tighten it, never loosen it.
REQUIRED_INDEPENDENT_REVIEWS = 1

# Commit authors that cannot satisfy lane review by construction: a bot
# does not run a CTO role, cannot write a reviews/ record, and does not
# stamp an `LWB-Agent:` trailer. Without this, every Dependabot PR from #6
# onward fails `lwb-lanes` on a missing trailer -- which would train us to
# merge past a red lane check, the exact habit this gate exists to prevent.
# A bot commit is still bound by every other check (commit identity, env
# leak, tests); it is only exempt from the two-CTO lane review.
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
    # GENERATED VENDOR OUTPUT IS SHARED, NOT LANE-OWNED, and this exception
    # must be checked FIRST, before the lane prefixes below would claim it.
    #
    # `plugins/<agent>/lwb/vendor/` is not hand-authored content. It is
    # machine-written by `scripts/lwb_build.py` (a SHARED script) from
    # `core/` and `adapters/` (SHARED and lane sources), and `lwb_build.py
    # --check` fails CI whenever it drifts from those sources. Treating it as
    # the agent's own lane created a DEADLOCK that had gone unnoticed because
    # nothing had exercised it: any change to `core/` must be re-vendored into
    # BOTH plugins or CI fails, but a claude-authored commit may not write
    # `plugins/codex/`, so NO claude session could land a core change at all.
    #
    # That is not a hypothetical. `core/lwb_core/rules/` still contained
    # exactly one rule, and the only commit in this repo's history to touch
    # `plugins/codex/lwb/vendor/` is the bootstrap commit. The lane rule was
    # silently holding the shared core closed against the only CLI in
    # operation -- see docs/maintainers/proof-of-completion-plan.md.
    #
    # Classifying it `shared` is the honest answer rather than a loophole: the
    # bytes are derived from shared sources, they are reviewed wherever those
    # sources are reviewed, and a shared path still requires independent
    # review before it lands. It does NOT weaken the lane rule for anything a
    # human or agent actually writes -- `plugins/codex/lwb/hooks/`,
    # `plugins/codex/lwb/bin/` and every other authored path under a lane are
    # untouched by this exception.
    for agent in ("claude", "codex"):
        if posix.startswith(f"plugins/{agent}/lwb/vendor/"):
            return "shared"

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
        encoding="utf-8",
        errors="replace",
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
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def resolve_head_sha(rev_range: str) -> Optional[str]:
    """Resolve the full sha of the head of `rev_range` (e.g. "base..head").

    Returns None if the ref cannot be resolved, so callers can fail loudly
    instead of silently skipping the freshness check.
    """
    head_ref = rev_range.split("..")[-1] if ".." in rev_range else rev_range
    result = subprocess.run(
        ["git", "rev-parse", head_ref],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def _is_record_only_commit(sha: str) -> bool:
    """True when every file `sha` touches lives under `reviews/` or `proof/`.

    A commit with no files at all (e.g. an empty commit) is NOT record-only
    — `all()` over an empty list is vacuously True, which would wrongly let
    a no-op commit skip past the walk.
    """
    files = commit_files(sha)
    if not files:
        return False
    for f in files:
        posix = f.replace("\\", "/")
        if not (posix.startswith("reviews/") or posix.startswith("proof/")):
            return False
    return True


def resolve_reviewable_head(rev_range: str) -> Optional[str]:
    """Resolve the sha a review record's `reviewed_commit` must match.

    The raw branch head is the wrong thing to compare against: committing a
    review record itself advances the head past the sha that record names,
    so no committed record could ever match the raw head. This walks back
    from the head, skipping any commit whose changed files are ALL under
    `reviews/` or `proof/` (pure record-keeping, nothing that needs its own
    review), and returns the first commit that changed anything else --
    the "reviewable head". If every commit from the head backward is
    record-only, there is nothing to skip past, so this falls back to the
    raw head rather than walking off into unrelated history.

    Returns None if the head cannot be resolved at all, so callers fail
    loudly instead of silently skipping the freshness check.
    """
    head_sha = resolve_head_sha(rev_range)
    if head_sha is None:
        return None

    result = subprocess.run(
        ["git", "log", "--format=%H", head_sha],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    shas = [line for line in result.stdout.splitlines() if line.strip()]
    if not shas:
        return head_sha

    for sha in shas:
        if not _is_record_only_commit(sha):
            return sha

    # Every commit from the head backward is record-only: nothing to skip
    # past, so fall back to the raw head rather than returning nothing.
    return head_sha


def commits_in_range(rev_range: str) -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H", rev_range],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


# reviews/schema.json is the checked-in shape description. Used to be
# "loaded by nothing" (reviews/README.md said so in plain words) -- a third
# unenforced description of the record shape, on top of README.md and this
# module's own hand checks, would have been worse than the two that already
# existed. Wired in here, hand-rolled the same way scripts/lwb_check_proof.py
# validates proof/schema.json -- this repo is stdlib-only, so a real
# jsonschema validator is not an option, and a purpose-built check of the
# small slice of JSON Schema this file actually uses (required, enum,
# pattern) is honest about what it covers rather than pretending to a
# generic implementation. Read from a path fixed at import time, NOT from
# the (test-mutable) REPO_ROOT global -- tests reassign REPO_ROOT to a
# throwaway tmp_path repo that has no reviews/schema.json of its own, and
# the schema being validated against is a property of the real repo's
# format, not of where a given test happens to stage its fake records.
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "reviews" / "schema.json"


def _load_review_schema() -> dict:
    import json

    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


# Types this repo's hand-rolled schema check understands, mapped from a
# JSON Schema "type" name to a predicate. `bool` is deliberately NOT
# accepted for "integer": `isinstance(True, int)` is True in Python (bool
# is an int subclass), so a naive `isinstance(value, int)` check would
# silently accept `"pr": true` as an integer. Checked as its own branch,
# ahead of the general int check, rather than folded into it.
def _type_matches(value: object, type_name: str) -> bool:
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "object":
        return isinstance(value, dict)
    # An unrecognised type name in the schema is not this function's to
    # judge -- reviews/schema.json only ever uses the five above -- so an
    # unknown name is treated as unconstrained rather than guessed at.
    return True


def _validate_against_schema(data: dict, rel, errors: list[str]) -> None:
    """Hand-rolled subset of JSON Schema validation: required-field
    presence, `type`, `enum`, and `pattern` -- the only constructs
    reviews/schema.json actually uses. Appends to `errors`; does not
    return anything, since callers already track validity via the
    presence/absence of new error strings.

    `type` used to be checked by nothing -- reviews/schema.json declared
    `"pr": {"type": "integer"}` and the code never looked at it, so a
    record with `"pr": "19"` (a string) passed straight through. Checked
    FIRST, ahead of enum/pattern: a value of the wrong type failing an
    enum or pattern check too is not useful extra information, just noise
    on top of the real problem.
    """
    schema = _load_review_schema()
    for field in schema.get("required", ()):
        if field not in data:
            errors.append(f"{rel}: missing required field '{field}' (reviews/schema.json)")
    for field, spec in schema.get("properties", {}).items():
        if field not in data:
            continue
        value = data[field]
        type_name = spec.get("type")
        if type_name is not None and not _type_matches(value, type_name):
            errors.append(
                f"{rel}: '{field}' = {value!r} has type {type(value).__name__}, "
                f"want {type_name!r} (reviews/schema.json)"
            )
            continue
        enum = spec.get("enum")
        if enum is not None and value not in enum:
            errors.append(
                f"{rel}: '{field}' = {value!r} is not one of {enum!r} (reviews/schema.json)"
            )
        pattern = spec.get("pattern")
        if pattern is not None and isinstance(value, str) and not re.match(pattern, value):
            errors.append(
                f"{rel}: '{field}' = {value!r} does not match pattern {pattern!r} "
                "(reviews/schema.json)"
            )


def _parse_identity(
    value: object, field_label: str, rel, errors: list[str]
) -> Optional[tuple[str, str, str]]:
    """Parse an identity string into (role_and_model, session_token, date)
    per the "<role-and-model>-<session-token>-<date>" format, parsed from
    the RIGHT: the trailing "-YYYY-MM-DD" is the date, the segment before
    it (up to the next dash) is the session-token, and everything left
    over -- hyphens and all -- is role-and-model.

    This used to parse left-to-right with role, model and session-token
    each required to be a single dash-free segment, which hard-failed real
    identifiers this repo uses (`lw-verifier`, `claude-sonnet-5`) and
    pushed authors toward writing degraded ids just to satisfy the
    validator. Parsing from the right needs no opinion on where "role"
    ends and "model" begins -- only the date (a fixed, unambiguous shape)
    and the token (the one segment next to it) need to be isolated.

    Returns None (and appends to `errors`) when `value` is not a
    non-empty string, has no trailing date, has no token segment before
    the date, or its session-token is empty or itself date-shaped (a
    literal duplicate date, or a token trying to double as one)."""
    if not isinstance(value, str) or not value:
        errors.append(f"{rel}: {field_label} must be a non-empty string")
        return None
    m = _DATE_SUFFIX_RE.search(value)
    if not m:
        errors.append(
            f"{rel}: {field_label} {value!r} does not end in a '-YYYY-MM-DD' date "
            "(required '<role-and-model>-<session-token>-<date>' format, parsed from "
            f"the right; required from PR #{REVIEWER_ID_FORMAT_CUTOFF_PR})"
        )
        return None
    date = m.group(1)
    remainder = value[: m.start()]
    if "-" not in remainder:
        errors.append(
            f"{rel}: {field_label} {value!r} has no session-token segment before the "
            "date (required '<role-and-model>-<session-token>-<date>' format)"
        )
        return None
    role_and_model, _, token = remainder.rpartition("-")
    if not role_and_model or not token:
        errors.append(
            f"{rel}: {field_label} {value!r}: role-and-model and session-token must "
            "both be non-empty"
        )
        return None
    if token == date or _DATE_SHAPED_RE.match(token):
        errors.append(
            f"{rel}: {field_label} {value!r}: session-token must not itself be "
            "date-shaped"
        )
        return None
    return (role_and_model, token, date)


def _id_segments(value: str) -> set[str]:
    """The hyphen-delimited segments of an identity string, with a
    trailing '-YYYY-MM-DD' date stripped first -- so two reviews that
    simply happened on the same calendar day never count "2026", "09" or
    "19" as a shared segment. Works on ANY id ending in a real date, not
    only one that otherwise fits the '<role-and-model>-<session-token>-
    <date>' shape: used to check for a shared segment even against this
    repo's own historical, free-form ids."""
    m = _DATE_SUFFIX_RE.search(value)
    remainder = value[: m.start()] if m else value
    return {seg for seg in remainder.split("-") if seg}


def _shared_long_segment(id_a: str, id_b: str) -> Optional[str]:
    """A hyphen-delimited segment present in BOTH ids' segment SETS (date
    excluded) and at least MIN_SHARED_SEGMENT_LENGTH characters long, or
    None if there is no such segment. Deterministic when more than one
    qualifies: the shortest, then alphabetically first.

    Compares the SET of segments, not one fixed position (e.g. "the
    segment immediately before the date"). A fixed-position comparison is
    two different bugs at once, both found by adversarial review:
      - an author can defeat it by appending one throwaway segment after
        the real token, which shifts what sits "next to" the date without
        changing what the two ids actually share
        ("...-realtoken123-2026-09-19" vs
        "...-realtoken123-extra-2026-09-19" -- "realtoken123" is shared,
        but neither id's date-adjacent segment is);
      - it also MISSED this repo's own real self-review in PRs 15-17,
        where the shared session token ("f8da3f9e") is not adjacent to
        the date at all
        ("...-f8da3f9e-scope13to15-2026-09-18" vs
        "...-session-f8da3f9e-2026-09-18").
    Comparing sets closes both without introducing substring matching
    across segment boundaries -- "realtoken123" inside "xrealtoken123y"
    is a different problem this function does not try to solve, since
    chasing partial substrings invites the false positives
    MIN_SHARED_SEGMENT_LENGTH exists to avoid.

    This raises the cost of an ACCIDENTAL self-review. It does not detect
    deliberate evasion -- nothing stops two ids from sharing no segment at
    all while still naming the same underlying session under different
    words -- and nothing here or in reviews/README.md claims otherwise.
    """
    shared = _id_segments(id_a) & _id_segments(id_b)
    long_shared = sorted(s for s in shared if len(s) >= MIN_SHARED_SEGMENT_LENGTH)
    return long_shared[0] if long_shared else None


def _review_ok(
    review_path: Path,
    head_sha: str,
    pr_number: int,
    errors: list[str],
    notices: Optional[list[str]] = None,
) -> Optional[str]:
    """Validate one review record. Returns its reviewer_id, or None if invalid.

    `pr_number` is the AUTHORITATIVE PR number -- the one `independent_reviews`
    globbed `reviews/<pr_number>/` for -- not something read out of the
    record. This used to read `data.get("pr")` from inside the file and
    gate the whole REVIEWER_ID_FORMAT_CUTOFF_PR path on THAT self-declared
    value: a record filed at `reviews/19/sneaky.json` claiming `"pr": 18`
    was judged as a pre-cutoff, free-form-ok record purely because it said
    so, skipping the parseable-format check, the session-token check and
    the required dispatched-boolean entirely -- found by adversarial
    review. `pr_number` is compared against the record's own `pr` field
    below (a mismatch is an error naming both), and the cutoff decision
    is made on `pr_number`, never on `data.get("pr")`.

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
    enforced is AGREE, reviewer_id != commit_author_id, and freshness against
    `head_sha`: a `reviews/<pr>/` record is keyed only to a PR number, and a
    PR's code changes underneath it -- a record that reviewed an earlier
    round of the same PR must not silently authorize the current one.
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
    schema_errors_before = len(errors)
    _validate_against_schema(data, rel, errors)
    if len(errors) > schema_errors_before:
        return None

    # The record's own `pr` must agree with the directory it was found
    # under. A mismatch (wrong number, wrong type -- "19" the string,
    # 19.0 the float, missing, null) is rejected outright: it is either a
    # mistake or an attempt to borrow a lower PR's exemption from a higher
    # one's rules, and both deserve to fail the same way. `_type_matches`
    # above already flags a non-integer `pr` via the schema's declared
    # "integer" type, so this is a second, independent check on the VALUE,
    # not just the shape.
    record_pr = data.get("pr")
    if record_pr != pr_number:
        errors.append(
            f"{rel}: record's 'pr' ({record_pr!r}) does not match the PR this record "
            f"was found under (reviews/{pr_number}/) -- a review record must name the "
            "PR it actually belongs to"
        )
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
    reviewed_commit = data.get("reviewed_commit")
    # isinstance guard, not just truthiness: a non-string reviewed_commit
    # (e.g. the integer 1234567890) used to reach `len(reviewed_commit)`
    # below and crash the whole script with an uncaught TypeError. The
    # schema's "string" type on reviewed_commit now also catches this
    # earlier, via `_validate_against_schema` above, for the common case
    # -- this guard is the direct, load-bearing fix at the point of the
    # actual crash, kept so this check does not depend on schema
    # validation having run first to stay safe.
    if (
        not isinstance(reviewed_commit, str)
        or len(reviewed_commit) < 7
        or not head_sha.startswith(reviewed_commit)
    ):
        errors.append(
            f"{rel}: STALE — this record reviewed {reviewed_commit!r}, but the "
            f"current REVIEWABLE head is {head_sha!r} (record-only commits "
            "under reviews/ and proof/ are excluded when computing this "
            "head); the change must be re-reviewed"
        )
        return None

    # From REVIEWER_ID_FORMAT_CUTOFF_PR onward: both ids must be parseable,
    # must not share any hyphen-delimited segment of at least
    # MIN_SHARED_SEGMENT_LENGTH characters (the accidental self-review this
    # PR exists to catch -- see the module docstring measurement), and the
    # record must honestly declare whether the reviewer was dispatched by
    # the author's own session. This CANNOT establish genuine independence
    # -- a subagent the author dispatched itself can declare `false` -- so
    # it is recorded and surfaced, never trusted as proof. Gated on
    # `pr_number` (authoritative), never on `record_pr` (self-declared,
    # already reconciled with `pr_number` above, but the gate condition
    # itself must read the trusted value).
    if pr_number >= REVIEWER_ID_FORMAT_CUTOFF_PR:
        reviewer_parsed = _parse_identity(reviewer_id, "reviewer_id", rel, errors)
        author_parsed = _parse_identity(author_id, "commit_author_id", rel, errors)
        if reviewer_parsed is None or author_parsed is None:
            return None
        shared_segment = _shared_long_segment(reviewer_id, author_id)
        if shared_segment is not None:
            errors.append(
                f"{rel}: reviewer_id and commit_author_id share the segment "
                f"{shared_segment!r} ({len(shared_segment)} characters, at or above "
                f"MIN_SHARED_SEGMENT_LENGTH={MIN_SHARED_SEGMENT_LENGTH}) -- likely the "
                "same session or dispatch reviewing its own work, not an independent "
                "reviewer"
            )
            return None
        dispatched = data.get("reviewer_was_dispatched_by_author")
        if not isinstance(dispatched, bool):
            errors.append(
                f"{rel}: missing or non-boolean 'reviewer_was_dispatched_by_author' "
                f"(required from PR #{REVIEWER_ID_FORMAT_CUTOFF_PR}) -- the gate cannot "
                "establish independence on its own and requires this record to declare "
                "the relationship honestly instead of leaving it unstated"
            )
            return None
        if dispatched and notices is not None:
            notices.append(
                f"{rel}: reviewer_was_dispatched_by_author=true -- this review is NOT "
                "independent by construction (the reviewer is a subagent of the "
                "author's own session); the record is an audit trail only, not proof "
                "of independent review"
            )

    return str(reviewer_id)


def independent_reviews(
    pr_number: int,
    commit_sha: str,
    head_sha: str,
    errors: list[str],
    notices: Optional[list[str]] = None,
) -> bool:
    """True when this PR carries REQUIRED_INDEPENDENT_REVIEWS distinct reviewers."""
    review_dir = REPO_ROOT / "reviews" / str(pr_number)
    records = sorted(review_dir.glob("*.json")) if review_dir.is_dir() else []

    reviewer_ids = set()
    for record in records:
        reviewer_id = _review_ok(record, head_sha, pr_number, errors, notices)
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
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout.strip()


def is_bot_commit(sha: str) -> bool:
    """True when `sha`'s author is a bot that cannot satisfy lane review."""
    email = commit_author_email(sha)
    return any(pattern.search(email) for pattern in BOT_AUTHOR_PATTERNS)


def check_lanes(
    rev_range: str, pr_number: int, notices: Optional[list[str]] = None
) -> list[str]:
    """Check every commit in `rev_range`. Returns a list of failure strings.

    `notices` (optional, appended to in place) collects non-failing but
    load-bearing observations -- currently: a record whose
    `reviewer_was_dispatched_by_author` is `true`, printed so that fact is
    never silently absorbed into an apparent pass. See _review_ok.
    """
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
    head_sha = resolve_reviewable_head(rev_range)
    if head_sha is None:
        errors.append(f"{rev_range}: could not resolve reviewable head sha for freshness check")

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

        if touches_shared and head_sha is not None:
            independent_reviews(pr_number, sha, head_sha, errors, notices)

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

    notices: list[str] = []
    errors = check_lanes(f"{args.base}..{args.head}", args.pr_number, notices)
    for n in notices:
        print(f"NOTICE: {n}")
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
