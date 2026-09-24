"""adapters/claude/repo_facts.collect_matched_proof_facts, against real
on-disk proof records (no `git` needed here -- this function only reads
`proof/<branch>.json` content, not any git state).
"""

from __future__ import annotations

import json
from pathlib import Path

from adapters.claude.repo_facts import collect_matched_proof_facts


def _write_record(root: Path, branch: str, data: dict, proof_dir: str = "proof") -> Path:
    path = root.joinpath(*proof_dir.split("/"), f"{branch}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_no_branch_is_no_opinion(tmp_path):
    assert collect_matched_proof_facts(tmp_path, None) == (None, None)


def test_no_matching_record_is_no_opinion(tmp_path):
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (None, None)


def test_a_clean_record_is_not_self_certified_and_has_no_failure(tmp_path):
    _write_record(
        tmp_path,
        "feature-x",
        {
            "author": "session-a",
            "checked_by": "session-b",
            "commands": [{"argv": ["true"], "exit": 0, "expect_exit": 0}],
        },
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (False, False)


def test_a_self_certified_record_is_detected(tmp_path):
    _write_record(
        tmp_path,
        "feature-x",
        {"author": "session-a", "checked_by": "session-a", "commands": []},
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (True, False)


def test_an_empty_author_or_checked_by_is_never_self_certified(tmp_path):
    """Two empty strings are equal in Python -- must not be read as a match."""
    _write_record(tmp_path, "feature-x", {"author": "", "checked_by": "", "commands": []})
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (False, False)


def test_a_recorded_failed_command_is_detected(tmp_path):
    _write_record(
        tmp_path,
        "feature-x",
        {
            "author": "a",
            "checked_by": "b",
            "commands": [
                {"argv": ["true"], "exit": 0, "expect_exit": 0},
                {"argv": ["false"], "exit": 1, "expect_exit": 0},
            ],
        },
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (False, True)


def test_both_problems_together(tmp_path):
    _write_record(
        tmp_path,
        "feature-x",
        {
            "author": "a",
            "checked_by": "a",
            "commands": [{"argv": ["false"], "exit": 1, "expect_exit": 0}],
        },
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (True, True)


def test_a_record_missing_author_or_checked_by_fields_is_readable_but_unremarkable(tmp_path):
    _write_record(tmp_path, "feature-x", {"id": "feature-x"})
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (False, False)


def test_malformed_json_is_no_opinion_not_a_crash(tmp_path):
    path = tmp_path / "proof" / "feature-x.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (None, None)


def test_a_non_object_top_level_is_no_opinion(tmp_path):
    path = tmp_path / "proof" / "feature-x.json"
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (None, None)


def test_the_dot_lwb_proof_directory_is_honoured(tmp_path):
    _write_record(
        tmp_path,
        "feature-x",
        {"author": "a", "checked_by": "a", "commands": []},
        proof_dir=".lwb/proof",
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (True, False)


def test_a_slash_branch_name_maps_to_its_nested_record(tmp_path):
    _write_record(
        tmp_path,
        "feat/x-12",
        {"author": "a", "checked_by": "a", "commands": []},
    )
    assert collect_matched_proof_facts(tmp_path, "feat/x-12") == (True, False)


def test_a_branch_name_that_would_escape_proof_dir_is_refused(tmp_path):
    """A `..` segment must never let a crafted branch name read outside
    `proof/` -- see `_branch_proof_path`."""
    (tmp_path / "secret.json").write_text(
        json.dumps({"author": "a", "checked_by": "a", "commands": []}), encoding="utf-8"
    )
    assert collect_matched_proof_facts(tmp_path, "../secret") == (None, None)


def test_an_oversized_record_is_not_read(tmp_path, monkeypatch):
    from adapters.claude import repo_facts as module

    monkeypatch.setattr(module, "_MAX_PROOF_RECORD_BYTES", 4)
    _write_record(
        tmp_path,
        "feature-x",
        {"author": "a", "checked_by": "a", "commands": []},
    )
    assert collect_matched_proof_facts(tmp_path, "feature-x") == (None, None)
