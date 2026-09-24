"""lwb_proof_coverage: a landed deliverable this branch can see, with no record.

`docs/requirements/build-plan.md`, Phase 1 item 1.1: `proof_coverage` has
existed since PR #6 only as an internal CI script
(`scripts/lwb_check_proof.py::check_coverage`, run by `.github/workflows/ci.yml`
as the `lwb-proof-coverage` job, post-merge, on push to `main`) -- named in
the plan, absent from the shipped `lwb` plugin. This module is what makes
it a RULE: installed into every consuming repo, not just enforced inside
this one.

## What it checks, and how this differs from CI's own check

CI's `check_coverage` walks `git log` over a full revision range with a
real subprocess and full repository history -- the authoritative check,
and it still runs, unchanged, as the `lwb-proof-coverage` job. That is not
available here: `core/lwb_core` does no I/O, and the adapter that gathers
facts for it (`adapters/claude/repo_facts.py`) must not shell out to `git`
(owner directive 8; see that module's "No subprocess, on purpose") and
must stay cheap enough to run before every hook event.

So the fact this rule reads -- `event.repo.landed_unproven`, populated by
`adapters/claude/repo_facts.collect_landed_unproven` -- is a BEST-EFFORT,
BOUNDED, LOCAL approximation: a walk of loose commit objects reachable
from HEAD (first-parent only, up to a fixed depth), stopping the moment
it reaches a packed one. See that function's docstring for exactly what
this can and cannot see. This rule inherits that scope honestly: it warns
about what the adapter found, and says nothing about what it could not
reach. A consuming repo that wants the exhaustive, `git log`-backed
version of this check gets it from adopting this repository's own CI job
pattern, not from the hook.

## What it reports

Fires on the same trigger `lwb_proof_required` does -- a `PreToolUse`
`Bash` event whose command publishes (`git push`, `gh pr create`, `gh pr
merge`; see `lwb_proof_required._scan_command`, reused here rather than
re-implemented, so the two rules can never disagree about what counts as
a publish). That keeps this rule as rare and meaningful as the one it
sits beside, rather than firing on every single Bash call a session
makes.

When `event.repo.landed_unproven` is non-empty, reports every entry (each
already formatted `"<sha prefix> (#<PR>)"` by the adapter), explicitly
labelled as a local, non-exhaustive scan so the finding never overstates
what was actually checked.

## Silence

- `event.repo is None`: the adapter gathered nothing. No opinion.
- `event.repo.facts_incomplete`: the adapter looked and could not fully
  read something -- same posture as `lwb_proof_required`, silence rather
  than a claim built on a partial read.
- `event.repo.landed_unproven == ()`: either nothing was found, or the
  walk could not reach far enough to find anything (see above). Both look
  identical to this rule on purpose -- an empty result is never promoted
  to "confirmed covered".

## Mode

Ships at `"warn"` in `core/policy/default.json`, per this repository's own
discipline (see `lwb_proof_required`'s docstring): a new gate lands
report-only first and is armed in a separate change once there is
evidence about what it fires on in practice. Item 1.3 of the plan (arming
`proof_required`) is a later step for that rule alone; nothing here is
armed to deny.

See docs/rules/lwb-proof-coverage.md for the policy-author-facing
description.
"""

from __future__ import annotations

from typing import Optional

from ..config import RuleConfig
from ..events import Event
from .lwb_proof_required import _COMMAND_KEY, _TOOL_NAME, _scan_command

rule_id = "lwb_proof_coverage"

#: How many of `event.repo.landed_unproven` to name in the finding before
#: falling back to a count. The list is already capped by the adapter
#: (`_MAX_LANDED_UNPROVEN`); this is a further cap on what is worth
#: printing in one line.
_MAX_NAMED = 5


def evaluate(event: Event, config: RuleConfig):
    """Warn (or deny) when a publish is about to land with unproven history
    already reachable from HEAD. See the module docstring for scope and
    what "unproven" means here.
    """
    from ..engine import Finding  # local import: engine imports this module.

    if event.hook_event != "PreToolUse" or event.tool_name != _TOOL_NAME:
        return None

    command = event.tool_input.get(_COMMAND_KEY)
    if not isinstance(command, str) or not command.strip():
        return None

    publishes, _pr_numbers = _scan_command(command)
    if not publishes:
        return None

    repo = event.repo
    if repo is None:
        # The adapter gathered no facts. Absence of evidence, not evidence
        # of absence -- say nothing, same discipline as lwb_proof_required.
        return None
    if repo.facts_incomplete:
        return None

    gaps = repo.landed_unproven
    if not gaps:
        return None

    named = ", ".join(gaps[:_MAX_NAMED])
    remainder = len(gaps) - _MAX_NAMED
    more = f", and {remainder} more" if remainder > 0 else ""
    return Finding(
        rule_id=rule_id,
        mode=config.mode,
        reason=(
            f"{len(gaps)} landed deliverable(s) reachable from HEAD have no matching "
            f"proof record (best-effort local scan, not exhaustive -- see "
            f"docs/rules/lwb-proof-coverage.md): {named}{more}. Add a proof/<id>.json "
            f"for each, or list it in proof/exempt.json with a reason."
        ),
    )
