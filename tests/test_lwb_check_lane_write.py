"""Tests for scripts/lwb_check_lane_write.py's `evaluate` against fixtures.

Covers both hosts' event shape: Claude's Edit/Write/MultiEdit/NotebookEdit
`file_path`, and Codex's `apply_patch` patch-text `*** Update File:` header.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lwb_check_lane_write import _relativize, evaluate  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "lane_write"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_claude_edit_in_lane_allowed():
    out = evaluate("claude", _load("claude_edit_in_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_claude_edit_shared_allowed():
    out = evaluate("claude", _load("claude_edit_shared.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_claude_edit_out_of_lane_denied():
    out = evaluate("claude", _load("claude_edit_out_of_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "plugins/codex/lwb/bin/lwb_hook.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_relativize_returns_none_for_a_path_outside_the_repo():
    """Directive 5 divides THIS repo into lanes. It says nothing about the
    rest of the filesystem."""
    for outside in (
        str(Path.home() / ".claude" / "CLAUDE.md"),
        str(Path.home() / ".claude" / "projects" / "some-proj" / "memory" / "note.md"),
    ):
        assert _relativize(outside) is None, outside


def test_relativize_keeps_paths_inside_the_repo():
    inside = str(REPO_ROOT / "plugins" / "claude" / "lwb" / "bin" / "lwb_hook.py")
    assert _relativize(inside) == "plugins/claude/lwb/bin/lwb_hook.py"


def test_write_outside_the_repo_is_allowed():
    """Regression: the hook denied a session writing its own memory dir or
    global config, because an absolute path outside REPO_ROOT fell through
    to classify_path as "other"."""
    for outside in (
        str(Path.home() / ".claude" / "CLAUDE.md"),
        str(Path.home() / ".claude" / "projects" / "p" / "memory" / "MEMORY.md"),
    ):
        event = {"tool_name": "Write", "tool_input": {"file_path": outside}}
        out = evaluate("claude", event)
        assert out["hookSpecificOutput"]["permissionDecision"] == "allow", outside


def test_out_of_lane_inside_the_repo_is_still_denied_by_absolute_path():
    """Relaxing the outside-the-repo case must not relax the real gate."""
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(REPO_ROOT / "plugins" / "codex" / "x.py")},
    }
    out = evaluate("claude", event)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_codex_apply_patch_in_lane_allowed():
    out = evaluate("codex", _load("codex_apply_patch_in_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_codex_apply_patch_out_of_lane_denied():
    out = evaluate("codex", _load("codex_apply_patch_out_of_lane.json"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "plugins/claude/lwb/bin/lwb_hook.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_unparseable_event_fails_open():
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_non_edit_tool_is_ignored():
    out = evaluate("claude", {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "plugins/codex/lwb/bin/lwb_hook.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
