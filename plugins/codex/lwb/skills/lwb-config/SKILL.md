---
name: lwb-config
description: Read or edit lwb's gate-policy configuration for this session or project (Codex side; the same policy file the enforcing PreToolUse hook in hooks/hooks.json reads).
---

# lwb-config (Codex)

Identical policy format and file to the Claude Code plugin: see
`core/policy/schema.json` and `core/policy/default.json` in the lwb
repository. This skill reads and edits that same file — it is the file the
Codex plugin's own `hooks/hooks.json` `PreToolUse` hook enforces against.

## Reading the active policy

1. Check `LWB_POLICY_PATH` in the environment; if set, that file is active.
2. Otherwise the vendored `core/policy/default.json` is active.
3. List every configured rule's id and mode plainly.

## Changing a rule's mode

1. Edit only the named rule's `mode` (and `options`, if any).
2. Validate the result against `core/policy/schema.json` before reporting
   the change as live.
3. Remind the user explicitly: a `deny` mode here is enforced immediately
   by `hooks/hooks.json`'s `PreToolUse` hook, the same way it is on the
   Claude Code plugin — see lwb-report to preview a decision without
   waiting for a real dispatch to hit it.
