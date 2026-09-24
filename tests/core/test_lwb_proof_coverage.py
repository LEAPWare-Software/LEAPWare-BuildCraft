"""lwb_proof_coverage as a PURE unit: Events in, Findings out.

No tmpdir, no git repository, no subprocess anywhere in this file, same
purity split `tests/core/test_lwb_proof_required.py` documents. The
impure collector (`collect_landed_unproven`) is tested in
`tests/adapters/test_claude_repo_facts_landed_unproven.py`.
"""

from __future__ import annotations

import pytest

from lwb_core.config import RuleConfig, RuleMode
from lwb_core.events import Event, RepoFacts
from lwb_core.rules import lwb_proof_coverage

RULE = lwb_proof_coverage

WARN = RuleConfig(mode=RuleMode.WARN)
DENY = RuleConfig(mode=RuleMode.DENY)


def _bash(command: str, repo=None) -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        repo=repo,
    )


GAPS = RepoFacts(branch="main", proof_ids=(), landed_unproven=("abc123def456 (#41)",))
NO_GAPS = RepoFacts(branch="main", proof_ids=("41",), landed_unproven=())


# --------------------------------------------------------------------
# The two decisions
# --------------------------------------------------------------------


def test_a_publish_with_landed_gaps_produces_a_finding():
    finding = RULE.evaluate(_bash("git push", GAPS), WARN)
    assert finding is not None
    assert finding.rule_id == "lwb_proof_coverage"
    assert finding.mode is RuleMode.WARN
    assert "abc123def456 (#41)" in finding.reason
    assert "1 landed deliverable" in finding.reason


def test_a_publish_with_no_gaps_is_silent():
    assert RULE.evaluate(_bash("git push", NO_GAPS), WARN) is None


def test_the_finding_says_it_is_not_exhaustive():
    """The scan is best-effort/local -- the finding must say so, every time,
    so it is never read as a claim of full coverage."""
    finding = RULE.evaluate(_bash("git push", GAPS), WARN)
    assert "not exhaustive" in finding.reason


def test_more_than_the_named_cap_falls_back_to_a_count():
    many = RepoFacts(
        branch="main",
        proof_ids=(),
        landed_unproven=tuple(f"{i:012x} (#{i})" for i in range(1, 8)),
    )
    finding = RULE.evaluate(_bash("git push", many), WARN)
    assert finding is not None
    assert "7 landed deliverable" in finding.reason
    assert "and 2 more" in finding.reason


# --------------------------------------------------------------------
# Trigger: same publish-detection as lwb_proof_required
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    ["ls -la", "git status", "git commit -m 'git push later'", "gh pr view 24"],
)
def test_non_publishing_commands_are_untouched(command):
    assert RULE.evaluate(_bash(command, GAPS), WARN) is None


def test_non_bash_tools_are_untouched():
    event = Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "git push the branch"},
        repo=GAPS,
    )
    assert RULE.evaluate(event, WARN) is None


def test_non_pretooluse_events_are_untouched():
    event = Event(
        hook_event="Stop", tool_name="Bash", tool_input={"command": "git push"}, repo=GAPS
    )
    assert RULE.evaluate(event, WARN) is None


@pytest.mark.parametrize("tool_input", [{}, {"command": ""}, {"command": 17}])
def test_a_missing_or_non_string_command_is_untouched(tool_input):
    event = Event(hook_event="PreToolUse", tool_name="Bash", tool_input=tool_input, repo=GAPS)
    assert RULE.evaluate(event, WARN) is None


# --------------------------------------------------------------------
# The purity contract: no facts means no opinion
# --------------------------------------------------------------------


def test_no_repo_facts_means_no_opinion():
    assert RULE.evaluate(_bash("git push", repo=None), WARN) is None


def test_incomplete_facts_are_silent_even_with_gaps_present():
    repo = RepoFacts(
        branch="main",
        proof_ids=(),
        landed_unproven=("abc123def456 (#41)",),
        facts_incomplete=True,
        facts_incomplete_reason="could not read proof/: PermissionError",
    )
    assert RULE.evaluate(_bash("git push", repo), WARN) is None


# --------------------------------------------------------------------
# Mode
# --------------------------------------------------------------------


def test_mode_is_honoured_so_a_policy_can_arm_it():
    finding = RULE.evaluate(_bash("git push", GAPS), DENY)
    assert finding is not None
    assert finding.mode is RuleMode.DENY
