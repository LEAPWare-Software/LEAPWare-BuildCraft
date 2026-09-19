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
3. **DONE. Mission landed.** Decisions and open items:
   `docs/requirements/decisions.md` -- READ IT FIRST, do not re-decide.
   Branch tips, counts and PR state are NOT written here; they rot in
   minutes. Re-derive per `docs/handoff-protocol.md`.
4. **Proof of completion: five PRs landed (#17-#21).** Digests are
   re-executed and compared in CI, report-only. Read
   `docs/maintainers/proof-of-completion-plan.md` before touching a gate.
5. **IN FLIGHT: PR #22**, the state-claim gate. It is the ONLY red step on
   `main`, on all six runners, since #18. Its first fix made the gate pass
   on garbage; an independent reviewer returned DISAGREE, then AGREE after
   the rewrite. D20 is SUPERSEDED IN PRACTICE: two genuinely independent
   reviews now exist (`reviews/21/`, `reviews/22/`), both from a separate
   peer session. Do NOT relabel an identifier to manufacture a third.
6. **AT SESSION START, before anything: verify the shipped hook fires.**
   `hooks.json` uses `"matcher": "Agent"`, never confirmed against a live
   tool name. Register a marker hook, START A NEW SESSION, dispatch a
   subagent, check the marker; repeat for `"Task"`. A mid-session edit is
   never read -- measured. If neither fires, the only hook this product
   ships has never run.
7. **Then:** make re-execution blocking (only after a Linux runner shows
   digests reproducing); close the fork gap (no secrets on a fork, so no
   outside PR can go green while `CONTRIBUTING.md` says otherwise);
   install the plugin in this repo.
8. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-19 06:48 UTC
main SHA: 539ee659ce3473f5a8f7af6e30074b90e2ccd73c
CLI: claude
Session: goal-1.0.0

Open PRs:
#22 The state-claim gate could never pass after a merge — main has been red for four merges (lwb-postmerge-gate)

Deliverable proof state (from proof/):
14/14 proven
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
