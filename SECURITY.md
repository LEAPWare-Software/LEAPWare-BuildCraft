# Security Policy

## Reporting a vulnerability

Please report a suspected vulnerability privately via GitHub's
["Report a vulnerability"](https://github.com/LEAPWare-Software/LEAPWare-BuildCraft/security/advisories/new)
flow on this repository (once published), rather than a public issue. If
that is not available yet, open an issue with the security-sensitive
details omitted and a maintainer will follow up privately.

Include, where possible:

- The affected file(s) or plugin (`plugins/claude/lwb` or `plugins/codex/lwb`).
- Whether the issue is in the pure engine (`core/`), an adapter, or a
  plugin's own script.
- Reproduction steps and, if relevant, whether a `deny`-mode rule can be
  bypassed.

## Scope notes

- `core/` and `adapters/` do no I/O and hold no secrets; a report there is
  most likely about a rule's logic (a `deny` that should fire but doesn't,
  or vice versa).
- Both plugins fail OPEN on a broken or missing policy file, by design (see
  `docs/policy.md#fail-open`). That is documented behavior, not itself a
  vulnerability report — but a way to force a policy file into a broken
  state from outside the user's own edits would be.
- Both plugins ship an enforcing `PreToolUse` hook (see
  `docs/install-codex.md` for the Codex plugin's own citation trail).

## Supported versions

Pre-1.0: only the latest tagged release receives fixes.
