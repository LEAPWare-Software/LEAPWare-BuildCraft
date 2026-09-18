# Mission and scope

Section 1 of the requirements package (`docs/requirements/approach.md`).
Owner-approved 2026-09-18. Decisions D1-D8 in
`docs/requirements/decisions.md` are settled inputs to this, not
re-openable here.

## Mission

**BuildCraft gives an AI development team full SDLC coverage at the lowest
measured token cost that clears a quality floor.**

**Coverage** comes from adopting proven skills and plugins wherever they
exist, and building only what does not.

**Quality** is enforced mechanically -- stages, roles and gates decided at
the CLI's own hook boundary, allow, warn or deny -- so the floor holds
without trusting anyone to follow it. Every claim of *done* leaves
evidence a human can audit later.

**Efficiency** is measured, never claimed. Meet the quality floor first,
then choose the lowest measured token cost among tested configurations
that meet it, reporting the tested frontier and its uncertainty rather
than an absolute optimum.

Owner-approved 2026-09-18. This reconciles this repo's earlier mission
with the LEAPWare full-SDLC implementation plan of 2026-09-10 and its
approved design document, which carried the owner's own goal: full SDLC
coverage, maximum quality, maximum token efficiency. The earlier mission
here stated the quality half and was silent on cost; the earlier plan
stated the goal and defined how to measure it honestly. Both halves are
now in one place.

### The quality floor

Quality comes first: a configuration becomes eligible on cost only once it
has cleared the floor.

1. The task's acceptance criteria were written down **before** the work
   started.
2. Every one of them is met.
3. Every mechanical gate is green -- tests, leak scan, lane check, proof
   check.
4. Every claim of *done* carries a proof record with real captured exit
   codes and an honest `unproven[]` list.
5. No unauthorised destructive action occurred.

Item 1 has no mechanical check today -- nothing records or timestamps
acceptance criteria before work starts -- so it is verified by the
reviewer reading the PR's own chronology. Closing that is required work,
not an accepted gap.

A configuration that fails any of these is not cheaper -- it is
disqualified. Cost is compared only among configurations that clear the
floor.

*Unauthorised* means any action on the destructive list in
`docs/handoff-protocol.md`'s hard rules, taken without an explicit
instruction from the owner: a repository settings change, a force-push, a
history rewrite, or deleting a remote ref other than a branch whose work
is verified landed. That list is finite and each entry is a fact about
what happened, not a matter of opinion, and the instruction is on the
record. So item 5 is a check, not a judgement.

**Read the list there, not a copy of it here.** This paragraph used to
inline its own copy, which included "a merge". D19 then made merging a
green, reviewed PR ordinary work, `docs/handoff-protocol.md` was updated,
and this copy was not -- so the definition the deny-capable rule actually
cites went on calling an authorised merge unauthorised. An independent
review of PR #16 found it after the same conflict had already been fixed
once, one file away. A second copy of a rule is a second place for it to
rot; the four items above are named only to keep this readable, and
`docs/handoff-protocol.md` governs.

The floor governs **how this project delivers**: it applies to every
deliverable here, today. It is not the same thing as what the shipped
plugin enforces for its users, which decision D1 sets to warn-only in 1.0.
Warn-only concerns the product's behaviour toward others; the floor
concerns ours.

The floor is built from signals this repository already produces, so
applying it costs almost nothing. Items 3 and 4 are enforced mechanically
today. The only new habit is item 1: state what *done* means before
starting, which is what makes the floor checkable at the end without a
seeded-failure corpus or a severity taxonomy.

### Measuring efficiency

Record total input, cached input, uncached input, output, retries, setup
overhead, tool overhead and wall time, separately. For equal quality,
choose fewer tokens. A smaller skill with worse results fails. A quality
gain that costs more tokens is a tradeoff, not a saving. Never alter
models or settings to manufacture a comparison. A missing measurement is
unknown, never zero. Instruction-length proxies are not billed savings,
and compressing text after it has entered model context does not recover
what it already cost.

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
4. **Adopt before building.** Where a proven skill or plugin already does
   the job, adopt it with pinned provenance and a recorded licence rather
   than writing our own. Building is the fallback, not the default.

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
| `plugins/codex/lwb` -- PreToolUse hook plus skills, same engine | EXISTS |
| Skills `lwb-status`, `lwb-config`, `lwb-report`, `lwb-handoff` | EXISTS |
| Skills `lwb-prove`, `lwb-stage`, `lwb-review`, `lwb-doctor` | PROPOSED |

### Tools

Fifteen exist under `scripts/`: `lwb_check_proof`, `lwb_lanes`,
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
