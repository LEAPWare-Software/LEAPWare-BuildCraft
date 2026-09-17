#!/usr/bin/env python3
"""CI check `lwb-prefix`: every user-facing entrypoint starts with `lwb`.

Checks (stdlib only):
  - Every `skills/<name>/SKILL.md` directory name under `plugins/**` starts
    with `lwb-`, and its front-matter `name:` field matches the directory.
  - Every `command`, `bin/`, or `scripts/` script a user or plugin manifest
    can invoke directly — `plugins/*/*/bin/*.py` and `scripts/*.py` — starts
    with `lwb`, except this script's own module (checked by name) and
    non-entrypoint helpers explicitly allow-listed below.
  - Both plugin manifests' `"name"` field is exactly `lwb`.

Exits 0 and prints "lwb-prefix check passed" on success; otherwise prints
every failure found (not just the first) and exits 1.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files under scripts/ and plugins/*/*/bin/ that are not themselves a
# user-facing entrypoint (helpers, __init__, dunder files) and so are
# exempt from the `lwb` prefix.
_NON_ENTRYPOINT_EXEMPT = {"__init__.py"}


def _check_skills(errors: list[str]) -> None:
    for skill_md in sorted(REPO_ROOT.glob("plugins/*/*/skills/*/SKILL.md")):
        dir_name = skill_md.parent.name
        if not dir_name.startswith("lwb-"):
            errors.append(f"skill directory does not start with 'lwb-': {skill_md.parent}")
            continue
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(\S+)\s*$", text, re.MULTILINE)
        if not m or m.group(1) != dir_name:
            errors.append(
                f"{skill_md}: front-matter 'name:' does not match directory name '{dir_name}'"
            )


def _check_scripts(errors: list[str]) -> None:
    for py in sorted(REPO_ROOT.glob("scripts/*.py")):
        if py.name in _NON_ENTRYPOINT_EXEMPT:
            continue
        if not py.name.startswith("lwb"):
            errors.append(f"scripts/ entrypoint does not start with 'lwb': {py}")

    for py in sorted(REPO_ROOT.glob("plugins/*/*/bin/*.py")):
        if py.name in _NON_ENTRYPOINT_EXEMPT:
            continue
        if not py.name.startswith("lwb"):
            errors.append(f"plugin bin/ entrypoint does not start with 'lwb': {py}")


def _check_manifests(errors: list[str]) -> None:
    for manifest_path in sorted(REPO_ROOT.glob("plugins/*/*/.claude-plugin/plugin.json")) + sorted(
        REPO_ROOT.glob("plugins/*/*/.codex-plugin/plugin.json")
    ):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {manifest_path}: {exc}")
            continue
        if data.get("name") != "lwb":
            errors.append(f"{manifest_path}: plugin id is '{data.get('name')}', want 'lwb'")

    for marketplace_path in (
        REPO_ROOT / ".claude-plugin" / "marketplace.json",
        REPO_ROOT / ".agents" / "plugins" / "marketplace.json",
    ):
        try:
            data = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {marketplace_path}: {exc}")
            continue
        for entry in data.get("plugins", []):
            if isinstance(entry, dict) and entry.get("name") != "lwb":
                errors.append(
                    f"{marketplace_path}: plugin entry id is '{entry.get('name')}', want 'lwb'"
                )


def check() -> list[str]:
    errors: list[str] = []
    _check_skills(errors)
    _check_scripts(errors)
    _check_manifests(errors)
    return errors


def main() -> int:
    errors = check()
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("lwb-prefix check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
