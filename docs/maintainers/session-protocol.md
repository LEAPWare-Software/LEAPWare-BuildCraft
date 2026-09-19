# Session protocol

How work is actually done in this repo, learned the hard way. `HANDOFF.md`
says where things stand; `docs/requirements/decisions.md` says what was
decided; this says how to operate.

## Landing a change

Every shared-path change goes: branch -> commit -> push -> PR ->
independent review -> proof and review records -> merge queue -> branch
cleanup. `main` is protected by ruleset 23627212: no deletion, no
force-push, PR required, 9 required checks, squash-only, merge queue.

**Enable the hooks first, in every fresh clone:**

```
git config core.hooksPath scripts/githooks
```

That one setting enables both hooks in `scripts/githooks/`:

- `commit-msg` rejects a commit with no `LWB-Agent:` trailer.
- `pre-commit` refuses to commit graphify build artifacts — its graph,
  JSON, report, vault or cache — which embed absolute paths carrying the
  operator's username, into this PUBLIC repo. It checks what is STAGED,
  so `git add -f` does not get past it either. It checks paths, never
  needles: a needle scan needs `LWB_PRIVATE_NEEDLES`, which is a CI
  secret absent from an ordinary shell, so it would fail UNCONFIGURED on
  every commit and be switched off within a day.

On the trailer specifically: Without it the trailer
is caught only by `lwb-lanes` in CI, after the commit is pushed — and the
only repair then is a history rewrite, which this machine's permission
settings deny outright (`Bash(git push* --force*)` is on the global deny
list, with no prompt to approve). One missing trailer therefore costs a
whole branch rebuild. It already has: PR #14 was rebuilt as PR #15 for
exactly this, after PR #13 was rebuilt as PR #14 for a leaked name.

The same constraint is why a commit here is never amended after it is
pushed. Fix forward, or rebuild the branch from `origin/main`.

**Merging.** Repo-level auto-merge is DISABLED and a merge queue is
ACTIVE, so `gh pr merge --squash` fails with "Auto merge is not allowed
for this repository". Do not enable auto-merge; do not change any repo
setting. Enqueue through GraphQL instead:

```
PRID=$(gh api graphql -f query='query{repository(owner:"LEAPWare-Software",name:"LEAPWare-BuildCraft"){pullRequest(number:N){id}}}' --jq '.data.repository.pullRequest.id')
gh api graphql -f query="mutation{enqueuePullRequest(input:{pullRequestId:\"$PRID\"}){mergeQueueEntry{position state}}}"
```

Then poll `gh pr view N --json state,mergeCommit` until MERGED.

## Writing a proof record

Generate it from really-run commands with a throwaway script OUTSIDE the
repo; never hand-write an exit code or a hash. Delete the script after.

- **Sanitise before hashing.** Replace the repo root with `<repo>`, the
  home directory with `<home>`, and any remaining absolute path with
  `<path>` -- then take `sha256` over the SANITISED text so the digest is
  reproducible. This is not optional: this repo is public, several checks
  print absolute paths, and a verbatim tail leaks a user-profile path.
  **Sanitise every field you write, not just captured output.** A record
  was rejected for putting a transcript path into `tokens.source` while
  its command tails were clean.
- **Never include `lwb_check_proof.py --pr N` for the record's own PR** --
  a record cannot contain proof of its own existence. Verify it after.
- Keys are exactly `argv`, `exit`, `expect_exit`, `tail`, `sha256`. A
  record using `cmd`/`exit_code` was rejected.
- Records for PR 12 onward also need `acceptance_criteria` and `tokens`.
  A field with no measurable source is `"unknown"`, never `0`.
- `unproven[]` is where the record says what it does NOT establish. Use it
  honestly; it is the most valuable part.

## Before writing any status

Run `python scripts/lwb_check_state_claims.py --repo .` before writing a
status update, a handoff, or any other claim about branch tips, commit
counts, or open PRs into a tracked `.md` file. It catches a document
hand-asserting volatile git/PR state instead of citing a live command --
see the script's own module docstring for exactly what it can and cannot
catch (it makes DOCUMENTS honest, not things said aloud to the owner).

## Review discipline

An independent reviewer is a separate session, briefed only on the
requirement and the diff. **Keep every DISAGREE round in the review
record** rather than only the final AGREE -- the rounds are where the
value is. `reviewed_commit` binds a record to the commit it examined; a
record naming an older substantive commit is STALE and rejected.
Record-only commits, touching nothing outside `reviews/` and `proof/`, are
skipped when computing the head, so the process terminates.

## Traps that have actually bitten

- A squash-merged branch needs `git branch -D`; `-d` refuses it because
  its commits are not ancestors of `main`, and that refusal is NOT
  evidence of unlanded work.
- To check whether a branch landed, diff its tip against the squash commit
  it produced -- never against current `main`, which has moved on.
- `git branch -a` output can be condensed by tooling into a summary line
  that hides remote refs. Use
  `git for-each-ref --format='%(refname)' refs/heads refs/remotes` for any
  state that gates a decision.
- CI cannot see stale local branches, stashes or untracked files: it runs
  on a fresh checkout. That debris is only catchable at a session boundary.
- A force-push may be refused by the permission layer even when the owner
  has authorised it. Do not retry; move the work to a fresh branch instead.

## Five gates that could not do their job

Written in good faith, all looked correct, all found by review or by the
gates themselves. Assume a sixth exists.

1. `--coverage` ran at PR time looking for a squash subject GitHub only
   creates at merge time. It could never fire.
2. The shared-path review rule demanded a record from a CLI vendor nobody
   runs. It could never be satisfied.
3. The proof gate accepted a digit-string `deliverable` as a PR alias, so
   a record for step 6 of an unrelated plan satisfied PR #6.
4. `reviewed_commit` required a match with the head, but committing the
   record moved the head. It could never pass.
5. The env-leak check shipped a placeholder needle, so directive 8 --
   marked SACRED -- enforced its path half and no-opped its name half.

The lesson each time: a check that passes without checking looks exactly
like a check that works.
