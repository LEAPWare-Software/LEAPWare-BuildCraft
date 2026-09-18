# Vision and scope

Section 1 of the requirements package (`docs/requirements/approach.md`).
Owner-approved 2026-09-18. Decisions D1-D8 in
`docs/requirements/decisions.md` are settled inputs to this, not
re-openable here.

## Mission

**BuildCraft makes delivery discipline unskippable for AI coding agents.**

Stages, roles and gates are decided at the CLI's own hook boundary --
allow, warn or deny -- and every decision and every claim of *done* leaves
an evidence record a human can audit later.

The target: **"done" means the same thing to the agent that says it and to
the person reading it six months later.**

## Why it cannot be advisory

This repo is its own first customer, and as a customer it failed three
times in a single session on 2026-09-17, every failure under green CI:

- Two governance gates could never fire. The proof-coverage check looked
  for GitHub's `(#N)` squash subject while running at PR time, when that
  commit does not yet exist; the shared-path review rule demanded one
  record per CLI vendor, which a single-CLI repo could never satisfy.
- Owner directive 8, marked SACRED, was breached inside the file meant to
  enforce it: five private-name literals sat in plaintext in a public
  repo, invisible because that file was on the scanner's own exemption
  list.
- A test asserted a hole was correct behaviour, so the suite defended the
  defect.

Each was found by independent adversarial review, not by the author. A
rule an agent states, believes and violates is the problem this product
exists to remove.

## Principles

1. **Mechanical over stated.** A rule that lives only in a prompt is
   advisory. It must return allow, warn or deny.
2. **Evidence over assertion.** "Tests pass" is a claim. A captured exit
   code and a hash of the output is evidence.
3. **Fail open, never silent.** A broken or missing policy must never
   block work -- and must never report success either. An unarmed check
   reports UNCONFIGURED, not green.

## Non-goals

BuildCraft is not a second orchestrator, not a linter or formatter, not a
code-quality judge, not a sandbox, and not a replacement for CI. It
inspects no shell command and decides nothing about whether content is
safe.

## Scope

`EXISTS` is shipped and tested today. `PROPOSED` is approved to build and
not yet written.

### Core -- pure, stdlib only, zero I/O

| Component | State | Role |
|---|---|---|
| `events.py` (`Event`) | EXISTS | The one neutral shape every rule reads |
| `engine.py` (`evaluate` -> `Decision`) | EXISTS | Registry order; stops at the first deny |
| `config.py` (`Policy`) | EXISTS | `off`/`warn`/`deny`; fail-open |
| `ledger.py` | EXISTS | One JSON line per decision |
| `rules/__init__.py` | EXISTS | Registry -- one no-op rule today |

### Rule families -- the product itself

Per D1, all three families ship in 1.0 **warn-only**; deny modes follow in
1.1 from ledger evidence.

| Family | Rules | State |
|---|---|---|
| Stage | `stage_order`, `stage_evidence` | PROPOSED |
| Role | `independence`, `lane_write` | PROPOSED |
| Proof | `proof_required`, `proof_coverage`, `proof_integrity` | PROPOSED |
| Hygiene | `env_leak`, `commit_identity`, `instruction_dep` | PROPOSED -- these exist as CI scripts, not yet as rules |

### Stages and roles

Per D2: `design -> qa -> review -> security -> delivery -> release ->
operations`.

Per D3, independence is the role rule: a `qa`, `review` or `security`
actor may not have authored any earlier stage of the same deliverable. A
project policy may tighten this, never loosen it.

### Plugins and skills

| Component | State |
|---|---|
| `plugins/claude/lwb` -- PreToolUse hook plus skills | EXISTS |
| `plugins/codex/lwb` -- skills, no hook | EXISTS |
| Skills `lwb-status`, `lwb-config`, `lwb-report`, `lwb-handoff` | EXISTS |
| Skills `lwb-prove`, `lwb-stage`, `lwb-review`, `lwb-doctor` | PROPOSED |

### Tools

Fourteen exist under `scripts/`: `lwb_check_proof`, `lwb_lanes`,
`lwb_check_env_leak`, `lwb_check_commit_identity`,
`lwb_check_no_instruction_dep`, `lwb_check_prefix`,
`lwb_check_hook_launch`, `lwb_check_hosted_runners`,
`lwb_check_lane_write`, `lwb_handoff`, `lwb_build`, `lwb_release`,
`lwb_apply_rulesets`, and the two plugin validators.

### SDLC processes

| Process | State |
|---|---|
| Proof of Completion, pre-merge and post-merge | EXISTS |
| Handoff protocol -- 3000-byte cap, re-derive rather than trust | EXISTS |
| Lane discipline and independent review | EXISTS |
| Owner decision log | EXISTS |
| Requirements approach -- evidence, draft, audit, freeze | EXISTS as process |
| Acceptance evidence recorder, lifted from the legacy repo | PROPOSED -- origin and licence check first |
| Release and versioning scheme | PROPOSED -- blocked on plugin version drift |

## Known state, stated plainly

The mission is currently proven on this repo and unimplemented as a
product. Every gate with teeth today -- lane separation, proof of
completion, independent review, leak scanning -- is a *contributor* gate
run by `scripts/` in CI. The shipped plugin registers exactly one rule,
`lwb_version`, which is a deliberate no-op walking skeleton. Closing that
gap is what the rule families above are for.
