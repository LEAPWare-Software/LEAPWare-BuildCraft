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

## Captured output must be sanitized

Directive 7 wants really-captured command output. Directive 8 (**SACRED**)
forbids this repo carrying anything about the machine it was built on.
Raw output collides with both, and not hypothetically: `lwb_handoff.py`
prints absolute paths, so the first real proof record written here carried
a Windows user-profile path — drive letter, account name and all — into a
public repo, and the `lwb-env-leak` gate rejected it. (This paragraph
cannot show you the offending string: the same gate scans this file, and
rejected an earlier draft of it for quoting one.)

So before a record is written:

- Replace the repo root with `<repo>`, the home directory with `<home>`,
  and any remaining local absolute path with `<path>`, in every `tail`
  line.
- Take `sha256` over the **sanitized** text, so anyone applying the same
  substitutions reproduces the same digest. A hash of unpublishable bytes
  is not verifiable by anyone.
- Say so in `unproven[]`, because a sanitized tail is not verbatim output.

Two things cannot go in `commands[]` at all:

- `lwb_check_proof.py --pr <N>` for the record's own PR — a record cannot
  contain proof of its own existence. Verify it after writing the record.
- Anything printing a private-name needle, for the obvious reason.

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
