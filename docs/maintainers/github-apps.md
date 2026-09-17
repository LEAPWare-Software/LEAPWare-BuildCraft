# GitHub Apps: lwb-claude, lwb-codex

Two least-privilege GitHub Apps give each CLI its own committing/merging
identity in this repo, instead of either CLI acting as a human account or
a shared PAT. **This document does not create either App** — App creation
is a click-through, owner-only action; the manifests here only pin down
exactly what gets clicked.

## Why two Apps, not one

`lwb-claude` is Claude Code's identity, `lwb-codex` is Codex's. Separate
identities mean a compromised or misbehaving credential for one CLI is
revocable (delete/reinstall that one App) without touching the other, and
commit/PR authorship in `git log` and the GitHub UI tells the two apart.

## Permissions (both Apps, identical, least privilege)

| Permission | Level | Why |
|---|---|---|
| Contents | Read & write | Push branches, read files |
| Pull requests | Read & write | Open/update PRs, read PR state |
| Checks | Read | Read CI status (never write a check run) |
| Metadata | Read | Required baseline for any App |

No other repository permission, and **no organization permission** — these
Apps operate on `LEAPWare-Software/LEAPWare-BuildCraft` only, nothing
org-wide. Webhook is **inactive** (`hook_attributes.active: false`): these
Apps are used for API calls (`gh api` / REST) made by a CLI session, not for
receiving events.

## Creating an App from its manifest (owner-only, click-through)

GitHub's [App manifest flow](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest)
takes a manifest JSON and turns it into a real App with almost no
form-filling:

1. Go to the org's App creation-from-manifest page:
   `https://github.com/organizations/LEAPWare-Software/settings/apps/new`
   (or, for a personal-account App instead of an org App, the equivalent
   user settings page).
2. On that page there is a form that POSTs a manifest to GitHub; use the
   contents of `.github/apps/lwb-claude.json` (or `lwb-codex.json`) as the
   manifest body — GitHub's own manifest flow expects it submitted via a
   small auto-submitting HTML form or the `gh api` App-manifest conversion
   endpoint, not pasted directly into the App settings UI field-by-field.
   The simplest path is: create a blank App by hand with the *same name,
   description and permissions* as the manifest, since manifest-flow
   automation is unnecessary for a one-time setup with only 4 permissions.
3. After creation, GitHub shows the App's **private key** exactly once —
   download it immediately. It is not recoverable afterward; a lost key
   means generating a new one (the old one still works until revoked).
4. Install the App on `LEAPWare-Software/LEAPWare-BuildCraft` only (not
   "all repositories").
5. Note the **App ID** and **Installation ID** — both are needed alongside
   the private key to authenticate as the App (e.g. via `gh auth` App-token
   exchange, or a client library that mints an installation access token).

## Where the private key lives (never the repo)

The private key is a secret with repo write + PR write access — treat it
like a deploy credential, not a config value:

- Store it in **a secrets manager** (the org's existing secret store —
  whatever LEAPWare already uses for Alpaca/broker credentials is the right
  place, not a new one-off). Never commit it, never put it in `.env` even
  locally, never paste it into a chat transcript.
- Each laptop that needs to act as `lwb-claude` or `lwb-codex` pulls the key
  from that secrets manager at session start (or has it injected as an
  environment variable by the shell profile, itself sourced from the
  secrets manager) — it is never written to disk inside either repo
  checkout.
- If a key is ever exposed (committed, logged, pasted somewhere public),
  revoke it immediately from the App's settings page and generate a
  replacement; revocation is instant and does not require deleting the App.

## What these Apps do NOT do

Neither App's permission set includes anything that lets it change repo
settings, rulesets, or branch protection, delete the repo, or act outside
this one repository. Merging a PR is possible with `pull_requests: write`
in principle, but per this repo's own operating rules (see
`docs/maintainers/repository-settings.md`), no agent — under its own
identity or an App's — enables auto-merge or merges a PR; that stays an
owner action regardless of which credential technically could.
