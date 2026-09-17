#!/usr/bin/env python3
"""Validate plugins/claude/lwb against the shape Claude Code plugins require.

Checks (stdlib only):
  - .claude-plugin/plugin.json exists, is valid JSON, has name/version/description.
  - hooks/hooks.json exists, is valid JSON, and every command array references
    ${CLAUDE_PLUGIN_ROOT} rather than an absolute path.
  - bin/lwb_hook.py exists.
  - vendor/lwb_core and vendor/adapters/claude exist (i.e. scripts/lwb_build.py
    has been run — this does NOT itself run build.py).
  - Root .claude-plugin/marketplace.json references this plugin's source path.

Exits 0 and prints "validation passed" on success; otherwise prints every
failure found (not just the first) and exits 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "claude" / "lwb"


def _read_json(path: Path, errors: list[str]):
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return None


def validate() -> list[str]:
    errors: list[str] = []

    manifest = _read_json(PLUGIN_DIR / ".claude-plugin" / "plugin.json", errors)
    if isinstance(manifest, dict):
        for field in ("name", "version", "description", "license"):
            if not manifest.get(field):
                errors.append(f"plugin.json missing required field: {field}")

    hooks = _read_json(PLUGIN_DIR / "hooks" / "hooks.json", errors)
    if isinstance(hooks, dict):
        hooks_obj = hooks.get("hooks")
        if not isinstance(hooks_obj, dict) or not hooks_obj:
            errors.append("hooks.json has no 'hooks' object or it is empty")
        else:
            for event_name, entries in hooks_obj.items():
                if not isinstance(entries, list):
                    errors.append(f"hooks.json: '{event_name}' is not a list")
                    continue
                for entry in entries:
                    for hook in entry.get("hooks", []):
                        args = hook.get("args", [])
                        joined = " ".join([str(hook.get("command", ""))] + [str(a) for a in args])
                        if "${CLAUDE_PLUGIN_ROOT}" not in joined:
                            errors.append(
                                f"hooks.json: a '{event_name}' hook command does not "
                                "reference ${CLAUDE_PLUGIN_ROOT}"
                            )

    if not (PLUGIN_DIR / "bin" / "lwb_hook.py").is_file():
        errors.append("missing plugins/claude/lwb/bin/lwb_hook.py")

    vendor_core = PLUGIN_DIR / "vendor" / "lwb_core"
    vendor_adapter = PLUGIN_DIR / "vendor" / "adapters" / "claude"
    if not vendor_core.is_dir():
        errors.append(f"missing {vendor_core} — run scripts/lwb_build.py")
    if not vendor_adapter.is_dir():
        errors.append(f"missing {vendor_adapter} — run scripts/lwb_build.py")

    marketplace = _read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json", errors)
    if isinstance(marketplace, dict):
        sources = [p.get("source") for p in marketplace.get("plugins", []) if isinstance(p, dict)]
        if "./plugins/claude/lwb" not in sources:
            errors.append(
                "root .claude-plugin/marketplace.json does not list source "
                "'./plugins/claude/lwb'"
            )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("Claude plugin validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
