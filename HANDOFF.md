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

1. **DONE: #7-#27, #31, #39.** Decisions: `docs/requirements/decisions.md`
   -- READ FIRST, do not re-decide. Branch tips and PR state are not
   written here; re-derive per `docs/handoff-protocol.md`.
2. **THE CLOUD LOOP IS LIVE (D27).** A conductor routine picks work
   every 2h; a separate reviewer routine writes the gating record
   hourly. D27's rule: separate cron entries, no trigger path
   conductor->reviewer -- PROCEDURAL, not mechanical: #27's own
   reviewer was manually fired by its author's session
   (`reviews/27/dispatch-correction.md`); no gate caught it.
3. **IN FLIGHT: #43** (re-cuts #32, the #27 correction; #32 was
   PERMANENTLY BLOCKED -- unclearable DISAGREE, stale HANDOFF.md, a
   leaked domain, force-push denied -- and superseded). Reviewable
   head `bc6874c` had an independent AGREE; this merge lands a real
   commit after it, so that AGREE is now STALE -- needs a fresh
   review. #29 (runbook) is CLOSED, unmerged, not superseded.
   Re-derive PR/review state per `docs/handoff-protocol.md`.
4. **WHAT BLOCKS 1.0.0.** 0 of 13 stages enforced, 2 rules shipped,
   0 armed to deny, 2 of 8 skills working. **A consuming repo installs
   `lwb` and gets a no-op.** Phase 1 is `lwbpoce`.
5. **DEFECT PATTERN:** "I could not check" must never share a
   representation with "I checked and found nothing". Live in Codex's
   lane. The hook has still never been seen to fire from `hooks.json`.
6. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-24 06:08 UTC
main SHA: e5f29bfaccec90199f983b778c1d7689b8c24d33
CLI: claude
Session: session_01EkvcWAEAV2sJYoN51CPrTF

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
22/22 proven
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
