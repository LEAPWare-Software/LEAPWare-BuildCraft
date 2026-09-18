# HANDOFF

The transition only: where `main` is, what landed, what is in flight, the
next step. Session start, re-derive commands, hard rules and traps live in
`docs/handoff-protocol.md` — read that first, every session.

## In flight

In order. Do not start step *n+1* before step *n* is done and proven.

1. **DONE.** SDLC scaffold (`lwb`) up; PR #1 merged, 16/16 green. Repo is
   **PUBLIC** (Apache-2.0). Detail: `docs/requirements/decisions.md`.
2. **DONE; GitHub Apps DEFERRED.** Ruleset `main` (id 23627212) active.
   Apps (`lwb-claude`, `lwb-codex`) not created — no App API, no browser
   session; `gh auth` covers it. Detail: `docs/requirements/decisions.md`.
3. **Mission settled; PR #13 NOT merged.** `docs/requirements/mission.md`
   carries the owner-approved mission: full SDLC coverage at the lowest
   measured token cost that clears a quality floor. Decisions D1-D14 and
   the open-items list are in `docs/requirements/decisions.md` -- READ IT
   FIRST and do not re-decide settled questions.
   **Branch `lwb-mission-final` (pushed) holds the work**, six commits,
   all checks green locally. PR #13 was against the OLD branch
   `lwb-mission-clean`, whose history contains a superseded commit with a
   leaked username; it is closed. The stale remote `lwb-mission-clean` is
   deleted. Land the work from `lwb-mission-final`: open a fresh PR, write
   review and proof records naming the new PR number.
   Environment changed this session: RTK removed (hook, binary, and the
   `@RTK.md` import), Ponytail skill deleted, caveman enabled for output
   compression only. Backup paths: `docs/requirements/decisions.md` (D14).
4. Every deliverable: proof record, pushed, CI green, announced
   `LWB - Alert: <id> DONE ...`.

<!-- lwb-handoff:begin -->

Generated: 2026-09-18 21:56 UTC
main SHA: c33b56059ac99e8d30467bd3ffdd8adcd7886760
CLI: claude
Session: assessment-2026-09-18

Open PRs:
#13 Settle the mission, make its floor testable, bind reviews to commits (lwb-mission-clean)

Deliverable proof state (from proof/):
- traps-no-left-behinds: PROVEN (commit 9463214739b90a6de1ae0b384fdc8ac2b1e6e40c)
- mission-rename: PROVEN (commit 3ae781f12c85da8e133d0138188a65d7e655ea03)
- mission-settled-and-review-binding: PROVEN (commit d3eb1d6a55c00d86e907d6da8eea7e89a5f6e708)
- lwb-gates-enforceable: PROVEN (commit bbb07b950d0f0c37a9edc896d2073aa359cf475f)
- lwb-vision: PROVEN (commit 9df414f6f0ab2a86e3b2c0e1bdd2d42fbf949a59)
- handoff-vision-landed: PROVEN (commit 77896a94967d23d52fb0744d78a2cfdd6e593ee5)

<!-- lwb-handoff:end -->

## Where to look

- Session start, re-derive commands, hard rules, traps →
  `docs/handoff-protocol.md`
- Pure core, adapters, lanes, fail-open layers → `docs/architecture.md`
- Policy file format and mode semantics → `docs/policy.md`
- Full session detail, gates that failed, environment changes →
  `docs/maintainers/session-handoff-2026-09-18.md`
