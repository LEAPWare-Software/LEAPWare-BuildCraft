"""The IMPURE half: adapters/claude/repo_facts.py, and the whole path
(hook JSON) -> Event -> Decision -> rendered Claude output.

Fake repositories are built on disk here rather than mocked, because what
is being checked IS the on-disk layout: `.git` as a directory, `.git` as a
worktree pointer file, a detached HEAD, `proof/` vs `.lwb/proof/`. A mock
of `read_text` would prove only that the mock works.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from adapters.claude.hook_io import parse_event, render_decision
from adapters.claude.repo_facts import (
    collect_proof_ids,
    collect_repo_facts,
    find_repo_root,
    read_branch,
)
from lwb_core.config import Policy, RuleConfig, RuleMode
from lwb_core.engine import evaluate
from lwb_core.events import RepoFacts

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_repo(root: Path, branch: str = "feature-x", proof_dir: str = "proof",
               records=("21", "22")) -> Path:
    """A minimal but REAL git layout: a .git directory holding a HEAD ref."""
    (root / ".git").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "HEAD").write_text(f"ref: refs/heads/{branch}\n", encoding="utf-8")
    if records:
        directory = root.joinpath(*proof_dir.split("/"))
        directory.mkdir(parents=True, exist_ok=True)
        for record in records:
            (directory / f"{record}.json").write_text("{}", encoding="utf-8")
    return root


# --------------------------------------------------------------------
# Root discovery
# --------------------------------------------------------------------


def test_repo_root_is_found_from_a_nested_directory(tmp_path):
    _make_repo(tmp_path)
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    assert find_repo_root(str(nested)) == tmp_path.resolve()


def test_no_repository_yields_no_facts(tmp_path):
    """Outside a repo the adapter gathers nothing, and the rule stays silent."""
    assert find_repo_root(str(tmp_path)) is None
    assert collect_repo_facts(str(tmp_path)) is None


# --------------------------------------------------------------------
# Branch reading, without running git
# --------------------------------------------------------------------


def test_branch_is_read_from_a_plain_clone(tmp_path):
    _make_repo(tmp_path, branch="lwb-ship-proof-rule")
    assert read_branch(tmp_path) == "lwb-ship-proof-rule"


def test_branch_is_read_through_a_worktree_gitdir_pointer(tmp_path):
    """A worktree's `.git` is a FILE holding `gitdir: <path>`.

    This repo's own work happens in worktrees under `.worktrees/`, so
    getting the WORKTREE's branch (not the main checkout's) is the case
    that actually matters here.
    """
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (main / ".git" / "worktrees" / "wt" / "HEAD").write_text(
        "ref: refs/heads/side-branch\n", encoding="utf-8"
    )

    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(
        f"gitdir: {(main / '.git' / 'worktrees' / 'wt').as_posix()}\n", encoding="utf-8"
    )

    assert find_repo_root(str(worktree)) == worktree.resolve()
    assert read_branch(worktree) == "side-branch"


def test_detached_head_reads_as_no_branch(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("a" * 40 + "\n", encoding="utf-8")
    assert read_branch(tmp_path) is None


def test_a_missing_head_reads_as_no_branch(tmp_path):
    (tmp_path / ".git").mkdir()
    assert read_branch(tmp_path) is None


def test_the_collector_does_not_shell_out_to_git():
    """Owner directive 8: no dependency on this machine, `git` on PATH included.

    Asserted over the module's IMPORTS via the AST, not over its text: the
    first version of this test grepped for the string and failed on its own
    docstring, which explains at length why there is no subprocess.
    """
    import ast

    source = (REPO_ROOT / "adapters" / "claude" / "repo_facts.py").read_text(
        encoding="utf-8"
    )
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "subprocess" not in imported, imported
    assert "shutil" not in imported, imported


def test_the_collector_agrees_with_real_git_in_this_checkout():
    """The fixtures above are only worth something if the format is real.

    Reads this actual repository -- a worktree, in the session that wrote
    this -- and compares against `git rev-parse --abbrev-ref HEAD`.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return  # no git available; the fixture tests above still stand
    expected = result.stdout.strip()
    if expected == "HEAD":
        return  # detached; covered by its own test
    assert read_branch(REPO_ROOT) == expected


# --------------------------------------------------------------------
# Proof record discovery
# --------------------------------------------------------------------


def test_proof_ids_are_filename_stems(tmp_path):
    _make_repo(tmp_path, records=("7", "24", "exempt"))
    assert set(collect_proof_ids(tmp_path)) == {"7", "24", "exempt"}


def test_a_consuming_repo_may_use_dot_lwb_proof(tmp_path):
    """A consuming repo must not have to adopt this repo's top-level layout."""
    _make_repo(tmp_path, proof_dir=".lwb/proof", records=("101",))
    assert collect_proof_ids(tmp_path) == ["101"]


def test_both_proof_directories_are_merged_without_duplicates(tmp_path):
    _make_repo(tmp_path, proof_dir="proof", records=("1", "2"))
    (tmp_path / ".lwb" / "proof").mkdir(parents=True)
    (tmp_path / ".lwb" / "proof" / "2.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".lwb" / "proof" / "3.json").write_text("{}", encoding="utf-8")
    assert collect_proof_ids(tmp_path) == ["1", "2", "3"]


def test_no_proof_directory_is_an_empty_list_not_an_error(tmp_path):
    _make_repo(tmp_path, records=())
    assert collect_proof_ids(tmp_path) == []


def test_collect_repo_facts_returns_the_neutral_shape(tmp_path):
    _make_repo(tmp_path, branch="feature-x", records=("21",))
    facts = collect_repo_facts(str(tmp_path))
    assert isinstance(facts, RepoFacts)
    assert facts.branch == "feature-x"
    assert facts.proof_ids == ("21",)


def test_a_slash_branch_name_can_be_cleared_by_the_message_it_receives(tmp_path):
    """Finding 2 (THE BLOCKER): a nested id must round-trip through the rule.

    Before the fix: `directory.glob("*.json")` does not recurse, so
    `proof/feat/x-12.json` is invisible and the id space never contains
    `"feat/x-12"` -- the finding tells you to create exactly the file you
    already created, forever.

    After the fix: the collector walks `proof/` recursively and yields the
    path relative to the proof dir, slash-joined, with `.json` stripped --
    so the id space DOES contain `"feat/x-12"`, the branch matches it
    directly, and the rule goes silent. This is the actual fix; the
    directory walk is just the mechanism that produces it.
    """
    import sys as _sys

    _make_repo(tmp_path, branch="feat/x-12", records=())

    sys_path_added = str(REPO_ROOT) not in _sys.path
    if sys_path_added:
        _sys.path.insert(0, str(REPO_ROOT))
    from lwb_core.config import Policy, RuleConfig, RuleMode
    from lwb_core.rules import lwb_proof_required

    warn = Policy(rules={"lwb_proof_required": RuleConfig(mode=RuleMode.WARN)})

    # 1. Before creating any record: the rule names a path to create.
    facts_before = collect_repo_facts(str(tmp_path))
    assert facts_before == RepoFacts(branch="feat/x-12", proof_ids=())

    raw = _hook_json("git push -u origin HEAD", tmp_path)
    event = parse_event(raw, repo=facts_before)
    finding = lwb_proof_required.evaluate(event, warn.rules["lwb_proof_required"])
    assert finding is not None
    assert "add proof/feat/x-12.json before publishing" in finding.reason

    # 2. Create EXACTLY the path the message named.
    named_path = tmp_path / "proof" / "feat" / "x-12.json"
    named_path.parent.mkdir(parents=True, exist_ok=True)
    named_path.write_text("{}", encoding="utf-8")

    # 3. Re-collect: the id space now contains "feat/x-12" with forward
    #    slashes (checked literally, so a backslash id from os.sep on
    #    Windows would fail this the same way a missing id would).
    facts_after = collect_repo_facts(str(tmp_path))
    assert "feat/x-12" in facts_after.proof_ids

    # 4. Re-evaluate: the rule is now silent.
    event_after = parse_event(raw, repo=facts_after)
    assert lwb_proof_required.evaluate(event_after, warn.rules["lwb_proof_required"]) is None


def test_flat_ids_still_work_after_the_recursive_walk(tmp_path):
    """`proof/22.json` must still yield `"22"`, not `"22"` nested oddly."""
    _make_repo(tmp_path, records=("22",))
    assert "22" in collect_proof_ids(tmp_path)


def test_nested_proof_ids_use_forward_slashes_on_every_platform(tmp_path):
    _make_repo(tmp_path, records=())
    nested = tmp_path / "proof" / "feat" / "x-12.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("{}", encoding="utf-8")
    ids = collect_proof_ids(tmp_path)
    assert "feat/x-12" in ids
    assert not any("\\" in i for i in ids)


# --------------------------------------------------------------------
# Adapter enrichment
# --------------------------------------------------------------------


def test_parse_event_attaches_repo_facts_and_defaults_to_none():
    raw = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
           "tool_input": {"command": "git push"}}
    assert parse_event(raw).repo is None

    facts = RepoFacts(branch="b", proof_ids=("1",))
    assert parse_event(raw, repo=facts).repo is facts


def test_repo_facts_are_not_smuggled_through_extra():
    """`extra` is documented as "fields no shipped rule reads" -- keep it so."""
    raw = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
           "tool_input": {"command": "git push"}, "cwd": "/somewhere"}
    event = parse_event(raw, repo=RepoFacts(branch="b", proof_ids=()))
    assert "repo" not in event.extra
    assert event.extra["cwd"] == "/somewhere"


# --------------------------------------------------------------------
# End to end: hook JSON -> Decision -> Claude's own output shape
# --------------------------------------------------------------------


def _hook_json(command: str, cwd: Path) -> dict:
    return {
        "session_id": "sanitized-session-0009",
        "transcript_path": "/sanitized/path/transcript.jsonl",
        "cwd": str(cwd),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "Push the branch"},
    }


SHIPPED = Policy(
    rules={
        "lwb_version": RuleConfig(mode=RuleMode.WARN),
        "lwb_proof_required": RuleConfig(mode=RuleMode.WARN),
    }
)


def test_end_to_end_warn_case(tmp_path):
    """No record for this branch: allowed, but the warning is in the output."""
    _make_repo(tmp_path, branch="feature-x", records=("21", "22"))
    raw = _hook_json("git push -u origin HEAD", tmp_path)

    event = parse_event(raw, repo=collect_repo_facts(raw["cwd"]))
    decision = evaluate(event, SHIPPED)
    output = render_decision(decision)

    assert decision.permit is True
    assert [f.rule_id for f in decision.findings] == ["lwb_version", "lwb_proof_required"]
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "no proof record for 'feature-x'" in (
        output["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_end_to_end_pass_case(tmp_path):
    """Add proof/feature-x.json and the rule goes silent -- same command."""
    _make_repo(tmp_path, branch="feature-x", records=("21", "22", "feature-x"))
    raw = _hook_json("git push -u origin HEAD", tmp_path)

    event = parse_event(raw, repo=collect_repo_facts(raw["cwd"]))
    decision = evaluate(event, SHIPPED)
    output = render_decision(decision)

    assert decision.permit is True
    assert [f.rule_id for f in decision.findings] == ["lwb_version"]
    assert output["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "proof record" not in (
        output["hookSpecificOutput"].get("permissionDecisionReason", "")
    )


def test_end_to_end_deny_case_when_a_policy_arms_the_rule(tmp_path):
    _make_repo(tmp_path, branch="feature-x", records=("21",))
    raw = _hook_json("gh pr merge 99 --squash", tmp_path)

    event = parse_event(raw, repo=collect_repo_facts(raw["cwd"]))
    decision = evaluate(
        event,
        Policy(rules={"lwb_proof_required": RuleConfig(mode=RuleMode.DENY)}),
    )
    output = render_decision(decision)

    assert decision.permit is False
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "'99'" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_end_to_end_ordinary_command_is_untouched(tmp_path):
    _make_repo(tmp_path, branch="feature-x", records=())
    raw = _hook_json("python -m pytest tests/ -q", tmp_path)

    decision = evaluate(parse_event(raw, repo=collect_repo_facts(raw["cwd"])), SHIPPED)
    assert [f.rule_id for f in decision.findings] == ["lwb_version"]


# --------------------------------------------------------------------
# Through the real hook script, as a real install would run it
# --------------------------------------------------------------------


def test_the_shipped_hook_script_warns_on_a_real_bash_publish(tmp_path):
    """The VENDORED plugin, run as a subprocess, on a real fake repo.

    This is the one test that proves the rule actually ships: it imports
    nothing, and runs plugins/claude/lwb/bin/lwb_hook.py against its own
    vendored copy of the rule and the vendored default policy.
    """
    work = tmp_path / "consumer"
    work.mkdir()
    _make_repo(work, branch="feature-x", records=("21",))

    hook_script = REPO_ROOT / "plugins" / "claude" / "lwb" / "bin" / "lwb_hook.py"
    env = {
        "LWB_LEDGER_PATH": str(tmp_path / "ledger.jsonl"),
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    result = subprocess.run(
        [sys.executable, str(hook_script)],
        cwd=str(work),
        input=json.dumps(_hook_json("git push -u origin HEAD", work)),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "no proof record for 'feature-x'" in (
        payload["hookSpecificOutput"]["permissionDecisionReason"]
    )
