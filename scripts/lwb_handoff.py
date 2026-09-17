#!/usr/bin/env python3
"""Validate and regenerate the "In flight" block of HANDOFF.md.

HANDOFF.md is the repo's own re-derivable state file (see
docs/handoff-protocol.md). This script is the ONLY thing that writes the
generated block; everything else in HANDOFF.md is prose a human/agent
wrote by hand and this script never touches.

Usage:
    python scripts/lwb_handoff.py --check                      # validate HANDOFF.md, exit 1 on failure
    python scripts/lwb_handoff.py --write [--cli NAME] [--session ID]
        # regenerate the generated block in place. --cli and --session
        # record which CLI/session wrote this handoff and its own id, so a
        # reader can tell which session last re-derived state; both are
        # free-form strings and optional (default "unknown" / an
        # auto-generated timestamp-based id) -- this script does not
        # validate them against any external identity source.

Stdlib only. Cross-platform (no shell strings, argv lists to subprocess).
No network calls other than what `gh` itself performs; --check never
shells out at all, so it is safe to run offline / in CI without `gh` auth
for read-only validation of the file shape.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HANDOFF_PATH = REPO_ROOT / "HANDOFF.md"
PROOF_DIR = REPO_ROOT / "proof"

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Owner ruling, 2026-09-17: HANDOFF.md carries the transition only and is
# capped at 3000 bytes. Durable reference (session start, re-derive
# commands, hard rules, traps) moved to docs/handoff-protocol.md. A cap
# reached is a signal to move content into docs/, never to trim meaning.
SIZE_CAP_BYTES = 3000

BEGIN_MARKER = "<!-- lwb-handoff:begin -->"
END_MARKER = "<!-- lwb-handoff:end -->"

# Only the transition sections are required here now. "Start of session",
# "Re-derive state", "Hard rules" and "Traps" are required of
# docs/handoff-protocol.md instead (see PROTOCOL_REQUIRED_SECTIONS), so
# moving them out of HANDOFF.md cannot silently lose them.
REQUIRED_SECTIONS = [
    "# HANDOFF",
    "## In flight",
    "## Where to look",
]

PROTOCOL_DOC = REPO_ROOT / "docs" / "handoff-protocol.md"

PROTOCOL_REQUIRED_SECTIONS = [
    "## Start of session",
    "## Re-derive state",
    "## Hard rules",
    "## Traps",
]

# Patterns that must never appear in a committed HANDOFF.md: an absolute
# path (POSIX or a Windows drive letter) or a real person's name/account
# fragment. This keeps the file honest about SACRED (no local-environment
# dependence) and keeps a human identity out of a machine-read file.
FORBIDDEN_PATTERNS = [
    re.compile(r"[A-Za-z]:\\"),  # Windows drive letter, e.g. C:\
    re.compile(r"(?<!\w)/(?:Users|home)/\w+"),  # POSIX home directory
]

# Private-name needles come from the one source of truth,
# scripts/lwb_check_env_leak.py's resolve_needles(), which reads them from
# the LWB_PRIVATE_NEEDLES environment variable (a repository secret in CI).
#
# They used to be five literals HERE: the owner's own name and three private
# project names, committed in plaintext to a PUBLIC repo. That is the exact
# breach owner directive 8 calls SACRED, sitting inside the file meant to
# prevent it. It survived because this file was on the env-leak scanner's
# own exemption list (_PATTERN_DATA_EXEMPT), so the scanner could not see
# its own needles -- an exemption added to stop false positives ended up
# concealing a real one. Both exemptions are now gone with the literals.
#
# A needle list is configuration, not source. Never re-add a real name here.
from lwb_check_env_leak import resolve_needles  # noqa: E402


class ValidationError(Exception):
    """Raised by _validate() with a human-readable reason."""


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _run_gh(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _utc_now_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _proof_state_lines() -> list[str]:
    """One line per proof/*.json deliverable: id and PROVEN/INVALID/reason.

    Reuses scripts/lwb_check_proof.py's own record validator so this never
    drifts from what the `lwb-proof` CI job itself enforces. An empty
    proof/ directory (the common case today -- see proof/README.md) is not
    an error; it just means the list is "(none yet)".
    """
    import lwb_check_proof  # local import: only --write needs this, --check must not

    if not PROOF_DIR.is_dir():
        return ["(none yet)"]

    # schema.json is the shape and exempt.json is the named-gap list (see
    # proof/README.md); neither is a proof record, and reporting exempt.json
    # as INVALID for lacking a 'deliverable' field is noise, not a finding.
    records = sorted(
        p for p in PROOF_DIR.glob("*.json") if p.name not in ("schema.json", "exempt.json")
    )
    if not records:
        return ["(none yet)"]

    lines: list[str] = []
    for path in records:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            lines.append(f"- {path.name}: INVALID (bad JSON: {exc})")
            continue
        errors = lwb_check_proof._validate_record(path, data)
        deliverable = data.get("deliverable", path.stem) if isinstance(data, dict) else path.stem
        if errors:
            lines.append(f"- {deliverable}: INVALID ({errors[0]})")
        else:
            lines.append(f"- {deliverable}: PROVEN (commit {data.get('commit')})")
    return lines


def _generate_block(cli: str = "unknown", session: str = "unknown") -> str:
    """Build the text between BEGIN_MARKER and END_MARKER from git/gh state.

    Every value here is re-derived live; nothing is carried over from a
    previous run. gh calls degrade to "unavailable" rather than failing
    the whole regeneration, since --write may run without gh auth. `cli`
    and `session` are supplied by the caller (`--cli`/`--session`), not
    derived -- see the module docstring for why.
    """
    main_sha = _run_git(["rev-parse", "origin/main"]) or _run_git(["rev-parse", "main"]) or "unknown"
    generated_at = _utc_now_iso()

    pr_list = _run_gh(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,headRefName,statusCheckRollup",
            "--template",
            "{{range .}}#{{.number}} {{.title}} ({{.headRefName}})\n{{end}}",
        ]
    )
    if not pr_list:
        pr_list = "(unavailable: no `gh` auth in this environment, or no open PRs)"

    lines = [
        BEGIN_MARKER,
        "",
        f"Generated: {generated_at}",
        f"main SHA: {main_sha}",
        f"CLI: {cli}",
        f"Session: {session}",
        "",
        "Open PRs:",
        pr_list.strip() if pr_list.strip() else "(none)",
        "",
        "Deliverable proof state (from proof/):",
        *_proof_state_lines(),
        "",
        END_MARKER,
    ]
    return "\n".join(lines) + "\n"


def _validate(text: str) -> list[str]:
    errors: list[str] = []

    size = len(text.encode("utf-8"))
    if size > SIZE_CAP_BYTES:
        errors.append(f"HANDOFF.md is {size} bytes, over the {SIZE_CAP_BYTES}-byte cap")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"missing required section heading: {section!r}")

    begin_count = text.count(BEGIN_MARKER)
    end_count = text.count(END_MARKER)
    if begin_count != 1:
        errors.append(f"expected exactly one {BEGIN_MARKER!r}, found {begin_count}")
    if end_count != 1:
        errors.append(f"expected exactly one {END_MARKER!r}, found {end_count}")
    if begin_count == 1 and end_count == 1:
        begin_idx = text.index(BEGIN_MARKER)
        end_idx = text.index(END_MARKER)
        if end_idx < begin_idx:
            errors.append("end marker appears before begin marker")

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            errors.append(f"forbidden pattern found (absolute path): {pattern.pattern!r}")

    lowered = text.lower()
    for needle in resolve_needles():
        if needle in lowered:
            errors.append(f"forbidden substring found: {needle!r}")

    # The durable sections moved out of HANDOFF.md under the 3000-byte cap.
    # Assert they landed in the protocol doc, so "trim HANDOFF.md" can never
    # quietly become "delete the hard rules".
    if not PROTOCOL_DOC.exists():
        errors.append(f"missing {PROTOCOL_DOC.name}: the moved sections have nowhere to live")
    else:
        protocol = PROTOCOL_DOC.read_text(encoding="utf-8")
        for section in PROTOCOL_REQUIRED_SECTIONS:
            if section not in protocol:
                errors.append(
                    f"docs/handoff-protocol.md is missing required section heading: {section!r}"
                )

    return errors


def cmd_check() -> int:
    if not HANDOFF_PATH.exists():
        print(f"FAIL: {HANDOFF_PATH} does not exist", file=sys.stderr)
        return 1
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    errors = _validate(text)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: {HANDOFF_PATH} passes all checks ({len(text.encode('utf-8'))} bytes)")
    return 0


def cmd_write(cli: str = "unknown", session: str = "unknown") -> int:
    if not HANDOFF_PATH.exists():
        print(f"FAIL: {HANDOFF_PATH} does not exist; cannot regenerate a block into nothing", file=sys.stderr)
        return 1
    text = HANDOFF_PATH.read_text(encoding="utf-8")
    if text.count(BEGIN_MARKER) != 1 or text.count(END_MARKER) != 1:
        print("FAIL: HANDOFF.md must already contain exactly one begin/end marker pair to regenerate", file=sys.stderr)
        return 1
    begin_idx = text.index(BEGIN_MARKER)
    end_idx = text.index(END_MARKER) + len(END_MARKER)
    new_block = _generate_block(cli=cli, session=session).rstrip("\n")
    new_text = text[:begin_idx] + new_block + text[end_idx:]
    HANDOFF_PATH.write_text(new_text, encoding="utf-8", newline="\n")
    errors = _validate(new_text)
    if errors:
        for error in errors:
            print(f"WARN after write: {error}", file=sys.stderr)
        return 1
    print(f"OK: wrote regenerated block to {HANDOFF_PATH}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="validate HANDOFF.md, exit 1 on failure")
    group.add_argument("--write", action="store_true", help="regenerate the generated block in place")
    parser.add_argument(
        "--cli", default="unknown", help="which CLI is writing this handoff, e.g. claude or codex"
    )
    parser.add_argument(
        "--session", default="unknown", help="this session's own id, for the generated block"
    )
    args = parser.parse_args(argv)

    if args.check:
        return cmd_check()
    return cmd_write(cli=args.cli, session=args.session)


if __name__ == "__main__":
    sys.exit(main())
