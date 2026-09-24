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

def test_resolve_pr_numbers_from_workflow_dispatch():
    """workflow_dispatch's pr_number input names the PR explicitly."""
    numbers = auto_queue.resolve_pr_numbers({"inputs": {"pr_number": "42"}}, "workflow_dispatch")
    assert numbers == [42]


def test_resolve_pr_numbers_from_workflow_dispatch_rejects_non_numeric():
    numbers = auto_queue.resolve_pr_numbers(
        {"inputs": {"pr_number": "not-a-number"}}, "workflow_dispatch"
    )
    assert numbers is None


def test_resolve_pr_numbers_from_workflow_run_uses_head_sha_not_pull_requests(monkeypatch):
    """`workflow_run.pull_requests` is documented unreliable and can be
    empty even when the commit has an open PR -- so it must never be read.
    Resolution goes through `commits/{sha}/pulls` instead."""
    event = {
        "workflow_run": {
            "head_sha": "deadbeef",
            # Deliberately empty, as GitHub's own docs say it can be.
            "pull_requests": [],
        }
    }
    calls = []

    def fake_api(path):
        calls.append(path)
        assert path == "repos/LEAPWare-Software/LEAPWare-BuildCraft/commits/deadbeef/pulls"
        return [{"number": 7, "state": "open", "base": {"ref": "main"}}]

    monkeypatch.setattr(auto_queue, "_api", fake_api)
    numbers = auto_queue.resolve_pr_numbers(event, "workflow_run")
    assert numbers == [7]
    assert calls, "must resolve from the head sha, not trust the empty pull_requests list"


def test_resolve_pr_numbers_from_workflow_run_excludes_closed_and_wrong_base(monkeypatch):
    event = {"workflow_run": {"head_sha": "deadbeef", "pull_requests": []}}
    monkeypatch.setattr(
        auto_queue,
        "_api",
        lambda p: [
            {"number": 1, "state": "closed", "base": {"ref": "main"}},
            {"number": 2, "state": "open", "base": {"ref": "other"}},
            {"number": 3, "state": "open", "base": {"ref": "main"}},
        ],
    )
    numbers = auto_queue.resolve_pr_numbers(event, "workflow_run")
    assert numbers == [3]


def test_resolve_pr_numbers_from_workflow_run_missing_sha_is_unresolved():
    numbers = auto_queue.resolve_pr_numbers({"workflow_run": {}}, "workflow_run")
    assert numbers is None


def test_resolve_pr_numbers_from_workflow_run_unreadable_api_is_unresolved(monkeypatch):
    monkeypatch.setattr(auto_queue, "_api", lambda p: None)
    numbers = auto_queue.resolve_pr_numbers({"workflow_run": {"head_sha": "deadbeef"}}, "workflow_run")
    assert numbers is None


def test_resolve_pr_numbers_from_schedule_sweeps_every_open_pr(monkeypatch):
    """Neither `inputs` nor `workflow_run` is present on a schedule event --
    every open PR targeting main is swept. This is the legitimate case
    that an event-shape-only check used to over-generalize from: an empty
    event dict sweeps ONLY because event_name is genuinely "schedule"."""
    calls = []

    def fake_api(path):
        calls.append(path)
        assert path == "repos/LEAPWare-Software/LEAPWare-BuildCraft/pulls?state=open&base=main&per_page=100"
        return [{"number": 5}, {"number": 9}]

    monkeypatch.setattr(auto_queue, "_api", fake_api)
    numbers = auto_queue.resolve_pr_numbers({}, "schedule")
    assert numbers == [5, 9]
    assert calls


def test_resolve_pr_numbers_from_schedule_unreadable_api_is_unresolved(monkeypatch):
    monkeypatch.setattr(auto_queue, "_api", lambda p: None)
    numbers = auto_queue.resolve_pr_numbers({}, "schedule")
    assert numbers is None


def test_resolve_pr_numbers_non_schedule_event_with_empty_payload_does_not_sweep(monkeypatch):
    """The bug an independent reviewer found: an unreadable/missing event
    payload must NOT silently escalate a targeted run into a repo-wide
    sweep. `event_name` (not the event dict's shape) is what gates the
    sweep, so a workflow_dispatch or workflow_run event that arrives with
    an empty/unreadable `{}` payload must come back unresolved, and must
    never fall through to the "sweep every open PR" API call."""
    calls = []
    monkeypatch.setattr(auto_queue, "_api", lambda p: calls.append(p) or None)

    for event_name in ("workflow_dispatch", "workflow_run"):
        numbers = auto_queue.resolve_pr_numbers({}, event_name)
        assert numbers is None, f"event_name={event_name!r} must not sweep on an empty payload"

    assert calls == [], "an empty payload on a non-schedule event must never call the API at all"


def test_resolve_pr_numbers_schedule_event_name_still_sweeps_with_empty_event(monkeypatch):
    """The legitimate case the fix above must not break: event_name ==
    "schedule" sweeps correctly even with a genuinely empty event dict."""
    monkeypatch.setattr(
        auto_queue,
        "_api",
        lambda p: [{"number": 11}, {"number": 12}],
    )
    numbers = auto_queue.resolve_pr_numbers({}, "schedule")
    assert numbers == [11, 12]


def test_emit_find_prs_prints_github_output_shape(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setattr(auto_queue, "resolve_pr_numbers", lambda event, event_name: [1, 2, 3])
    assert auto_queue.emit_find_prs() == 0
    out = capsys.readouterr().out
    assert "prs=1,2,3" in out


def test_emit_find_prs_unresolved_prints_empty_prs_and_does_not_fail(monkeypatch, capsys):
    """A lookup failure must not fail the job -- the schedule sweep and the
    next workflow_run get another chance.

    This also pins the fix for a real defect: `_api` and `emit_find_prs`
    used to print their `NOTICE: ...` diagnostics to stdout, which the
    workflow appends straight into `$GITHUB_OUTPUT` -- a NOTICE line with
    no `=` in it makes the Actions runner treat that file as malformed and
    fail the step outright. So this asserts the actual LINE STRUCTURE of
    stdout, not a substring: stdout must be exactly the `prs=` line and
    nothing else, and the NOTICE text must land on stderr instead.
    """
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setattr(auto_queue, "resolve_pr_numbers", lambda event, event_name: None)
    assert auto_queue.emit_find_prs() == 0
    captured = capsys.readouterr()
    stdout_lines = [line for line in captured.out.splitlines() if line.strip()]
    assert stdout_lines == ["prs="], (
        "stdout must contain ONLY the prs= GITHUB_OUTPUT line -- anything else "
        f"here lands in $GITHUB_OUTPUT too: {stdout_lines!r}"
    )
    assert "NOTICE" in captured.err
    assert "NOTICE" not in captured.out

