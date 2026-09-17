# Rule: `lwb_version`

**Status:** shipped, the walking-skeleton rule. Source:
`core/lwb_core/rules/lwb_version.py`. Default mode: `warn` (see
`core/policy/default.json`) — a safe no-op: it reports the plugin version
and never blocks a dispatch, even if a policy file (incorrectly)
configures it to `deny`. It ships as a safe walking skeleton rather than
a real enforcing rule so the pipeline can be proven end to end before
any stage/role/gate rule is designed and built on top of it.

## What it checks

Fires on every event, unconditionally — every `hook_event` value, with or
without a `tool_name` — unlike a normal rule that only has an opinion on
one event shape. There is no trigger condition to miss.

## What it reports

A `Finding` whose `reason` states this build's `lwb_core.__version__`,
e.g. `"lwb 0.1.0: reporting only, no policy enforced yet"`. The `mode` on
that `Finding` is always `WARN`, regardless of `config.mode` — see the
next section.

## Options

None. `options` is accepted by the schema but currently ignored by this
rule.

## Modes

| Mode | Behavior |
|---|---|
| `off` | No check runs (the engine skips OFF rules before calling this one). |
| `warn` | The version report is recorded (ledger, `permissionDecisionReason`) but the dispatch proceeds. |
| `deny` | Same as `warn` — this rule refuses to deny under any configuration; see `evaluate()`'s docstring. |

## Why this rule, first

It is deliberately small and deliberately harmless: no trigger condition,
no external state, and a hard guarantee (enforced in the rule itself, not
merely by the shipped default) that installing this walking skeleton can
never itself block a dispatch. It exists to prove the full pipeline —
hook fires, adapter parses, engine evaluates, adapter renders, host acts
on the render — works end-to-end before BuildCraft's real SDLC gate rules
(stage checks, role lanes, and whatever enforcement each needs) are
designed and built on top of the same scaffolding. See
`tests/core/test_lwb_version.py`,
`tests/adapters/test_claude_hook_io.py`,
`tests/adapters/test_codex_hook_io.py`, and
`tests/conformance/test_same_decision_both_adapters.py` for the tests
that exercise it at every layer.
