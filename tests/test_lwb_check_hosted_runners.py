"""Tests for scripts/lwb_check_hosted_runners.py."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_hosted_runners as check_mod  # noqa: E402


def test_this_repos_own_workflows_pass():
    original = check_mod.REPO_ROOT
    original_dir = check_mod.WORKFLOWS_DIR
    try:
        assert check_mod.check() == []
    finally:
        check_mod.REPO_ROOT = original
        check_mod.WORKFLOWS_DIR = original_dir


def test_flags_a_self_hosted_literal_runner(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "bad.yml").write_text(
        "name: Bad\n"
        "on: push\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: self-hosted\n"
        "    steps:\n"
        "      - run: echo hi\n",
        encoding="utf-8",
    )

    original = check_mod.REPO_ROOT
    original_dir = check_mod.WORKFLOWS_DIR
    try:
        check_mod.REPO_ROOT = tmp_path
        check_mod.WORKFLOWS_DIR = workflows
        findings = check_mod.check()
    finally:
        check_mod.REPO_ROOT = original
        check_mod.WORKFLOWS_DIR = original_dir

    assert any("self-hosted" in f for f in findings)


def test_flags_a_bad_matrix_os_entry(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "bad-matrix.yml").write_text(
        "name: Bad Matrix\n"
        "on: push\n"
        "jobs:\n"
        "  test:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, my-office-pc]\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps:\n"
        "      - run: echo hi\n",
        encoding="utf-8",
    )

    original = check_mod.REPO_ROOT
    original_dir = check_mod.WORKFLOWS_DIR
    try:
        check_mod.REPO_ROOT = tmp_path
        check_mod.WORKFLOWS_DIR = workflows
        findings = check_mod.check()
    finally:
        check_mod.REPO_ROOT = original
        check_mod.WORKFLOWS_DIR = original_dir

    assert any("my-office-pc" in f for f in findings)


def test_clean_hosted_only_workflow_has_no_findings(tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "clean.yml").write_text(
        "name: Clean\n"
        "on: push\n"
        "jobs:\n"
        "  test:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, windows-latest, macos-latest]\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps:\n"
        "      - run: echo hi\n"
        "  other:\n"
        "    runs-on: ubuntu-22.04\n"
        "    steps:\n"
        "      - run: echo hi\n",
        encoding="utf-8",
    )

    original = check_mod.REPO_ROOT
    original_dir = check_mod.WORKFLOWS_DIR
    try:
        check_mod.REPO_ROOT = tmp_path
        check_mod.WORKFLOWS_DIR = workflows
        findings = check_mod.check()
    finally:
        check_mod.REPO_ROOT = original
        check_mod.WORKFLOWS_DIR = original_dir

    assert findings == []
