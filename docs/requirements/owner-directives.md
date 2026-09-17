# Owner directives — TODO placeholder

This file is a placeholder. It intentionally does not carry any real
project's owner directives: this repo is a generic, project-neutral
scaffold, and the actual requirements-gathering session for BuildCraft's
own real rules (stage checks, role lanes, gates) has not happened yet —
see `HANDOFF.md`'s "In flight" section.

When that session runs, replace this file with the real, numbered,
binding directives it produces, one line each, following the same shape
`docs/requirements/approach.md` describes (evidence before drafting, an
adversarial audit before owner decisions, a freeze only after that).

## Directive numbers already load-bearing in this scaffold

A handful of directive numbers are already cited by scripts, tests, and
docs shipped in this scaffold, because those checks are generic enough to
ship before the real requirements session. Any real directives package
that replaces this file **must** keep these numbers meaning what they
already mean here, or update every citation below in the same change:

- **Directive 3** — the plugin must not depend on `CLAUDE.md` or
  `AGENTS.md` (local, project, or global) at runtime. Cited by
  `scripts/lwb_check_no_instruction_dep.py`,
  `tests/test_no_instruction_file_dependency.py`.
- **Directive 5** — lane discipline: each CLI's own lane is its own to
  edit; a shared path needs adversarial review from both. Cited by
  `scripts/lwb_check_lane_write.py`, `scripts/lwb_lanes.py`,
  `docs/architecture.md`.
- **Directive 7** — Proof of Completion on every deliverable: done means
  committed AND pushed, with a proof record and green CI. Cited by
  `scripts/lwb_check_proof.py`, `proof/README.md`, `proof/schema.json`.
- **Directive 8** — SACRED: this repo's build/test/deploy must not depend
  on, or leak, anything about the machine or private project it was built
  on. Cited by `docs/architecture.md`, `scripts/lwb_check_env_leak.py`.
- **Directive 10** — commit identity is `LEAPWare <leapware@outlook.com>`
  (or an allow-listed bot); no other author belongs in this repo's
  history. Cited by `scripts/lwb_check_commit_identity.py`.

Everything else — what BuildCraft's real stage/role/gate rules are, what
they check, and how they are configured — is undecided and must not be
invented here.
