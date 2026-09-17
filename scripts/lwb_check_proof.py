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

    return errors


def validate_all() -> tuple[list[str], int]:
    errors: list[str] = []
    count = 0
    if PROOF_DIR.is_dir():
        for path in sorted(PROOF_DIR.glob("*.json")):
            if path.name == "schema.json":
                continue
            count += 1
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"{path.relative_to(REPO_ROOT)}: invalid JSON: {exc}")
                continue
            errors.extend(_validate_record(path, data))
    return errors, count


def main() -> int:
    errors, count = validate_all()
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
