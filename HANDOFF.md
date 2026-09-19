# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

1. **DONE.** SDLC scaffold (`lwb`) up. Repo is **PUBLIC** (Apache-2.0):
   everything committed is world-readable, history included.
2. **DONE; GitHub Apps DEFERRED.** Ruleset `main` (23627212) active. See
   `docs/requirements/decisions.md` for both.
3. **DONE. Mission landed.** `docs/requirements/mission.md` carries the
   owner-approved mission. The numbered decisions and the open-items list
   are in `docs/requirements/decisions.md` -- READ IT FIRST; do not
   re-decide settled questions. Environment changes this session: D14.
   Branch tips, counts and PR state are NOT written here -- they rot in
   minutes. Re-derive per `docs/handoff-protocol.md`; the block below is
   a timestamped snapshot, not the truth.
4. **IN FLIGHT. Proof of completion made mechanical**, in five small PRs
   -- one big one is what killed #13 and #14. Two adversarial audit
   rounds found 13 blockers; the open ones, the five-PR split and the
   list of what this will NOT cover are in
   `docs/maintainers/proof-of-completion-plan.md`. Read it before
   touching any gate.
5. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 01:17 UTC
main SHA: a65e2ef64fed2dc4ce328b7464b2bc0c9cdb3cad
CLI: claude
Session: goal-1.0.0

Open PRs:
(unavailable: no `gh` auth in this environment, or no open PRs)

Deliverable proof state (from proof/):
- traps-no-left-behinds: PROVEN (commit 9463214739b90a6de1ae0b384fdc8ac2b1e6e40c)
- mission-rename: PROVEN (commit 3ae781f12c85da8e133d0138188a65d7e655ea03)
- mission-settled-and-review-binding: PROVEN (commit d3eb1d6a55c00d86e907d6da8eea7e89a5f6e708)
- mission-stages-architecture-and-trailer-gate: PROVEN (commit 229bd30945241adfa666807cbfe7447f8ef52d78)
- authority-model-trial-protocol-and-claim-directive: PROVEN (commit 23e1c58ccc5af7c1c3bf16cbe04939f498da0998)
- honest-evidence-leak-and-build-integrity: PROVEN (commit 7baafd3012e850add76fce79922e6c1222de23d9)
- lwb-gates-enforceable: PROVEN (commit bbb07b950d0f0c37a9edc896d2073aa359cf475f)
- lwb-vision: PROVEN (commit 9df414f6f0ab2a86e3b2c0e1bdd2d42fbf949a59)
- handoff-vision-landed: PROVEN (commit 77896a94967d23d52fb0744d78a2cfdd6e593ee5)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Architecture, policy format → `docs/architecture.md`, `docs/policy.md`
- Session detail, gates that failed, environment changes →
  `docs/maintainers/session-handoff-2026-09-18.md`
- Proof-of-completion plan, open blockers, what it will NOT cover →
  `docs/maintainers/proof-of-completion-plan.md`
