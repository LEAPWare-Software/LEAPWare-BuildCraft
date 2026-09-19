"""Tests for the verifiability fields on proof/*.json commands[] entries.

docs/maintainers/proof-of-completion-plan.md, open blockers 1-3: a proof
record's commands[] entries must say which sanitiser produced their digest
(`sanitiser_version`), whether the command is independently re-executable
(`verifiable` / `verifiable_reason` from a closed enum), and, for any
command whose argv names a git revision range, exactly which shas it ran
against (`resolved_base` / `resolved_head`) -- without those a CI
re-execution resolves a different commit than the one the record proves
and an honest record fails.

These fields are enforced only for records whose typed `pr` is >= 20 (the
plan's stated cutoff), exactly like the pr >= 12 gate for
acceptance_criteria/tokens -- existing records (7-19) predate the scheme
and are never rewritten to add fields that were never captured.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402


def _pr20_base(**overrides):
    record = {
        "deliverable": "falsifiable-records",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "pr": 20,
        "mutations": [],
        "unproven": [],
        "acceptance_criteria": [{"criterion": "it works", "met": True}],
        "tokens": {
            "total_input": 1,
            "cached_input": 0,
            "uncached_input": 1,
            "output": 1,
            "retries": "unknown",
            "setup_overhead": "unknown",
            "tool_overhead": "unknown",
            "wall_time_seconds": 1,
            "source": "transcript message.usage",
        },
        "commands": [
            {
                "argv": ["python", "scripts/lwb_check_prefix.py"],
                "exit": 0,
                "expect_exit": 0,
                "tail": ["ok"],
                "sha256": "b" * 64,
                "sanitiser_version": "1",
                "verifiable": True,
            }
        ],
    }
    record.update(overrides)
    return record


def _cmd(**overrides):
    base = {
        "argv": ["python", "scripts/lwb_check_prefix.py"],
        "exit": 0,
        "expect_exit": 0,
        "tail": ["ok"],
        "sha256": "b" * 64,
        "sanitiser_version": "1",
        "verifiable": True,
    }
    base.update(overrides)
    return base


def test_pr20_command_with_sanitiser_version_and_verifiable_passes():
    errors = lwb_check_proof._validate_record(Path("r.json"), _pr20_base())
    assert errors == []


def test_pr20_command_missing_sanitiser_version_fails():
    record = _pr20_base(commands=[_cmd()])
    del record["commands"][0]["sanitiser_version"]
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("sanitiser_version" in e for e in errors)


def test_pr20_command_with_empty_sanitiser_version_fails():
    record = _pr20_base(commands=[_cmd(sanitiser_version="")])
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("sanitiser_version" in e for e in errors)


def test_pr20_command_missing_verifiable_fails():
    record = _pr20_base(commands=[_cmd()])
    del record["commands"][0]["verifiable"]
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("verifiable" in e for e in errors)


def test_false_verifiable_with_no_reason_is_rejected():
    record = _pr20_base(commands=[_cmd(verifiable=False)])
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any(
        "verifiable_reason" in e and "lwb_check_prefix.py" in e for e in errors
    )


def test_false_verifiable_with_reason_outside_enum_is_rejected():
    record = _pr20_base(
        commands=[_cmd(verifiable=False, verifiable_reason="it was raining")]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any(
        "verifiable_reason" in e and "it was raining" in e for e in errors
    )


def test_false_verifiable_with_each_enum_reason_is_accepted():
    for reason in (
        "nondeterministic-output",
        "git-range-not-reproducible",
        "needs-repo-secret",
        "needs-build-step",
    ):
        record = _pr20_base(commands=[_cmd(verifiable=False, verifiable_reason=reason)])
        errors = lwb_check_proof._validate_record(Path("r.json"), record)
        assert errors == [], (reason, errors)


def test_true_verifiable_needs_no_reason():
    record = _pr20_base(commands=[_cmd(verifiable=True)])
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_range_command_missing_resolved_shas_is_rejected():
    record = _pr20_base(
        commands=[
            _cmd(
                argv=["python", "scripts/lwb_check_env_leak.py", "--range", "origin/main..HEAD"],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any(
        "resolved_base" in e and "lwb_check_env_leak.py" in e for e in errors
    )


def test_range_command_with_resolved_shas_is_accepted():
    record = _pr20_base(
        commands=[
            _cmd(
                argv=["python", "scripts/lwb_check_env_leak.py", "--range", "origin/main..HEAD"],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
                resolved_base="c" * 40,
                resolved_head="d" * 40,
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_range_command_via_separate_base_head_flags_requires_resolved_shas():
    """lwb_lanes.py takes --base/--head as separate flags rather than a
    single 'a..b' argv token -- still a range command."""
    record = _pr20_base(
        commands=[
            _cmd(
                argv=[
                    "python", "scripts/lwb_lanes.py",
                    "--base", "origin/main", "--head", "HEAD",
                ],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("resolved_base" in e and "lwb_lanes.py" in e for e in errors)


def test_non_range_command_does_not_require_resolved_shas():
    record = _pr20_base(commands=[_cmd()])
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_pr19_record_without_new_fields_still_passes():
    """The pr >= 20 gate stays inert below 20: verifiability enforcement
    must not retroactively break records that predate the scheme. (The
    separate pr >= 12 gate for acceptance_criteria/tokens still applies,
    so this record carries those -- it is testing ONLY that the
    verifiability fields are not additionally required.)"""
    record = {
        "deliverable": "reviewer-identity",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "pr": 19,
        "acceptance_criteria": [{"criterion": "it works", "met": True}],
        "tokens": {
            "total_input": 1,
            "cached_input": 0,
            "uncached_input": 1,
            "output": 1,
            "retries": "unknown",
            "setup_overhead": "unknown",
            "tool_overhead": "unknown",
            "wall_time_seconds": 1,
            "source": "transcript message.usage",
        },
        "commands": [
            {
                "argv": ["python", "-m", "pytest", "tests/", "-q"],
                "exit": 0,
                "expect_exit": 0,
                "tail": ["265 passed"],
                "sha256": "e" * 64,
            }
        ],
        "mutations": [],
        "unproven": [],
    }
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []
