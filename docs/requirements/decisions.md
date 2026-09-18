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
enabled. Backups at `.bak-2026-09-18` and `.bak2-2026-09-18`. `rtk`
remains on the user PATH as a dangling entry, left for the owner.
