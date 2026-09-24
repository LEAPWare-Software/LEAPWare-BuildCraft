"""Every tracked GitHub Actions workflow must be valid YAML.

WHY THIS EXISTS. An unquoted colon in a step NAME --
`- name: lwb-proof-reexecute (report-only: re-run ...)` -- made
`.github/workflows/ci.yml` unparseable. GitHub's response to an
unparseable workflow is not a failing check: it creates NO
`pull_request` run for that workflow at all. So the test matrix, the
lane gate, the proof gates and the leak scan silently stopped running,
and the pull request displayed six checks instead of sixteen. Eleven
commits landed on that branch before anyone noticed, because the author
was reading local gate output and treating it as CI.

That is this repository's signature defect in its purest form: a check
that is not running is indistinguishable from a check that is passing.
`docs/maintainers/session-protocol.md` lists five earlier instances.

Hand-inspection is what let it through -- the workflow was eyeballed and
declared structurally fine by someone who could not parse it, because
PyYAML was not installed. So this test uses a real parser or it fails
loudly; it never silently approves.

THE SKIP IS DELIBERATELY ASYMMETRIC. Locally, PyYAML may be absent and
the test skips with a message. In CI it must NOT skip: a skipped parse
check in CI would recreate the exact blindness it exists to prevent, so
when a CI environment variable is set, a missing parser is a FAILURE.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _tracked_workflow_files() -> list[pathlib.Path]:
    """Workflow files as GIT sees them, not as the filesystem does.

    `git ls-files` rather than a glob: an untracked local experiment is not
    something CI will ever run, and a tracked file deleted from disk should
    surface as an error rather than vanish from the check.
    """
    result = subprocess.run(
        ["git", "ls-files", ".github/workflows"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        pytest.fail(f"git ls-files failed: {result.stderr.strip()}")
    return [REPO_ROOT / line for line in result.stdout.split() if line.strip()]


def _require_yaml():
    """Import PyYAML, or skip locally and FAIL in CI. Never silently pass."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        in_ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
        if in_ci:
            pytest.fail(
                "PyYAML is not installed in CI, so the workflow parse check "
                "cannot run. A SKIPPED parse check in CI is the blindness this "
                "test exists to prevent -- install pyyaml in the workflow's "
                "dependency step rather than letting this skip."
            )
        pytest.skip("PyYAML not installed locally; this check is mandatory in CI")
    return yaml


def test_every_tracked_workflow_is_valid_yaml():
    yaml = _require_yaml()
    files = _tracked_workflow_files()
    assert files, "no tracked workflow files found -- git ls-files returned nothing"

    errors = []
    for path in files:
        if not path.is_file():
            errors.append(f"{path.name}: tracked by git but missing on disk")
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 -- any parse failure is a failure
            errors.append(f"{path.name}: {exc}")

    assert not errors, (
        "a workflow file does not parse, so GitHub will create NO run for it "
        "and its checks will be invisible rather than red:\n  " + "\n  ".join(errors)
    )


def test_ci_workflow_still_declares_the_jobs_the_ruleset_requires():
    """Parsing is not enough: the required contexts must still exist.

    The branch ruleset requires named checks. A workflow that parses but has
    lost or renamed a job leaves those contexts permanently pending, which
    blocks every PR with no error message -- the opposite failure to an
    invisible check, and just as silent.
    """
    yaml = _require_yaml()
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    data = yaml.safe_load(ci.read_text(encoding="utf-8"))

    jobs = data.get("jobs", {})
    for required in ("test", "lwb-portable", "lwb-hosted-runners"):
        assert required in jobs, (
            f"ci.yml no longer defines the '{required}' job; the branch ruleset "
            "names its checks as required, so they would stay pending forever"
        )


def test_auto_queue_workflow_triggers_on_workflow_run_and_schedule_not_check_suite():
    """The headline fix PR #44 exists for: `check_suite` never fires for a
    suite GitHub Actions itself created, so the auto-queue workflow had
    literally never run in this repository's history. A mutation
    reverting `on:` back to `check_suite:`, or pointing `workflow_run`'s
    `workflows` list at names that do not exist, must fail this test --
    nothing else in this file asserts on the `on:` section at all.

    PyYAML resolves the bare scalar key `on` to the boolean `True` (YAML
    1.1's implicit typing), not the string `"on"` -- `data[True]`, not
    `data["on"]`, is the trigger block.
    """
    yaml = _require_yaml()
    path = REPO_ROOT / ".github" / "workflows" / "auto-queue.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    on = data.get(True)
    assert on is not None, "auto-queue.yml has no 'on:' trigger block at all"
    assert "check_suite" not in on, (
        "check_suite never fires for a suite GitHub Actions itself created -- "
        "this is the exact defect PR #44 fixes; it must not come back"
    )

    workflow_run = on.get("workflow_run")
    assert workflow_run is not None, "auto-queue.yml must trigger on workflow_run"
    workflows = workflow_run.get("workflows") or []
    for name in ("CI", "Handoff"):
        assert name in workflows, (
            f"workflow_run.workflows is missing {name!r}: {workflows!r} -- CI "
            "alone already produces every context the branch ruleset requires "
            "and its workflow_run event fires only once all of CI's jobs have "
            "finished, so firing on CI is already sufficient for correctness; "
            "listening to Handoff too is deliberate belt-and-braces (a second "
            "chance against a missed, delayed, or skipped CI-only trigger), "
            "not a correctness requirement -- but both names must stay listed"
        )

    assert "schedule" in on, "auto-queue.yml must keep its schedule sweep as the retry/self-heal"

    dispatch = on.get("workflow_dispatch")
    assert dispatch is not None, "auto-queue.yml must keep workflow_dispatch for an explicit PR number"
    pr_number_input = (dispatch.get("inputs") or {}).get("pr_number") or {}
    assert pr_number_input.get("required") is True, "workflow_dispatch's pr_number input must stay required"
    assert pr_number_input.get("type") == "string", "workflow_dispatch's pr_number input must stay a string"


def test_auto_queue_find_step_actually_invokes_the_script():
    """N1, independent review of PR #44. The 'on:' test above proves the
    workflow trigger fires; it says nothing about whether the "Find the
    pull requests" step still invokes the script the trigger fix depends
    on. PROBED: replacing that step's `run:` with
    `echo "prs=" >> "$GITHUB_OUTPUT"` (disconnecting the script from the
    workflow entirely) left the full test suite green, because nothing
    asserted the step's `run:` field at all. This closes that gap directly."""
    yaml = _require_yaml()
    path = REPO_ROOT / ".github" / "workflows" / "auto-queue.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    steps = data["jobs"]["queue"]["steps"]
    find_steps = [s for s in steps if s.get("id") == "find"]
    assert find_steps, "auto-queue.yml has no step with id: find"
    run = find_steps[0].get("run") or ""
    assert "auto_queue.py" in run and "--find-prs" in run, (
        f"the 'find' step's run: no longer invokes the script: {run!r} -- "
        "the workflow's trigger fix is disconnected from the code it is "
        "meant to drive"
    )


def test_auto_queue_trigger_workflow_names_exist_in_tracked_workflows():
    """N2, independent review of PR #44. `workflow_run.workflows` names
    "CI" and "Handoff" as hardcoded strings; nothing checked them against
    the real workflow files' own `name:` fields. PROBED: renaming ci.yml's
    `name: CI` to `name: Continuous Integration` left the full suite green
    -- the workflow_run trigger goes silently dead and nothing here would
    catch it. This cross-checks every entry against every tracked
    workflow's declared name."""
    yaml = _require_yaml()
    real_names = set()
    for path in _tracked_workflow_files():
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        name = (data or {}).get("name")
        if name:
            real_names.add(name)

    auto_queue_path = REPO_ROOT / ".github" / "workflows" / "auto-queue.yml"
    data = yaml.safe_load(auto_queue_path.read_text(encoding="utf-8"))
    workflows = ((data.get(True) or {}).get("workflow_run") or {}).get("workflows") or []
    assert workflows, "auto-queue.yml's workflow_run.workflows is empty"
    for name in workflows:
        assert name in real_names, (
            f"auto-queue.yml's workflow_run.workflows names {name!r}, which is "
            f"not the `name:` of any tracked workflow ({sorted(real_names)!r}) "
            "-- a rename of the real workflow would silently kill this trigger"
        )


def test_auto_queue_job_skips_non_success_workflow_run_conclusions():
    """N3, independent review of PR #44 (and its predecessor's N1).
    `workflow_run: types: [completed]` fires for a 'failure', 'cancelled'
    or 'skipped' conclusion just as readily as 'success', and nothing
    checked that sibling field -- so a failed CI run drove a full
    (harmless but wasteful) resolve-and-enqueue attempt. This asserts a
    conclusion-gating condition exists on the queue job (or an equivalent
    step-level condition covering every step)."""
    yaml = _require_yaml()
    path = REPO_ROOT / ".github" / "workflows" / "auto-queue.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    queue = data["jobs"]["queue"]
    job_if = queue.get("if") or ""
    step_ifs = [s.get("if") or "" for s in queue.get("steps", [])]

    def gates_conclusion(expr: str) -> bool:
        return "workflow_run" in expr and "conclusion" in expr and "success" in expr

    assert gates_conclusion(job_if) or all(
        gates_conclusion(expr) for expr in step_ifs if step_ifs
    ), (
        "no job-level or step-level 'if:' in auto-queue.yml's queue job checks "
        "github.event.workflow_run.conclusion == 'success' -- a failed or "
        "cancelled CI/Handoff run would still drive a full resolve-and-enqueue "
        f"attempt (job if: {job_if!r})"
    )


def test_auto_queue_enqueue_step_does_not_abort_the_loop_on_first_failure():
    """B1, independent review of PR #47 (this workflow's prior recut of
    #44). GitHub Actions runs `run:` blocks under `bash -e` by default, and
    `scripts/cloud/auto_queue.py`'s main() returns EXIT_ERROR (1) for
    several ordinary, expected outcomes (a rejected enqueue mutation, an
    unreadable PR, an unreadable ruleset -- see that module's own
    docstring). Under `-e`, the OLD loop body -- LWB_PR_NUMBER="$pr"
    python scripts/cloud/auto_queue.py as the last statement inside the
    `for`, with no `|| ...` after it -- let the first PR's nonzero exit
    kill the whole step immediately, so every PR after it in that tick's
    `prs=` list was silently never considered. REPRODUCED by the reviewer
    with a literal `bash -e` probe over a 3-item loop where the first item
    exits 1: only the first item is ever attempted, and a completion
    marker after the loop never prints.

    This does not re-run the shell (that would be over-engineering a
    parse-level test file); it asserts the fix's shape directly: the
    'Enqueue if ready' step's `run:` text must not invoke `auto_queue.py`
    as a bare last-statement in the loop body, and must instead record a
    failing iteration's exit (`|| rc=` or equivalent) and propagate it
    only after the loop (`exit "$rc"` or equivalent) -- the minimal fix
    that lets every PR in the list get its own attempt regardless of an
    earlier one's outcome, while still failing the step overall if any PR
    errored."""
    yaml = _require_yaml()
    path = REPO_ROOT / ".github" / "workflows" / "auto-queue.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    steps = data["jobs"]["queue"]["steps"]
    enqueue_steps = [s for s in steps if s.get("name") == "Enqueue if ready"]
    assert enqueue_steps, "auto-queue.yml has no 'Enqueue if ready' step"
    run = enqueue_steps[0].get("run") or ""
    assert "auto_queue.py" in run, (
        "the 'Enqueue if ready' step no longer invokes auto_queue.py at all: "
        f"{run!r}"
    )

    lines = [line.rstrip() for line in run.splitlines() if line.strip()]
    invoking = [line for line in lines if "auto_queue.py" in line]
    assert invoking, "no line in the step's run: invokes auto_queue.py"
    for line in invoking:
        assert "||" in line, (
            "the 'Enqueue if ready' step invokes auto_queue.py without a "
            f"trailing '|| ...': {line!r} -- under Actions' default `bash -e`, "
            "the first PR in the loop that exits nonzero (an expected outcome "
            "for a rejected enqueue mutation, an unreadable PR, or an "
            "unreadable ruleset -- see auto_queue.py's own docstring) would "
            "abort the step immediately, so every PR after it in that tick's "
            "list is silently never considered"
        )

    assert re.search(r'exit\s+"?\$rc"?', run) or re.search(r"exit\s+\$\?", run), (
        "the 'Enqueue if ready' step's run: never re-raises a recorded "
        "failure after the loop (e.g. exit \"$rc\"): "
        f"{run!r} -- without this, a per-PR failure would go unreported and "
        "the step would report success even though an enqueue attempt "
        "actually failed"
    )


def test_step_names_with_a_colon_are_quoted():
    """The specific mistake that caused this, caught at its own shape.

    `name: foo (report-only: bar)` parses as a mapping and breaks the file.
    A generic parse test catches it only after it is written; this names the
    shape so the failure message says what to do.
    """
    yaml = _require_yaml()
    for path in _tracked_workflow_files():
        if not path.is_file():
            continue
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = raw.strip()
            if not stripped.startswith("- name:"):
                continue
            value = stripped[len("- name:"):].strip()
            if value.startswith(('"', "'")):
                continue
            assert ": " not in value, (
                f"{path.name}:{lineno}: step name contains ': ' and is unquoted, "
                f"which YAML reads as a nested mapping and which made this very "
                f"file unparseable: {value!r}. Wrap the name in double quotes."
            )
