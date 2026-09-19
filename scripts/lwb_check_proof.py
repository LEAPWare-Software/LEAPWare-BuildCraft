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
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROOF_DIR = REPO_ROOT / "proof"

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
    number (`7.json` .. `19.json`), so a bare-digit filename stem is the
    equivalent authority here: a signal that sits OUTSIDE the record's own
    claim, exactly like the directory does for reviews/.

    Returns `None` for a non-digit stem -- `schema.json` documents
    `deliverable` as "an issue/step number or a short slug", so a
    slug-named file is ordinary and carries no filename-derived authority
    either way. See `_validate_record` for the fail-closed handling of
    that no-authority case, and the residual gap it does not close.
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

    # Fail closed, not open: when the filename names a PR number and the
    # record's own self-declared 'pr' disagrees with it, that disagreement
    # is itself an error (it is either a mistake or an attempt to write a
    # lower, more lenient number into the record to dodge the enforcement
    # cutoffs below), AND gating uses the STRICTER of the two numbers --
    # never the self-declared one alone, which is exactly the value under
    # attack. Found by adversarial review: nothing previously cross-checked
    # a record's self-declared 'pr' against anything outside the record's
    # own content, so an ADDITIONAL record (distinct from whichever one
    # satisfies `check_pr_has_record` for the real PR) could lie about its
    # own 'pr' and sail through `validate_all()`'s field requirements
    # entirely -- the identical shape of the bug PR #19 fixed in
    # `lwb_lanes.py::_review_ok`.
    #
    # Residual gap, stated plainly rather than silently left: a record filed
    # under a SLUG name (no digit filename at all) carries no filename-
    # derived authority, so a self-declared 'pr' on a slug-named file cannot
    # be cross-checked by this mechanism -- there is nothing outside the
    # record's own claim to check it against. Closing that fully needs
    # either a `proof/<pr>/<slug>.json` directory convention (mirroring
    # `reviews/<pr>/`) or CI threading the real PR number into every
    # `validate_all()` invocation (today only `lwb-proof-pr` passes `--pr`;
    # the plain `lwb-proof` job, which runs on every PR, does not). Both are
    # out of scope here.
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

    Without resolved shas, CI re-executing any of these forms resolves a
    different commit than the one the record proves, and an honest record
    fails -- exactly the failure mode that gets a gate switched off."""
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


def check_pr_has_record(pr_number: int) -> list[str]:
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
    """
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
    args = parser.parse_args()

    errors, count = validate_all()
    if args.rev_range:
        errors.extend(check_coverage(args.rev_range))
    if args.pr_number:
        errors.extend(check_pr_has_record(args.pr_number))
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
