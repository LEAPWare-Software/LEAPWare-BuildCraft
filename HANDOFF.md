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
3. **The requirements package**, per `docs/requirements/approach.md`,
   replacing the TODO placeholder in
   `docs/requirements/owner-directives.md`. Owner decisions recorded: all
   three rule families (stage, role, proof) ship in 1.0 **warn-only**, deny
   modes from 1.1 on ledger evidence; stages are `design → qa → review →
   security → delivery → release → operations`; role separation is
   reviewer-independence only (a `qa`/`review`/`security` author may not
   have authored an earlier stage of the same deliverable), and policy may
   tighten it, never loosen it; stage state derives from `proof/*.json`
   plus one added `stage` field — no new state store, no network in a hook.
   Then the lift from the private legacy repo (acceptance checker and its
   tests, provenance/vendor pattern), each piece origin- and
   licence-checked before it lands.
4. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-17 22:14 UTC
main SHA: 68ac412247c03d109273de33948391581fdbec56
CLI: claude
Session: gates-2026-09-17

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
(none yet)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Pure core, adapters, lanes, fail-open layers → `docs/architecture.md`
- Policy file format and mode semantics → `docs/policy.md`
