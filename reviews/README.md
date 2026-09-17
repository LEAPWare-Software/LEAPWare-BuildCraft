# reviews/

Adversarial cross-CLI review records for a shared-path change, per owner
directive 5 and `scripts/lwb_lanes.py`.

## When a review is required

Any commit (with an `LWB-Agent: claude` or `LWB-Agent: codex` trailer,
never `human`) that touches a shared path — `core/`, `scripts/`, `.github/`,
`docs/`, `proof/`, `reviews/`, `tests/`, `HANDOFF.md`, `AGENTS.md`,
`CLAUDE.md`, `README.md` — needs
`scripts/lwb_lanes.REQUIRED_INDEPENDENT_REVIEWS` (currently **1**) distinct
independent reviewers recorded under `reviews/<pr>/`, each in a record with
`"verdict": "AGREE"` and a `reviewer_id` differing from the commit's
`commit_author_id`, before `scripts/lwb_lanes.py` (the `lwb-lanes` CI job)
passes. Bootstrap exception: the PRs named in `BOOTSTRAP_EXEMPT_PRS`.

**Changed in PR #6 — this used to demand BOTH `claude-cto.json` AND
`codex-cto.json`.** That coupled independence to a CLI *vendor* when the
property that matters is a distinct reviewer *identity* — which this file
already said, three paragraphs down ("two different sessions, not the same
one reviewing itself"). It was also unsatisfiable: one CLI operates this
repo, so from PR #6 every shared-path change would have been unmergeable,
and an unsatisfiable gate is worse than a strict one because it gets routed
around. The filename no longer matters; the identities do. Raise
`REQUIRED_INDEPENDENT_REVIEWS` when a second reviewer identity is routinely
available. This is a change in directive 5's *enforcement*, recorded here
and carried into the requirements package as an owner decision.

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

- The **filename does not matter** and `reviewer_agent` is informational.
  This file used to say `reviewer_agent` must match the filename; that check
  was removed in PR #6 along with the per-vendor requirement, and nothing
  loads `schema.json` at all, so its `enum` on `reviewer_agent` is likewise
  unenforced. Only `verdict` and the two identity fields are checked.
- **KNOWN WEAKNESS, flagged by the independent review of PR #6:**
  `reviewer_id` and `commit_author_id` are self-attested strings. Nothing
  cross-checks them against git authorship, the `LWB-Agent:` trailer, or any
  session registry — the only enforcement is literal string inequality. A
  single operator can author a commit and then write a record bearing a
  different invented `reviewer_id`. Binding review identity to something
  externally verifiable is an open owner decision recorded in the
  requirements package; until it is decided, treat these records as an
  audit trail, not as proof.
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
