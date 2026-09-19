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
  - `repo` holds repository facts an adapter GATHERED FROM THE OUTSIDE
    WORLD for rules to read. See `RepoFacts` below for why that is a
    declared, typed field and not a bag inside `extra`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class RepoFacts:
    """Repository state an adapter observed, frozen into data for pure rules.

    `core/lwb_core` does no I/O (docs/architecture.md). A rule that needs to
    know "which branch is this" or "does a proof record exist" therefore
    cannot go and look: something impure must look on its behalf and hand
    the answer in. That is what this type is -- the declared, typed channel
    for adapter-observed repository facts.

    It is deliberately NOT carried in `Event.extra`. `extra`'s contract
    (above) is "adapter-native fields no shipped rule reads" -- a
    round-trip bag for data nobody understands. Facts a shipped rule is
    REQUIRED to read are the opposite: they are part of the neutral
    contract between adapters and rules, so they get a name, a type and a
    docstring here, where the author of a second adapter can see exactly
    what must be populated for the same rules to work. Putting them in
    `extra` would make every rule that read them a violation of `extra`'s
    own documented contract, and would hide from a new adapter author that
    there was anything to populate at all.

    `repo is None` on an `Event` means "this adapter did not gather repo
    facts" -- which is NOT the same as "it looked and found nothing". A
    rule must treat None as no-opinion, never as absence-of-proof; see
    `rules/lwb_proof_required.py`.

    branch: the checked-out branch name, or None when it could not be
        determined (detached HEAD, no git directory, unreadable HEAD).
    proof_ids: identifiers of the proof records present in the repository,
        as a tuple so an `Event` stays immutable and hashable. An
        identifier is a record file's stem: `proof/24.json` -> `"24"`. An
        empty tuple means the adapter looked and found none.
    """

    branch: Optional[str] = None
    proof_ids: Tuple[str, ...] = ()


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
    repo: repository facts the adapter observed, for rules that need them.
        None when the adapter gathers none -- see `RepoFacts`.
    """

    hook_event: str
    tool_name: Optional[str] = None
    tool_input: Mapping[str, Any] = field(default_factory=dict)
    prompt: Optional[str] = None
    session_id: Optional[str] = None
    transcript_path: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)
    repo: Optional[RepoFacts] = None
