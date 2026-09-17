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

from lwb_check_lane_write import evaluate  # noqa: E402

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
