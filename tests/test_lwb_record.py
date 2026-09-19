"""Tests for scripts/lwb_record.py, the committed proof-record recorder.

Replaces the throwaway `capture.py` that docs/maintainers/session-protocol.md
used to tell every session to hand-write and delete. See
docs/maintainers/proof-of-completion-plan.md, open blocker 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_record  # noqa: E402
import lwb_sanitise  # noqa: E402


def test_run_command_captures_argv_exit_and_expect_exit():
    entry = lwb_record.run_command([sys.executable, "-c", "print('hi')"], expect_exit=0)
    assert entry["argv"] == [sys.executable, "-c", "print('hi')"]
    assert entry["exit"] == 0
    assert entry["expect_exit"] == 0


def test_run_command_records_nonzero_exit_honestly():
    entry = lwb_record.run_command(
        [sys.executable, "-c", "import sys; sys.exit(3)"], expect_exit=0
    )
    assert entry["exit"] == 3
    assert entry["expect_exit"] == 0


def test_run_command_output_is_sanitised():
    home = str(Path.home())
    entry = lwb_record.run_command(
        [sys.executable, "-c", f"print({home!r})"], expect_exit=0
    )
    assert "<home>" in "\n".join(entry["tail"])
    assert home not in "\n".join(entry["tail"])


def test_run_command_sha256_is_over_sanitised_text_not_raw():
    home = str(Path.home())
    entry = lwb_record.run_command(
        [sys.executable, "-c", f"print({home!r})"], expect_exit=0
    )
    import subprocess
    raw = subprocess.run(
        [sys.executable, "-c", f"print({home!r})"], capture_output=True, text=True
    )
    combined_raw = raw.stdout + raw.stderr
    combined_sanitised = lwb_sanitise.sanitise(combined_raw)
    import hashlib
    assert entry["sha256"] == hashlib.sha256(combined_sanitised.encode("utf-8")).hexdigest()


def test_run_command_tail_is_at_most_ten_nonempty_lines():
    code = "for i in range(30): print(i)"
    entry = lwb_record.run_command([sys.executable, "-c", code], expect_exit=0)
    assert len(entry["tail"]) == 10
    assert entry["tail"][-1] == "29"


def test_run_command_carries_sanitiser_version():
    entry = lwb_record.run_command([sys.executable, "-c", "print('x')"], expect_exit=0)
    assert entry["sanitiser_version"] == lwb_sanitise.SANITISER_VERSION


def test_run_command_never_run_raises_rather_than_faking_a_result():
    """A command that cannot even be launched (bad executable) is an
    ERROR, never silently recorded as if it produced a zero exit."""
    import pytest
    with pytest.raises(Exception):
        lwb_record.run_command(["this-executable-does-not-exist-xyz"], expect_exit=0)


def test_run_command_accepts_verifiable_true():
    entry = lwb_record.run_command(
        [sys.executable, "-c", "print('x')"], expect_exit=0, verifiable=True
    )
    assert entry["verifiable"] is True
    assert "verifiable_reason" not in entry


def test_run_command_requires_reason_when_not_verifiable():
    import pytest
    with pytest.raises(ValueError):
        lwb_record.run_command(
            [sys.executable, "-c", "print('x')"], expect_exit=0, verifiable=False
        )


def test_run_command_rejects_reason_outside_enum():
    import pytest
    with pytest.raises(ValueError):
        lwb_record.run_command(
            [sys.executable, "-c", "print('x')"],
            expect_exit=0,
            verifiable=False,
            verifiable_reason="because",
        )


def test_run_command_accepts_valid_reason_when_not_verifiable():
    entry = lwb_record.run_command(
        [sys.executable, "-c", "print('x')"],
        expect_exit=1,
        verifiable=False,
        verifiable_reason="nondeterministic-output",
    )
    assert entry["verifiable"] is False
    assert entry["verifiable_reason"] == "nondeterministic-output"


def test_run_command_accepts_resolved_base_and_head():
    entry = lwb_record.run_command(
        [sys.executable, "-c", "print('x')"],
        expect_exit=0,
        resolved_base="a" * 40,
        resolved_head="b" * 40,
    )
    assert entry["resolved_base"] == "a" * 40
    assert entry["resolved_head"] == "b" * 40


def test_run_commands_builds_a_commands_array():
    spec = [
        {"argv": [sys.executable, "-c", "print('a')"], "expect_exit": 0},
        {"argv": [sys.executable, "-c", "print('b')"], "expect_exit": 0},
    ]
    commands = lwb_record.run_commands(spec)
    assert len(commands) == 2
    assert all("sha256" in c for c in commands)


def test_summarise_verifiability_counts_true_and_false():
    commands = [
        {"verifiable": True},
        {"verifiable": True},
        {"verifiable": False, "verifiable_reason": "needs-build-step"},
    ]
    summary = lwb_record.summarise_verifiability(commands)
    assert summary["verifiable_count"] == 2
    assert summary["total_count"] == 3
    assert summary["summary"] == "2 of 3 commands are independently re-executable"


def test_summarise_verifiability_never_claims_full_falsifiability_in_wording():
    commands = [{"verifiable": True}]
    summary = lwb_record.summarise_verifiability(commands)
    assert "falsifiable" not in summary["summary"].lower()
    assert "independently re-executable" in summary["summary"]
