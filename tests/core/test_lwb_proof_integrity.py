"""lwb_proof_integrity as a PURE unit: Events in, Findings out.

No tmpdir, no git repository, no subprocess anywhere in this file, same
purity split `tests/core/test_lwb_proof_required.py` documents. The
impure collector (`collect_matched_proof_facts`) is tested in
`tests/adapters/test_claude_repo_facts_matched_proof.py`.
"""

from __future__ import annotations

import pytest

from lwb_core.config import RuleConfig, RuleMode
from lwb_core.events import Event, RepoFacts
from lwb_core.rules import lwb_proof_integrity

RULE = lwb_proof_integrity

WARN = RuleConfig(mode=RuleMode.WARN)
DENY = RuleConfig(mode=RuleMode.DENY)


def _bash(command: str, repo=None) -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        repo=repo,
    )


CLEAN = RepoFacts(
    branch="main",
    proof_ids=("main",),
    matched_proof_self_certified=False,
    matched_proof_has_failed_command=False,
)
SELF_CERTIFIED = RepoFacts(
    branch="main",
    proof_ids=("main",),
    matched_proof_self_certified=True,
    matched_proof_has_failed_command=False,
)
FAILED_COMMAND = RepoFacts(
    branch="main",
    proof_ids=("main",),
    matched_proof_self_certified=False,
    matched_proof_has_failed_command=True,
)
BOTH = RepoFacts(
    branch="main",
    proof_ids=("main",),
    matched_proof_self_certified=True,
    matched_proof_has_failed_command=True,
)
NO_OPINION = RepoFacts(
    branch="main",
    proof_ids=(),
    matched_proof_self_certified=None,
    matched_proof_has_failed_command=None,
)


# --------------------------------------------------------------------
# The two decisions
# --------------------------------------------------------------------


def test_a_self_certified_record_produces_a_finding():
    finding = RULE.evaluate(_bash("git push", SELF_CERTIFIED), WARN)
    assert finding is not None
    assert finding.rule_id == "lwb_proof_integrity"
    assert "self" in finding.reason
    assert "main" in finding.reason


def test_a_recorded_failed_command_produces_a_finding():
    finding = RULE.evaluate(_bash("git push", FAILED_COMMAND), WARN)
    assert finding is not None
    assert "exit" in finding.reason


def test_both_problems_are_named_in_one_finding():
    finding = RULE.evaluate(_bash("git push", BOTH), WARN)
    assert finding is not None
    assert "self" in finding.reason
    assert "exit" in finding.reason


def test_a_clean_record_is_silent():
    assert RULE.evaluate(_bash("git push", CLEAN), WARN) is None


def test_no_matching_record_is_silent_not_a_violation():
    """None means no-opinion -- this is lwb_proof_required's territory."""
    assert RULE.evaluate(_bash("git push", NO_OPINION), WARN) is None


def test_the_finding_says_it_does_not_re_execute():
    finding = RULE.evaluate(_bash("git push", SELF_CERTIFIED), WARN)
    assert "does not re-run" in finding.reason


# --------------------------------------------------------------------
# Trigger: same publish-detection as lwb_proof_required
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    ["ls -la", "git status", "git commit -m 'git push later'", "gh pr view 24"],
)
def test_non_publishing_commands_are_untouched(command):
    assert RULE.evaluate(_bash(command, SELF_CERTIFIED), WARN) is None


def test_non_bash_tools_are_untouched():
    event = Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "git push the branch"},
        repo=SELF_CERTIFIED,
    )
    assert RULE.evaluate(event, WARN) is None


def test_non_pretooluse_events_are_untouched():
    event = Event(
        hook_event="Stop",
        tool_name="Bash",
        tool_input={"command": "git push"},
        repo=SELF_CERTIFIED,
    )
    assert RULE.evaluate(event, WARN) is None


@pytest.mark.parametrize("tool_input", [{}, {"command": ""}, {"command": 17}])
def test_a_missing_or_non_string_command_is_untouched(tool_input):
    event = Event(
        hook_event="PreToolUse", tool_name="Bash", tool_input=tool_input, repo=SELF_CERTIFIED
    )
    assert RULE.evaluate(event, WARN) is None


# --------------------------------------------------------------------
# The purity contract: no facts means no opinion
# --------------------------------------------------------------------


def test_no_repo_facts_means_no_opinion():
    assert RULE.evaluate(_bash("git push", repo=None), WARN) is None


def test_incomplete_facts_are_silent_even_with_a_problem_present():
    repo = RepoFacts(
        branch="main",
        proof_ids=("main",),
        matched_proof_self_certified=True,
        facts_incomplete=True,
        facts_incomplete_reason="could not read .git/HEAD: IsADirectoryError",
    )
    assert RULE.evaluate(_bash("git push", repo), WARN) is None


# --------------------------------------------------------------------
# Mode
# --------------------------------------------------------------------


def test_mode_is_honoured_so_a_policy_can_arm_it():
    finding = RULE.evaluate(_bash("git push", SELF_CERTIFIED), DENY)
    assert finding is not None
    assert finding.mode is RuleMode.DENY
