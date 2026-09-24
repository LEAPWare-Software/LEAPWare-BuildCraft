# BuildCraft 1.0.0 — the build plan

Owner-approved 2026-09-19, phase by phase, in a live walkthrough.

**This closes required-work item 6** (`docs/requirements/decisions.md`),
which read: *"No consolidated plan exists... the sequenced plan is not
written."* It had been open since 2026-09-18. Before this document, the
plan lived scattered across `mission.md`, `decisions.md`,
`owner-directives.md`, `docs/maintainers/proof-of-completion-plan.md` and
`HANDOFF.md`, with no single sequenced statement of what gets built in
what order.

---

## THE CONDITION ON EVERY PHASE

> **Before we build anything, in any phase, we must absolutely,
> positively have double-checked that there is no WORTHY AND VETTED tool
> or plugin that already does it.**

Owner ruling, 2026-09-19, attached to the stage list in D23 and restated
here because a condition in a decision log is a condition nobody reads.

It applies to all thirteen stages **including the three that D12 assigned
lwb to build**. That survey is a snapshot, and *"nothing credible exists"*
is exactly the class of claim this repository has learned not to take on
trust. Principle 4 of the mission — adopt before building — had never
once been acted on when this plan was written: zero of eight surveyed
components had been trialled, and no adoption register existed.

## THE THREE LENSES

Every phase and every status is stated in the owner's framing of the
mission:

- **Coverage** — does the lifecycle have something doing the job?
- **Quality** — is it enforced mechanically, or merely asked for?
- **Efficiency** — is the token cost measured, or claimed?

The mission is all three. An earlier summary of it described only part of
Quality and dropped Coverage and Efficiency entirely; the owner corrected
that, and this framing is the correction made permanent.

---

## Phase 1 — `lwbpoce`, the proof-of-completion engine

**`lwbpoce` means the fully vetted proof-of-completion engine INTERNAL AND
EXTERNAL** — the one we use to build lwb, *and* the one that ships inside
lwb for people who install it. Both halves. The owner's definition,
correcting an earlier reading that treated it as a single component to be
slotted somewhere.

**Why first (CTO call, owner-approved):**

1. Every later phase will claim *done*. Without this engine none of those
   claims is checkable, and we would build the rest on exactly the
   unverified ground that this repository keeps catching.
2. It is the only part substantially built, so Phase 1 closes fastest and
   yields a genuinely completed phase rather than a paper one.
3. `proof_required` is one of only **two** rules D9 permits to block in
   1.0. It is foundational to the enforcement model, not merely to
   bookkeeping.
4. Proving the internal-to-external path once de-risks every rule family
   that follows.

The one argument against — that adopting outside components might change
what evidence looks like — does not hold: proof records are tool-agnostic.

**State at plan time:** internal ~9 of 9 built. **Shipping: 1 of 9.**

| | |
|---|---|
| Coverage | The receipts exist and work — for *us*. A consuming repo gets one warning rule. |
| Quality | Nothing is armed to deny. Re-execution, the part that makes a record hard to fake, is report-only and cannot fail a build. |
| Efficiency | Token cost is recorded per deliverable and never compared. |

| # | Item |
|---|---|
| 1.1 | Ship `proof_coverage` and `proof_integrity` as rules — named in the plan, absent from the code |
| 1.2 | Make `deny` **fail closed** — today it permits when it cannot read git, advertising enforcement it cannot deliver |
| 1.3 | Arm `proof_required` to deny — only after 1.2; locked by test until then |
| 1.4 | Make re-execution **blocking** — needs the changed path proven on a real runner first |
| 1.5 | **Acceptance criteria recorded before work starts** — quality-floor item 1. See D24 |
| 1.6 | Define *authorised*, then build `no_unauthorised_destructive_action` — required-work item 10; the plan's second deny-capable rule |
| 1.7 | **More than one reachable reviewer identity** — see "Why 1.7 exists" below |
| 1.8 | **CONFIRMED 2026-09-24, Linux/Claude Code 2.1.282 only.** Both `hooks.json` matchers (`Bash`, `Agent`) were observed firing in a real, live Claude Code session with the plugin loaded via `--plugin-dir` — a ledger line appeared for each. See `docs/maintainers/hook-fires-verification-2026-09-24.md` for the exact reproduction, environment, and what this does *not* cover (other OSes/versions, other permission modes, deny-mode policy behavior). |

**Done when:** a consuming repo installs `lwb` and cannot publish work that
lacks evidence — and we can show that happening in a repo that is not ours.

**Why 1.7 exists, and why it is not bureaucracy.** On 2026-09-19 PR #27
was code-complete and could not land, because the repository had exactly
**one reachable independent reviewer identity** and that peer session had
been paused by its own owner. No amount of correctness could move it. A
proof protocol that nobody can sign off is not a protocol. Two reviewers
were reachable within the hour once the problem was named, and the second
immediately found defects the first had not — including a green gate for a
plugin that could never fire. The single point of failure was real and it
was ours.

## Phase 2 — Adoption trials

**This phase decides how much of BuildCraft we actually build.** Per D21.

| | |
|---|---|
| Coverage | This *is* the coverage phase: every one of the 13 stages gets a verdict — adopt, build, or genuinely uncovered. |
| Quality | Each candidate passes a scoped trial against the quality floor (D13, protocol in D18) before entering the stack. Nothing is adopted on its README. |
| Efficiency | Each trial is measured for token cost. This is where *measured, never claimed* stops being a sentence. |

| # | Item |
|---|---|
| 2.1 | **Double-check all 13 stages for existing tools** — the owner's condition, including the three we assigned ourselves |
| 2.2 | Trial the 8 named adoptables — Spec Kit, Superpowers, `code-review`, `security-review`, Trail of Bits, Sentry/Datadog MCP, PagerDuty MCP, Dependabot |
| 2.3 | Resolve the 3 contested or thin ones — `claude-mem` is **contested** (inflated star count tied to an unaffiliated crypto token, plus a filed security issue); architecture and documentation tooling is thin |
| 2.4 | **Build the adoption register** — pinned version, commit hash, licence per component. Does not exist today |
| 2.5 | **Recover the missing fifteenth responsibility** — D12 claims fifteen and names fourteen, claims eight adoptables and names seven. It is written down nowhere and was not invented to make the count work |

**Done when:** every stage has a verdict backed by a trial, and the
register records exactly what we depend on and under what licence.

**Risk:** this phase can substantially *shrink* the product. That is the
point, and it means Phase 4's size is unknown until this finishes.

## Phase 3 — Stage and role enforcement

Where BuildCraft starts behaving like an SDLC tool rather than an evidence
recorder. Today the plugin does not know that stages exist.

| | |
|---|---|
| Coverage | The 13 stages become real to the software. |
| Quality | **Warn-only, by decision.** D9 splits rules by signal: facts may block, judgements may only warn. *"You skipped a stage"* is a judgement. |
| Efficiency | Sequencing prevents wasted work — no security review on code that has not passed tests. |

| # | Item |
|---|---|
| 3.1 | `stage_order` — a later stage cannot precede an earlier one |
| 3.2 | `stage_evidence` — a stage claims completion only with evidence |
| 3.3 | `independence` — a reviewer may not have authored an earlier stage of the same deliverable (D16) |
| 3.4 | `lane_write` as a **shipped rule**, not only our CI script |
| 3.5 | **Build the runner** — D17 settled two entrypoints, *hooks gate, a runner sequences*. **The runner does not exist.** Nothing can sequence stages without it |
| 3.6 | Write the evidence contract; update `docs/architecture.md` — required-work item 9 |

**Two honest limits, stated here rather than discovered later:**

1. **Identity is self-attested.** D16 records it: a reviewer says who it
   is and nothing verifies that. These records are an audit trail, not
   proof of independence.
2. **Warn-only means advisory.** A team that ignores the warnings proceeds
   unimpeded. Deliberate under D9 — but Phase 3 alone makes skipping a
   stage *visible*, not impossible.

**Dependency:** cannot start until Phase 2 reports which stages have
tools, because sequencing adopted components is most of what the runner
does.

**Risk:** 3.5 is the largest single unbuilt piece in the plan — a second
entrypoint that has never existed, settled by decision and never designed.
Every other item in the plan is a rule: read an event, return a verdict,
stay pure. The runner has state, orchestrates other people's tools, and
survives across many steps. A different shape from anything in the
codebase.

## Phase 4 — Build only what nothing covers

**Cannot be scoped until Phase 2 reports.** Deliberate: its size is
determined by what the trials find, not by what was assumed.

| # | Item | Status |
|---|---|---|
| 4.1 | Build/CI artifact integrity | candidate — **weakest justification, attack first** |
| 4.2 | Safe schema and data changes | candidate |
| 4.3 | Release and deployment | candidate |
| ~~4.4~~ | ~~Retirement / decommissioning~~ | **eliminated by owner ruling, D23** |

**The pattern across all three:** the *mechanics* exist in abundance —
migration tools, release tooling, artifact signing. What does not exist is
a **decision at the hook boundary** about whether an agent may perform the
action. That is a coherent reason to build, and it is falsifiable, which
is what makes Phase 2 worth running.

**Where the plan argues against itself:** 4.1's justification is
materially weaker than the other two. SLSA, Sigstore and in-toto exist,
are credible, and address artifact provenance directly. If Phase 2 finds
one covers us, 4.1 disappears — and the committed-`.pyc`-runs-instead-of-
reviewed-source problem found on 2026-09-19 gets solved by someone else's
maintained work.

## Phase 5 — Efficiency measurement

**Half the mission has zero tooling.** One schema field, no mechanism.

| # | Item |
|---|---|
| 5.1 | Run configurations against a fixed task set, record real cost |
| 5.2 | Report the **tested frontier with its uncertainty**, never an absolute optimum |
| 5.3 | Enforce that a missing measurement is **unknown, never zero** |
| 5.4 | Feed Phase 2 — each adoption trial reports cost, not only capability |

**Rules the mission already fixes:** a smaller skill with worse results
fails and is not a saving; a quality gain costing more tokens is a
trade-off; never alter models or settings to manufacture a comparison;
instruction-length proxies are not billed savings, and compressing text
after it enters context does not recover what it already cost.

**The instrument is a floor of unknown tightness — see D25.** Our own
accounting is cumulative across PRs, excludes every subagent, and has
three structurally unknowable fields. Phase 5's real job is not a perfect
instrument; it is making the instrument's limits explicit every time a
number is used.

## Phase 6 — Drive a real repo

**The 1.0.0 bar (D22), and the first time BuildCraft is judged by
something other than itself.**

| | |
|---|---|
| Coverage | Does real work fit the 13 stages, or did we invent a lifecycle nobody works in? |
| Quality | Do gates fire on real work, and on the *right* things? |
| Efficiency | What does governance cost per unit of real work? |

| # | Item |
|---|---|
| 6.1 | Choose a real LEAPWare repo with live work — not a demo, ruled out explicitly |
| 6.2 | Install via the documented path — **never executed against any foreign repo** |
| 6.3 | Run real changes through the applicable stages, evidence recorded |
| 6.4 | Record every obstruction and false positive |
| 6.5 | Fix and repeat until a full cycle completes clean |

**First subjects, D26:** SessionKeeper or Pulse first — Python, active,
nothing at stake — to shake out the never-executed install path. **The
real bar on ShellUX, after its v1 release ships:** TypeScript, actively
developed, and the one that proves we are not language-coupled. Every gate
we have written is Python, run by Python, checking Python conventions; if
BuildCraft only works in Python repos we would never discover it by
testing on Python repos. Governing ShellUX *during* its release would be
the worst possible first test: highest stakes, least proven tool.
Watchtower is excluded — the owner has ruled it will not be there long
term.

**This phase settles the question open since the product began:** does the
hook fire when Claude Code dispatches it? Every check we have runs the
hook ourselves. In a real repo either it fires or it does not.

**The risk that matters:** a false positive does not fail a test, it
blocks someone's actual delivery. Two mitigations belong inside the phase:
every rule starts at `warn` in that repo and is armed only after being
observed behaving correctly; and a documented one-step disable that does
not require understanding the plugin.

**Reservation, recorded at plan time:** this phase can discover that the
13 stages do not match how work actually flows, sending us back to Phase 3
late. That is the argument for running a thin slice of real work early
rather than waiting for the full plan to be built.

## Phase 7 — Release 1.0.0

Small phase; the gate in front of it is large.

| # | Item |
|---|---|
| 7.1 | Reconcile versions — five sources say `0.1.0`, **the codex plugin says `0.2.0+codex`** |
| 7.2 | Write the CHANGELOG — everything sits under `[Unreleased]` |
| 7.3 | **Prove the release pipeline works** — `release.yml` triggers on a `v*` tag and **has never run**, because there has never been a tag |
| 7.4 | Tag `v1.0.0` — irreversible, public, under LEAPWare's name. **Owner's call** |
| 7.5 | Publish |

**The trap in 7.3:** going straight to `v1.0.0` means the first execution
of our release pipeline is the most important release we will do. A
throwaway pre-release tag proves the pipeline while the stakes are nil.

**Done when:** someone outside LEAPWare can install `lwb` and have it
govern their SDLC, and we can show it doing so.

---

## The plan end to end

| # | Phase | Gate to leave it |
|---|---|---|
| 1 | `lwbpoce` — proof engine, internal and external | A consuming repo cannot publish unevidenced work |
| 2 | Adoption trials | Every stage has a verdict backed by a trial |
| 3 | Stage and role enforcement | The plugin refuses out-of-order work |
| 4 | Build what nothing covers | Every stage has a tool or a component |
| 5 | Efficiency measurement | Decisions cite measured cost at equal quality |
| 6 | Drive a real repo | A real deliverable completes, team unobstructed |
| 7 | Release 1.0.0 | Someone outside LEAPWare can use it |

## Decisions this plan rests on

D9 rule classes · D12 four areas to build · D13 prove every adoption ·
D15 stages derive from the responsibility map · D16 independence ·
D17 two entrypoints · D18 trial protocol · **D21** adopt before build ·
**D22** the real-repo 1.0.0 bar · **D23** the thirteen stages ·
**D24** GitHub-anchored acceptance criteria · **D25** order-of-magnitude
efficiency · **D26** first-subject repos.

## How this document should be read

Everything above is a plan, not a record of work. The status claims in it
were measured on 2026-09-19 and will rot. Re-derive before trusting any of
them — which is the same instruction
`docs/maintainers/proof-of-completion-plan.md` closes with, for the same
reason.
