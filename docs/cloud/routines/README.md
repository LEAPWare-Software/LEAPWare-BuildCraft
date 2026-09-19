# Routine specifications

Three routines. **None of them is scheduled.** Creating a routine is the
owner's action at claude.ai/code, after an audit. These files are the
specification and the literal prompt text to paste when that happens.

| routine | schedule | may write | dispatches roles |
|---|---|---|---|
| [conductor](conductor.md) | every 2 hours, **one entry per track** | `track-*` branches, pull requests, ledger comments, `needs-owner` issues | yes |
| [watchdog](watchdog.md) | hourly | the ledger issue body's `## Status` section, ledger comments, `needs-owner` issues | no |
| [reviewer](reviewer.md) | hourly, **its own entry** | `reviews/*` branches, pull request comments, ledger comments | yes (`lw-verifier`) |

## The one structural rule

**A conductor cannot dispatch a reviewer.** The reviewer is a separate cron
entry, and a routine has no means of creating or triggering another routine. A
conductor's only way to get a review is to open a pull request and wait for the
clock. See `docs/cloud/runbook.md` section 6.

If a future change makes it possible for a conductor to start a reviewer, the
independence claim in the runbook becomes false and must be withdrawn in the
same change.

## Every prompt carries the same preamble

Each file below repeats the authorization block, the allowed write paths, the
connector prohibition and the owner-command rule **verbatim**. That is
deliberate duplication: a routine refuses unattended writes unless its own
prompt states the authorization, and a routine never reads a file it was not
told to read. A prompt that says "see the runbook" authorizes nothing.

## Prompt hygiene, measured by ShellUX

- **Never embed a PAT in a routine prompt.** The cloud model refuses it.
- **Every dispatch carries a `BUDGET: <n>k` line.**
- **Forbid the account's connectors explicitly.** Routines get Microsoft 365,
  Google Drive and others auto-attached; a prompt that does not forbid them
  invites their use.
- **The prompt must say the session dies at its final answer**, so the routine
  waits for its subagents instead of finishing over the top of them.
