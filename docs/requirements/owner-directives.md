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

## Directives stated by the owner directly

Not reconstructed from a gate, not inferred from a citation: stated by the
owner in session, quoted, and dated. This is the section the placeholder
above was waiting for, and it starts with one entry rather than none.

### Directive 7a — confirm that what is claimed done is truly done · SACRED · 2026-09-18

> "u must always confirm that what u say is done is truly done. sacred"

An assertion of completion is not completion. Every claim that something
is done must be backed by a command that was actually run and whose output
was actually read — not by memory, not by intention, and not by a
subagent's self-report taken at face value.

This is directive 7 (Proof of Completion) applied to *speech* rather than
to deliverables. Directive 7 already governs what lands in the repo; this
governs what is said to the owner about it, which had no rule at all.

Standing consequences, each traceable to a real failure in the session
that produced this directive:

- **A sha, a count or a size is copied from a command, never typed from
  memory.** A 40-character commit sha was once written into a review
  record from memory; it was wrong, and was caught only because it was
  checked against `git rev-parse` before the commit.
- **A subagent's report of its own work is a claim, not evidence.** An
  extraction agent reported 42 nodes and 53 edges; the file it wrote held
  41 and 61.
- **"Should pass" is not "passes".** A claim that the lane gate would fail
  on exactly one line was made without running it. It failed on four.
- **A document asserting current state is stale the moment it is
  written.** Branch tips, commit counts and open-PR lists are re-derived,
  never quoted from prose.
- **Where a claim cannot be independently checked, say so in the same
  breath.** The env-leak history scan needs `LWB_PRIVATE_NEEDLES`, which
  the independent reviewer does not have, so every proof record carrying
  that result names it as unverified by the reviewer.

Enforcement today is `scripts/lwb_check_proof.py` for deliverables and
nothing at all for statements. Making the second half mechanical is
required work — the honest position is that this directive currently binds
conduct, not code.

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
  edit; a shared path needs independent adversarial review. Cited by
  `scripts/lwb_check_lane_write.py` and `scripts/lwb_lanes.py`.
  `docs/architecture.md` was listed here too and does NOT cite directive 5
  — it cites directive 8 only. Found by an independent audit of this
  file's own claims; a directives file that miscites its own enforcement
  is the first thing a reader would trust and the last thing anyone
  checks.
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
