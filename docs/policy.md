# Policy file format

A buildcraft policy is one JSON file matching `core/policy/schema.json`:

```json
{
  "rules": {
    "lwb_version": {
      "mode": "warn",
      "options": {}
    }
  }
}
```

- Top-level: only `"$schema"` (optional, informational) and `"rules"`
  (required) are allowed.
- `"rules"` is an object keyed by `rule_id` — see
  `core/lwb_core/rules/__init__.py`'s `RULES` list for every rule id a
  build of buildcraft knows about.
- Each rule entry has a required `"mode"`, one of `"off"`, `"warn"`, or
  `"deny"`, and an optional `"options"` object whose shape is rule-specific
  (documented per rule under `docs/rules/`).
- A rule not mentioned in `"rules"` behaves as `"off"`.

## Mode semantics

| Mode | Effect |
|---|---|
| `off` | The rule is never evaluated for this event. |
| `warn` | The rule's finding, if any, is surfaced (in a hook's `permissionDecisionReason`, in the ledger) but never blocks the action. |
| `deny` | The rule's finding, if any, blocks the action. |

The engine evaluates rules in registry order and stops at the first `deny`
finding (see `core/lwb_core/engine.py`); `warn` findings from rules that
ran before a `deny` are still recorded.

## Fail-open

**A missing, unreadable, or malformed policy file never blocks anything.**
Concretely:

- `lwb_core.config.load_policy_dict(None)` — or any non-dict input —
  returns a `Policy` with `rules={}` and `degraded=True`. Every
  `rule_config(...)` call against it returns `mode=RuleMode.OFF`.
- A policy dict with a `"rules"` key that isn't an object behaves the same
  way.
- A single rule entry that isn't an object, or whose `"mode"` isn't a
  recognized string, resolves that ONE rule to `off` without affecting any
  other rule in the same file (see `lwb_core/config.py::load_policy_dict`).
- `plugins/claude/lwb/bin/lwb_hook.py` turns "file doesn't exist" and
  "file isn't valid JSON" into the same `None` input, so both hit the same
  fail-open path.

This is a deliberate product decision, not an oversight: a policy authoring
bug must not be able to block every subagent dispatch in a session. It is
configurable in the sense that a future rule COULD choose to deny on a
broken policy for itself — nothing in the engine prevents a rule from doing
so — but no shipped rule does, and the registry-level default stays
fail-open.

## Where a policy file lives

- Claude Code plugin: `LWB_POLICY_PATH` env var if set, otherwise the
  vendored `core/policy/default.json` bundled at
  `plugins/claude/lwb/vendor/policy/default.json`.
- Codex plugin: same convention, read by the `lwb-config` /
  `lwb-report` skills rather than a hook (see `docs/install-codex.md`).

## The bundled default

`core/policy/default.json` ships four rules, every one of them in `warn`
mode:

- `lwb_version` — a safe no-op that reports the plugin version and never
  blocks a dispatch, even if misconfigured to `deny` (see
  `core/lwb_core/rules/lwb_version.py`).
- `lwb_proof_required`, `lwb_proof_coverage`, `lwb_proof_integrity` — the
  proof-of-completion family (`docs/rules/lwb-proof-required.md`,
  `docs/rules/lwb-proof-coverage.md`, `docs/rules/lwb-proof-integrity.md`).
  None is armed to `deny` in the shipped default: this repository's own
  discipline is to land a new gate report-only first and arm it in a
  separate, later change once there is ledger evidence about what it
  actually fires on.

BuildCraft's remaining stage/role/gate rules are designed and built in
later phases, on top of the same fail-open scaffolding. See
`examples/policies/example-routing.json` for a larger, generic illustration
of a multi-rule policy shape (not a real deployed policy — see that file's
own header comment).
