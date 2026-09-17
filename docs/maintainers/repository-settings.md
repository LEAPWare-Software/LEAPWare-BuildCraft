# Repository settings: rulesets, merge queue, squash-only

This repo is governed by a GitHub repository **ruleset**
(`.github/rulesets/main.json`), not classic branch protection. Rulesets are
the current GitHub mechanism; they are versioned as JSON here so the live
config is diffable and reproducible from any machine, not something only
visible by clicking through repo Settings.

## What `main.json` enforces

- **`target: branch`, `conditions.ref_name: ["~DEFAULT_BRANCH"]`** — applies
  to `main` specifically (the `~DEFAULT_BRANCH` alias tracks the repo's
  default branch even if it's ever renamed).
- **`enforcement: active`, `bypass_actors: []`** — the ruleset is live and
  nobody, no role, no app, bypasses it. If a future change needs a bypass
  actor, that is itself a reviewed change to this file, not a UI toggle.
- **`deletion`** — `main` cannot be deleted.
- **`non_fast_forward`** — no force-push to `main`, ever.
- **`pull_request`** — every change to `main` goes through a PR:
  `required_approving_review_count: 0` (this repo's own review protocol is a
  documented review record — `reviews/<pr-number>/<agent>-cto.json` — not a
  GitHub-approval click, so GitHub's own count stays at zero on purpose),
  `dismiss_stale_reviews_on_push:
  true` (a new push invalidates a stale approval), `allowed_merge_methods:
  ["squash"]` (squash-only: one commit per PR on `main`, no merge commits, no
  rebase-merge).
- **`required_status_checks`** — `strict_required_status_checks_policy: true`
  (the PR branch must be up to date with `main` before merging) and the six
  CI job names from `.github/workflows/ci.yml`'s matrix (`test (<os>,
  <python-version>)` for each of ubuntu/windows/macos-latest × 3.10/3.12).
  If the matrix changes, update both `ci.yml` and this list together — a
  renamed job that isn't in this list can never gate a merge.
- **`merge_queue`** — `merge_method: SQUASH`, `grouping_strategy: ALLGREEN`
  (the queue only merges a batch once every entry in it is green — no
  partial-pass merges), small min/max group sizes (1..5) and a 10-minute
  `check_response_timeout_minutes` so a stuck check doesn't block the queue
  indefinitely. `ci.yml` **must** carry the `on: merge_group:` trigger, or
  CI never runs for queue entries and every queued PR times out.

## Re-applying from any machine

```
gh auth login            # once, if not already authenticated
python scripts/lwb_apply_rulesets.py --dry-run   # inspect the JSON that would be sent
python scripts/lwb_apply_rulesets.py             # create or update by name
```

`apply_rulesets.py` reads every `.github/rulesets/*.json` file, looks up
whether a ruleset with that `name` already exists on the repo, and either
creates it (`POST /repos/{owner}/{repo}/rulesets`) or updates it in place
(`PUT /repos/{owner}/{repo}/rulesets/{id}`). It shells out to `gh api`, so it
carries whatever account `gh` is authenticated as — it needs no token or
secret of its own, and it never touches the CLI's stored credentials.

## Repo-level merge settings (not part of the ruleset)

Squash-only, auto-merge-eligible, delete-branch-on-merge are repository
settings, not ruleset rules:

```
gh api -X PATCH repos/LEAPWare-Software/LEAPWare-BuildCraft \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F allow_auto_merge=true \
  -F delete_branch_on_merge=true \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY
```

## Bootstrap is owner-only

Nothing in this repo — no script, no CI job, no agent — enables auto-merge
on a PR or merges a PR. Applying the ruleset and the repo settings above
only makes squash + merge-queue + auto-merge *available*; turning auto-merge
on for a specific PR, and the first click that exercises the merge queue, is
the owner's own action.
