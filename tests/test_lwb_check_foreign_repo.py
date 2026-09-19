"""Tests for scripts/lwb_check_foreign_repo.py.

Runs the script itself as a subprocess (not an in-process import) so this
suite covers the same `lwb-foreign-repo` CI job locally: it drives the
shipped Claude Code hook against a scratch repo outside this checkout and
asserts the whole matrix resolves to `permissionDecision: "allow"`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "lwb_check_foreign_repo.py"


def test_lwb_check_foreign_repo_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"lwb_check_foreign_repo.py failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "lwb-foreign-repo check passed" in result.stdout
