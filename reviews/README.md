# reviews/

Adversarial cross-CLI review records for a shared-path change, per owner
directive 5 and `scripts/lwb_lanes.py`.

## When a review is required

Any commit (with an `LWB-Agent: claude` or `LWB-Agent: codex` trailer,
never `human`) that touches a shared path — `core/`, `scripts/`, `.github/`,
`docs/`, `proof/`, `reviews/`, `HANDOFF.md`, `AGENTS.md`, `CLAUDE.md`,
`README.md` — needs BOTH `reviews/<pr>/claude-cto.json` and
`reviews/<pr>/codex-cto.json` present, each with `"verdict": "AGREE"`,
before `scripts/lwb_lanes.py` (the `lwb-lanes` CI job) passes. Bootstrap
exception: enforced only for PR numbers greater than 5 — see
`scripts/lwb_lanes.py`'s module docstring.

## Record shape (see `schema.json`)

```json
{
  "pr": 17,
  "reviewer_agent": "claude",
  "reviewer_id": "claude-cto-session-2026-09-20",
  "commit_author_agent": "codex",
  "commit_author_id": "codex-worker-session-2026-09-19",
  "verdict": "AGREE",
  "notes": "Checked core/lwb_core/rules/new_rule.py against the schema; agrees with the codex worker's read of directive 15."
}
```

- `reviewer_agent` must match the filename (`claude-cto.json` ->
  `"claude"`, `codex-cto.json` -> `"codex"`).
- `reviewer_id` and `commit_author_id` are free-form identity strings (a
  session id, a dispatch id — whatever the CLI in question uses to name a
  specific run) and **must differ from each other**: a reviewer may never
  be the same identity as the commit's own author, even when both happen
  to run under the same CLI brand (e.g. a Claude CTO role reviewing a
  Claude implementer's commit — two different sessions, not the same one
  reviewing itself). `scripts/lwb_lanes.py` enforces this by literal string
  inequality; it is on the reviewer to give the two fields genuinely
  distinct values, not merely different-looking ones.
- `verdict` is `"AGREE"` or `"DISAGREE"`; only `"AGREE"` satisfies the gate.
