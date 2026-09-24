# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

**THE PLAN IS `docs/requirements/build-plan.md`** -- seven phases,
owner-approved 2026-09-19. Read it before starting anything. Session
detail: `docs/maintainers/session-handoff-2026-09-19.md`. Gate traps:
`docs/maintainers/proof-of-completion-plan.md`.

**THE CONDITION ON EVERY PHASE:** absolutely, positively double-check
that no WORTHY AND VETTED tool already does it before building anything.

1. **DONE: #7-#50.** Decisions: `docs/requirements/decisions.md` --
   READ FIRST, do not re-decide. `main` tip #50 (6afc545), green.
   Phase 1.1 (`lwb_proof_coverage`+`lwb_proof_integrity` at `warn`) DONE
   via #50 (re-cut of #49's bad reviewer-B identity, not a
   deliverable bug). Re-derive per `docs/handoff-protocol.md`.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. D27's rule: separate cron entries, no trigger path
   conductor->reviewer -- PROCEDURAL, not mechanical: #27's own
   reviewer was manually fired by its author's session
   (`reviews/27/dispatch-correction.md`); no gate caught it.
3. **IN FLIGHT (track A), Phase 1 continuing:** #51 (1.2), #52/#53
   (1.6, #53 re-cuts #52's bad identity). Also open #45,
   #47/#48, #44, #40. **#46 (this D27 correction) is separate:** main drifted past
   its base again; resolved via a real merge + HANDOFF regeneration,
   moving the reviewable head past the three `reviews/46/` AGREEs --
   stale by design (D20), needs a fresh independent review.
4. **WHAT BLOCKS 1.0.0.** 0/13 stages, 4 rules on `main` (1.1 landed), 0 armed
   to deny, 2/8 skills working.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-24 17:58 UTC
main SHA: 6afc545646faa9b241ffe60ee4c612f50e4437f8
CLI: claude
Session: session_01EkvcWAEAV2sJYoN51CPrTF

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
23/23 proven
(all proven; none outstanding)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Architecture, policy format → `docs/architecture.md`, `docs/policy.md`
- Session detail, gates that failed, environment changes →
  `docs/maintainers/session-handoff-2026-09-18.md`
- Proof-of-completion plan, open blockers, what it will NOT cover →
  `docs/maintainers/proof-of-completion-plan.md`
