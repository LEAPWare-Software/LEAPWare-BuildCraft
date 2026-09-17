"""Shape checks for .github/rulesets/*.json.

Not a call to GitHub -- these are the properties apply_rulesets.py and the
GitHub rulesets API both depend on, checked without any network access so
a malformed ruleset fails fast in `pytest`, not at apply time.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULESETS_DIR = REPO_ROOT / ".github" / "rulesets"

REQUIRED_TOP_LEVEL_KEYS = {"name", "target", "enforcement", "bypass_actors", "conditions", "rules"}


def _ruleset_paths() -> list[Path]:
    return sorted(RULESETS_DIR.glob("*.json"))


def test_at_least_one_ruleset_exists():
    assert _ruleset_paths(), f"no *.json files under {RULESETS_DIR}"


def test_each_ruleset_has_required_top_level_keys():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED_TOP_LEVEL_KEYS - data.keys()
        assert not missing, f"{path.name} missing top-level keys: {missing}"


def test_each_ruleset_is_active_with_empty_bypass_actors():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["enforcement"] == "active", f"{path.name}: enforcement must be 'active'"
        assert data["bypass_actors"] == [], f"{path.name}: bypass_actors must be empty"


def test_each_ruleset_targets_branch():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["target"] == "branch", f"{path.name}: target must be 'branch'"


def test_each_ruleset_has_unique_rule_types():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        rules = data["rules"]
        assert isinstance(rules, list) and rules, f"{path.name}: rules must be a non-empty list"
        types = [rule["type"] for rule in rules]
        assert len(types) == len(set(types)), f"{path.name}: duplicate rule types: {types}"


def test_pull_request_rule_requires_squash_only_when_present():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        for rule in data["rules"]:
            if rule["type"] != "pull_request":
                continue
            params = rule["parameters"]
            assert params["allowed_merge_methods"] == ["squash"], (
                f"{path.name}: pull_request rule must allow only squash merges"
            )


def test_merge_queue_rule_uses_squash_and_allgreen_when_present():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        for rule in data["rules"]:
            if rule["type"] != "merge_queue":
                continue
            params = rule["parameters"]
            assert params["merge_method"] == "SQUASH", f"{path.name}: merge_queue must use SQUASH"
            assert params["grouping_strategy"] == "ALLGREEN", (
                f"{path.name}: merge_queue must use ALLGREEN grouping"
            )
            for key in (
                "min_entries_to_merge",
                "max_entries_to_merge",
                "max_entries_to_build",
                "check_response_timeout_minutes",
            ):
                assert key in params, f"{path.name}: merge_queue missing '{key}'"


def test_required_status_checks_rule_lists_nonempty_contexts_when_present():
    for path in _ruleset_paths():
        data = json.loads(path.read_text(encoding="utf-8"))
        for rule in data["rules"]:
            if rule["type"] != "required_status_checks":
                continue
            params = rule["parameters"]
            assert params["strict_required_status_checks_policy"] is True
            checks = params["required_status_checks"]
            assert checks, f"{path.name}: required_status_checks list is empty"
            for check in checks:
                assert check.get("context"), f"{path.name}: a status check is missing 'context'"
