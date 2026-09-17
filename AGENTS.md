# AGENTS.md — contributor instructions for Codex

These are instructions for building this repo, not runtime config. The
lwb plugin itself must never read or depend on this file at runtime.

- Read `HANDOFF.md` first, every session.
- Your lane: `plugins/codex/`, `adapters/codex/`, `tests/**/codex/`.
  Claude's lane (`plugins/claude/`, `adapters/claude/`,
  `tests/**/claude/`) is not yours to edit.
- A shared path (`core/`, `docs/`, root config) needs adversarial review
  by the CIO role on *both* CLIs, in agreement, before it lands.
- Every deliverable needs a Proof of Completion: committed, pushed, CI
  green, announced as `LWB - Alert: <id> DONE ...`. See
  `docs/handoff-protocol.md`.
- Worktrees live only under `<repo>/.worktrees/<branch>`. Never create a
  worktree or clone as a sibling folder next to the repo.
