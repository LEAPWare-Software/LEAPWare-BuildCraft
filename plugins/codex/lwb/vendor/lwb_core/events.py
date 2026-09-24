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
    facts_incomplete: True when the adapter could not fully gather these
        facts -- e.g. a proof directory or `.git/HEAD` exists but could
        not be READ (permission denied), as opposed to legitimately not
        existing. This is NOT the same as `branch is None` or
        `proof_ids == ()`: those can mean "looked and there is nothing
        there", a fact a rule may safely reason about. This field means
        "looked and could not tell" -- a rule must not treat it the same
        as an empty result. See `rules/lwb_proof_required.py`, which
        stays silent rather than risk a false deny built on facts it does
        not actually have when this is set.
    facts_incomplete_reason: human-readable detail for the above, or None.
    landed_unproven: identifiers of commits reachable from HEAD (walking
        first-parent) whose subject looks like a squash-merge (a
        trailing `(#N)`, GitHub's own convention) and whose PR number N
        has no matching entry in `proof_ids`, after applying
        `proof/exempt.json`'s carve-out -- see
        `rules/lwb_proof_coverage.py`. Each entry is a human-readable
        `"<sha prefix> (#<N>)"` string, ready to report. This is a
        BEST-EFFORT, BOUNDED, LOCAL scan (see
        `adapters/claude/repo_facts.collect_landed_unproven`): it can
        only read commits still present as loose objects, stops at a
        packed one, and is capped at a fixed depth. An empty tuple means
        "found none within what was walkable" -- NEVER a claim that all
        of history was checked. A rule must not treat this as
        exhaustive coverage.
    matched_proof_self_certified: for the proof record whose id equals
        the checked-out branch name (the one identifier available
        without parsing the triggering command -- see
        `rules/lwb_proof_required.py`'s fuller PR-number/branch-token
        matching, not duplicated here), True when that record's own
        JSON declares a non-empty `checked_by` equal to a non-empty
        `author` -- a record certifying itself. None when there is no
        such record, or its content could not be read or parsed as a
        JSON object; a rule must treat None as no-opinion, the same
        discipline `repo is None` gets.
    matched_proof_has_failed_command: for the same matched record, True
        when any of its `commands[]` entries records an `exit` that
        differs from its own `expect_exit` -- a command the record
        itself admits did not pass. None under the same conditions as
        `matched_proof_self_certified`.
    """

    branch: Optional[str] = None
    proof_ids: Tuple[str, ...] = ()
    facts_incomplete: bool = False
    facts_incomplete_reason: Optional[str] = None
    landed_unproven: Tuple[str, ...] = ()
    matched_proof_self_certified: Optional[bool] = None
    matched_proof_has_failed_command: Optional[bool] = None


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
