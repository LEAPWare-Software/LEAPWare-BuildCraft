# Requirements approach for lwb 1.0.0

Owner-approved approach for turning `owner-directives.md` into a shipped
1.0.0. Order matters: evidence before drafting, an adversarial audit
before owner decisions, a freeze only after that. No step is skipped and
no step is done by the same role that did the previous one.

## Steps

1. **Evidence** (`sonnet`, explorer role). Gather the measured baseline
   (below) and the Claude-vs-Codex capability matrix. Recon only — no
   drafting.
2. **Draft** (`opus`, architect role). Turn evidence + owner directives
   into the full package (sections below). The architect did not gather
   the evidence — reduces anchoring on a single read of the facts.
3. **Adversarial audit** (`sonnet`, verifier role, explicitly *not* the
   drafter). Checks every requirement against its directive, every
   acceptance test against its requirement, every capability claim against
   its cited source. Blockers only, per this repo's review protocol.
4. **Apply findings**. Drafter or another worker fixes blockers; no
   re-review round beyond what the audit already found (Paper Fast Lane
   discipline, adapted from the sibling repo's review protocol, applies
   here as "one round, blockers only").
5. **Owner decisions**. Anything the audit could not resolve alone (a
   genuine tradeoff, an ambiguous directive) goes to the owner as a short
   list of named decisions, not an essay.
6. **Freeze v1.0**. Once owner decisions are recorded, the package is
   frozen — a numbered requirement's ID never changes meaning after
   freeze; a correction is a new requirement or an explicit amendment.

Each step ends with a Proof of Completion per `docs/handoff-protocol.md`.

## Package sections

1. Vision, scope, non-goals, personas.
2. Evidence base: what was actually read/run to support every claim below
   (file, command, or doc, with enough detail to re-run it).
3. Measured baseline: current sizes, token costs, CI durations — numbers,
   not impressions.
4. Functional requirements, one per owner directive (or a decomposition
   of one), each with: a stable ID, the triggering event, the decision
   the plugin makes, a Given/When/Then acceptance test, and a mutation
   proof (a test that fails if the behavior regresses, not just a test
   that the happy path returns true once).
5. Policy/config schema and precedence — explicit rule: a project-level
   policy must not loosen a user-level policy (narrower may tighten,
   never loosen).
6. Measurement and reporting: what gets counted, where, and who reads it.
7. Claude vs Codex capability matrix, every row backed by a verified
   source (doc link or a command run against the actual CLI, not
   recollection).
8. Non-functional requirements: cross-platform (Windows/macOS/Linux,
   matching CI's own matrix), stdlib-only, hook latency and per-hook
   token-overhead budget, no network calls from a hook, fail-open vs
   fail-closed per rule class, install/upgrade/uninstall behavior, size
   budget (directive 14), statusline behavior (directive 6).
9. Bypass/threat model: what a determined session could route around
   (subprocess calls a hook never sees, a config edit before the hook
   reloads it) and which of those this package accepts vs. closes.
10. Open-source governance: license, contribution flow, CODEOWNERS,
    security reporting — already partly present in this repo's root
    files; this section is the requirements-level statement, not a
    restatement of CONTRIBUTING.md.
11. Traceability matrix: requirement ID → test → proof record. No
    requirement ships without a row.
12. Owner decisions: the list from step 5 above, with the owner's actual
    answer recorded, not just the question.
13. Out of scope: directive 16, plus anything else the audit determines
    is out of scope and the owner confirms.
