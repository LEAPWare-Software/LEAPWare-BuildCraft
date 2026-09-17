# CLAUDE.md — contributor instructions for Claude Code

These are instructions for building this repo, not runtime config. The
lwb plugin itself must never read or depend on this file at runtime.

- Read `HANDOFF.md` first, every session.
- Your lane: `plugins/claude/`, `adapters/claude/`, `tests/**/claude/`.
  Codex's lane (`plugins/codex/`, `adapters/codex/`, `tests/**/codex/`) is
  not yours to edit.
- A shared path (`core/`, `docs/`, `scripts/`, `tests/`, `.github/`,
  `proof/`, `reviews/`, root config) needs independent adversarial CTO
  review before it lands: `REQUIRED_INDEPENDENT_REVIEWS` distinct
  reviewer identities recorded under `reviews/<pr>/`, each with verdict
  AGREE and a `reviewer_id` differing from the commit author. Changed in
  PR #6 from "one record per CLI vendor" — independence is a property of
  the reviewer's identity, not of which CLI brand they run under, and the
  vendor form was unsatisfiable with a single CLI in operation. See
  `reviews/README.md`.
- Every deliverable needs a Proof of Completion: committed, pushed, CI
  green, announced as `LWB - Alert: <id> DONE ...`. See
  `docs/handoff-protocol.md`.
- Worktrees live only under `<repo>/.worktrees/<branch>`. Never create a
  worktree or clone as a sibling folder next to the repo.
