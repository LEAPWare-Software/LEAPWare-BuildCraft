"""Owner directive 3: the plugin must not depend on CLAUDE.md or AGENTS.md.

Two independent proofs:

1. A static scan (`scripts/lwb_check_no_instruction_dep.py`, also run in CI
   as its own job) finds no reference to either filename in runtime code
   under `plugins/`, `core/`, or `adapters/`.
2. A dynamic proof: both plugins' hook entry points run correctly — same
   PreToolUse allow decision — from a working directory with no CLAUDE.md or
   AGENTS.md anywhere up its ancestor chain. If either hook silently walked
   up looking for one of those files, this would either fail to find a
   real one (harmless on its own) or, if it happened to hit one from an
   unrelated project higher up the real filesystem, behave differently
   between machines — which is exactly the dependency directive 3 forbids.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))
lwb_check_no_instruction_dep = importlib.import_module("lwb_check_no_instruction_dep")

_WARN_POLICY = {
    "$schema": "./schema.json",
    "rules": {"lwb_version": {"mode": "warn", "options": {}}},
}

# (plugin dir under plugins/, fixture path)
HOOK_TARGETS = [
    (
        REPO_ROOT / "plugins" / "claude" / "lwb",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "claude" / "pretooluse_agent_no_budget.json",
    ),
    (
        REPO_ROOT / "plugins" / "codex" / "lwb",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "codex" / "pretooluse_agent_no_budget.json",
    ),
]


def test_scan_finds_no_reference_in_this_checkout():
    assert lwb_check_no_instruction_dep.find_violations() == []


def test_scan_catches_a_planted_reference(tmp_path):
    scan_root = tmp_path / "plugins"
    scan_root.mkdir()
    planted = scan_root / "leaky.py"
    planted.write_text('"""Reads CLAUDE.md for policy."""\n', encoding="utf-8")

    original_dirs = lwb_check_no_instruction_dep.SCAN_DIRS
    original_root = lwb_check_no_instruction_dep.REPO_ROOT
    try:
        lwb_check_no_instruction_dep.REPO_ROOT = tmp_path
        lwb_check_no_instruction_dep.SCAN_DIRS = ("plugins",)
        violations = lwb_check_no_instruction_dep.find_violations()
    finally:
        lwb_check_no_instruction_dep.REPO_ROOT = original_root
        lwb_check_no_instruction_dep.SCAN_DIRS = original_dirs

    assert any("CLAUDE.md" in v for v in violations)


def test_both_hooks_run_correctly_with_no_instruction_files_up_the_tree(tmp_path, monkeypatch):
    # tmp_path (pytest's own temp dir, outside this repo's own tree) has no
    # CLAUDE.md or AGENTS.md anywhere up its ancestry -- confirm that before
    # trusting the rest of the test.
    for parent in (tmp_path, *tmp_path.parents):
        assert not (parent / "CLAUDE.md").exists()
        assert not (parent / "AGENTS.md").exists()

    for plugin_dir, fixture in HOOK_TARGETS:
        hook_script = plugin_dir / "bin" / "lwb_hook.py"
        policy_path = tmp_path / f"{plugin_dir.parent.name}-policy.json"
        policy_path.write_text(json.dumps(_WARN_POLICY), encoding="utf-8")
        ledger_path = tmp_path / f"{plugin_dir.parent.name}-ledger.jsonl"

        env = {
            "LWB_POLICY_PATH": str(policy_path),
            "LWB_LEDGER_PATH": str(ledger_path),
            "PATH": __import__("os").environ.get("PATH", ""),
            "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
        }

        result = subprocess.run(
            [sys.executable, str(hook_script)],
            cwd=str(tmp_path),  # working directory has no instruction file up its tree
            input=fixture.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["hookSpecificOutput"]["permissionDecision"] == "allow"
