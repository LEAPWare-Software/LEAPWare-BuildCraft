"""The merge decision, which is the one decision with no human behind it.

WHY THESE TESTS AND NOT OTHERS. `scripts/lwb_auto_queue.py` is the only
thing in this repository that can ask for a pull request to be merged
without a person present. If its readiness test is wrong in the
permissive direction, unreviewed work lands while every gate reports
success -- this repository's signature defect, with the one mitigation
that has always caught it (someone looking) removed.

So every test here is a REFUSAL path. The one test that asserts a pass
exists only to prove the refusals are not refusing unconditionally.

Two of them exist because the script's own comments made a claim that
nothing enforced:

  * `test_required_review_count_matches_the_lane_gate` -- the script
    duplicates `REQUIRED_INDEPENDENT_REVIEWS` rather than importing it,
    and says in a comment that "a mismatch is caught by
    tests/test_lwb_auto_queue.py". Until this file existed, that
    sentence was false: the file it named was not in the tree. A comment
    asserting that a check exists, where no check exists, is the same
    defect as a check that cannot run -- it is just written in English.

  * `test_a_stale_review_record_does_not_satisfy_the_gate` -- a review
    record that names an earlier commit is exactly what a reviewer
    produces when the head moves under it mid-review, which has happened
    on this repository twice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_auto_queue as aq  # noqa: E402

HEAD = "a" * 40
OTHER = "b" * 40

RULESET_WITH_CHECKS = [{"id": 1}]
RULESET_DETAIL = {
    "rules": [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "gate-one"},
                    {"context": "gate-two"},
                ]
            },
        }
    ]
}


def _pr(state="open", draft=False, base="main", head=HEAD):
    return {"state": state, "draft": draft, "base": {"ref": base}, "head": {"sha": head}}


def _good_proof(pr=7):
    return {"pr": pr, "author": "author-id", "checked_by": "someone-else"}


def _good_review(reviewed=HEAD):
    return {
        "verdict": "AGREE",
        "reviewer_id": "reviewer-x",
        "commit_author_id": "author-id",
        "reviewed_commit": reviewed,
    }


_UNSET = object()  # so `proof=None` can mean "absent", not "use the default"


class FakeRepo:
    """Stands in for every GitHub read the script performs.

    Deliberately routed through the script's own read helpers rather than
    through `subprocess`, so a test says what the API returned rather than
    what `gh` printed.
    """

    def __init__(self, *, pr=_UNSET, checks=_UNSET, proof=_UNSET, reviews=_UNSET):
        self.pr = _pr() if pr is _UNSET else pr
        self.checks = (
            {"gate-one": "success", "gate-two": "success"} if checks is _UNSET else checks
        )
        self.proof = _good_proof() if proof is _UNSET else proof
        self.reviews = {"cloud.json": _good_review()} if reviews is _UNSET else reviews

    def install(self, monkeypatch, pr_number=7):
        monkeypatch.setattr(aq, "required_contexts", lambda: ["gate-one", "gate-two"])
        monkeypatch.setattr(aq, "check_conclusions", lambda sha: dict(self.checks))
        monkeypatch.setattr(
            aq, "_gh_json", lambda args: self.pr if "pulls" in " ".join(args) else {}
        )

        def contents(path, ref):
            if path == f"proof/{pr_number}.json":
                return self.proof
            name = path.rsplit("/", 1)[-1]
            return self.reviews.get(name)

        monkeypatch.setattr(aq, "_contents_json", contents)
        monkeypatch.setattr(aq, "_list_dir", lambda path, ref: list(self.reviews))


# ---------------------------------------------------------------------------
# the one passing case
# ---------------------------------------------------------------------------


def test_a_fully_satisfied_pr_is_ready(monkeypatch):
    FakeRepo().install(monkeypatch)
    ready, head, reasons = aq.readiness(7, None)
    assert ready is True, reasons
    assert head == HEAD


# ---------------------------------------------------------------------------
# refusals: the checks themselves
# ---------------------------------------------------------------------------


def test_an_absent_required_check_is_not_a_passing_one(monkeypatch):
    """The distinction this repository keeps failing to make.

    An unparseable workflow once produced NO check run at all rather than
    a red one, and work landed on the silence.
    """
    FakeRepo(checks={"gate-one": "success"}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("gate-two" in r and "has not reported" in r for r in reasons)


def test_a_pending_check_is_not_a_passing_one(monkeypatch):
    FakeRepo(checks={"gate-one": "success", "gate-two": "pending"}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("pending" in r for r in reasons)


def test_a_failing_check_blocks(monkeypatch):
    FakeRepo(checks={"gate-one": "success", "gate-two": "failure"}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("failure" in r for r in reasons)


def test_an_empty_ruleset_raises_rather_than_reporting_nothing_required(monkeypatch):
    """'No required checks' must never read as 'all required checks passed'."""
    monkeypatch.setattr(
        aq,
        "_gh_json",
        lambda args: RULESET_WITH_CHECKS
        if args[-1].endswith("rulesets")
        else {"rules": []},
    )
    with pytest.raises(aq.CouldNotCheck):
        aq.required_contexts()


def test_required_contexts_reads_the_live_ruleset(monkeypatch):
    def fake(args):
        return RULESET_WITH_CHECKS if args[-1].endswith("rulesets") else RULESET_DETAIL

    monkeypatch.setattr(aq, "_gh_json", fake)
    assert aq.required_contexts() == ["gate-one", "gate-two"]


# ---------------------------------------------------------------------------
# refusals: the records
# ---------------------------------------------------------------------------


def test_a_missing_proof_record_blocks(monkeypatch):
    FakeRepo(proof=None).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("no proof record" in r for r in reasons)


def test_a_self_certified_proof_record_blocks(monkeypatch):
    """`checked_by == author` means nobody checked it."""
    FakeRepo(proof={"pr": 7, "author": "same", "checked_by": "same"}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("self-certified" in r for r in reasons)


def test_a_proof_record_for_a_different_pr_blocks(monkeypatch):
    FakeRepo(proof={"pr": 99, "author": "a", "checked_by": "b"}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("does not declare pr" in r for r in reasons)


def test_no_review_records_blocks(monkeypatch):
    FakeRepo(reviews={}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("no review records" in r for r in reasons)


def test_a_disagree_verdict_does_not_satisfy_the_gate(monkeypatch):
    record = _good_review()
    record["verdict"] = "DISAGREE"
    FakeRepo(reviews={"cloud.json": record}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("not AGREE" in r for r in reasons)


def test_a_reviewer_who_is_the_author_does_not_satisfy_the_gate(monkeypatch):
    """Self-review is the failure the whole records system exists to prevent."""
    record = _good_review()
    record["reviewer_id"] = record["commit_author_id"]
    FakeRepo(reviews={"cloud.json": record}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("does not differ" in r for r in reasons)


def test_a_review_with_no_reviewer_id_does_not_satisfy_the_gate(monkeypatch):
    record = _good_review()
    record["reviewer_id"] = ""
    FakeRepo(reviews={"cloud.json": record}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False


def test_a_stale_review_record_does_not_satisfy_the_gate(monkeypatch):
    """A record naming an earlier commit reviewed code that has since moved.

    This is not hypothetical: a reviewer on this repository returned AGREE
    at one commit while three further commits and a thousand changed lines
    landed underneath it.
    """
    FakeRepo(reviews={"cloud.json": _good_review(reviewed=OTHER)}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("is not this head" in r for r in reasons)


def test_a_review_record_that_is_not_an_object_blocks(monkeypatch):
    FakeRepo(reviews={"cloud.json": ["not", "an", "object"]}).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any("not a JSON object" in r for r in reasons)


# ---------------------------------------------------------------------------
# refusals: the pull request itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pr,fragment",
    [
        (_pr(state="closed"), "not open"),
        (_pr(draft=True), "draft"),
        (_pr(base="release"), "not main"),
    ],
)
def test_refuses_closed_draft_and_wrong_base(monkeypatch, pr, fragment):
    FakeRepo(pr=pr).install(monkeypatch)
    ready, _, reasons = aq.readiness(7, None)
    assert ready is False
    assert any(fragment in r for r in reasons)


def test_a_moved_head_blocks(monkeypatch):
    """Pinning matters: anything pushed after the checks passed is unreviewed."""
    FakeRepo().install(monkeypatch)
    ready, _, reasons = aq.readiness(7, OTHER)
    assert ready is False
    assert any("head moved" in r for r in reasons)


# ---------------------------------------------------------------------------
# the arming switch, and "could not check" never passing as "checked"
# ---------------------------------------------------------------------------


def test_unarmed_never_enqueues_even_when_ready(monkeypatch):
    monkeypatch.delenv(aq.ARM_ENV, raising=False)
    monkeypatch.setattr(aq, "readiness", lambda pr, head: (True, HEAD, []))
    called = []
    monkeypatch.setattr(aq, "enqueue", lambda *a: called.append(a))
    monkeypatch.setattr(sys, "argv", ["lwb_auto_queue.py", "--pr", "7"])
    assert aq.main() == aq.EXIT_DECIDED
    assert called == [], "the shipped state must never enqueue"


def test_armed_but_not_ready_never_enqueues(monkeypatch):
    monkeypatch.setenv(aq.ARM_ENV, aq.ARM_VALUE)
    monkeypatch.setattr(aq, "readiness", lambda pr, head: (False, HEAD, ["a reason"]))
    called = []
    monkeypatch.setattr(aq, "enqueue", lambda *a: called.append(a))
    monkeypatch.setattr(sys, "argv", ["lwb_auto_queue.py", "--pr", "7"])
    assert aq.main() == aq.EXIT_DECIDED
    assert called == []


def test_armed_and_ready_enqueues_pinned_to_the_head(monkeypatch):
    monkeypatch.setenv(aq.ARM_ENV, aq.ARM_VALUE)
    monkeypatch.setattr(aq, "readiness", lambda pr, head: (True, HEAD, []))
    called = []
    monkeypatch.setattr(aq, "enqueue", lambda pr, head: called.append((pr, head)))
    monkeypatch.setattr(sys, "argv", ["lwb_auto_queue.py", "--pr", "7"])
    assert aq.main() == aq.EXIT_DECIDED
    assert called == [(7, HEAD)], "the enqueue must be pinned to the measured head"


def test_could_not_check_exits_differently_from_not_ready(monkeypatch):
    """The exit code must distinguish 'I checked' from 'I could not check'."""

    def boom(pr, head):
        raise aq.CouldNotCheck("the API was unreachable")

    monkeypatch.setattr(aq, "readiness", boom)
    called = []
    monkeypatch.setattr(aq, "enqueue", lambda *a: called.append(a))
    monkeypatch.setenv(aq.ARM_ENV, aq.ARM_VALUE)
    monkeypatch.setattr(sys, "argv", ["lwb_auto_queue.py", "--pr", "7"])
    assert aq.main() == aq.EXIT_COULD_NOT_CHECK
    assert aq.EXIT_COULD_NOT_CHECK != aq.EXIT_DECIDED
    assert called == []


def test_an_unreadable_record_raises_rather_than_reading_as_absent(monkeypatch):
    """A record that exists but cannot be parsed is not a record that is missing."""

    def bad_gh(args, allow_fail=False):
        return "!!!not base64!!!"

    monkeypatch.setattr(aq, "_gh", bad_gh)
    with pytest.raises(aq.CouldNotCheck):
        aq._contents_json("proof/7.json", HEAD)


# ---------------------------------------------------------------------------
# the claims the script and its workflow make about themselves
# ---------------------------------------------------------------------------


def test_required_review_count_matches_the_lane_gate():
    """`scripts/lwb_auto_queue.py` duplicates this constant deliberately,
    because the workflow runs the default branch's code against a PR's
    records. The duplication is only safe if something compares them."""
    lanes_source = (REPO_ROOT / "scripts" / "lwb_lanes.py").read_text(encoding="utf-8")
    for line in lanes_source.splitlines():
        if line.startswith("REQUIRED_INDEPENDENT_REVIEWS"):
            expected = int(line.split("=", 1)[1].split("#")[0].strip())
            break
    else:  # pragma: no cover - the constant is load-bearing in both files
        pytest.fail("REQUIRED_INDEPENDENT_REVIEWS not found in scripts/lwb_lanes.py")
    assert aq.REQUIRED_INDEPENDENT_REVIEWS == expected


def _auto_queue_workflow():
    import yaml

    raw = (REPO_ROOT / ".github" / "workflows" / "lwb-auto-queue.yml").read_text(
        encoding="utf-8"
    )
    # `on:` is the YAML 1.1 boolean True, not the string "on".
    return yaml.safe_load(raw)


def _checkout_steps(workflow):
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            uses = str(step.get("uses") or "")
            if uses.startswith("actions/checkout"):
                yield step


def test_the_workflow_never_checks_out_pull_request_code_under_a_write_token():
    """The workflow holds `pull-requests: write`. If a pull-request-driven
    trigger is ever added, an unpinned checkout would run PR-controlled code
    with that token.

    THE FIRST VERSION OF THIS TEST WAS VACUOUS AND AN INDEPENDENT CLOUD
    REVIEWER CAUGHT IT. It asked `"default_branch" in workflow_text`, a
    substring search over the whole file -- and that string already appears
    in the COMMENT above the checkout step, the comment warning about this
    exact hazard. So the guard was satisfied by its own warning, passed
    unconditionally, and would have kept passing after someone added a
    `pull_request:` trigger. A test for "a check that still passes when you
    break what it guards" that itself could not fail.

    This version parses the YAML and looks at the checkout STEP.
    """
    workflow = _auto_queue_workflow()
    triggers = workflow.get(True) or workflow.get("on") or {}
    if isinstance(triggers, str):
        triggers = {triggers: None}
    pr_driven = {"pull_request", "pull_request_target", "workflow_run"} & set(triggers)

    steps = list(_checkout_steps(workflow))
    assert steps, "the workflow must check out something for this guard to mean anything"

    unpinned = [s for s in steps if not (s.get("with") or {}).get("ref")]
    assert not pr_driven or not unpinned, (
        f"{sorted(pr_driven)} trigger(s) are pull-request-driven while "
        f"{len(unpinned)} checkout step(s) pin no `ref`. Pin "
        "`ref: ${{ github.event.repository.default_branch }}`; a job holding "
        "`pull-requests: write` must never run pull-request-controlled code."
    )


def test_that_guard_actually_fails_when_the_hazard_is_introduced():
    """Proves the guard above is not vacuous, which is the whole point.

    Rather than trust that it would fail, construct the hazardous shape --
    a pull-request-driven trigger plus an unpinned checkout -- and assert
    the same predicate rejects it.
    """
    hazardous = {
        True: {"pull_request": {"branches": ["main"]}},
        "permissions": {"pull-requests": "write"},
        "jobs": {"decide": {"steps": [{"uses": "actions/checkout@v7"}]}},
    }
    triggers = hazardous.get(True) or {}
    pr_driven = {"pull_request", "pull_request_target", "workflow_run"} & set(triggers)
    unpinned = [s for s in _checkout_steps(hazardous) if not (s.get("with") or {}).get("ref")]
    assert pr_driven and unpinned, "the constructed hazard is not hazardous"

    pinned = {
        True: {"pull_request": {"branches": ["main"]}},
        "jobs": {
            "decide": {
                "steps": [
                    {
                        "uses": "actions/checkout@v7",
                        "with": {"ref": "${{ github.event.repository.default_branch }}"},
                    }
                ]
            }
        },
    }
    still_unpinned = [
        s for s in _checkout_steps(pinned) if not (s.get("with") or {}).get("ref")
    ]
    assert not still_unpinned, "pinning a ref must satisfy the guard"
