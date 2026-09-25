# Rule: `lwb_no_unauthorised_destructive_action`

**Status:** shipped, report-only. Source:
`core/lwb_core/rules/lwb_no_unauthorised_destructive_action.py`. Default
mode: `warn` (see `core/policy/default.json`).

`docs/requirements/build-plan.md`, Phase 1 item 1.6. This is the plan's
**second deny-capable rule** (D9), alongside `lwb_proof_required`. It
gates the four destructive actions `docs/handoff-protocol.md`'s "## Hard
rules" section names for this repository's own conduct, generalized for a
consuming repo that has no built-in concept of "the owner."

## What it checks

A `PreToolUse` event for the **`Bash`** tool whose command matches one of
four categories:

| Category | Recognized | Not recognized (deliberately) |
|---|---|---|
| `force_push` | `git push --force`/`-f`/`--force-with-lease[=...]` | `git -C <path> push -f`, an env-prefixed push |
| `history_rewrite` | `git rebase`, `git filter-branch`, `git filter-repo`, `git commit --amend`, `git reset --hard` | `git reflog expire && git gc --prune=now`, every other way history can change |
| `delete_ref` | `git push <remote> --delete <ref>` / `-d <ref>`, `git push <remote> :<ref>` | a ref deleted through `gh api`, a **local** `git branch -D` (out of scope — the hard rule is about a *remote* ref) |
| `settings_change` | `gh repo edit`/`gh repo delete`, `gh api` with a mutating method (`-X`/`--method` PATCH/PUT/DELETE/POST) against `repos/<owner>/<repo>`, a `.../rulesets` path, a `.../branches/.../protection` path, or `.../actions/permissions` | any other mutating GitHub API shape |

Quoted spans and heredoc bodies are blanked out first, and `--dry-run`,
`-n`, `--help`, `-h` anywhere in a segment make that segment not count —
the same quote/heredoc/segment-splitting machinery `lwb_proof_required`
uses, reused rather than re-implemented so the two rules can never
disagree about where one shell command ends and the next begins.

## The merge carve-out

A `git merge` or `gh pr merge` command is **never** classified as any of
the four categories, unconditionally, regardless of policy. This mirrors
D19's "merging is ordinary work" verbatim: `docs/handoff-protocol.md`
carves merging out of its own hard rules, and this rule carves it out of
its detection the same way — a squash-merge is not mistaken for a history
rewrite, and `gh pr merge` is not mistaken for a settings change.

## What "authorised" means

`docs/handoff-protocol.md`'s hard rules name **the owner** as the
authority. The shipped plugin has no such concept — `core/lwb_core` does
no I/O and knows nothing about who runs a consuming repo. So this rule
generalizes authorisation the same way every other `core/lwb_core` rule
resolves configuration: **from the consuming repo's own policy file**,
never from anything this rule infers about intent.

```json
{
  "rules": {
    "lwb_no_unauthorised_destructive_action": {
      "mode": "warn",
      "options": {
        "allow": {
          "force_push": false,
          "history_rewrite": false,
          "settings_change": false,
          "delete_ref": false
        },
        "verified_landed_branches": []
      }
    }
  }
}
```

- **`options.allow.<category>: true`** authorises every command in that
  category, unconditionally. The blanket mechanism, shared by all four.
- **`options.verified_landed_branches`** — `delete_ref` only. Names
  branches the *policy author's own process* has already confirmed
  landed (their own tip-vs-squash-commit diff, their own CI job — however
  they do it). Deleting one of these branches remotely is authorised
  without needing the blanket `delete_ref` allow.

### What this rule deliberately does NOT do

`docs/handoff-protocol.md` carves "a branch whose work is verified landed"
out of its own remote-ref-deletion rule as *ordinary cleanup, needing no
owner*. This rule does **not** verify that automatically. Confirming a
branch's tip is really an ancestor of what was squash-merged is
history-ancestry work — a subprocess or a bounded repository walk — that
does not fit `core/lwb_core`'s I/O-free, per-hook-event purity budget (see
`adapters/claude/repo_facts.py`'s "No subprocess, on purpose"). Rather
than invent an approximation and risk false confidence, this rule asks the
policy author to name branches their own process already verified,
through `verified_landed_branches`. Automatic ancestry verification is
genuinely unresolved here; building it would mean teaching an adapter a
new `RepoFacts` field the way `collect_landed_unproven` was built, and
that is not done in this change.

## What it reports

```
unauthorised destructive action: a force-push. docs/handoff-protocol.md's
hard rules require the owner's explicit instruction for this; a consuming
repo authorises it by setting policy options.allow.force_push to true.
See docs/rules/lwb-no-unauthorised-destructive-action.md
```

A `delete_ref` finding also names the target ref, and adds the
`verified_landed_branches` route in its message.

## Modes

| Mode | Behavior |
|---|---|
| `off` | No check runs. |
| `warn` | **Shipped default.** The finding is recorded and the command proceeds. |
| `deny` | The command is blocked. |

Unlike `lwb_version`, this rule uses `config.mode` verbatim — it **is**
armable by policy, per D9. It nevertheless ships at `warn`: this
repository's own discipline of landing a gate report-only first and
arming it in a separate, later change once there is ledger evidence about
what it actually fires on (same as `lwb_proof_required` and the two proof
rules). Arming it to deny is a distinct, later build-plan item, not part
of this change.

## When it says nothing, on purpose

- The command is not one of the four recognized shapes — including every
  merge, unconditionally.
- `event.repo is None` — the adapter gathered no repo facts. Same
  discipline as `lwb_proof_required`: this is what keeps the rule inert
  under an adapter that has not been taught to collect repo facts (today:
  Codex), rather than warning on every destructive command forever.
- `event.repo.facts_incomplete` — the adapter looked and could not fully
  read something. "Could not check" must never look like "checked, found
  nothing."

## Purity

`core/lwb_core` does no I/O. Command classification reads only
`event.tool_input`; authorisation reads only `config.options`.
`event.repo` is consulted only as a presence/completeness gate, exactly as
documented above — no other field of it is read.

## Tests

- `tests/core/test_lwb_no_unauthorised_destructive_action.py` — the rule
  as a pure unit: each of the four categories, the merge carve-out, the
  `verified_landed_branches` carve-out, the general policy-allowlist
  mechanism, `event.repo is None` / `facts_incomplete` silence, and mode
  honouring.
- `tests/core/test_engine_mutation.py` — proves the rule is wired into
  `RULES`, not merely present in the tree.
