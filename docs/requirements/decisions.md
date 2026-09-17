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

## D6 — GitHub Apps deferred · 2026-09-17

`lwb-claude` and `lwb-codex` are not created. GitHub has no App-creation
API and the manifest flow needs an authenticated browser session, which a
CLI session cannot reach. They block nothing: `gh auth` already commits and
merges. Revisit when a second CLI, or a revocable per-CLI identity, is
actually needed.

Standing instruction: do **not** generate an App private key until there is
a decided place to keep it. GitHub shows it once and it carries repo write.

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
