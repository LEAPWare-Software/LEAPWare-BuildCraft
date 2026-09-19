#!/usr/bin/env python3
"""In-repo session lane hook: deny a write outside the calling CLI's lane.

This is a PreToolUse hook wired into THIS repo's own `.claude/settings.json`
and `.codex/hooks.json` (see those files), separate from the lwb PRODUCT's
own `lwb_version` policy hook — this one enforces owner directive 5 ("Codex
works only on the Codex part, Claude only on the Claude part...") on
whoever is editing THIS repo, using the same lane classification
`scripts/lwb_lanes.py` uses for the commit-level `lwb-lanes` CI check. The
CI check is the check of record (it looks at what was actually committed);
this hook is a same-session nudge that stops an out-of-lane edit before it
happens, so a contributor finds out immediately rather than at PR review.

Reads one JSON event from stdin:
  - Claude Code `PreToolUse` shape: `tool_name` in {Edit, Write, MultiEdit,
    NotebookEdit}, with a `file_path` or `notebook_path` in `tool_input`.
  - Codex `PreToolUse` shape: `tool_name` "apply_patch" (Codex's one
    file-editing tool, the documented equivalent of Claude's four — see
    docs/install-codex.md), with the patch text carrying one or more
    `*** (Add|Update|Delete) File: <path>` header lines, the apply_patch
    patch format's documented way of naming the file(s) a patch touches.

If no file path can be determined from the event shape, this hook does
NOT deny — silently allowing an edit it can't parse is the safe failure
direction for a same-session nudge that is not itself the enforcement of
record (see module docstring); the `lwb-lanes` CI check still catches an
out-of-lane commit regardless of what this hook did or didn't catch.

Scope: only paths INSIDE this repo are lane-checked. Owner directive 5
divides this repo into lanes and says nothing about the rest of the
filesystem, so a write to a session's own memory directory, a global
`~/.claude/CLAUDE.md`, or a scratch file is allowed — see `_relativize`.

Usage:
    python scripts/lwb_check_lane_write.py --agent claude
    python scripts/lwb_check_lane_write.py --agent codex

Stdlib only. Always exits 0 (both hosts read the decision from the JSON
body, not the exit code — see docs/install-claude.md / docs/install-codex.md).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lwb_lanes import REPO_ROOT, classify_path  # noqa: E402

CLAUDE_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
CODEX_EDIT_TOOLS = {"apply_patch"}

APPLY_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


def _extract_paths(agent: str, raw: dict) -> list[str]:
    tool_name = raw.get("tool_name")
    tool_input = raw.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if agent == "claude" and tool_name in CLAUDE_EDIT_TOOLS:
        for key in ("file_path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return [value]
        return []

    if agent == "codex" and tool_name in CODEX_EDIT_TOOLS:
        for key in ("input", "patch", "command"):
            value = tool_input.get(key)
            if isinstance(value, str):
                matches = APPLY_PATCH_FILE_RE.findall(value)
                if matches:
                    return matches
        value = tool_input.get("file_path")
        if isinstance(value, str) and value:
            return [value]
        return []

    return []


def _relativize(path_str: str) -> Optional[str]:
    """Repo-relative form of `path_str`, or None if it is not inside this repo.

    Returning None matters. Owner directive 5 divides THIS repo into lanes;
    it says nothing about the rest of the filesystem. An absolute path that
    is not under REPO_ROOT used to fall through to `classify_path` unchanged,
    which called it "other" and denied the write -- so this hook blocked a
    session from writing its own memory directory, its global
    `~/.claude/CLAUDE.md`, or any scratch file, none of which is a lane
    violation. A path outside the repo is simply not this hook's business.
    """
    try:
        p = Path(path_str)
        if p.is_absolute():
            try:
                return str(p.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
            except ValueError:
                return None  # absolute, but outside this repo
    except OSError:
        return None
    return path_str.replace("\\", "/")


def evaluate(agent: str, raw: dict) -> dict:
    paths = _extract_paths(agent, raw)
    offenders = []
    for path_str in paths:
        rel = _relativize(path_str)
        if rel is None:
            continue  # outside this repo: not a lane question
        cls = classify_path(rel)
        if cls not in (agent, "shared"):
            offenders.append(rel)

    if offenders:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"lwb lane guard: {agent} may not write outside its lane or shared "
                    f"paths: {', '.join(offenders)} (owner directive 5; see "
                    f"docs/requirements/owner-directives.md and reviews/README.md)"
                ),
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=["claude", "codex"])
    args = parser.parse_args()

    raw_input = sys.stdin.read()
    try:
        raw_event = json.loads(raw_input) if raw_input.strip() else {}
    except json.JSONDecodeError:
        raw_event = {}

    print(json.dumps(evaluate(args.agent, raw_event)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
