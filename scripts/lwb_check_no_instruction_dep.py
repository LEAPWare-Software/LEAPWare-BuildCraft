#!/usr/bin/env python3
"""CI check `lwb-no-instruction-dep`: runtime code never names CLAUDE.md or
AGENTS.md.

Owner directive 3: "The plugin must not depend on any CLAUDE.md or
AGENTS.md (local, project, or global). All policy lives in the plugin."
Those files are contributor-only docs (this repo's own `CLAUDE.md` /
`AGENTS.md` at the root tell a human or CLI which lane to work in) — no
hook, adapter, or engine module may read them or even name them, or a
future edit could quietly grow a real dependency.

Scans every `.py` file under `plugins/`, `core/`, and `adapters/` (this
covers both the source trees and each plugin's vendored copy) for the
literal substrings `CLAUDE.md` and `AGENTS.md`. This is a literal string
scan, not an AST check, deliberately: it catches a reference inside a
comment or docstring too, since a doc-only reference in a bin/ script is
still a place a future contributor could turn into a real read.

Usage:
    python scripts/lwb_check_no_instruction_dep.py

Stdlib only. Exits 0 and prints "lwb-no-instruction-dep check passed" on
success; otherwise prints every finding (file:line) and exits 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("plugins", "core", "adapters")
FORBIDDEN = ("CLAUDE.md", "AGENTS.md")


def find_violations() -> list[str]:
    violations: list[str] = []
    for scan_dir in SCAN_DIRS:
        base = REPO_ROOT / scan_dir
        if not base.is_dir():
            continue
        for py_file in sorted(base.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                violations.append(f"{py_file}: could not read ({exc})")
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                for needle in FORBIDDEN:
                    if needle in line:
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{lineno}: references '{needle}'"
                        )
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        for v in violations:
            print(f"FAIL: {v}")
        return 1
    print("lwb-no-instruction-dep check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
