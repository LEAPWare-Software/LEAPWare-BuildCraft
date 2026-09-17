#!/usr/bin/env python3
"""The Codex PreToolUse hook entry point. Stdlib only, no third-party imports.

Mirrors `plugins/claude/lwb/bin/lwb_hook.py` exactly, swapping the Claude
adapter for the Codex one and `CLAUDE_PLUGIN_DATA` for `PLUGIN_DATA` (the
env var Codex sets for a plugin-bundled hook's writable data directory —
see docs/install-codex.md). Codex's `PreToolUse` hook reads its decision
from `hookSpecificOutput.permissionDecision` in the JSON on stdout, the
same shape Claude Code's hook protocol uses, so this always exits 0.

This script is deliberately thin: every decision-relevant line of logic
lives in lwb_core or adapters/codex/hook_io.py, both under vendor/ next to
this file (populated by scripts/lwb_build.py).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_BIN_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _BIN_DIR.parent
_VENDOR_DIR = _PLUGIN_ROOT / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from adapters.codex.hook_io import load_policy, parse_event, render_decision  # noqa: E402
from lwb_core.engine import evaluate  # noqa: E402
from lwb_core.ledger import ledger_record  # noqa: E402


def _resolve_policy_path() -> Path:
    """User override policy, if present, else the bundled default.

    Reads `LWB_POLICY_PATH` if set (for tests and advanced setups) and
    otherwise falls back to the bundled `core/policy/default.json` vendored
    alongside this script.
    """
    import os

    override = os.environ.get("LWB_POLICY_PATH")
    if override:
        return Path(override)
    return _VENDOR_DIR / "policy" / "default.json"


def _load_policy_dict(path: Path):
    """Read and parse the policy file. Fail-open: any error -> None."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ledger_path() -> Path:
    import os

    override = os.environ.get("LWB_LEDGER_PATH")
    if override:
        return Path(override)
    data_dir = os.environ.get("PLUGIN_DATA")
    if data_dir:
        return Path(data_dir) / "ledger.jsonl"
    # Fall back to a per-plugin-root ledger next to bin/, kept out of the
    # tracked tree by .gitignore's state/ rule at repo root; a real install's
    # PLUGIN_DATA env var is expected to be set by Codex itself.
    return _PLUGIN_ROOT / "state" / "ledger.jsonl"


def main() -> int:
    raw_input = sys.stdin.read()
    try:
        raw_event = json.loads(raw_input) if raw_input.strip() else {}
    except json.JSONDecodeError:
        raw_event = {}

    event = parse_event(raw_event)
    policy = load_policy(_load_policy_dict(_resolve_policy_path()))
    decision = evaluate(event, policy)

    record = ledger_record(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hook_event=event.hook_event,
        tool_name=event.tool_name,
        decision=decision,
        session_id=event.session_id,
    )
    try:
        ledger_path = _ledger_path()
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        # Ledger write failure must not block a dispatch decision either.
        pass

    print(json.dumps(render_decision(decision)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
