# Changelog

All notable changes to this project are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial scaffold: `lwb_core` pure engine (`Event` -> `Decision`), the
  `lwb_version` walking-skeleton rule (a safe no-op: allows every event,
  reports the plugin version, never denies — the real SDLC gate rules are
  designed and built in a later session, on top of this same scaffolding),
  the Claude Code adapter and plugin (enforcing `PreToolUse` hook), the Codex
  adapter and plugin (enforcing `PreToolUse` hook — see
  `docs/install-codex.md`), `scripts/lwb_build.py` (vendoring), both
  plugin validators, and the unit / adapter / conformance test suite.
- Codex plugin hook: `plugins/codex/lwb/hooks/hooks.json` +
  `bin/lwb_hook.py`, `adapters/codex/hook_io.render_decision`, superseding
  the earlier reporting-only decision now that the plugin-bundled-hooks
  manifest shape is confirmed documented (`docs/install-codex.md`).
