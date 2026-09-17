#!/usr/bin/env python3
"""CI check backing the `lwb-portable` job: run each plugin's hook EXACTLY
as declared, for both Claude Code and Codex.

For each of `plugins/claude/lwb/hooks/hooks.json` and
`plugins/codex/lwb/hooks/hooks.json`, this takes the literal `command`
string for the `PreToolUse` / `Agent` hook, substitutes `${CLAUDE_PLUGIN_ROOT}`
/ `${PLUGIN_ROOT}` the same way each host does (a plain string replace,
before the shell ever sees it), and executes that string through the
platform shell exactly as the host CLI would (`shell=True`: `cmd.exe` on
Windows, `sh` elsewhere) — the portable dual-interpreter launch chosen in
`docs/architecture.md#the-hook-launch-method` specifically because it is
safe to test this way, without installing anything beyond a `setup-python`
Python already on `PATH`.

A policy pointing `lwb_version` at `warn` mode is pointed at via
`LWB_POLICY_PATH` and a `PreToolUse`/`Agent` fixture is fed on stdin, so a
correct run must print `hookSpecificOutput.permissionDecision: "allow"`
(lwb_version never denies).

Usage:
    python scripts/lwb_check_hook_launch.py

Stdlib only. Exits 0 and prints "lwb-portable check passed" on success;
otherwise prints every failure found (not just the first) and exits 1.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (plugin dir, root-var name, fixture file)
TARGETS = [
    (
        REPO_ROOT / "plugins" / "claude" / "lwb",
        "CLAUDE_PLUGIN_ROOT",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "claude" / "pretooluse_agent_no_budget.json",
    ),
    (
        REPO_ROOT / "plugins" / "codex" / "lwb",
        "PLUGIN_ROOT",
        REPO_ROOT / "tests" / "adapters" / "fixtures" / "codex" / "pretooluse_agent_no_budget.json",
    ),
]

_WARN_POLICY = {
    "$schema": "./schema.json",
    "rules": {"lwb_version": {"mode": "warn", "options": {}}},
}


def _hook_command(hooks_json: Path) -> str:
    hooks = json.loads(hooks_json.read_text(encoding="utf-8"))
    for entry in hooks["hooks"]["PreToolUse"]:
        if entry.get("matcher") == "Agent":
            for hook in entry["hooks"]:
                return hook["command"]
    raise SystemExit(f"FAIL: no PreToolUse/Agent hook found in {hooks_json}")


def _check_one(plugin_dir: Path, root_var: str, fixture: Path, errors: list[str]) -> None:
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    command = _hook_command(hooks_json).replace("${" + root_var + "}", str(plugin_dir))

    with tempfile.TemporaryDirectory(prefix="lwb-portable-") as tmp:
        policy_path = Path(tmp) / "warn-policy.json"
        policy_path.write_text(json.dumps(_WARN_POLICY), encoding="utf-8")

        env = dict(os.environ)
        env["LWB_POLICY_PATH"] = str(policy_path)
        env["LWB_LEDGER_PATH"] = str(Path(tmp) / "ledger.jsonl")

        result = subprocess.run(
            command,
            shell=True,
            cwd=REPO_ROOT,
            input=fixture.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

    if result.returncode != 0:
        errors.append(
            f"{plugin_dir}: hook command exited {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        return

    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        errors.append(f"{plugin_dir}: hook stdout was not valid JSON: {exc}\nstdout: {result.stdout}")
        return

    decision = payload.get("hookSpecificOutput", {}).get("permissionDecision")
    if decision != "allow":
        errors.append(f"{plugin_dir}: expected permissionDecision 'allow', got {decision!r}: {payload}")


def main() -> int:
    errors: list[str] = []
    for plugin_dir, root_var, fixture in TARGETS:
        _check_one(plugin_dir, root_var, fixture, errors)

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1

    print("lwb-portable check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
