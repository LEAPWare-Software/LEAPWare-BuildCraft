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
    if isinstance(pr, int) and pr >= 12:
        errors.extend(_validate_acceptance_criteria(rel, data.get("acceptance_criteria")))
        errors.extend(_validate_tokens(rel, data.get("tokens")))

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
