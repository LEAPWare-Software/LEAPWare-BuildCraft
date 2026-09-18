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
3. **The requirements package** ← IN PROGRESS, per
   `docs/requirements/approach.md`. Section 1 of 13 is DONE:
   `docs/requirements/mission.md` (owner-approved 2026-09-18) carries the
   mission, principles, non-goals and the EXISTS/PROPOSED inventory.
   Twelve sections remain. Owner decisions D1-D8 are in
   `docs/requirements/decisions.md` — read them, do not re-decide. D5
   holds an OPEN question the package must answer: what binds a reviewer
   identity to something externally verifiable. NOTE:
   `docs/requirements/owner-directives.md` is STILL the TODO placeholder;
   the numbered directives do not exist yet. Then the legacy lift
   (acceptance checker and its tests, provenance/vendor pattern), each
   piece origin- and licence-checked before it lands.
4. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-18 17:36 UTC
main SHA: 9ad59c7fbd9564e215a81e80193feea53bcf7f4e
CLI: claude
Session: handoff-2026-09-18

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
- lwb-gates-enforceable: PROVEN (commit bbb07b950d0f0c37a9edc896d2073aa359cf475f)
- lwb-vision: PROVEN (commit 9df414f6f0ab2a86e3b2c0e1bdd2d42fbf949a59)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Pure core, adapters, lanes, fail-open layers → `docs/architecture.md`
- Policy file format and mode semantics → `docs/policy.md`
