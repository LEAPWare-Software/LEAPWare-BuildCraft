# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

1. **DONE.** This repo stands up as the project-neutral SDLC scaffold
   (`lwb`). PR #1 squash-merged, 16/16 green. The repo is **PUBLIC** under
   Apache-2.0: everything committed is world-readable permanently, history
   included.
2. **Ruleset DONE; GitHub Apps DEFERRED.** Ruleset `main` (id 23627212) is
   active on the default branch: no deletion, no force-push, PR required,
   9 required checks, squash-only, merge queue. The two Apps
   (`lwb-claude`, `lwb-codex`, manifests in `.github/apps/`) are **not
   created** — GitHub has no API for App creation, the manifest flow needs
   an authenticated browser session, and no Chrome extension is reachable
   from a CLI session. They block nothing: `gh auth` already commits and
   merges. Do them when a second CLI or a revocable per-CLI identity is
   actually needed. Do NOT generate a private key until there is a decided
   place to put it — GitHub shows it once and it carries repo write.
3. **The requirements package** ← NEXT, per
   `docs/requirements/approach.md`, replacing the TODO placeholder in
   `docs/requirements/owner-directives.md`. Eight owner decisions are
   already recorded in **`docs/requirements/decisions.md`** (D1–D8: rule
   families and phasing, stages, role separation, derived stage state,
   identity-based review, Apps deferred, needles as config, history
   accepted) — read that file, do not re-decide them. D5 carries a NAMED
   OPEN DECISION the package must answer: what binds a reviewer identity to
   something externally verifiable. Then the lift from the private legacy
   repo (acceptance checker and its tests, provenance/vendor pattern), each
   piece origin- and licence-checked before it lands.
4. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-17 22:38 UTC
main SHA: 68ac412247c03d109273de33948391581fdbec56
CLI: claude
Session: gates-2026-09-17

Open PRs:
#7 Make directives 5 and 7 actually enforceable (lwb-gates-clean)
#6 Make directive 7 enforceable; decouple directive 5 from CLI vendor (lwb-gates-enforceable)

Deliverable proof state (from proof/):
- lwb-gates-enforceable: PROVEN (commit bbb07b950d0f0c37a9edc896d2073aa359cf475f)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Pure core, adapters, lanes, fail-open layers → `docs/architecture.md`
- Policy file format and mode semantics → `docs/policy.md`
