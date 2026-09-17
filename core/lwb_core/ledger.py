"""Pure formatting for the append-only decision ledger.

This module turns a `Decision` (plus a few adapter-supplied facts) into ONE
JSON-serializable dict per event — the record an adapter appends, one line
per call, to its own ledger file. It does not open, write, or rotate any
file: that is the adapter's job (see adapters/claude/hook_io.py), because
the file location and rotation policy differ per host (Claude Code plugin
data dir vs. a Codex-side path).

Kept deliberately tiny: a ledger line is meant to be `jq`-able years from
now without this module's help, so it is plain data, not a class with
behavior.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .engine import Decision


def ledger_record(
    *,
    timestamp: str,
    hook_event: str,
    tool_name: Optional[str],
    decision: Decision,
    session_id: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Build one ledger line. `timestamp` is caller-supplied (no clock here)."""
    record: dict = {
        "timestamp": timestamp,
        "hook_event": hook_event,
        "tool_name": tool_name,
        "session_id": session_id,
        "permit": decision.permit,
        "deny_reason": decision.deny_reason,
        "warnings": list(decision.warnings),
        "findings": [
            {"rule_id": f.rule_id, "mode": f.mode.value, "reason": f.reason}
            for f in decision.findings
        ],
    }
    if extra:
        record["extra"] = dict(extra)
    return record
