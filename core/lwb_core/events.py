"""The neutral event shape every adapter normalizes into before the engine runs.

`Event` is the ONE data shape rules are written against. An adapter (Claude
Code hook JSON, a future Codex hook JSON, ...) translates its own native
payload into this shape; the engine and every rule in `rules/` never see the
native payload. This is what makes a conformance test meaningful: feed the
same `Event` through two adapters' encoders and decoders and expect the same
`Decision`.

Field notes:
  - `session_id` and `transcript_path` are carried through for ledger
    correlation but no shipped rule branches on them.
  - `extra` holds adapter-specific data a rule is NOT expected to read; it
    exists so an adapter can round-trip fields it doesn't understand rather
    than dropping them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class Event:
    """A normalized hook event, independent of which agent runtime produced it.

    hook_event: the lifecycle point, e.g. "PreToolUse", "SubagentStop", "Stop".
    tool_name: the tool being invoked, when hook_event is a tool hook
        (e.g. "Agent", "Read", "Bash"). None for lifecycle hooks with no tool.
    tool_input: the tool's input payload, e.g. {"prompt": "...", "subagent_type": "..."}.
    prompt: convenience extraction of a dispatch prompt string, when present
        in tool_input under a recognized key ("prompt" or "description").
    session_id: opaque session identifier, for ledger correlation only.
    transcript_path: opaque path string, for ledger correlation only.
    extra: adapter-native fields no shipped rule reads.
    """

    hook_event: str
    tool_name: Optional[str] = None
    tool_input: Mapping[str, Any] = field(default_factory=dict)
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    transcript_path: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)
