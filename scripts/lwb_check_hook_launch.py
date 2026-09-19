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


def _agent_hook_entry(hooks_json: Path) -> dict:
    """The literal PreToolUse hook entry `hooks.json` registers for `Agent`.

    Returns the WHOLE hook dict, not just `command` -- mirrors
    `scripts/lwb_check_foreign_repo.py`'s `_bash_hook_entry`, and for the
    same reason: an independent reviewer found this function used to read
    `command` out of this dict specifically to avoid assuming, then this
    script hardcoded `timeout=30` for the subprocess call regardless of
    what `hooks.json` declared (10, for both matchers, in both plugins).
    A hook that runs 10-30s is killed by Claude Code at the declared
    timeout in a real session; this check silently proved nothing about
    that failure mode, on all three OSes the `lwb-portable` job runs, for
    the ONLY matcher this repository ever exercises the launch of (see
    `_check_one`'s `commandWindows` handling below for the other half of
    the same finding). See `_check_one`.

    A `matcher` may name more than one tool, "|"-separated; this treats
    `Agent` as covered when it is the whole matcher or one of the
    "|"-separated names in it, matching `_bash_hook_entry`'s convention
    rather than the exact-string check this function used to do -- both
    plugins currently declare a bare `"Agent"` matcher, so this widens
    what would match without narrowing anything that matches today.
    """
    hooks = json.loads(hooks_json.read_text(encoding="utf-8"))
    for entry in hooks.get("hooks", {}).get("PreToolUse", []):
        matcher = entry.get("matcher", "")
        names = [name.strip() for name in matcher.split("|")]
        if "Agent" in names:
            for hook in entry.get("hooks", []):
                if hook.get("command"):
                    return hook
    raise SystemExit(f"FAIL: no PreToolUse/Agent hook found in {hooks_json}")


def _check_one(plugin_dir: Path, root_var: str, fixture: Path, errors: list[str]) -> None:
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    entry = _agent_hook_entry(hooks_json)

    timeout = entry.get("timeout")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        errors.append(
            f"{plugin_dir}: the Agent PreToolUse entry in {hooks_json} declares no "
            "numeric 'timeout' -- this check refuses to substitute a value "
            "hooks.json does not itself declare"
        )
        return

    # `commandWindows`, when declared, is the string the host actually
    # launches on Windows (see `plugins/codex/lwb/hooks/hooks.json`,
    # already read by `scripts/lwb_validate_codex_plugin.py`). Launching
    # `command` unconditionally meant the one OS where `commandWindows`
    # changes the meaning of the launch was the one OS where this check
    # never read it -- found by an independent reviewer.
    use_windows_command = os.name == "nt" and isinstance(entry.get("commandWindows"), str)
    command_str = entry["commandWindows"] if use_windows_command else entry["command"]
    command = command_str.replace("${" + root_var + "}", str(plugin_dir))

    with tempfile.TemporaryDirectory(prefix="lwb-portable-") as tmp:
        policy_path = Path(tmp) / "warn-policy.json"
        policy_path.write_text(json.dumps(_WARN_POLICY), encoding="utf-8")

        env = dict(os.environ)
        env["LWB_POLICY_PATH"] = str(policy_path)
        env["LWB_LEDGER_PATH"] = str(Path(tmp) / "ledger.jsonl")

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=REPO_ROOT,
                input=fixture.read_text(encoding="utf-8"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            errors.append(
                f"{plugin_dir}: hook exceeded its declared timeout of {timeout}s "
                f"({hooks_json}) for command {command!r} -- Claude Code would kill "
                "this hook at that timeout in a real session\n"
                f"stdout so far: {exc.stdout!r}\nstderr so far: {exc.stderr!r}"
            )
            return

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
