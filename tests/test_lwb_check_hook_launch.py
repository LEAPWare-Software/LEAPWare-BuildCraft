"""Tests for BLOCKER 1 of the independent review of PR #27
(reviews/buildcraft/pr27-c75a37b...md, section 1): `scripts/lwb_check_hook_launch.py`
(the `lwb-portable` job) launched the shipped hook with a hardcoded
`timeout=30` while `hooks.json` declares 10 -- so a hook that runs
10-30s, which Claude Code would kill in a real session, still passed
this gate. This file imports the script as a module and drives
`_check_one` / `_agent_hook_entry` directly against synthetic plugin
directories, so it does not depend on the real hook actually being slow
(that reproduction lives in HANDOFF.md / the commit's own before/after
measurement, since sleeping the real shipped hook for a whole test run
is not something a unit suite should pay for on every run).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "lwb_check_hook_launch.py"

_spec = importlib.util.spec_from_file_location("lwb_check_hook_launch", SCRIPT_PATH)
lwb_check_hook_launch = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lwb_check_hook_launch
_spec.loader.exec_module(lwb_check_hook_launch)  # type: ignore[union-attr]

FIXTURE = REPO_ROOT / "tests" / "adapters" / "fixtures" / "claude" / "pretooluse_agent_no_budget.json"


def _write_hooks_json(plugin_dir: Path, entry: dict) -> None:
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [entry]}}), encoding="utf-8"
    )


def test_a_missing_declared_timeout_fails_loudly_instead_of_substituting_one(tmp_path):
    """This is the shape of BLOCKER 1 itself, made non-vacuous: without
    the fix, this scenario ran the hook subprocess with a hardcoded 30s
    regardless of what (or whether) hooks.json declared a timeout. After
    the fix, a missing/non-numeric declared timeout is a FAILURE, not a
    silent fallback."""
    plugin_dir = tmp_path / "plugin"
    _write_hooks_json(
        plugin_dir,
        {
            "matcher": "Agent",
            "hooks": [{"type": "command", "command": "python -c \"print(1)\""}],
        },
    )
    errors: list[str] = []
    lwb_check_hook_launch._check_one(plugin_dir, "CLAUDE_PLUGIN_ROOT", FIXTURE, errors)
    assert errors, "expected a failure for a hooks.json with no declared timeout"
    assert "no numeric 'timeout'" in errors[0]


def test_the_declared_timeout_is_the_one_actually_enforced(tmp_path):
    """A hook that runs LONGER than its own declared timeout must fail
    this check, at (approximately) the declared timeout -- not at some
    larger hardcoded value. This is the direct mutation-tested version of
    the reviewer's `time.sleep(12)` / declared-10s reproduction."""
    plugin_dir = tmp_path / "plugin"
    slow_command = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    _write_hooks_json(
        plugin_dir,
        {
            "matcher": "Agent",
            "hooks": [{"type": "command", "command": slow_command, "timeout": 1}],
        },
    )
    errors: list[str] = []
    import time as _time

    started = _time.monotonic()
    lwb_check_hook_launch._check_one(plugin_dir, "CLAUDE_PLUGIN_ROOT", FIXTURE, errors)
    elapsed = _time.monotonic() - started

    assert errors, "a hook exceeding its declared timeout must fail this check"
    assert "declared timeout of 1s" in errors[0]
    # Generous upper bound, well under the OLD hardcoded 30s: on Windows,
    # `shell=True` spawns cmd.exe as the immediate child, and killing it
    # at the declared timeout does not always kill the grandchild python
    # process it launched (no job object) -- subprocess.run's
    # communicate() can then block briefly draining the grandchild's
    # inherited stdout/stderr pipes until IT exits. That is a platform
    # quirk of the launch method itself (pre-existing, shared by every
    # check in this repository that runs a hook this way), not something
    # this fix changes -- the assertion above (the declared 1s is the
    # value NAMED in the failure) is what actually pins Blocker 1; this
    # bound only guards against a regression back to the old 30s wait.
    assert elapsed < 9, f"expected the 1s declared timeout to be enforced, took {elapsed:.1f}s"


def test_a_matcher_naming_multiple_tools_is_still_recognized():
    """`_agent_hook_entry` widens the exact `"Agent"` string match to the
    same "|"-splitting `_bash_hook_entry` in lwb_check_foreign_repo.py
    documents and implements, so a matcher like "Agent|Task" is still
    found rather than raising "no PreToolUse/Agent hook found"."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        hooks_json = Path(tmp) / "hooks.json"
        hooks_json.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Agent|Task",
                                "hooks": [{"type": "command", "command": "echo hi", "timeout": 5}],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        entry = lwb_check_hook_launch._agent_hook_entry(hooks_json)
        assert entry["command"] == "echo hi"


def test_the_real_hooks_json_declares_a_numeric_timeout_for_both_plugins():
    """Regression guard against the exact defect this fix addresses:
    both shipped hooks.json files must declare a numeric timeout for the
    Agent matcher, or this check itself cannot run at all."""
    for plugin_dir in (
        REPO_ROOT / "plugins" / "claude" / "lwb",
        REPO_ROOT / "plugins" / "codex" / "lwb",
    ):
        entry = lwb_check_hook_launch._agent_hook_entry(plugin_dir / "hooks" / "hooks.json")
        timeout = entry.get("timeout")
        assert isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
