"""Pins the one legitimate correction to a proof record this repo has ever
made: `proof/20.json` originally marked `lwb_handoff.py --check` as
`verifiable: true`. That command's output embeds the byte count of the
GENERATED block in `HANDOFF.md`, which legitimately changes with repo
state (main SHA, open-PR listing, proof-state summary) -- so its digest
can only reproduce when the byte count happens to coincide across commits,
which is not "reproducible", it is a coincidence. Confirmed by observing
the SAME command print 2262 bytes on `main` (f8cb770) and 2214 bytes on a
feature branch (107d5f4) with no change to the tracked file itself.

This is a correction to the record AUTHOR'S OWN CLASSIFICATION, never to
captured evidence: `sha256`, `tail`, `exit`, and `argv` for this command
must be byte-for-byte identical to what shipped in PR #20. Only
`verifiable` (true -> false) and the addition of `verifiable_reason` may
differ, plus a new `unproven[]` entry admitting the mistake. Rewriting the
captured fields instead would be exactly the fabrication proof records
exist to prevent -- see proof/README.md and this test.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_PATH = REPO_ROOT / "proof" / "20.json"

# The captured evidence for this command, exactly as PR #20 shipped it --
# never touched by the correction.
FROZEN_ARGV = ["python", "scripts/lwb_handoff.py", "--check"]
FROZEN_EXIT = 0
FROZEN_TAIL = ["OK: <repo>/HANDOFF.md passes all checks (2214 bytes)"]
FROZEN_SHA256 = "75c03a5b153adf1686b42590fdb5ecf5e2cd1cf9ea0b307c66e7d81471224348"


def _handoff_check_command():
    data = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    for cmd in data["commands"]:
        if cmd.get("argv") == FROZEN_ARGV:
            return data, cmd
    raise AssertionError("proof/20.json no longer carries a lwb_handoff.py --check command")


def test_handoff_check_captured_evidence_is_unchanged():
    """The fix corrects a flag, not the evidence -- these fields must stay
    exactly as originally recorded."""
    _data, cmd = _handoff_check_command()
    assert cmd["argv"] == FROZEN_ARGV
    assert cmd["exit"] == FROZEN_EXIT
    assert cmd["tail"] == FROZEN_TAIL
    assert cmd["sha256"] == FROZEN_SHA256


def test_handoff_check_is_now_marked_unverifiable():
    """The command embeds HANDOFF.md's generated-block byte count, which
    varies with repo state (main SHA, open-PR listing, proof-state
    summary) independent of the tracked content at the recorded commit --
    its digest is not reproducible, and marking it verifiable: true was
    the author's own mistake, not a machine-checkable one."""
    _data, cmd = _handoff_check_command()
    assert cmd.get("verifiable") is False
    assert cmd.get("verifiable_reason") == "nondeterministic-output"


def test_record_admits_the_correction_in_unproven():
    data, _cmd = _handoff_check_command()
    unproven_text = " ".join(data.get("unproven", []))
    assert "lwb_handoff.py" in unproven_text
    assert "byte" in unproven_text.lower()
    assert "verifiable" in unproven_text.lower()


def test_the_other_two_verifiable_true_commands_are_unaffected():
    """lwb_check_prefix.py and lwb_check_no_instruction_dep.py print a
    fixed success string on their passing path -- no count, no path, no
    timestamp -- confirmed by reading both scripts' source. They stay
    verifiable: true; this correction does not touch them."""
    data = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    still_true = {
        tuple(c["argv"])
        for c in data["commands"]
        if c.get("verifiable") is True
    }
    assert ("python", "scripts/lwb_check_prefix.py") in still_true
    assert ("python", "scripts/lwb_check_no_instruction_dep.py") in still_true
    assert ("python", "scripts/lwb_handoff.py", "--check") not in still_true
