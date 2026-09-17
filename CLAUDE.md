# CLAUDE.md — contributor instructions for Claude Code

These are instructions for building this repo, not runtime config. The
lwb plugin itself must never read or depend on this file at runtime.

- Read `HANDOFF.md` first, every session.
- Your lane: `plugins/claude/`, `adapters/claude/`, `tests/**/claude/`.
  Codex's lane (`plugins/codex/`, `adapters/codex/`, `tests/**/codex/`) is
  not yours to edit.
- A shared path (`core/`, `docs/`, root config) needs adversarial review
  by the CTO role on *both* CLIs, in agreement, before it lands.
- Every deliverable needs a Proof of Completion: committed, pushed, CI
  green, announced as `LWB - Alert: <id> DONE ...`. See
  `docs/handoff-protocol.md`.
- Worktrees live only under `<repo>/.worktrees/<branch>`. Never create a
  worktree or clone as a sibling folder next to the repo.
