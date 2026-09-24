"""lwb_proof_integrity: a structural, execution-free check on the record backing a publish.

`docs/requirements/build-plan.md`, Phase 1 item 1.1. `proof_integrity` is
the OTHER half named in the plan and absent from the shipped plugin: in
CI, `scripts/lwb_check_proof.py --reexecute` actually RE-RUNS every
command a proof record claims is `verifiable: true` and compares the
resulting digest against what the record recorded -- the check that makes
a record hard to fake. `.github/workflows/ci.yml` runs it report-only
(`continue-on-error: true`) because digest reproducibility across hosted
runners has not yet been proven; see the comment above that step, and
Phase 1 item 1.4 ("make re-execution blocking"), which is a separate,
later piece of work this rule does not attempt.

## Why this rule does not re-execute anything

Re-running a proof record's commands means spawning arbitrary recorded
subprocesses -- potentially a full test suite -- from inside a
`PreToolUse` hook. D17 (`docs/requirements/decisions.md`) settled this
question for the whole architecture: hooks GATE, a separate runner (not
yet built -- Phase 3 item 3.5) SEQUENCES, precisely because invoking
something that can take minutes inside a hook puts that latency in front
of every tool call and turns a hung command into a hung session. This
rule stays on the gate side of that line: it is a *structural* check,
reasoning only from what the matched record's own JSON already claims
about itself, never from re-running it. That is a real, useful, much
narrower thing than re-execution -- and it is honestly scoped as such
throughout this module, per the brief for this item: report what can be
learned from facts the adapter gathers, not solve cross-runner digest
reproducibility here.

## What it checks

Fires on the same publish trigger `lwb_proof_required` and
`lwb_proof_coverage` use (see `lwb_proof_required._scan_command`, reused
rather than re-implemented). When it fires, it reads two facts the
adapter already computed about the ONE proof record identified by the
current branch name (`adapters/claude/repo_facts.collect_matched_proof_facts`
-- deliberately the narrower, branch-only identifier, not
`lwb_proof_required`'s fuller PR-number/branch-token matching, so this
module needs no copy of that command-parsing logic to know which record
to look at):

- **Self-certification.** The record's own `checked_by` equals its own
  `author` -- the same defect `scripts/lwb_check_proof.py`'s
  `_validate_record` rejects in CI (`'checked_by' equals 'author' --
  proof cannot be self-certified`), surfaced here at the moment the
  publish is about to happen rather than only after a PR is opened.
- **A recorded failure.** Some `commands[]` entry's own `exit` does not
  equal its own `expect_exit` -- the record ADMITS, in its own content,
  that a command it lists did not pass.

Both are read straight off the record's JSON; neither requires running
anything.

## Silence

- No matching record (branch has none, or `event.repo` carries no
  `matched_proof_*` opinion -- `None`, not `False`): no opinion. A
  missing or unreadable record is `lwb_proof_required`'s territory, not
  this rule's -- this rule only ever has something to say about a record
  that DOES exist and IS readable.
- `event.repo is None` or `event.repo.facts_incomplete`: same silence as
  every other rule in this family.
- Neither structural problem is present: silence, even if the record is
  otherwise unremarkable in every way this rule does not check (this is
  not a full validator -- `scripts/lwb_check_proof.py` remains that).

## Mode

Ships at `"warn"` in `core/policy/default.json`, same discipline as every
other rule in this family: report-only first, armed later, separately,
once there is evidence about what it fires on.

See docs/rules/lwb-proof-integrity.md for the policy-author-facing
description.
"""

from __future__ import annotations

from ..config import RuleConfig
from ..events import Event
from .lwb_proof_required import _COMMAND_KEY, _TOOL_NAME, _scan_command

rule_id = "lwb_proof_integrity"


def evaluate(event: Event, config: RuleConfig):
    """Warn (or deny) when the proof record matched to this branch shows a
    structural integrity problem in its own content. See the module
    docstring for exactly what is and is not checked.
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
        return None
    if repo.facts_incomplete:
        return None

    problems = []
    if repo.matched_proof_self_certified is True:
        problems.append("checked_by equals author -- it certifies itself")
    if repo.matched_proof_has_failed_command is True:
        problems.append("one of its commands[] entries records an exit that does not match expect_exit")

    if not problems:
        return None

    return Finding(
        rule_id=rule_id,
        mode=config.mode,
        reason=(
            f"the proof record for '{repo.branch}' looks compromised: "
            f"{'; '.join(problems)}. This is a structural, execution-free check -- it "
            f"does not re-run any command; see docs/rules/lwb-proof-integrity.md"
        ),
    )
