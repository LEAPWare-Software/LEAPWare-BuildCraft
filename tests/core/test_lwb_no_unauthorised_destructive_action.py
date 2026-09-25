"""lwb_no_unauthorised_destructive_action as a PURE unit: Events in, Findings out.

Every test constructs an `Event` directly. There is no tmpdir, no git
repository and no subprocess anywhere in this file -- the same purity split
`test_lwb_proof_required.py` documents and enforces for its own rule.
"""

from __future__ import annotations

import pytest

from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate
from lwb_core.events import Event, RepoFacts
from lwb_core.rules import lwb_no_unauthorised_destructive_action as RULE

WARN = RuleConfig(mode=RuleMode.WARN)
DENY = RuleConfig(mode=RuleMode.DENY)

#: An ordinary repo with facts gathered -- the "adapter is doing its job"
#: baseline every test starts from unless it is specifically about missing
#: or incomplete facts.
REPO = RepoFacts(branch="main", proof_ids=("24",))


def _bash(command: str, repo=REPO) -> Event:
    return Event(
        hook_event="PreToolUse",
        tool_name="Bash",
        tool_input={"command": command},
        repo=repo,
    )


# --------------------------------------------------------------------
# The four destructive-action categories, unauthorised
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git push -f origin main",
        "git push --force origin main",
        "git push --force-with-lease origin main",
        "git push --force-with-lease=refs/heads/main:abc123 origin main",
    ],
)
def test_force_push_without_authorisation_warns(command):
    finding = RULE.evaluate(_bash(command), WARN)
    assert finding is not None
    assert finding.rule_id == "lwb_no_unauthorised_destructive_action"
    assert "force-push" in finding.reason


@pytest.mark.parametrize(
    "command",
    [
        "git rebase -i HEAD~3",
        "git rebase main",
        "git filter-branch --tree-filter true",
        "git filter-repo --path secrets.txt --invert-paths",
        "git commit --amend -m 'fix'",
        "git reset --hard HEAD~1",
    ],
)
def test_history_rewrite_without_authorisation_warns(command):
    finding = RULE.evaluate(_bash(command), WARN)
    assert finding is not None
    assert "history rewrite" in finding.reason


@pytest.mark.parametrize(
    "command",
    [
        "git push origin --delete old-branch",
        "git push origin -d old-branch",
        "git push --delete origin old-branch",
        "git push origin :old-branch",
    ],
)
def test_delete_ref_without_authorisation_warns(command):
    finding = RULE.evaluate(_bash(command), WARN)
    assert finding is not None
    assert "deleting a remote ref" in finding.reason
    assert "old-branch" in finding.reason


@pytest.mark.parametrize(
    "command",
    [
        "gh repo edit --delete-branch-on-merge",
        "gh repo delete owner/repo --yes",
        "gh api -X PATCH repos/OWNER/REPO -f has_issues=false",
        "gh api --method PUT repos/OWNER/REPO/rulesets/1 --input -",
        "gh api --method POST repos/OWNER/REPO/rulesets --input -",
        "gh api -X PATCH repos/OWNER/REPO/branches/main/protection",
        "gh api -X PUT repos/OWNER/REPO/actions/permissions",
    ],
)
def test_settings_change_without_authorisation_warns(command):
    finding = RULE.evaluate(_bash(command), WARN)
    assert finding is not None
    assert "repository settings change" in finding.reason


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/OWNER/REPO",  # GET, the default -- reads, does not change
        "gh api -X GET repos/OWNER/REPO",
        "git push origin main",
        "git status",
        "git commit -m 'ordinary work'",
        "git branch -D already-merged-locally",  # LOCAL delete, out of scope
        "gh pr view 24",
    ],
)
def test_ordinary_and_out_of_scope_commands_are_silent(command):
    assert RULE.evaluate(_bash(command), WARN) is None


# --------------------------------------------------------------------
# The merge carve-out (D19): never classified as destructive, ever
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git merge feature-x",
        "git merge --no-ff feature-x",
        "gh pr merge 24 --squash",
        "gh pr merge 24 --merge",
    ],
)
def test_merge_is_never_flagged_even_with_no_policy_configured(command):
    """The merge carve-out holds even with the emptiest possible config --
    no allowlist, WARN mode, nothing authorising anything. If merge were
    treated as a destructive action it would warn here; it must not.
    """
    assert RULE.evaluate(_bash(command), WARN) is None


def test_merge_is_not_flagged_even_under_deny():
    assert RULE.evaluate(_bash("gh pr merge 24 --squash"), DENY) is None


# --------------------------------------------------------------------
# The verified-landed-branch-deletion carve-out
# --------------------------------------------------------------------


def test_a_branch_named_in_verified_landed_branches_is_authorised():
    config = RuleConfig(
        mode=RuleMode.WARN,
        options={"verified_landed_branches": ["old-branch", "another-one"]},
    )
    assert RULE.evaluate(_bash("git push origin --delete old-branch"), config) is None


def test_a_branch_not_named_in_verified_landed_branches_still_warns():
    """Removing the target-matching logic must not make every delete_ref
    silent -- only the NAMED branch is authorised.
    """
    config = RuleConfig(
        mode=RuleMode.WARN,
        options={"verified_landed_branches": ["old-branch"]},
    )
    finding = RULE.evaluate(_bash("git push origin --delete some-other-branch"), config)
    assert finding is not None
    assert "some-other-branch" in finding.reason


def test_verified_landed_branches_does_not_authorise_a_different_category():
    """The carve-out is delete_ref-SPECIFIC. Naming a branch there must not
    also silence a force-push.
    """
    config = RuleConfig(
        mode=RuleMode.WARN,
        options={"verified_landed_branches": ["old-branch"]},
    )
    finding = RULE.evaluate(_bash("git push -f origin main"), config)
    assert finding is not None
    assert "force-push" in finding.reason


# --------------------------------------------------------------------
# The general policy-allowlist mechanism
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    "category,command",
    [
        ("force_push", "git push -f origin main"),
        ("history_rewrite", "git rebase main"),
        ("delete_ref", "git push origin --delete some-branch"),
        ("settings_change", "gh repo edit --delete-branch-on-merge"),
    ],
)
def test_an_explicit_policy_allowlist_authorises_its_own_category(category, command):
    config = RuleConfig(mode=RuleMode.WARN, options={"allow": {category: True}})
    assert RULE.evaluate(_bash(command), config) is None


def test_allowlisting_one_category_does_not_authorise_another():
    config = RuleConfig(mode=RuleMode.WARN, options={"allow": {"force_push": True}})
    finding = RULE.evaluate(_bash("git rebase main"), config)
    assert finding is not None
    assert "history rewrite" in finding.reason


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"allow": {}},
        {"allow": {"force_push": False}},
        {"allow": "not-a-mapping"},
        {"allow": None},
    ],
)
def test_absent_or_malformed_allowlist_does_not_authorise(options):
    config = RuleConfig(mode=RuleMode.WARN, options=options)
    finding = RULE.evaluate(_bash("git push -f origin main"), config)
    assert finding is not None


# --------------------------------------------------------------------
# The purity contract: no facts means no opinion
# --------------------------------------------------------------------


def test_no_repo_facts_means_no_opinion():
    """`repo is None` is "the adapter gathered nothing", not "nothing found" --
    same discipline lwb_proof_required documents. Keeps this rule inert
    under an adapter that has not been taught to collect repo facts, today
    the Codex adapter.
    """
    assert RULE.evaluate(_bash("git push -f origin main", repo=None), WARN) is None


def test_facts_incomplete_means_no_opinion():
    repo = RepoFacts(facts_incomplete=True, facts_incomplete_reason="permission denied")
    assert RULE.evaluate(_bash("git push -f origin main", repo=repo), WARN) is None


def test_repo_none_is_silent_even_when_policy_would_otherwise_deny():
    """A missing adapter signal must win over an armed policy -- this rule
    is not allowed to fabricate a repo-facts-dependent opinion it cannot
    honestly have, regardless of mode.
    """
    assert RULE.evaluate(_bash("git push -f origin main", repo=None), DENY) is None


# --------------------------------------------------------------------
# Everything else this rule is not about
# --------------------------------------------------------------------


def test_non_bash_tools_are_untouched():
    event = Event(
        hook_event="PreToolUse",
        tool_name="Agent",
        tool_input={"prompt": "force-push the branch"},
        repo=REPO,
    )
    assert RULE.evaluate(event, WARN) is None


def test_non_pretooluse_events_are_untouched():
    event = Event(
        hook_event="Stop",
        tool_name="Bash",
        tool_input={"command": "git push -f origin main"},
        repo=REPO,
    )
    assert RULE.evaluate(event, WARN) is None


@pytest.mark.parametrize("tool_input", [{}, {"command": ""}, {"command": 17}])
def test_a_missing_or_non_string_command_is_untouched(tool_input):
    event = Event(
        hook_event="PreToolUse", tool_name="Bash", tool_input=tool_input, repo=REPO
    )
    assert RULE.evaluate(event, WARN) is None


@pytest.mark.parametrize(
    "command",
    [
        "git push --force --dry-run origin main",
        "git push -f -n origin main",
        "git rebase --help",
    ],
)
def test_a_dry_run_or_help_is_not_gated(command):
    assert RULE.evaluate(_bash(command), WARN) is None


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "remember to git push -f later"',
        "echo 'git rebase main' >> notes.txt",
    ],
)
def test_a_destructive_shape_named_inside_a_quoted_string_is_not_gated(command):
    assert RULE.evaluate(_bash(command), WARN) is None


def test_a_destructive_command_later_in_a_chain_is_still_recognized():
    finding = RULE.evaluate(_bash("python -m pytest -q && git push -f origin main"), WARN)
    assert finding is not None


def test_the_rule_reads_nothing_but_its_arguments():
    """A crude but real purity probe, mirroring test_lwb_proof_required.py."""
    import inspect

    source = inspect.getsource(RULE)
    for forbidden in ("import os", "import subprocess", "open(", "Path(", "environ"):
        assert forbidden not in source, f"rule must stay pure, found {forbidden!r}"


# --------------------------------------------------------------------
# Mode: this rule is armable, and ships quiet
# --------------------------------------------------------------------


def test_mode_is_honoured_so_a_policy_can_arm_it():
    finding = RULE.evaluate(_bash("git push -f origin main"), DENY)
    assert finding is not None
    assert finding.mode is RuleMode.DENY


def test_through_the_engine_warn_permits_and_deny_blocks():
    event = _bash("git push -f origin main")

    warn_decision = evaluate(
        event, Policy(rules={"lwb_no_unauthorised_destructive_action": WARN})
    )
    assert warn_decision.permit is True
    assert any("force-push" in w for w in warn_decision.warnings)

    deny_decision = evaluate(
        event, Policy(rules={"lwb_no_unauthorised_destructive_action": DENY})
    )
    assert deny_decision.permit is False
    assert "force-push" in (deny_decision.deny_reason or "")


def test_off_means_the_rule_never_runs():
    decision = evaluate(
        _bash("git push -f origin main"),
        Policy(
            rules={
                "lwb_no_unauthorised_destructive_action": RuleConfig(mode=RuleMode.OFF)
            }
        ),
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
    assert (
        policy["rules"]["lwb_no_unauthorised_destructive_action"]["mode"] == "warn"
    )


def test_no_shipped_policy_file_arms_this_rule_to_deny():
    """EVERY shipped policy, not just the source one -- see the identical
    lock in test_lwb_proof_required.py for why the vendored copies matter
    just as much as `core/policy/default.json`.
    """
    import json
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    policies = sorted(repo_root.glob("core/policy/default.json")) + sorted(
        repo_root.glob("plugins/*/lwb/vendor/policy/default.json")
    )
    assert len(policies) >= 3, f"expected source + both vendored policies, got {policies}"

    for path in policies:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = (
            data.get("rules", {})
            .get("lwb_no_unauthorised_destructive_action", {})
            .get("mode")
        )
        assert mode != "deny", (
            f"{path.relative_to(repo_root)} arms "
            "lwb_no_unauthorised_destructive_action to deny. Arming it is a "
            "separate, later build-plan item -- see "
            "docs/rules/lwb-no-unauthorised-destructive-action.md."
        )


def test_the_rule_is_registered():
    from lwb_core.rules import RULES

    assert RULE in RULES
