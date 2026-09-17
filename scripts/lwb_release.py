#!/usr/bin/env python3
"""Build zip release artifacts for both plugins.

Runs `scripts/lwb_build.py` (to refresh vendor/), then both validators, then
zips `plugins/claude/lwb/` and `plugins/codex/lwb/` into
`dist/lwb-claude-<version>.zip` and `dist/lwb-codex-<version>.zip`, where
`<version>` is read from each plugin's own manifest. Refuses to produce an
artifact if a validator fails. Stdlib only.

Usage: python scripts/lwb_release.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"


def _run(args: list[str]) -> int:
    print(f"$ {' '.join(args)}")
    return subprocess.call([sys.executable, *args], cwd=REPO_ROOT)


def _zip_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_file():
                zf.write(path, path.relative_to(src.parent))


def main() -> int:
    if _run(["scripts/lwb_build.py"]) != 0:
        print("build.py failed")
        return 1
    if _run(["scripts/lwb_validate_claude_plugin.py"]) != 0:
        print("Claude plugin validation failed — refusing to release")
        return 1
    if _run(["scripts/lwb_validate_codex_plugin.py"]) != 0:
        print("Codex plugin validation failed — refusing to release")
        return 1

    claude_manifest = json.loads(
        (REPO_ROOT / "plugins" / "claude" / "lwb" / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    codex_manifest = json.loads(
        (REPO_ROOT / "plugins" / "codex" / "lwb" / ".codex-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )

    claude_version = claude_manifest["version"]
    codex_version = codex_manifest["version"]

    _zip_dir(
        REPO_ROOT / "plugins" / "claude" / "lwb",
        DIST_DIR / f"lwb-claude-{claude_version}.zip",
    )
    _zip_dir(
        REPO_ROOT / "plugins" / "codex" / "lwb",
        DIST_DIR / f"lwb-codex-{codex_version}.zip",
    )
    print(f"wrote {DIST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
