#!/usr/bin/env python3
"""The Claude Code PreToolUse hook entry point. Stdlib only, no third-party imports.

Reads one JSON event from stdin, loads the policy (bundled default, or a
user override — see `_resolve_policy_path`), evaluates it through the
shared engine, appends one ledger line, and writes the Claude-shaped
decision to stdout. Exit code is always 0: Claude Code's PreToolUse
contract reads the decision from the JSON body
(`hookSpecificOutput.permissionDecision`), not from the process exit code —
see docs/install-claude.md for the citation this relies on.

This script is deliberately thin: every decision-relevant line of logic
lives in lwb_core or adapters/claude/hook_io.py, both under vendor/ next to
this file (populated by scripts/lwb_build.py). This file only does I/O and
wiring, so a bug here is a plumbing bug, not a policy bug.
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

from adapters.claude.hook_io import load_policy, parse_event, render_decision  # noqa: E402
from adapters.claude.repo_facts import collect_repo_facts  # noqa: E402
from lwb_core.engine import evaluate  # noqa: E402
from lwb_core.ledger import ledger_record  # noqa: E402


def _resolve_policy_path() -> Path:
    """User override policy, if present, else the bundled default.

    Reads `LWB_POLICY_PATH` if set (for tests and advanced setups, since a
    Claude Code plugin does not write configuration under its own install
    directory) and otherwise falls back to the bundled
    `core/policy/default.json` vendored alongside this script.
    """
    import os

    override = os.environ.get("LWB_POLICY_PATH")
    if override:
        return Path(override)
    return _VENDOR_DIR / "policy" / "default.json"


def _load_policy_dict(path: Path):
    """Read and parse the policy file. Fail-open: any error -> (None, reason).

    `None` (the first element) is passed through to `load_policy` as
    before; `config.load_policy_dict` treats a non-mapping as a degraded,
    all-OFF policy. This function's job is only to turn "file missing" /
    "bad JSON" into that same shape rather than raising, per the
    fail-open contract in lwb_core/config.py -- but it now also returns
    WHY, as the second element, rather than dropping it. An independent
    reviewer found this used to fail SILENTLY: an unreadable bundled
    policy produced `{"permissionDecision":"allow"}` with no reason at
    all, indistinguishable from a clean event with nothing to say. Fail
    open, never fail silent -- see main()'s `policy_error` handling.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def _ledger_path() -> Path:
    import os

    override = os.environ.get("LWB_LEDGER_PATH")
    if override:
        return Path(override)
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data_dir:
        return Path(data_dir) / "ledger.jsonl"
    # Fall back to a per-plugin-root ledger next to bin/, kept out of the
    # tracked tree by .gitignore's state/ rule at repo root; a real install's
    # CLAUDE_PLUGIN_DATA env var is expected to be set by Claude Code itself.
    return _PLUGIN_ROOT / "state" / "ledger.jsonl"


def main() -> int:
    raw_input = sys.stdin.read()
    try:
        raw_event = json.loads(raw_input) if raw_input.strip() else {}
    except json.JSONDecodeError:
        raw_event = {}

    # Repository facts are gathered HERE, in the I/O layer, and frozen into
    # the Event -- lwb_core is pure and cannot look for itself. See
    # adapters/claude/repo_facts.py. Claude Code sends the project
    # directory as `cwd`; fall back to this process's own cwd if absent.
    #
    # Fail-open, never fail SILENT: an independent reviewer found that a
    # `collect_repo_facts` crash here used to disappear into `repo = None`
    # with nothing recorded -- indistinguishable from "gathered facts, no
    # repo found" (the ordinary, expected None). The decision must still
    # stay `allow` (a broken collector must not block a dispatch), but the
    # crash now has to say so in `permissionDecisionReason`. See
    # `repo_error` below and its use after `evaluate`.
    cwd = raw_event.get("cwd") if isinstance(raw_event, dict) else None
    repo = None
    repo_error = None
    try:
        repo = collect_repo_facts(cwd if isinstance(cwd, str) else None)
    except Exception as exc:  # noqa: BLE001 - fail-quiet, same contract as the ledger write
        repo_error = f"{exc.__class__.__name__}: {exc}"

    event = parse_event(raw_event, repo=repo)
    policy_path = _resolve_policy_path()
    policy_dict, policy_error = _load_policy_dict(policy_path)
    policy = load_policy(policy_dict)
    decision = evaluate(event, policy)

    # Same principle as the repo-facts crash above, for the other silent
    # path the same reviewer found: a bundled policy that cannot be read
    # used to render as `{"permissionDecision":"allow"}` with NO reason at
    # all. "I checked and found nothing" and "I could not check" must
    # never share a representation -- so a collector or policy failure is
    # appended to the decision's warnings, exactly like a crashing rule
    # (core/lwb_core/engine.py) already surfaces there.
    extra_warnings = []
    if repo_error:
        extra_warnings.append(
            f"lwb: repo facts unavailable ({repo_error}) -- rules that need "
            "repository facts (e.g. lwb_proof_required) could not run for this event"
        )
    elif repo is not None and repo.facts_incomplete:
        # One layer below a collector crash: the collector ran and
        # returned data, but part of what it read (a proof directory or
        # .git/HEAD) existed and could not be READ -- e.g. permission
        # denied. lwb_proof_required.evaluate() already refuses to treat
        # that as "checked, found nothing" and stays silent; this is what
        # makes the fact that it COULD NOT CHECK visible in the output
        # instead of merely quiet. Independent reviewer's Attacks C/D
        # (proof/ and .git/HEAD made unreadable) found both a false deny
        # and a silent allow reachable here before this branch existed.
        extra_warnings.append(
            f"lwb: repo facts incomplete ({repo.facts_incomplete_reason}) -- "
            "rules that need repository facts (e.g. lwb_proof_required) may "
            "have stayed silent for this event rather than risk acting on "
            "facts they could not fully gather"
        )
    if policy_error:
        extra_warnings.append(
            f"lwb: policy unreadable at {policy_path} ({policy_error}) -- "
            "falling back to a policy with every rule off"
        )
    elif policy.degraded:
        # Same principle, one layer lower again: the policy file WAS read
        # and parsed, but its shape or a rule's mode was malformed (e.g.
        # a typo'd mode string) -- `lwb_core/config.py`'s own docstring
        # says this condition "is recorded so an adapter can log it", and
        # until now nothing did: `degraded`/`degraded_reason` were set by
        # `load_policy_dict` and read by no adapter, no hook, no script.
        # A typo that silently disarms an armed rule must not render the
        # same as a clean policy with nothing to say.
        extra_warnings.append(
            f"lwb: policy degraded ({policy.degraded_reason}) -- one or more "
            "rules may have resolved to off because of a malformed policy entry"
        )
    if extra_warnings:
        from dataclasses import replace

        decision = replace(decision, warnings=[*decision.warnings, *extra_warnings])

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
