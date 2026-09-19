"""The auto-queue decision, which is what lets a PR land without a laptop.

WHY THESE TESTS AND NOT OTHERS. This job asks the merge queue to take a
pull request. If its readiness test is wrong in the permissive direction,
unreviewed work lands while every gate reports success -- which is this
repository's signature defect with the stakes raised, because there is no
human in the loop to notice.

So the tests that matter are the ones that prove it REFUSES: an absent
check, a pending check, a failing check, a draft, a closed PR, and -- the
one that is easy to get wrong -- a ruleset that could not be read at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "cloud"))

import auto_queue  # noqa: E402


def _checks(**named):
    return {
        "check_runs": [
            {"name": n, "status": "completed", "conclusion": c}
            if c not in ("queued", "in_progress")
            else {"name": n, "status": c, "conclusion": None}
            for n, c in named.items()
        ]
    }


def test_all_green_is_ready(monkeypatch):
    monkeypatch.setattr(auto_queue, "_api", lambda p: _checks(a="success", b="success"))
    ready, why = auto_queue._all_required_checks_green("sha", ["a", "b"])
    assert ready is True, why


def test_an_absent_check_is_not_a_passing_one(monkeypatch):
    """The distinction this repository keeps failing to make.

    A check that is not running is indistinguishable from a check that is
    passing -- unless something insists on its presence. An unparseable
    workflow once produced NO run at all rather than a red one, and eleven
    commits landed before anyone noticed.
    """
    monkeypatch.setattr(auto_queue, "_api", lambda p: _checks(a="success"))
    ready, why = auto_queue._all_required_checks_green("sha", ["a", "b"])
    assert ready is False
    assert "absent" in why and "b" in why


def test_a_pending_check_is_not_a_passing_one(monkeypatch):
    monkeypatch.setattr(auto_queue, "_api", lambda p: _checks(a="success", b="in_progress"))
    ready, why = auto_queue._all_required_checks_green("sha", ["a", "b"])
    assert ready is False
    assert "not green" in why


def test_a_failing_check_blocks(monkeypatch):
    monkeypatch.setattr(auto_queue, "_api", lambda p: _checks(a="success", b="failure"))
    ready, why = auto_queue._all_required_checks_green("sha", ["a", "b"])
    assert ready is False
    assert "b=failure" in why


def test_unreadable_check_runs_block_rather_than_pass(monkeypatch):
    """`_api` returns None when it could not read. That must never be
    treated as "read it, found nothing wrong"."""
    monkeypatch.setattr(auto_queue, "_api", lambda p: None)
    ready, why = auto_queue._all_required_checks_green("sha", ["a"])
    assert ready is False
    assert "could not read" in why


def test_an_unreadable_ruleset_is_an_error_not_a_pass(monkeypatch):
    """If the ruleset cannot be read, the required list is unknown. The
    job must fail loudly rather than enqueue against an empty list."""
    monkeypatch.setattr(auto_queue, "_api", lambda p: None)
    assert auto_queue.required_contexts() is None


def test_an_empty_required_list_refuses_to_enqueue(monkeypatch):
    """A ruleset listing NO required checks means there is no evidence to
    stand on. Enqueuing then would be landing work on nothing at all."""
    monkeypatch.setattr(auto_queue, "required_contexts", lambda: [])
    monkeypatch.setattr(
        auto_queue,
        "_api",
        lambda p: {"state": "open", "draft": False, "base": {"ref": "main"}, "head": {"sha": "s" * 40}},
    )
    monkeypatch.setenv("LWB_PR_NUMBER", "1")
    called = []
    monkeypatch.setattr(auto_queue, "enqueue", lambda *a: called.append(a) or True)
    assert auto_queue.main() == auto_queue.EXIT_ERROR
    assert called == [], "must not enqueue when the ruleset requires nothing"


@pytest.mark.parametrize(
    "pr,reason",
    [
        ({"state": "closed", "draft": False, "base": {"ref": "main"}, "head": {"sha": "s" * 40}}, "closed"),
        ({"state": "open", "draft": True, "base": {"ref": "main"}, "head": {"sha": "s" * 40}}, "draft"),
        ({"state": "open", "draft": False, "base": {"ref": "other"}, "head": {"sha": "s" * 40}}, "base"),
    ],
)
def test_refuses_closed_draft_and_wrong_base(monkeypatch, pr, reason):
    monkeypatch.setattr(auto_queue, "_api", lambda p: pr)
    monkeypatch.setenv("LWB_PR_NUMBER", "1")
    called = []
    monkeypatch.setattr(auto_queue, "enqueue", lambda *a: called.append(a) or True)
    assert auto_queue.main() == auto_queue.EXIT_NOT_READY, reason
    assert called == [], f"must not enqueue a {reason} pull request"
