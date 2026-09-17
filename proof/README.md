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
