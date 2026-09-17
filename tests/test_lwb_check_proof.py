"""Tests for scripts/lwb_check_proof.py against tests/fixtures/proof/.

These fixtures live under tests/fixtures/proof/, never under the real
proof/ directory — proof/ is proof of a real deliverable, not test data
(see proof/README.md: "This scaffolding session wrote NO proof records").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_proof  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "proof"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_record_has_no_errors():
    errors = lwb_check_proof._validate_record(FIXTURES / "valid.json", _load("valid.json"))
    assert errors == []


def test_self_certified_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "self_certified.json", _load("self_certified.json"))
    assert any("self-certified" in e for e in errors)


def test_exit_mismatch_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "exit_mismatch.json", _load("exit_mismatch.json"))
    assert any("expect_exit" in e for e in errors)


def test_missing_field_record_is_rejected():
    errors = lwb_check_proof._validate_record(FIXTURES / "missing_field.json", _load("missing_field.json"))
    assert any("unproven" in e for e in errors)


def test_real_proof_directory_validates_clean():
    # This scaffolding session ships proof/ with no records yet (see
    # proof/README.md) -- an empty proof/ is not itself a failure. Once a
    # deliverable lands its own proof/<id>.json, the validator must still
    # find every record clean, not a failure.
    errors, count = lwb_check_proof.validate_all()
    assert errors == []
    assert count >= 0
