# Owner decisions

The running decision log `docs/requirements/approach.md` §12 calls for:
"the owner's actual answer recorded, not just the question." Each entry is
dated, states what was decided, and — where it matters — what it changed
from and why. Nothing here is a proposal; proposals live in the package
draft until they are answered.

`HANDOFF.md` points here rather than carrying these, under the 3000-byte
transition-only cap (owner ruling, 2026-09-17).

## D1 — Rule families and phasing · 2026-09-17

All three rule families (stage, role, proof) ship in **1.0 warn-only**.
Deny modes are enabled in 1.1 from ledger evidence, not guessed up front.

Rejected: shipping one family deny-capable first (proof, or stage). The
warn-only release makes the ledger the evidence base for 1.1's thresholds,
which nothing else can supply.

**AMENDED 2026-09-18.** Warn-only in 1.0 contradicted the settled mission,
which requires quality enforced mechanically "without trusting anyone to
follow it" -- warn notifies and trusts. Independent review also found the
evidence argument unsound: `docs/architecture.md` states a ledger write
failure is swallowed, so a warn-only 1.0 can under-report silently and
bias the very data 1.1 was to be built from. Split instead: rules mapping
directly to quality-floor items ship **deny-capable in 1.0** -- proof
record required, and no unauthorised destructive action -- because both
are objective and low false-positive. Stage-ordering and role-independence
stay warn-only in 1.0, being judgement-heavy and prone to misfire.
Separately, ledger write failures must be counted and surfaced rather than
swallowed, or 1.1's evidence base is worthless.

## D2 — Stages · 2026-09-17

The seven roles from the legacy repo become the ordered stages:

`design → qa → review → security → delivery → release → operations`

This collapses stage and role onto one vocabulary. Consequence accepted:
`operations` has no natural gate in a plugin repo.

**SUPERSEDED 2026-09-18 by D15.** These seven were ported from the legacy
repo's roles and never passed the adoption check the mission's fourth
principle requires. D15 derives the stage vocabulary from D12's map of
fifteen SDLC responsibilities instead. D15 claimed to supersede this
decision but D2 carried no annotation, so a reader stopping here saw a
superseded rule stated as current -- found by an independent audit, and
the same omission D5 and D10 were each given an annotation to prevent.

## D3 — Role separation · 2026-09-17

**Reviewer-independence only.** For a proof record whose stage is `qa`,
`review` or `security`, its `author` must not appear as `author` in any
earlier-stage record for the same `deliverable`. A project policy may
tighten this, never loosen it (per `approach.md` §5).

Rejected: every consecutive stage must differ. Legacy's own role contract
permits "the smallest sufficient role set", so strict consecutive
separation would warn constantly — and in a warn-only 1.0, constant
warnings destroy the ledger evidence D1 depends on.

Known limit, recorded rather than implied: this cannot detect shared-model
blind spots. Legacy's role contract concedes the same. It belongs in the
package's threat model (§9), not in a rule.

## D4 — Stage state is derived, not stored · 2026-09-17

Stage state comes from `proof/*.json`, which already carries `deliverable`,
`author` and `checked_by`, plus one added `stage` field. No new state store.

The adapter reads the records and hands the engine a plain mapping, keeping
`core/lwb_core` I/O-free. Rejected: a plugin-data-dir store (breaks
cross-CLI handoff and fresh-clone portability) and anything reading `gh`
(violates the no-network-from-a-hook rule, `approach.md` §8).

## D5 — Shared-path review is identity-based, N=1 · 2026-09-17 (PR #6)

`REQUIRED_INDEPENDENT_REVIEWS = 1`, vendor-agnostic: one record under
`reviews/<pr>/` with verdict `AGREE` and a `reviewer_id` differing from the
commit's `commit_author_id`. Any filename.

**Changed from:** one record per CLI *vendor* — both `claude-cto.json` and
`codex-cto.json`. That coupled independence to a vendor when the property
that matters is a distinct reviewer identity, and it was unsatisfiable with
a single CLI in operation, so from PR #6 every shared-path change would have
been unmergeable.

**Open decision, NOT settled.** The independent review of PR #6 flagged
that the 2→1 change was self-serving — the author needed it to land that
very PR — and that `reviewer_id` and `commit_author_id` are self-attested
strings which nothing cross-checks against git authorship, the
`LWB-Agent:` trailer, or any session registry. The owner ruled on
2026-09-17 to keep N=1 and revisit here. So:

- Until identity binding is designed, `reviews/*` records are an **audit
  trail, not proof**.
- The package must answer: what binds a reviewer identity to something
  externally verifiable, given a subagent reviewer has no git identity of
  its own?

Rejected for now: requiring an owner GitHub approval on every shared-path
PR (nearly everything here is a shared path, so it would gate all work on
one person); reverting to two reviewers (deadlocks until a second reviewer
identity exists).

**SUPERSEDED 2026-09-18 by D10.** The premise is gone: D5 mediated between
two CLI reviewer identities, and the owner has eliminated CTO co-approval
and deferred Codex. See D10.

## D6 — GitHub Apps deferred · 2026-09-17

`lwb-claude` and `lwb-codex` are not created. GitHub has no App-creation
API and the manifest flow needs an authenticated browser session, which a
CLI session cannot reach. They block nothing: `gh auth` already commits and
merges. Revisit when a second CLI, or a revocable per-CLI identity, is
actually needed.

Standing instruction: do **not** generate an App private key until there is
a decided place to keep it. GitHub shows it once and it carries repo write.

**AMENDED 2026-09-18.** The conclusion (defer both Apps) stands but the
reasoning was stale. `lwb-codex` is not pending-on-need; Codex itself is
deferred as a deliverable (D11). Revisit condition is now "when Codex is
undeferred", not "when a second CLI is needed".

## D7 — Private-name needles are configuration · 2026-09-17 (PR #5)

Real private-name needles come from the `LWB_PRIVATE_NEEDLES` environment
variable (a repository secret in CI), never from committed source. An
unconfigured run **fails** as `UNCONFIGURED` rather than passing quietly.
`PUBLIC_NEEDLES` is deliberately empty: a name this repo publishes on
purpose is not a leak.

Forced by finding five private-name literals committed in plaintext to this
public repo, in the file meant to prevent exactly that, hidden behind that
file's own scanner exemption.

## D8 — Public git history accepted · 2026-09-17

Those five names remain in commits `79b2626` and `31a75ab` on public
`main`. The owner chose to fix HEAD and accept the history: removing them
from HEAD does not erase them, and a rewrite cannot un-publish what was
already public.

## D9 — Enforcement split by rule class · 2026-09-18

See the D1 amendment. Deny-capable in 1.0: `proof_required`,
`no_unauthorised_destructive_action`. Warn-only in 1.0: `stage_order`,
`independence`. The test is whether a rule's signal is a fact or a
judgement. Facts may block; judgements may only warn until ledger evidence
justifies more.

## D10 — The owner approves; co-approval is eliminated · 2026-09-18

Shared-path changes need the **owner's** approval until he chooses to
delegate. The Claude/Codex CTO co-approval clause is eliminated.

Independent review remains available and is used heavily, but it is a tool
the CTO uses to attack his own work -- advisory, never a gate on the owner.

This moots D5's open question. It asked what binds a reviewer identity to
something externally verifiable, given a subagent reviewer has no git
identity. The owner has a GitHub identity that is externally verifiable, so
while he is the approver the question does not arise. It is recorded as
moot, not answered, and returns if he delegates or Codex is undeferred.

**SUPERSEDED 2026-09-18 by D19, as to mechanics.** The principle stands —
the owner is the authority and independent review is advisory, never a
gate on him. What changed is how his approval is obtained: D10 required it
on every shared-path change, and nearly every path here is shared, so it
read as "the owner approves every PR, forever". He named himself the
bottleneck and replaced it with proceed-by-default plus a veto. See D19
for the four classes that still escalate.

Live locations of the old clause, to be removed: `AGENTS.md` lines 10-11,
and `scripts/lwb_lanes.py`'s module docstring and its `SHARED_PREFIXES`
comment. `CLAUDE.md` is already correct and is the template.

## D11 — Codex deferred; Claude plugin first · 2026-09-18

The deliverable is a Claude plugin. Codex is deferred until the owner says
otherwise.

Deferral costs nothing and was verified, not assumed: `core/` has zero
dependency on the Codex adapter -- one descriptive docstring mention, no
import, no branch. Freezing the lane breaks no test and no CI job.

**Removal is a different matter and is NOT authorised.** `lwb_build.py`
and `lwb_release.py` hardcode both targets; `tests/conformance/` imports
the Codex adapter directly to assert both adapters render identically, so
deleting it errors on import rather than skipping. Nine tests stop
outright and two CI steps hard-fail. Defer by not developing further.

## D12 — lwb builds four areas, adopts the rest · 2026-09-18

Applying the mission's fourth principle honestly shrinks the build.

A survey of fifteen SDLC responsibilities found credible adoptable
components for eight: requirements (GitHub Spec Kit), implementation
(Superpowers), verification (Anthropic's `code-review` plugin), security
(Anthropic's `security-review` plus Trail of Bits), observability (Datadog
and Sentry MCP), incident response (PagerDuty MCP), vulnerability handling
(GitHub's Dependabot toolset). Three more are adoptable with caveats:
architecture/ADR and documentation are thinly adopted, and `claude-mem`
for handoff is contested -- inflated star count tied to an unaffiliated
crypto token, plus a filed security issue.

**Nothing credible exists for four, which lwb must build:** build/CI
artifact integrity, general-purpose safe schema and data changes, release
and deployment, and retirement/decommissioning.

So lwb's job is to sequence and enforce adopted components at the hook
boundary, and to build only those four. The seven-stage model becomes a
routing map over real tools rather than a taxonomy reimplemented here.

## D13 — Prove every adoption before it enters the stack · 2026-09-18

No component is adopted on its README. Each passes a scoped trial measured
against the quality floor and its token cost first. This is the owner's
own standard from the predecessor repo, where RTK and Headroom were
piloted before judgement -- and it is the standard that was NOT applied to
the components that later had to be removed.

## D14 — Tech stack: what the evidence actually shows · 2026-09-18

Findings from an independent evidence review, recorded because they were
expensive to obtain and are the basis of D12 and D13.

- **Ponytail — REMOVED.** Its headline claim was independently debunked:
  Colin Eberhardt (Scott Logic, June 2026) showed the original 80-94%
  figure was an artifact of comparing against a chatty non-agentic
  baseline, and that a seven-word prompt nearly matched the skill's
  100-line file. InfoQ covered it; the maintainer walked the number back
  to ~54%, which no third party has reproduced.
- **RTK — REMOVED.** The owner's own `tool-stack-decisions.md` rejected it
  ("do not add to the default stack... no PATH change, global hooks or
  production launcher is adopted"), yet it was found installed and wired
  as a `PreToolUse` hook on every Bash call. Its condensation hid three
  remote branches during this session by collapsing `git branch -a` into a
  summary line, causing a cleanup to be reported complete while the
  branches still existed -- the exact defect class the decision cited. No
  independent evidence for its claims; its own docs disclaim the headline.
- **chisle — already gone.** Installed for about two hours on 2026-09-16,
  judged worthless by the owner in that session, uninstalled. No
  independent evidence found for it either. Its orphaned spill directory
  was removed.
- **caveman — ENABLED, output half only.** Its output-terseness half is
  validated by an independent Adobe Research paper (CAVEWOMAN, arXiv
  2606.24083). The same paper indicates its input/memory-file compression
  half can RAISE net cost, so that half stays inert; it is a separate
  skill that runs only on explicit invocation.
- **Superpowers — kept.** One small independent controlled trial found it
  makes the model more disciplined, not smarter, with real overhead on
  trivial tasks. Thin but genuine evidence, and the only such trial found.
- **No independent evidence found at all** for Headroom, VibeSec, Task
  Observer or Unlazy. None is installed here.
- **The finding underneath all of them:** context rot is independently
  established (Chroma's study across 18 models; Liu et al., TACL 2024 on
  lost-in-the-middle), and system-prompt degradation has a rough measured
  threshold around 2,500-3,000 tokens. No one has published a study on
  whether compression tools recover the overhead of the instructions they
  inject to do the compressing -- which is precisely the number this
  mission's efficiency half requires.

**Environment changes already made on the owner's machine**, so a fresh
session does not rediscover them by surprise: RTK removed (hook, binary,
and the `@RTK.md` import from global `CLAUDE.md`, whose text told every
session its output was condensed); the Ponytail skill deleted; caveman
enabled. Backups at `~/.claude/CLAUDE.md.bak-2026-09-18`,
`~/.claude/settings.json.bak-2026-09-18`, and
`~/.claude/settings.json.bak2-2026-09-18`. `rtk`
remains on the user PATH as a dangling entry, left for the owner.

## D15 — Stages come from D12's map, not the legacy taxonomy · 2026-09-18

**Supersedes D2.** The seven stages
(`design → qa → review → security → delivery → release → operations`)
were ported from the legacy repo's seven roles and never passed the
adoption check the mission's fourth principle requires. D12 then changed
what the product is: a router that sequences adopted components at the
hook boundary plus four things lwb builds itself. A stage list that maps
onto no tool cannot route anything.

So the stage vocabulary is **derived from D12's fifteen SDLC
responsibilities**, each stage named for the responsibility it covers and
carrying the component that covers it. A responsibility with no component
and no gate does not become a stage.

Consequences accepted, and NOT yet carried out — `mission.md` §"Stages"
still names D2's seven, and the rule design and D16's rule text still use
them. Rewriting all three against D15's names is required work, item 8
below. This decision settles the vocabulary; it does not claim the rewrite
has happened. And `operations` stops being a stage with no gate — its
responsibilities
(observability, incident response) carry real components under D12 and are
named for those.

Rejected: keeping the seven and annotating them with tools (two
responsibilities sharing a stage name get gated identically when their
failure modes differ, and `operations` stays ungated); and cutting to the
four gateable stages only (the model stops describing an SDLC and becomes
a list of the places we happen to hold a hook).

## D16 — Independence stays lwb's rule; GitHub's cannot fire here · 2026-09-18

**Settles D3's open flag.** The adoption check was run against the live
repository, not against documentation:

- GitHub ships `require_last_push_approval`, but it is inert unless
  `required_approving_review_count` is at least 1. Ruleset 23627212 has
  that count at **0** and last-push approval **off**.
- Raising the count cannot work with the identities actually in play. PR
  #14's author is `LEAPWare-HQ` and the authenticated approver is
  `LEAPWare-HQ` — one account on both ends. GitHub refuses self-approval,
  so every PR would become unmergeable by the owner alone. That is the
  same defect class as the five gates listed in
  `docs/maintainers/session-handoff-2026-09-18.md`: a check that cannot
  pass.
- The two rules do not measure the same thing in any case. GitHub sees a
  pull request. lwb's rule spans proof records across stages for one
  deliverable, which GitHub cannot observe at any setting.

So lwb keeps its own cross-stage author-independence rule, **warn-only**
per D9, phrased against D15's stage names.

Known limit, restated rather than implied: `reviewer_id` and
`commit_author_id` are self-attested strings that nothing cross-checks
against git authorship or any session registry. These records are an
**audit trail, not proof**. This is the hole D5 flagged and D10 mooted
while the owner is the approver.

The adoption door reopens the moment a second externally verifiable
identity exists — a GitHub App under D6, a second account, or Codex under
D11. At that point `required_approving_review_count: 1` plus
`require_last_push_approval: true` becomes satisfiable and should be
adopted, because it binds independence to an identity GitHub verifies.

Rejected now: creating a GitHub App or second account to satisfy the rule
(reverses D6, and the standing instruction forbids generating a private
key with repo write before there is a decided place to keep it); and
deleting the rule outright (the cross-stage property is still the one the
quality floor names, and nothing else would carry it).

## D17 — Two entrypoints: hooks gate, a runner sequences · 2026-09-18

D12 made lwb a router over adopted components, which the architecture drawn
for the old scope never answered: does lwb *run* a component, or only
*gate* on the evidence one leaves behind? Hooks cannot do the first.
`approach.md` §8 forbids network from a hook; the fail-open argument in
`docs/architecture.md` assumes evaluation is cheap and local; and invoking
Spec Kit or a security scan inside a `PreToolUse` hook would put minutes of
latency in front of every tool call, with a hung MCP server becoming a hung
session.

So lwb has **two entrypoints over one core**:

- **The hook boundary gates.** Unchanged from today: pure core, fail-open,
  no network, no spawning. It reads evidence already on disk and returns
  allow/warn/deny. This is where `proof_required` and
  `no_unauthorised_destructive_action` live (D9).
- **A runner sequences.** A separate entrypoint outside the hook path — a
  command and/or a CI job — may take minutes, call MCP servers and invoke
  skills, driving adopted components in stage order. It has its own latency
  and failure budget and is never in front of a tool call.

`core/lwb_core` stays I/O-free and shared by both. The runner is a second
impure edge alongside the adapters, bounded by the same rule: all I/O at
the edges, none in the core.

Rejected: gate-only with no runner (smallest build and the strongest
fail-open story, but "full SDLC coverage" would shrink to coverage of the
checks while the operator wires the components together by hand); and
hooks that orchestrate (breaks the no-network rule, puts scan-length
latency in front of every tool call, and makes fail-open unreasonable).

**This creates the artifact neither option avoided: an evidence contract.**
Each adopted component must declare what it leaves on disk for lwb to read
— path, shape, and what counts as a pass. Without it the hook has nothing
to gate on and the runner has no way to tell that a stage succeeded. The
contract is also the natural input to D13's trial protocol, since a
component that cannot emit evidence cannot be measured against the quality
floor either.

## D18 — Trial protocol: one arm, recorded baseline, hard cap · 2026-09-18

**Settles D13**, which said prove every adoption but defined no procedure.
The owner's steer was explicit: best in class, but mind the token burn and
the process overhead that causes delay. That rules out the textbook
two-arm A/B, whose cost is paying twice for the same work.

So a trial runs **once**:

- **One arm.** The component is used on one real deliverable. The
  comparison baseline is the token data already recorded in `proof/*.json`
  for comparable work — already paid for, not re-run.
- **Hard cap.** 50,000 tokens and one session per trial, no follow-on
  dispatches. A trial that hits the cap is **abandoned**, and abandonment
  is recorded as a result. It is never extended.
- **Two pass criteria, by class.** A *coverage* component (it does work
  nothing currently does — `security-review`, PagerDuty MCP) passes if it
  produces evidence satisfying a named quality-floor item; its token cost
  is recorded but does not disqualify it. An *efficiency* component (it
  claims the same outcome for fewer tokens — caveman, graphify) passes
  only on a measured token drop past a stated threshold, with the quality
  floor held.
- **Every trial writes a record** with the numbers, so an adoption can be
  re-litigated later against its own evidence. That record is what was
  missing when Ponytail and RTK went in and had to come out (D14).

**Known weakness, stated rather than hidden:** a historical baseline is a
different task than the trial task, so a one-arm comparison is indicative,
not controlled. That is the price of not paying twice, and it is accepted
deliberately.

Rejected: one A/B for everything (a security scanner that finds real
issues fails a token test it was never designed to pass, so the protocol
would systematically reject the coverage half of the mission); and
published-evidence-only with no trial (cheapest, and it did catch
Ponytail, RTK and chisle — but D14's own closing finding is that nobody
has published on the question this mission actually asks, so most
candidates would be undecidable).

### First scheduled trial: graphify

Disposition, decided 2026-09-18: **keep installed, do not use on this
repository, use once on the predecessor repo for required-work item 5, and
treat that use as its D18 trial.**

Not used here because the corpus is small, the work is verification
against live state (`gh api`, running the gate scripts, diffing a claim
against what git says), and a static graph would go stale exactly like the
documents an independent review caught asserting false state this session.
The predecessor repo is the opposite case: large, unfamiliar, unmapped —
where a graph earns its indexing cost if it earns it anywhere.

It is an *efficiency* component under the two-class test. If it does not
show a measured token drop on that assessment, it is not adopted anywhere.

## D19 — Proceed by default; the owner holds a veto · 2026-09-18

**Supersedes D10's approval mechanics.** D10 made the owner the approver
of every shared-path change. In this repository nearly every path is
shared, so that read as "the owner approves every PR, forever" — a
bottleneck by construction. The owner named it as one and chose the fix.

**The CTO acts and records; the owner may reverse anything after the
fact.** No pre-approval is sought for ordinary work: committing, pushing,
opening and closing PRs, merging a PR whose gates and independent review
passed, branch and worktree cleanup, and any reversible change inside this
repository.

**Four classes still escalate, because they have no working undo here:**

1. Money.
2. Licence and legal.
3. The owner's machine settings, security settings especially.
4. Anything that would publish private data to this public repository.

**Risk accepted, recorded because the owner was told it before choosing:**
reversal is not free here. `main` is squash-only and protected, force-push
is denied outright by the machine's own settings, and D8 already accepted
that a public repository cannot un-publish. For several classes of action
the veto is therefore nominal — which is precisely why the four above stay
escalated. Every gate, every CI check and the independent review all keep
running; the change is that they report rather than block on the owner.

Rejected: a standing authority band approved once (the CTO's own
recommendation — it would have doubled as the missing definition of
"authorised" for the `no_unauthorised_destructive_action` rule, which
still needs one); and batching approvals per session (reduces
interruptions but not approvals, and work blocks between batches, so delay
gets worse).

**Consequence still owed:** `no_unauthorised_destructive_action` ships
deny-capable in 1.0 under D9 and has no definition of "authorised". D19
gives the CTO broad authority but does not define the term for a *user* of
the plugin. That definition is required work, item 10.

## D20 — A single session cannot produce an independent reviewer · 2026-09-19

Established by experiment, not by argument, on PR #21 -- the PR that
completes the proof-of-completion protocol.

The lane gate's collision check (D16, hardened in PR #19) refuses a review
record whose `reviewer_id` shares an 8-character-or-longer segment with
`commit_author_id`. On PR #21 it refused, because the only identifier
either reviewer could offer was the authoring session's own token.

**Two reviewers were asked, separately, for a dispatch identifier distinct
from the authoring session's. Both answered that they had none.** Neither
could see a task, run or invocation id for its own execution; the only
identifier in either context was the parent session's. Both were told
explicitly that a blocked PR was preferable to an invented string, and
both declined to construct one, each naming that as the fabrication
`reviews/README.md` already calls this mechanism's known weakness.

So the finding is not "the gate is too strict". It is:

**A session dispatching its own subagents cannot generate an independent
reviewer identity, because none exists to generate.** Earlier records
(PRs 7-13, 19, 20) carry distinct-looking reviewer tokens only because
those particular runs happened to surface an id; nothing about them was
more independent in substance.

Consequences, recorded so they are not relitigated:

- PR #21 cannot satisfy its own review gate in this session. It is
  complete as work and blocked as process. That is the gate doing its job
  against the person who built it.
- Independence in this repo requires a genuinely separate session -- a
  different operator, a different machine, or a peer session with its own
  token. Not a subagent, whatever id it reports.
- `reviewer_was_dispatched_by_author: true` remains the honest disclosure
  for every record this arrangement can produce, and the gate prints it.
- The owner decides whether to merge such work with the
  non-independence recorded, or to obtain a separate reviewer. Both are
  legitimate; silently relabelling an identifier is not, and would take
  ten seconds.

Rejected: lowering `MIN_SHARED_SEGMENT_LENGTH` or exempting a declared
subagent (both convert a true signal into a formality); using an internal
dispatch id the reviewer itself cannot see (it would pass the gate while
the reviewer remains unable to attest to its own identity, which is
exactly the laundering this decision exists to name).

## Required work, not deferred · 2026-09-18

The owner's rule is that nothing is deferred, with Codex (D11) the single
approved exception. The items below are therefore REQUIRED WORK, not
optional backlog. A structured assessment against the owner's predecessor
plan got roughly halfway; the numbered decisions above record what is
settled. These are
what remain, and they are owed.

1. **DONE 2026-09-18 — landed as PR #15**, squash-merged to `d0c1386`,
   verified by diffing the branch tip against the squash commit (empty),
   with `proof/15.json` and `reviews/15/`. It took three PR numbers: #13
   was abandoned for a leaked username in its branch history, #14 for a
   fix commit pushed without its `LWB-Agent:` trailer — unrepairable,
   because the only repair is a history rewrite and this machine denies
   force-push outright. The root cause is now gated at commit time by
   `scripts/githooks/commit-msg`. Both dead branches and
   `lwb-mission-settled` are deleted, local and remote.
2. **DONE 2026-09-18 — roles and stages resolved as D15 and D16.** The
   adoption check was run for both. Stages are rederived from D12's map
   (D15); independence stays lwb's rule because GitHub's cannot fire with
   one account on both ends of a PR (D16). The follow-on work this
   creates -- rewriting `mission.md` and the rule design against D15's
   stage names -- is item 8 below.
3. **DONE 2026-09-18 — architecture resolved as D17.** Hooks gate, a
   separate runner sequences, one I/O-free core under both. The follow-on
   work it creates is item 9.
4. **DONE 2026-09-18 — D13's protocol is D18.** One arm against a
   recorded baseline, 50k-token cap, two pass criteria by component
   class. The predecessor repo's frozen evaluation contract is still
   unassessed for reuse; that falls inside item 5.
5. **The legacy lift was never assessed** -- the acceptance-evidence
   recorder and the provenance/vendor pattern, each needing its own origin
   and licence check before anything lands in this public repo.
6. **No consolidated plan exists.** The original request was to merge the
   best of both repositories into one plan. The mission is merged and the
   decisions are recorded; the sequenced plan is not written.
7. **`owner-directives.md` is still a placeholder.** The numbered
   directives cited throughout this repo do not exist as a set.
   **Method chosen 2026-09-18 under D19, to keep the owner off the
   critical path:** each directive is RECONSTRUCTED from the gate that
   already enforces it — directive 8 from `lwb_check_env_leak.py`, 5 from
   `lwb_lanes.py`, 7 from `lwb_check_proof.py` — with the enforcing code
   path cited on every line. Nothing is invented: each entry is a reading
   of a check that already runs. Any directive cited in prose but enforced
   nowhere is listed separately as **UNSOURCED** for the owner to supply
   or strike, and that list is the only part needing his time. A directive
   that exists only in the owner's head or the predecessor repo will be
   missing until he says so.
8. **Rewrite the stage vocabulary against D15.** `mission.md`, the rule
   design and D16's rule text still use D2's seven legacy stage names.
   Created by D15, which supersedes D2.
9. **Write the evidence contract, and update `docs/architecture.md` for
   the runner.** Per component: what it leaves on disk, in what shape, and
   what counts as a pass. The architecture doc currently describes one
   entrypoint; D17 has two. Created by D17, and a prerequisite for D18's
   trial protocol (item 4) — a component that emits no evidence cannot be
   measured against the quality floor.
10. **Define "authorised" for `no_unauthorised_destructive_action`.** The
    rule ships deny-capable in 1.0 under D9 and has no definition of the
    word it turns on. D19 settles the CTO's authority in this repo; it
    does not tell a plugin user's session what counts as authorised.
    Created by D19. Note the history: an earlier attempt at this
    definition in this session invented a fifth destructive action that
    contradicted the repo's own no-left-behinds rule, which is why this is
    a named deliverable rather than a paragraph written in passing.

### Recommended order for the next session

1. Implement D10 and D11 -- remove the co-approval clause from `AGENTS.md`
   lines 10-11 and from `scripts/lwb_lanes.py`'s module docstring and its
   `SHARED_PREFIXES` comment; make `AGENTS.md` match `CLAUDE.md`; record
   Codex as deferred. Small, already decided, no design needed.
2. Ship the two deny-capable rules from D9 -- `proof_required` and
   `no_unauthorised_destructive_action`. The plugin today registers one
   no-op rule and enforces nothing for anyone; these two make it a product.
3. Build token measurement. Five slots are readable from transcript
   `message.usage`; three have no runtime source. Until this exists the
   mission's efficiency half is decoration.
   Measurable from a session transcript's `message.usage` blocks at
   `~/.claude/projects/<slug>/<session-id>.jsonl`: **total_input**
   (`input_tokens` + both cache fields), **cached_input**
   (`cache_read_input_tokens` + `cache_creation_input_tokens`),
   **uncached_input** (`input_tokens`), **output** (`output_tokens`, with
   an `output_tokens_details.thinking_tokens` sub-split), and
   **wall_time_seconds** (difference between first and last `timestamp`).
   NOT measurable -- no source in any hook payload, transcript or script:
   **retries**, **setup_overhead**, **tool_overhead**. Record those as
   `"unknown"`, never `0`. Two structural limits: usage attaches per model
   turn, never per tool call, so tokens can never be attributed to an
   individual tool call; and subagent transcripts are frequently deleted
   before `SubagentStop` fires, so subagent capture is lossy.
4. Then items 2-7 above.

## D21 — Trial the adoptable components BEFORE writing more rules · 2026-09-19

Owner-decided 2026-09-19, in answer to a direct question.

Principle 4 ("adopt before building") had never been acted on. D12 surveyed
15 SDLC responsibilities and named 8 adoptable components — Spec Kit,
Superpowers, Anthropic's `code-review` and `security-review`, Trail of
Bits, Sentry/Datadog MCP, PagerDuty MCP, Dependabot — and D13 set the
standard each must clear. **Zero had been trialled into the product**, and
no adoption register, pinned version, commit hash or licence record exists
for any of them.

Meanwhile 8 rules sit `PROPOSED` in `mission.md`. The temptation was to
start writing them.

**The decision: run the D13 scoped trials on the surveyed components
first.** Building our own rules before trialling what already exists would
contradict Principle 4 as written, and would risk rebuilding maintained
work. The likely shape of the outcome is that several SDLC responsibilities
get covered by someone else's component, and BuildCraft builds only the
glue plus the gates nobody else provides — but that is an expectation, not
a finding, and the trials decide it.

This is slower to a first visible rule. That is accepted.

**Status: CAPTURED, NOT STARTED.** The owner's instruction was "capture it
but stand by". No trial has been run. Do not begin one without the owner
saying so.

## D22 — 1.0.0 requires driving an SDLC in a REAL repo, not a demo · 2026-09-19

Owner-decided 2026-09-19, same exchange.

The owner's bar for 1.0.0 is that BuildCraft **has driven an SDLC in
another repository**. Asked whether that means a real project or a
purpose-built demo, the answer is a **real LEAPWare repo doing real work**:
`lwb` installed in an actual project, governing real changes end to end,
with stages enforced, gates firing and evidence recorded.

A purpose-built demo repo was explicitly not chosen. The reasoning the
option carried, and which the choice accepts: a demo is a rehearsal we
control, and it cannot surprise us the way real work does.

**Consequence, stated plainly so it is not rediscovered later:** no version
of this plugin is 1.0.0 until that has happened. Everything built to date —
the proof-of-completion layer, the lane fix, `lwb_proof_required` — governs
THIS repository's own contributions or warns in a foreign repo. None of it
has driven an SDLC anywhere.

**A correction belongs in this record.** On 2026-09-19 the author asked the
owner whether to cut 1.0.0, offering options including "publish 1.0.0 now"
and "publish 1.0.0 and arm deny". That question should not have been
asked. It was prompted by a session goal-tracker repeatedly reporting the
version number as unmet, which is not a reason to release. The owner's
reply — "I am unclear why you think we are at a 1.0.0 release level" — was
correct, and the audit that followed found 0 of 15 stages, 0 of 1 roles,
2 of ~10 plugin rules, 0 armed to deny, 2 of 8 working skills, and no
adoption register. See `docs/maintainers/proof-of-completion-plan.md`,
"1.0.0 readiness".

## D23 — The stage vocabulary, finally written down · 2026-09-19

Owner-decided 2026-09-19. **This is the rewrite D15 required and item 8 of
required work.** D15 settled HOW stages are derived; it explicitly did not
claim the derivation had been done, and it had not been — for a day, the
plan named seven stages while labelling them "history, not the
vocabulary".

Derivation rule applied, from D15: each stage is named for the
responsibility it covers and carries the component that covers it; a
responsibility with no component and no gate does not become a stage.

**THIRTEEN STAGES:**

| # | Stage | Component | Provided by |
|---|---|---|---|
| 1 | requirements | GitHub Spec Kit | adopt |
| 2 | architecture | thin — ADR tooling | adopt, owner ruled it IN |
| 3 | implementation | Superpowers | adopt |
| 4 | verification | Anthropic `code-review` | adopt |
| 5 | security | `security-review` + Trail of Bits | adopt |
| 6 | documentation | thin | adopt, owner ruled it IN |
| 7 | build integrity | — | lwb builds |
| 8 | data changes | — | lwb builds |
| 9 | release | — | lwb builds |
| 10 | observability | Datadog / Sentry MCP | adopt |
| 11 | incident response | PagerDuty MCP | **HOLD — no work** |
| 12 | vulnerability handling | Dependabot | adopt |
| 13 | handoff | `claude-mem` CONTESTED | lwb's own gate |

**Owner rulings that changed the derived list:**

- **Retirement / decommissioning is ELIMINATED.** It was one of the four
  responsibilities D12 said lwb must build. It is not a stage.
- **Incident response is HELD.** It stays in the vocabulary; no work is to
  be done on it.
- **Architecture and documentation STAY, and are critical.** The
  derivation rule would have dropped both — thin tooling, no gate — and
  the owner overruled that directly: "Architecture is critical as well as
  docs. must be in." So these two are stages by owner ruling rather than
  by derivation, which is recorded here so no later reader "corrects" the
  list back.

**A CONDITION THE OWNER ATTACHED TO THE WHOLE LIST, to be stated loudly in
the build plan and not buried:** we must absolutely, positively have
double-checked that there are no WORTHY AND VETTED tools or plugins for
each stage before building anything ourselves. This is Principle 4 given
teeth. It applies to all thirteen — including the stages D12 assigned to
lwb to build, because that survey is a year-zero snapshot and the
conclusion "nothing credible exists" is exactly the kind of claim this
repo has learned not to take on trust.

**Two gaps in the source map, found while deriving and NOT invented over:**

1. **D12 claims fifteen responsibilities and names fourteen.** The missing
   one is in the group with credible adoptable components.
2. **D12 claims eight adoptable components and names seven.** Same gap,
   seen from the other side.

The fifteenth responsibility is written down nowhere in this repo. It was
not fabricated to make the count work. Recovering it means re-running the
survey against its original source.

**`operations` is gone**, as D15 intended — a stage with no gate. Its work
is now stages 10 and 11, each named for what it actually does.

**Proof of completion is deliberately NOT a stage.** It is the evidence
layer that runs across all thirteen, which is why it is Phase 1
infrastructure rather than a step in the line — see D24.

## D24 — Acceptance criteria are anchored to GitHub's clock, not ours · 2026-09-19

Owner-decided 2026-09-19. Closes the design gap in quality-floor item 1.

**The floor's FIRST item has never had a mechanical check.** `mission.md`
states it plainly: *"nothing records or timestamps acceptance criteria
before work starts -- so it is verified by the reviewer reading the PR's
own chronology. Closing that is required work, not an accepted gap."*

Why it matters more than the other four floor items: every one of those
grades work AFTER the fact -- tests pass, gates green, evidence recorded.
Only item 1 stops an agent choosing the target after seeing where the
arrow landed. Without it, work can be built and criteria written
afterwards to describe whatever was built, and every downstream check goes
green. It is the cheapest way to fake *done*, and the one we could not
detect.

**Why it was unsolved rather than merely unbuilt.** Every approach that
keeps the evidence inside our own control fails:

| approach | why it fails |
|---|---|
| criteria in a committed file | nothing stops writing it last and committing it first |
| git commit timestamps | settable to any value |
| commit ORDER | history can be rewritten before pushing |
| the agent attests it | same agent doing the work -- self-attestation, the identical weakness that makes `reviewer_id` an audit trail rather than proof (D16) |

The pattern: **any evidence we produce, we can forge.** The proof has to
come from a clock we do not own.

**THE DECISION: work starts with a GitHub issue stating what done means,
and the gate compares GitHub's own creation timestamp against the first
commit of the deliverable.** We cannot forge GitHub's clock. The evidence
is external by construction.

**The cost, accepted explicitly:** this changes how work STARTS, not just
what we check at the end. Every deliverable opens with an issue, every
time, with no exception that can be argued into existence later. A gate
whose precondition is skippable is not a gate -- this repository has
documented eight instances of exactly that failure.

**Not yet designed, and not to be hand-waved when it is:** what counts as
"the first commit of a deliverable" when a branch is merged forward or a
deliverable spans branches; and what happens to work that legitimately
begins before its scope is known. Both need answering before the rule is
written, and neither is answered here.

This lands in Phase 1 as item 1.5. It is the only item in that phase that
changes the owner's process rather than our code, which is why it was the
owner's call and not the CTO's.

## D25 — Efficiency claims are order-of-magnitude only, limits stated every time · 2026-09-19

Owner-decided 2026-09-19.

The mission makes measured efficiency half the goal. The instrument we
have is not fit to adjudicate close calls, and pretending otherwise would
be the same species of false confidence this repository exists to remove.

**What is wrong with the instrument, measured not assumed:**

1. **Not attributable.** The `tokens` block in every proof record is
   CUMULATIVE across PRs 12-27. One figure for sixteen deliverables. The
   record's own `source` field says so.
2. **Excludes every subagent.** This session dispatched roughly 149
   subagent runs; none appears. The records call themselves *"a floor, not
   a total"*, which is honest and means the number is a lower bound of
   unknown tightness.
3. **Three of eight fields are structurally unknowable.** `retries`,
   `setup_overhead`, `tool_overhead` — `proof/schema.json` documents that
   no source exists for them on any current runtime. Not uncollected:
   uncollectable.
4. **Wall time is session duration, not work duration.** It includes every
   minute spent waiting on a reviewer.
5. **Two instruments disagree in units.** The session spend line reports
   weighted tokens; the proof records report raw input. Neither is
   complete and they are not comparable.

**THE DECISION: use measured cost to reject configurations that are
dramatically more expensive, never to choose between close ones. Every
published number states what it excludes.**

This is not a lowering of the bar — the mission already demands *"the
tested frontier and its uncertainty rather than an absolute optimum"*.
D25 makes that operative rather than aspirational.

**What would lift the ceiling, and is not in scope here:** per-deliverable
attribution needs a start boundary, which D24's GitHub issue anchor
supplies as a side effect; subagent capture is lossy by the runtime's
design, already recorded in the decision log; and the three unknowable
fields need the runtime to expose them, which we cannot fix from here.

## D26 — First subjects for driving a real repo · 2026-09-19

Owner-decided 2026-09-19, sequencing D22's real-repo bar.

**SessionKeeper or Pulse first; ShellUX for the real bar, after its v1
release ships.**

Criteria applied: live work flowing, not mid-release, tolerant of a day's
friction, someone actively in it, and — the one that decided it —
**ideally not Python**.

**The assumption most worth breaking:** every gate we have written is
Python, run by Python, checking Python conventions. If BuildCraft only
works in Python repositories we would never discover that by testing on
Python repositories, and five of the six candidates are Python. ShellUX is
TypeScript, which is why it carries the real bar.

**Why not ShellUX first:** it is mid-v1-release. Governing a release with
software that has never governed anything is the worst available first
test — highest stakes, least proven tool. First contact belongs somewhere
a day of friction costs nothing.

**Excluded: Watchtower.** The owner has ruled it will not be there long
term, so it is not a subject.

**Not the bar, but on the path:** installing lwb in BuildCraft itself is
dogfooding and is already required work. It does not answer the
foreign-repo question, so it is a prerequisite rather than the bar.

## D27 — The three decisions that make cloud-only migration possible · 2026-09-19

Owner ordered migration of all BuildCraft work to the cloud on
2026-09-19, approved directly in an inline survey. Three problems stood in
the way. These are the CTO rulings on each, recorded here because they
were issued to a cloud agent mid-run and would otherwise exist only in a
transcript.

### 1. Merging from the cloud — GitHub Actions does the queueing

**The problem, and nobody had noticed it.** BuildCraft merges via the
GraphQL mutation `enqueuePullRequest`: auto-merge is disabled on this
repo and the ruleset requires the merge queue. ShellUX MEASURED that
**GraphQL is blocked by the cloud proxy**. So every merge performed today
would have failed from a cloud routine. The repository's entire merge path
was unusable in the world we are migrating to.

**The ruling:** a GitHub Actions workflow performs the enqueue. It runs
INSIDE GitHub, so no proxy sits between it and the API.

The reason this is right rather than a workaround: **the thing doing the
enqueue should be the thing that can already see the checks.** An outside
caller has to ask; a workflow already knows. It watches for a PR that is
simultaneously all-checks-green and carrying a valid independent review
record, and enqueues that.

The proxy's CCR route may be documented as a FALLBACK, clearly marked
measured or not measured. It is not the primary path.

### 2. Independent review without a second human — the hard one

**The problem.** The gate requires a review whose `reviewer_id` differs
from the commit author and whose `reviewer_was_dispatched_by_author` is
false. Until now that meant another session, run by another person, on
another machine. In a cloud world there is nobody at a keyboard, and a
reviewer spawned by the builder is self-approval with extra steps.

This is not hypothetical: on 2026-09-19 PR #27 sat blocked for an hour
because the only reachable reviewer's session had been paused by its own
owner. Correctness was irrelevant.

**The principle, already settled here and merely applied:** independence
is a property of the REVIEWER'S IDENTITY, not of being a different human.
PR #6 established that when it replaced "one record per CLI vendor" with
distinct reviewer identities. D20 then settled that a single SESSION
cannot produce one.

**The ruling — a reviewer is independent when all three hold:**

1. it was NOT dispatched by the author;
2. it cannot see the author's context or reasoning;
3. it reads only what is on GitHub.

**A cron-scheduled routine satisfies all three. A subagent of the builder
satisfies none.** The clock dispatches it, so
`reviewer_was_dispatched_by_author` is honestly false.

**TWO sources, because one is a single point of failure and today proved
it:**

- **Primary:** a reviewer routine on its own cron schedule, never spawned
  by any conductor.
- **Secondary, cross-repo:** ShellUX's watcher already reviews BuildCraft
  PRs and publishes to its own `reviews/buildcraft` branch. Made
  reciprocal. Different repository, schedule and identity.

**THE STRUCTURAL RULE, and it is the part that matters:** a conductor
routine must be **structurally incapable** of dispatching its own
reviewer. Not a line of prose saying "do not review your own work" — this
repository has documented eight instances of a rule that lived only in
prose being violated, including by the author who wrote it. The reviewer
must be a SEPARATE cron entry with no trigger path from any conductor.

**WHAT THIS DOES NOT BUY, stated so the runbook cannot imply otherwise:**
every reviewer is still the same model on the same account. This is
separation of CONTEXT and DISPATCH. It is not separation of interest. It
is a real improvement on self-review and it is not the same thing as an
adversary.

### 3. "Lane" means two different things — rename the new one

In BuildCraft a **lane is an agent's FILE-OWNERSHIP boundary**
(`plugins/claude/` vs `plugins/codex/`), enforced by `scripts/lwb_lanes.py`
and a PreToolUse hook. That meaning is load-bearing in code and in CI and
does not change.

In ShellUX's runbook a "lane" is a parallel work-stream.

**The ruling:** parallel work-streams in BuildCraft are **TRACKS**. Never
"lane". The runbook carries an explicit note near the top that the two
repositories use the word differently and that anyone porting text between
them must translate — because a future routine will read one document and
act in the other repository, and the collision would be silent.

### HANDOFF.md in-flight detail, trimmed for the byte cap · 2026-09-18

Full detail on the first two in-flight steps, moved here so HANDOFF.md
could stay under its 3000-byte cap without losing the record:

- **Step 1 (DONE).** This repo stands up as the project-neutral SDLC
  scaffold (`lwb`). PR #1 squash-merged, 16/16 green. The repo is
  **PUBLIC** under Apache-2.0: everything committed is world-readable
  permanently, history included.
- **Step 2 (Ruleset DONE; GitHub Apps DEFERRED).** Ruleset `main` (id
  23627212) is active on the default branch: no deletion, no force-push,
  PR required, 9 required checks, squash-only, merge queue. The two Apps
  (`lwb-claude`, `lwb-codex`, manifests in `.github/apps/`) are **not
  created** -- GitHub has no API for App creation, the manifest flow
  needs an authenticated browser session, and no Chrome extension is
  reachable from a CLI session. They block nothing: `gh auth` already
  commits and merges. Do them when a second CLI or a revocable per-CLI
  identity is actually needed. Do NOT generate a private key until there
  is a decided place to put it -- GitHub shows it once and it carries
  repo write.
