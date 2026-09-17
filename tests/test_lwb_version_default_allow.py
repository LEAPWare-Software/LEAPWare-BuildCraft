"""BuildCraft ships a safe minimal hook first: `lwb_version` allows every
event, reports the plugin version, and never denies. The real SDLC gate
rules (stage checks, role lanes) are designed and built in a later
session, on top of this same scaffolding.

`core/policy/default.json` is the policy every real install ships with
unless a project or user overrides it. This test proves that shipped
default never blocks a dispatch, by running both real hook entry points
(`plugins/claude/lwb/bin/lwb_hook.py`, `plugins/codex/lwb/bin/lwb_hook.py`)
as subprocesses with NO `LWB_POLICY_PATH` override -- so each hook falls
back to its own vendored `vendor/policy/default.json`, exactly as a real
install would -- and asserts both allow and both report the version.

Mutation: change `lwb_version.evaluate` to honor `config.mode` (i.e. return
a DENY-mode Finding when configured to deny) and re-run
`python scripts/lwb_build.py` to sync the vendor trees --
`test_both_hooks_allow_under_the_shipped_default_policy` FAILS if
`core/policy/default.json` is also flipped to `"deny"` (the decision
becomes "deny", not "allow").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (plugin dir under plugins/, any fixture for that host's event shape --
# lwb_version fires on every event regardless of prompt content)
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


def test_both_hooks_allow_under_the_shipped_default_policy(tmp_path):
    for plugin_dir, fixture in HOOK_TARGETS:
        hook_script = plugin_dir / "bin" / "lwb_hook.py"
        ledger_path = tmp_path / f"{plugin_dir.parent.name}-ledger.jsonl"

        env = {
            # Deliberately NO LWB_POLICY_PATH: the hook must fall back to
            # its own vendored policy/default.json, the file a real
            # install ships and never overrides.
            "LWB_LEDGER_PATH": str(ledger_path),
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        }

        result = subprocess.run(
            [sys.executable, str(hook_script)],
            cwd=str(tmp_path),
            input=fixture.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["hookSpecificOutput"]["permissionDecision"] == "allow", (
            f"{plugin_dir}: shipped default policy did not allow: {payload}"
        )
        assert "lwb" in payload["hookSpecificOutput"]["permissionDecisionReason"]
