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


def _lwb_proof_pr_step(data: dict) -> dict:
    steps = data["jobs"]["test"]["steps"]
    matches = [
        s for s in steps if str(s.get("name", "")).startswith("lwb-proof-pr")
    ]
    assert len(matches) == 1, (
        "expected exactly one 'test' job step whose name starts with "
        f"'lwb-proof-pr', found {len(matches)}"
    )
    return matches[0]


def test_lwb_proof_pr_step_passes_pr_author():
    """Regression for a gap two independent reviewers flagged: the
    `lwb-proof-pr` step's `run:` command must keep passing `--pr-author`, or
    the bot-PR exemption in scripts/lwb_check_proof.py silently stops being
    wired up in CI while the rest of the suite stays green.

    THE VACUITY TRAP. A naive `"--pr-author" in <raw file text>` check would
    still pass even with the flag deleted from the actual `run:` block,
    because the string `--pr-author` also appears in this step's own
    explanatory comment a few lines above `run:`. So this test parses the
    workflow with PyYAML and asserts on the parsed step's own `run` string
    specifically, never on the whole raw file.
    """
    yaml = _require_yaml()
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    data = yaml.safe_load(ci.read_text(encoding="utf-8"))

    step = _lwb_proof_pr_step(data)
    run = step.get("run", "")
    assert "--pr-author" in run, (
        "the lwb-proof-pr step's 'run:' command no longer passes --pr-author -- "
        f"this silently disables the bot-PR exemption. run was:\n{run!r}"
    )

    # Prove this assertion is not vacuous the same way the trap could be:
    # a copy of the real run string with --pr-author stripped out (as the
    # regression would leave it) must fail the same assertion.
    mutated_run = "\n".join(
        line for line in run.splitlines() if "--pr-author" not in line
    )
    assert "--pr-author" not in mutated_run
    try:
        assert "--pr-author" in mutated_run
    except AssertionError:
        pass
    else:  # pragma: no cover -- would mean the probe itself is broken
        pytest.fail("mutation probe did not fail as expected -- test is vacuous")


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
