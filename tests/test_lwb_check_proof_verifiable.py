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


def test_range_command_via_equals_form_base_head_flags_is_detected():
    """lwb_lanes.py's own argparse accepts --base=X / --head=Y (equals
    form), not just separate tokens -- both must be recognised as a range."""
    record = _pr20_base(
        commands=[
            _cmd(
                argv=[
                    "python", "scripts/lwb_lanes.py",
                    "--base=origin/main", "--head=HEAD",
                ],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("resolved_base" in e and "lwb_lanes.py" in e for e in errors)


def test_range_command_via_caret_exclusion_syntax_is_detected():
    """git's '^ref' exclusion syntax (e.g. `git log A ^B`) names a range
    just as much as 'A..B' does."""
    record = _pr20_base(
        commands=[
            _cmd(
                argv=["git", "log", "HEAD", "^origin/main"],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("resolved_base" in e for e in errors)


def test_resolved_base_must_look_like_a_sha_not_a_symbolic_ref():
    """A record writing the UNRESOLVED symbolic ref itself
    ('origin/main', 'HEAD') into resolved_base/resolved_head defeats the
    field's entire purpose -- it must be a real sha, matching
    lwb_check_proof.py's existing COMMIT_RE convention for 'commit'."""
    record = _pr20_base(
        commands=[
            _cmd(
                argv=["python", "scripts/lwb_check_env_leak.py", "--range", "origin/main..HEAD"],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
                resolved_base="origin/main",
                resolved_head="HEAD",
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert any("resolved_base" in e and "origin/main" in e for e in errors)
    assert any("resolved_head" in e and "HEAD" in e for e in errors)


def test_resolved_shas_as_real_hex_shas_are_accepted():
    record = _pr20_base(
        commands=[
            _cmd(
                argv=["python", "scripts/lwb_check_env_leak.py", "--range", "origin/main..HEAD"],
                verifiable=False,
                verifiable_reason="git-range-not-reproducible",
                resolved_base="a" * 40,
                resolved_head="b" * 7,
            )
        ]
    )
    errors = lwb_check_proof._validate_record(Path("r.json"), record)
    assert errors == []


def test_bare_two_revision_form_is_a_documented_known_gap():
    """`git diff origin/main HEAD` (no '..', no '^', no --base/--head) is
    NOT detected as a range -- pinned as a known, documented gap rather
    than a silent one: distinguishing it from `git diff HEAD file.py`
    (one revision plus a pathspec) needs real git argument parsing this
    validator does not attempt. If this starts failing, the detection
    logic changed and the docstring must be updated to match."""
    assert lwb_check_proof._argv_has_git_range(
        ["git", "diff", "origin/main", "HEAD"]
    ) is False


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


# --- The self-declared 'pr' bypass, found by adversarial review of PR #19's
# own claim that lwb_check_proof.py was checked and safe. check_pr_has_record
# reconciles the record that CLAIMS a given PR (exact-match only), but
# nothing previously stopped an ADDITIONAL record from lying about its own
# 'pr' to dodge the pr >= 12 / pr >= 20 enforcement cutoffs entirely.
# reviews/<pr>/ derives its authoritative PR number from the DIRECTORY, not
# the record's own content (see lwb_lanes.py::_review_ok); proof/ has no
# per-PR directory, but this repo's own convention names every PR-tied
# record after its PR number (7.json .. 19.json), so a bare-digit FILENAME
# is the equivalent external-to-content authority here. A mismatch between
# a bare-digit filename and the record's self-declared 'pr' is rejected,
# and gating uses the STRICTER (higher) of the two -- fail closed on
# disagreement, never fail open onto the lower, exploitable number.


def test_digit_filename_disagreeing_with_self_declared_pr_is_rejected():
    """The exact bypass: a record filed as 20.json (this PR's own natural
    name) but self-declaring 'pr': 19 to dodge the pr >= 20 field
    requirements -- carrying a git-range command with no resolved_*, no
    sanitiser_version, and a non-boolean 'verifiable'."""
    record = _pr20_base(
        pr=19,
        commands=[
            {
                "argv": ["python", "scripts/lwb_check_env_leak.py", "--range", "origin/main..HEAD"],
                "exit": 0,
                "expect_exit": 0,
                "tail": ["ok"],
                "sha256": "b" * 64,
                "verifiable": "yes",  # non-boolean
            }
        ],
    )
    errors = lwb_check_proof._validate_record(Path("proof/20.json"), record)
    assert any(
        "does not match" in e and "20" in e and "19" in e for e in errors
    ), errors
    # Fail closed: gating still applies at the STRICTER number (20), so the
    # missing verifiability fields on the smuggled command are caught too.
    assert any("sanitiser_version" in e for e in errors), errors
    assert any("'verifiable' must be a boolean" in e for e in errors), errors
    assert any("resolved_base" in e for e in errors), errors


def test_digit_filename_agreeing_with_self_declared_pr_passes():
    record = _pr20_base()
    errors = lwb_check_proof._validate_record(Path("proof/20.json"), record)
    assert errors == []


def test_non_digit_filename_is_not_treated_as_authoritative():
    """schema.json documents 'deliverable' as an issue/step number OR a
    short slug -- a non-digit filename carries no filename-derived
    authority, so no mismatch is manufactured against it."""
    record = _pr20_base()
    errors = lwb_check_proof._validate_record(Path("proof/falsifiable-records.json"), record)
    assert errors == []


def test_digit_filename_below_cutoff_agreeing_with_pr_field_passes():
    """A genuinely historical record (7.json, pr: 7) must not be flagged --
    filename and self-declared pr agree, and neither crosses the cutoff."""
    record = {
        "deliverable": "7",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "pr": 7,
        "commands": [],
        "mutations": [],
        "unproven": [],
    }
    errors = lwb_check_proof._validate_record(Path("proof/7.json"), record)
    assert errors == []


def test_digit_filename_with_no_self_declared_pr_is_gated_by_the_filename_alone():
    """Fail closed: omitting 'pr' entirely would be an even easier dodge
    than lying about it, so a numeric filename with NO 'pr' field still
    gates on the filename's number -- there is no disagreement to report
    (nothing to compare against), but the strict requirements still apply."""
    record = {
        "deliverable": "20",
        "author": "claude",
        "checked_by": "codex",
        "commit": "a" * 40,
        "commands": [],
        "mutations": [],
        "unproven": [],
    }
    errors = lwb_check_proof._validate_record(Path("proof/20.json"), record)
    assert any("does not match" in e for e in errors) is False  # no pr to disagree with
    assert any("acceptance_criteria" in e for e in errors), errors
