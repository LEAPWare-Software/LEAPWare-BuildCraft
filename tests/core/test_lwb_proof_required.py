"""lwb_proof_required as a PURE unit: Events in, Findings out.

Every test here constructs an `Event` directly. There is no tmpdir, no git
repository and no subprocess anywhere in this file -- that is the point of
the purity split, and if any of it became necessary the rule would have
stopped being pure. The impure half is tested in
tests/adapters/test_claude_repo_facts.py.
"""

from __future__ import annotations

import pytest

from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate
from lwb_core.events import Event, RepoFacts
from lwb_core.rules import lwb_proof_required

RULE = lwb_proof_required


def _bash(command: str, repo=None) -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        repo=repo,
    )


WARN = RuleConfig(mode=RuleMode.WARN)
DENY = RuleConfig(mode=RuleMode.DENY)

#: A repo mid-work: a branch, and records for other people's PRs.
NO_MATCH = RepoFacts(branch="lwb-ship-proof-rule", proof_ids=("21", "22", "24"))
#: The same repo once this branch's record exists.
MATCH_BY_BRANCH = RepoFacts(
    branch="lwb-ship-proof-rule", proof_ids=("24", "lwb-ship-proof-rule")
)


# --------------------------------------------------------------------
# The two decisions
# --------------------------------------------------------------------


def test_publish_without_matching_record_produces_a_finding():
    finding = RULE.evaluate(_bash("git push -u origin HEAD", NO_MATCH), WARN)
    assert finding is not None
    assert finding.rule_id == "lwb_proof_required"
    assert finding.mode is RuleMode.WARN
    assert "lwb-ship-proof-rule" in finding.reason


def test_publish_with_a_record_named_for_the_branch_is_silent():
    assert RULE.evaluate(_bash("git push", MATCH_BY_BRANCH), WARN) is None


def test_publish_with_a_record_named_for_the_pr_on_the_command_line_is_silent():
    assert RULE.evaluate(_bash("gh pr merge 24 --squash", NO_MATCH), WARN) is None


def test_publish_naming_a_pr_with_no_record_produces_a_finding():
    finding = RULE.evaluate(_bash("gh pr merge 99 --squash", NO_MATCH), WARN)
    assert finding is not None
    assert "'99'" in finding.reason


def test_a_number_embedded_in_the_branch_name_counts_as_a_match():
    """Widening the match set makes the rule QUIETER -- the safe direction."""
    repo = RepoFacts(branch="pr/24-ship-the-rule", proof_ids=("24",))
    assert RULE.evaluate(_bash("git push", repo), WARN) is None


def test_no_records_at_all_still_warns():
    """A consuming repo that has adopted nothing is exactly the target case."""
    repo = RepoFacts(branch="main", proof_ids=())
    finding = RULE.evaluate(_bash("git push origin main", repo), WARN)
    assert finding is not None
    assert "0 record(s)" in finding.reason


# --------------------------------------------------------------------
# Everything else is silent
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "python -m pytest tests/ -q",
        "git status",
        "git commit -m 'work'",
        "git fetch origin",
        "gh pr view 24",
        "gh pr list",
        "gh run watch",
    ],
)
def test_ordinary_work_is_untouched(command):
    assert RULE.evaluate(_bash(command, NO_MATCH), WARN) is None


@pytest.mark.parametrize(
    "command",
    [
        "git push --dry-run",
        "git push -n origin main",
        "git push --help",
        "git push -h",
    ],
)
def test_a_dry_run_or_help_publishes_nothing_and_is_not_gated(command):
    assert RULE.evaluate(_bash(command, NO_MATCH), WARN) is None


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "remember to git push later"',
        "git commit -m 'gh pr create when done'",
        'echo "git push" >> notes.txt',
        "grep -rn 'git push' docs/",
    ],
)
def test_a_publish_named_inside_a_quoted_string_is_not_a_publish(command):
    assert RULE.evaluate(_bash(command, NO_MATCH), WARN) is None


def test_a_publish_that_is_not_the_first_token_is_not_recognized():
    """Under-match: `echo git push` must not fire."""
    assert RULE.evaluate(_bash("echo git push", NO_MATCH), WARN) is None


def test_a_heredoc_body_written_to_a_file_is_not_a_publish():
    """Finding 1: a heredoc BODY is data, not a new shell command.

    `cat > x.sh <<'EOF'` followed by a body line of `git push origin main`
    writes a SCRIPT; it does not publish. `_SEGMENT_SPLIT` (which splits on
    newlines among other things) must not treat the body's line as its own
    segment.
    """
    command = "cat > x.sh <<'EOF'\ngit push origin main\nEOF"
    assert RULE.evaluate(_bash(command, NO_MATCH), WARN) is None


def test_a_real_publish_on_the_introducer_line_is_still_caught_past_a_heredoc():
    """A heredoc used as stdin for a REAL publish must still be caught.

    `gh pr create --body-file - <<EOF ... EOF` genuinely runs `gh pr
    create` (the heredoc is its stdin, not a separate command) -- that IS
    a publish, on the introducer line itself, independent of whatever the
    heredoc body happens to contain. Stripping the body must not blind the
    rule to a real publish that precedes the `<<`.
    """
    command = "gh pr create --body-file - <<EOF\nthen something unrelated\nEOF"
    finding = RULE.evaluate(_bash(command, NO_MATCH), WARN)
    assert finding is not None


@pytest.mark.parametrize(
    "command",
    [
        "python -m pytest -q && git push",
        "git add -A; git commit -m ok; git push",
        "git fetch || git push origin HEAD",
        "git add -A\ngit push",
    ],
)
def test_a_publish_later_in_a_chain_is_still_recognized(command):
    """The one direction where NOT matching would be a real miss."""
    finding = RULE.evaluate(_bash(command, NO_MATCH), WARN)
    assert finding is not None, command


def test_non_bash_tools_are_untouched():
    event = Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "git push the branch"},
        repo=NO_MATCH,
    )
    assert RULE.evaluate(event, WARN) is None


def test_non_pretooluse_events_are_untouched():
    event = Event(
        hook_event="Stop",
        tool_name="Bash",
        tool_input={"command": "git push"},
        repo=NO_MATCH,
    )
    assert RULE.evaluate(event, WARN) is None


@pytest.mark.parametrize("tool_input", [{}, {"command": ""}, {"command": 17}])
def test_a_missing_or_non_string_command_is_untouched(tool_input):
    event = Event(
        hook_event="PreToolUse", tool_name="Bash", tool_input=tool_input, repo=NO_MATCH
    )
    assert RULE.evaluate(event, WARN) is None


# --------------------------------------------------------------------
# The purity contract: no facts means no opinion
# --------------------------------------------------------------------


def test_no_repo_facts_means_no_opinion():
    """`repo is None` is "the adapter gathered nothing", not "nothing found".

    This is what keeps the rule inert under an adapter that has not been
    taught to collect repo facts -- today, the Codex adapter. If this ever
    flipped to a warning, every Codex push would warn forever.
    """
    assert RULE.evaluate(_bash("git push", repo=None), WARN) is None


def test_detached_head_with_no_pr_number_is_silent():
    repo = RepoFacts(branch=None, proof_ids=("24",))
    assert RULE.evaluate(_bash("git push origin HEAD", repo), WARN) is None


def test_detached_head_still_judges_an_explicit_pr_number():
    repo = RepoFacts(branch=None, proof_ids=("24",))
    assert RULE.evaluate(_bash("gh pr merge 24", repo), WARN) is None
    assert RULE.evaluate(_bash("gh pr merge 99", repo), WARN) is not None


def test_the_rule_reads_nothing_but_its_arguments():
    """A crude but real purity probe: the module imports no I/O machinery."""
    import inspect

    source = inspect.getsource(lwb_proof_required)
    for forbidden in ("import os", "import subprocess", "open(", "Path(", "environ"):
        assert forbidden not in source, f"rule must stay pure, found {forbidden!r}"


# --------------------------------------------------------------------
# Mode: unlike lwb_version, this rule is armable
# --------------------------------------------------------------------


def test_mode_is_honoured_so_a_policy_can_arm_it():
    finding = RULE.evaluate(_bash("git push", NO_MATCH), DENY)
    assert finding is not None
    assert finding.mode is RuleMode.DENY


def test_through_the_engine_warn_permits_and_deny_blocks():
    event = _bash("git push", NO_MATCH)

    warn_decision = evaluate(event, Policy(rules={"lwb_proof_required": WARN}))
    assert warn_decision.permit is True
    assert any("no proof record" in w for w in warn_decision.warnings)

    deny_decision = evaluate(event, Policy(rules={"lwb_proof_required": DENY}))
    assert deny_decision.permit is False
    assert "no proof record" in (deny_decision.deny_reason or "")


def test_off_means_the_rule_never_runs():
    decision = evaluate(
        _bash("git push", NO_MATCH),
        Policy(rules={"lwb_proof_required": RuleConfig(mode=RuleMode.OFF)}),
    )
    assert decision.findings == []


def test_the_shipped_default_is_warn_not_deny():
    """The rule ships report-only. Arming it is a separate, deliberate change."""
    import json
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    policy = json.loads(
        (repo_root / "core" / "policy" / "default.json").read_text(encoding="utf-8")
    )
    assert policy["rules"]["lwb_proof_required"]["mode"] == "warn"


def test_the_rule_is_registered():
    from lwb_core.rules import RULES

    assert lwb_proof_required in RULES
