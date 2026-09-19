# proof/

Owner directive 7: **Proof of Completion on every deliverable; done =
committed AND pushed with a proof record and green CI; every proven
delivery is announced as `LWB - Alert:`.**

## What goes here

One `proof/<deliverable-id>.json` per deliverable, validated against
`schema.json` by `scripts/lwb_check_proof.py` (the `lwb-proof` CI job).
Nobody hand-writes a record and calls it proof without the commands in it
actually having been run — `checked_by` must be a different identity than
`author` precisely so a proof record is never self-certified.

This scaffolding session wrote NO proof records — `schema.json`, this
README, and the validator are the mechanism. Every deliverable from here
on writes its own.

## Coverage: the half that was missing until PR #6

`lwb_check_proof.py` originally validated the records that *existed* and
never asked whether one *should* exist. An empty `proof/` printed
"skipped (no records yet)" and exited 0, so the gate could not fail — and
five deliverables (PRs #1–#5) merged green straight through a rule this
repo calls load-bearing.

It is checked at **two** moments, because the two identifiers exist at
different times:

- **Pre-merge, blocking** — `--pr <N>` (`lwb-proof-pr`, on `pull_request`)
  requires a record with `"pr": <N>`. The PR number exists; the
  squash-merge commit does not.
- **Post-merge, detective** — `--coverage <base>..<head>`
  (`lwb-proof-coverage`, on push to `main`) requires every squash-merge in
  the range, identified by GitHub's trailing `(#N)` subject, to have a
  record.

The first version ran `--coverage` over `base..head` on `pull_request` and
was a guaranteed no-op: GitHub fabricates the `(#N)` commit **at merge
time**, so a PR's own commits never carry that subject. It would have
merged green and reported success forever. Independent review caught it.

**Both gates key exclusively on the typed `pr` integer.** A record is
written *inside* the PR it proves, so it can never name the squash sha —
which is why `commit` alone is not enough. And a fallback onto a
digit-string `deliverable` was removed as unsound: a `deliverable` is
normally an issue or step number, so a record for step 6 of an unrelated
plan silently satisfied PR #6's gate. Do not reintroduce it.

`exempt.json` names the five historical merges, each with a reason, rather
than back-filling invented evidence — a receipt written after the fact from
memory, for work whose output was never captured, is exactly the dishonesty
a proof record exists to prevent. A test asserts every exempt sha is a real
commit in this repo's history, so the list cannot be used to excuse a
future merge. **Adding an entry is not a substitute for writing a record.**

## Record shape

See `schema.json` for the enforced shape. In prose:

- `deliverable` — the deliverable's id.
- `author` — who did the work (a specific identity, not just `"claude"`).
- `checked_by` — who independently checked it; **must differ from `author`**.
- `commit` — the commit SHA this record proves.
- `commands[]` — every command run as proof, each with:
  - `argv` — the exact argv (not a shell string).
  - `exit` / `expect_exit` — actual vs. expected exit code.
  - `tail` — at most the last 10 lines of output.
  - `sha256` — a hash of the FULL captured output (stdout+stderr
    concatenated), not just the tail, so a truncated tail can never
    quietly hide a real failure — the hash is a hex string the validator
    checks looks like sha256 output; it does not itself re-run the
    command (this repo does not keep the full output blob around), so the
    honesty burden here is on whoever writes the record.
- `mutations[]` — every file this deliverable's work created or changed.
- `unproven[]` — anything claimed as part of this deliverable that this
  record does NOT prove. An empty list is a claim of total proof; use it
  honestly.

## Records 7-19 predate the sanitiser scheme

`docs/maintainers/session-protocol.md` used to tell every session to
hand-write a throwaway sanitiser script and delete it after. No two
sessions wrote the same rules -- records 7-13 replaced `<repo>`, `<home>`
and `<path>`; 15-19 replaced only `<repo>` and `<home>` -- and neither
script was ever committed, so **no digest in `proof/7.json` through
`proof/19.json` is independently reproducible by anyone, including the
record's own author.** This is stated here rather than fixed by
backfilling: a digest computed after the fact, from a rule set nobody can
prove ran at the time, would be a fabricated receipt -- exactly the
dishonesty a proof record exists to prevent.

From PR #20 onward, `scripts/lwb_sanitise.py` is committed, versioned code
(`SANITISER_VERSION`), and `scripts/lwb_record.py` -- the committed
recorder, replacing the throwaway script -- calls it and stamps the
version on every `commands[]` entry. See
`docs/maintainers/proof-of-completion-plan.md`, open blocker 1, and
`docs/maintainers/session-protocol.md`'s "Writing a proof record".

## Verifiability: `verifiable`, `verifiable_reason`, resolved shas

Not every command a proof record runs can be re-executed by CI on a fresh
checkout and digest-matched -- `pytest`'s output carries a wall clock and a
progress bar width, and `origin/main..HEAD` means something different by
the time CI checks it out. Pretending otherwise is the failure mode this
scheme exists to close, so records from PR #20 onward say so explicitly,
per command:

- `verifiable: true|false`. When `false`, `verifiable_reason` is required
  from a CLOSED enum: `nondeterministic-output`, `git-range-not-reproducible`,
  `needs-repo-secret`, `needs-build-step`. Free text is rejected -- a
  reason a validator cannot check is not a check.
- `resolved_base` / `resolved_head` are required on any command whose
  argv names a git revision range (a single `a..b` token, or separate
  `--base`/`--head` flags): the actual shas it ran against. Without them,
  CI re-running the symbolic argv resolves a different commit than the
  one the record proves.
- `sanitiser_version` names the `lwb_sanitise.SANITISER_VERSION` that
  produced this entry's digest.

**Say the measured split, never "falsifiable."** `scripts/lwb_record.py`'s
`summarise_verifiability()` derives "N of M commands are independently
re-executable" from a record's own `commands[]`. Use that sentence, with
the actual number, anywhere a human reads about this scheme -- never a
claim that records are falsifiable outright; they are falsifiable for the
commands marked `true`, and openly not for the rest.

## Captured output must be sanitized

Directive 7 wants really-captured command output. Directive 8 (**SACRED**)
forbids this repo carrying anything about the machine it was built on.
Raw output collides with both, and not hypothetically: `lwb_handoff.py`
prints absolute paths, so the first real proof record written here carried
a Windows user-profile path — drive letter, account name and all — into a
public repo, and the `lwb-env-leak` gate rejected it. (This paragraph
cannot show you the offending string: the same gate scans this file, and
rejected an earlier draft of it for quoting one.)

So before a record is written, `scripts/lwb_record.py` calls
`scripts/lwb_sanitise.py` on every command's captured output: the repo
root becomes `<repo>`, the home directory becomes `<home>`, and any
remaining local absolute path becomes `<path>`, before either `tail` or
`sha256` is computed. Anyone applying the same committed rules reproduces
the same digest -- a hash of unpublishable bytes is not verifiable by
anyone. Still true for any field you write by hand rather than through the
recorder: sanitize it the same way, and say so in `unproven[]`, because a
sanitized tail is not verbatim output.

Two things cannot go in `commands[]` at all:

- `lwb_check_proof.py --pr <N>` for the record's own PR — a record cannot
  contain proof of its own existence. Verify it after writing the record.
- Anything printing a private-name needle, for the obvious reason.

## Acceptance criteria and token cost (PR #12 onward)

Two fields tie the record to the mission's quality floor and efficiency
section, and both are enforced only for records whose typed `pr` is `>=
12`:

- `acceptance_criteria` -- a non-empty list of `{criterion, met}`. What
  "done" meant for this deliverable, agreed before the work started
  (floor item 1). Any `met: false` fails the record: an unmet criterion
  means the floor was not cleared, not a footnote.
- `tokens` -- an object carrying `total_input`, `cached_input`,
  `uncached_input`, `output`, `retries`, `setup_overhead`,
  `tool_overhead`, `wall_time_seconds`, and `source`. Each numeric field
  is a number or the exact string `"unknown"` -- **never zero for a
  field that was not actually measured**; `total_input` or `output`
  recorded as `0` is a hard failure, because that is exactly how an
  efficiency claim gets manufactured. Instruction-length proxies are not
  billed tokens. `total_input`, `cached_input`, `uncached_input`,
  `output` and `wall_time_seconds` are measurable from a session
  transcript's `message.usage` blocks; `retries`, `setup_overhead` and
  `tool_overhead` have no source on any current runtime and are always
  `"unknown"`. Usage attaches per model turn, not per tool call, so
  tokens can never be attributed to a single tool call, and subagent
  transcripts are often deleted before their cost is captured, so a
  missing subagent cost is `"unknown"`, not zero. See `schema.json` for
  the full field-by-field derivation.

Records from PR #11 and earlier (`proof/7.json` through `proof/11.json`)
predate both fields and are **not** backfilled with them: retro-fitting
measurements or criteria that were never taken, after the fact, would
falsify the very records this gate exists to keep honest. They keep
passing `lwb_check_proof.py` exactly as they always have.

## Validating

```
python scripts/lwb_check_proof.py
```

Validates every `proof/*.json` file against `schema.json`, plus the
structural checks a JSON Schema alone cannot express (`checked_by !=
author`, `exit == expect_exit` for every command). Exits 0 and prints
`lwb-proof check passed` when every record is clean, or a distinct
skipped-message when `proof/` has no records yet — an empty `proof/` is
not itself a failure (nothing to prove yet is not the same as a broken
proof record).
