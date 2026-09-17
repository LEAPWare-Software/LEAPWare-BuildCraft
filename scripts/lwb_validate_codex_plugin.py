#!/usr/bin/env python3
"""Validate plugins/codex/lwb against the shape this project's Codex plugin uses.

Checks (stdlib only):
  - .codex-plugin/plugin.json exists, is valid JSON, has name/version/
    description, and its "hooks" field points at "./hooks/hooks.json".
  - skills/lwb-config/SKILL.md and skills/lwb-report/SKILL.md exist.
  - hooks/hooks.json exists, is valid JSON, and every command (including
    commandWindows) array references ${PLUGIN_ROOT} rather than an
    absolute path — mirrors scripts/lwb_validate_claude_plugin.py's
    ${CLAUDE_PLUGIN_ROOT} check. See docs/install-codex.md for why this
    plugin now ships an enforcing hook rather than reporting-only.
  - bin/lwb_hook.py exists.
  - vendor/lwb_core and vendor/adapters/codex exist (scripts/lwb_build.py has
    been run — this does NOT itself run build.py).
  - .agents/plugins/marketplace.json references this plugin's path.

Exits 0 and prints "validation passed" on success; otherwise prints every
failure found (not just the first) and exits 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "codex" / "lwb"


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

    manifest = _read_json(PLUGIN_DIR / ".codex-plugin" / "plugin.json", errors)
    if isinstance(manifest, dict):
        for field in ("name", "version", "description"):
            if not manifest.get(field):
                errors.append(f"plugin.json missing required field: {field}")
        if manifest.get("hooks") != "./hooks/hooks.json":
            errors.append(
                "plugin.json 'hooks' field must be './hooks/hooks.json' "
                "(this plugin ships an enforcing hook, see docs/install-codex.md)"
            )

    for skill in ("lwb-config", "lwb-report"):
        skill_path = PLUGIN_DIR / "skills" / skill / "SKILL.md"
        if not skill_path.is_file():
            errors.append(f"missing {skill_path}")

    hooks = _read_json(PLUGIN_DIR / "hooks" / "hooks.json", errors)
    if isinstance(hooks, dict):
        hooks_obj = hooks.get("hooks")
        if not isinstance(hooks_obj, dict) or not hooks_obj:
            errors.append("hooks/hooks.json has no 'hooks' object or it is empty")
        else:
            for event_name, entries in hooks_obj.items():
                if not isinstance(entries, list):
                    errors.append(f"hooks/hooks.json: '{event_name}' is not a list")
                    continue
                for entry in entries:
                    for hook in entry.get("hooks", []):
                        commands = [str(hook.get("command", "")), str(hook.get("commandWindows", ""))]
                        if not any("${PLUGIN_ROOT}" in c for c in commands if c):
                            errors.append(
                                f"hooks/hooks.json: a '{event_name}' hook command does not "
                                "reference ${PLUGIN_ROOT}"
                            )

    if not (PLUGIN_DIR / "bin" / "lwb_hook.py").is_file():
        errors.append("missing plugins/codex/lwb/bin/lwb_hook.py")

    vendor_core = PLUGIN_DIR / "vendor" / "lwb_core"
    vendor_adapter = PLUGIN_DIR / "vendor" / "adapters" / "codex"
    if not vendor_core.is_dir():
        errors.append(f"missing {vendor_core} — run scripts/lwb_build.py")
    if not vendor_adapter.is_dir():
        errors.append(f"missing {vendor_adapter} — run scripts/lwb_build.py")

    marketplace = _read_json(REPO_ROOT / ".agents" / "plugins" / "marketplace.json", errors)
    if isinstance(marketplace, dict):
        paths = [
            p.get("source", {}).get("path")
            for p in marketplace.get("plugins", [])
            if isinstance(p, dict) and isinstance(p.get("source"), dict)
        ]
        if "./plugins/codex/lwb" not in paths:
            errors.append(
                "root .agents/plugins/marketplace.json does not list path "
                "'./plugins/codex/lwb'"
            )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("Codex plugin validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
