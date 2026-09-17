---
name: lwb-report
description: Summarize lwb's decision ledger for this session (what was allowed, warned, or denied, and why). Use when the user asks "what has lwb blocked", "show the spend policy log", or similar.
---

# lwb-report

lwb appends one JSON line per evaluated hook event to a ledger file (see
`lwb_core/ledger.py` for the record shape: timestamp, hook_event,
tool_name, permit, deny_reason, warnings, findings).

## Locating the ledger

1. Check `LWB_LEDGER_PATH` in the environment; if set, that file is the
   ledger.
2. Otherwise check `CLAUDE_PLUGIN_DATA` and look for `ledger.jsonl` under it.
3. Otherwise report that no ledger has been written yet — do not guess a path.

## Reporting

- Read the ledger as newline-delimited JSON; a malformed line is skipped and
  noted, not treated as fatal.
- Group by `permit` (denied vs. allowed) and by `rule_id` inside `findings`.
- For each denial, quote `deny_reason` verbatim — do not paraphrase why a
  dispatch was blocked.
- State the total line count read, so a partial read is never presented as
  the whole history.
