"""apply_rulesets.py must refuse to apply a ruleset before the repo's own
merge-method settings allow what that ruleset requires.

This is the LWB-D0 ordering bug: a ruleset requiring squash merges (via a
`pull_request` or `merge_queue` rule) fails on GitHub with a 422 if
`allow_squash_merge` is still false on the repo. The fix is to run the
settings PATCH first; this test locks in that scripts/lwb_apply_rulesets.py
catches the wrong order itself, with a clear message, rather than letting
the 422 be the first anyone hears of it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "lwb_apply_rulesets.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("apply_rulesets", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def apply_rulesets():
    return _load_module()


def test_required_merge_settings_reads_main_ruleset(apply_rulesets):
    rulesets = apply_rulesets._load_rulesets(apply_rulesets.RULESETS_DIR)
    required = apply_rulesets._required_merge_settings(rulesets)
    assert "allow_squash_merge" in required
    assert "main.json" in required["allow_squash_merge"]


def test_check_dies_when_repo_settings_not_ready(apply_rulesets, monkeypatch):
    rulesets = [
        (
            Path("fake.json"),
            {
                "name": "fake",
                "rules": [
                    {
                        "type": "pull_request",
                        "parameters": {"allowed_merge_methods": ["squash"]},
                    }
                ],
            },
        )
    ]
    monkeypatch.setattr(
        apply_rulesets,
        "_current_merge_settings",
        lambda repo: {"allow_squash_merge": False, "allow_merge_commit": True, "allow_rebase_merge": False},
    )
    with pytest.raises(SystemExit) as excinfo:
        apply_rulesets._check_merge_settings_or_die("owner/repo", rulesets)
    assert excinfo.value.code == 2


def test_check_passes_when_repo_settings_already_ready(apply_rulesets, monkeypatch):
    rulesets = [
        (
            Path("fake.json"),
            {
                "name": "fake",
                "rules": [
                    {
                        "type": "merge_queue",
                        "parameters": {"merge_method": "SQUASH"},
                    }
                ],
            },
        )
    ]
    monkeypatch.setattr(
        apply_rulesets,
        "_current_merge_settings",
        lambda repo: {"allow_squash_merge": True, "allow_merge_commit": False, "allow_rebase_merge": False},
    )
    # Should not raise.
    apply_rulesets._check_merge_settings_or_die("owner/repo", rulesets)


def test_check_is_a_noop_when_no_ruleset_requires_a_merge_method(apply_rulesets, monkeypatch):
    rulesets = [(Path("fake.json"), {"name": "fake", "rules": [{"type": "deletion"}]})]

    def _boom(repo):
        raise AssertionError("should not query repo settings when nothing requires a merge method")

    monkeypatch.setattr(apply_rulesets, "_current_merge_settings", _boom)
    # Should not raise, and should not call _current_merge_settings.
    apply_rulesets._check_merge_settings_or_die("owner/repo", rulesets)
