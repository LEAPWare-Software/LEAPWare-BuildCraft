"""Unit tests for scripts/lwb_check_commit_identity.py's allow-list logic.

Uses synthetic name/email pairs (not real commit data) so this test does
not depend on this repo's own history staying a particular shape.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_commit_identity as check_mod  # noqa: E402
import lwb_lanes  # noqa: E402


def test_leapware_identity_allowed():
    assert check_mod._is_allowed("LEAPWare", "leapware@outlook.com")


def test_dependabot_bot_identity_allowed():
    assert check_mod._is_allowed(
        "dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"
    )


def test_plain_bot_shape_allowed():
    assert check_mod._is_allowed("example-bot[bot]", "example-bot[bot]@users.noreply.github.com")


def test_random_human_identity_flagged():
    assert not check_mod._is_allowed("Someone Else", "someone@example.com")


def test_bot_name_without_bot_email_flagged():
    # Name claims to be a bot but the email doesn't match GitHub's own
    # noreply shape -- do not trust the name alone.
    assert not check_mod._is_allowed("dependabot[bot]", "attacker@example.com")


def test_leapware_name_wrong_email_flagged():
    assert not check_mod._is_allowed("LEAPWare", "not-leapware@example.com")


def _init_repo(repo):
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "LEAPWare"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "leapware@outlook.com"], cwd=repo, check=True)


def _commit(repo, path: str, content: str, message: str, author=None) -> str:
    """Like the fixture helper in tests/test_lwb_lanes.py, but able to
    commit under a NON-LEAPWare author (`author=(name, email)`), which is
    exactly the shape a reviewer's own record-only commit has."""
    fp = repo / path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    cmd = ["git"]
    if author is not None:
        name, email = author
        cmd += ["-c", f"user.name={name}", "-c", f"user.email={email}"]
    cmd += ["commit", "-q", "-m", message]
    subprocess.run(cmd, cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_record_only_commit_is_exempt_for_its_own_pr(tmp_path):
    """B5/the fix itself: a reviewer filing their own AGREE/DISAGREE
    record under reviews/<pr>/ must not fail this check, even though the
    commit's git author is not ALLOWED_HUMAN -- this is the exact false
    positive that permanently failed a PR (force-push denied) before this
    fix, since committing the record itself was what tripped the gate."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    _commit(
        repo,
        "reviews/9/independent-verifier.json",
        '{"pr": 9, "verdict": "AGREE"}\n',
        "record my own review",
        author=("Some Reviewer", "reviewer@example.com"),
    )

    original_check_root = check_mod.REPO_ROOT
    original_lanes_root = lwb_lanes.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        lwb_lanes.REPO_ROOT = repo
        findings = check_mod.check("HEAD~1..HEAD", 9)
    finally:
        check_mod.REPO_ROOT = original_check_root
        lwb_lanes.REPO_ROOT = original_lanes_root

    assert findings == []


def test_record_only_commit_for_a_different_pr_is_still_flagged(tmp_path):
    """B3 narrowing, exercised through this script: a record-only-shaped
    commit filed under a DIFFERENT pr_number than the one being checked
    must not dodge the identity check -- the exemption is scoped to THIS
    PR's own review/proof files, not "anything under reviews/ anywhere"."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    _commit(
        repo,
        "reviews/5/verifier.json",
        '{"pr": 5, "verdict": "AGREE"}\n',
        "impostor edit of another PR's review dir",
        author=("Some Reviewer", "reviewer@example.com"),
    )

    original_check_root = check_mod.REPO_ROOT
    original_lanes_root = lwb_lanes.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        lwb_lanes.REPO_ROOT = repo
        findings = check_mod.check("HEAD~1..HEAD", 9)
    finally:
        check_mod.REPO_ROOT = original_check_root
        lwb_lanes.REPO_ROOT = original_lanes_root

    assert findings == ["Some Reviewer <reviewer@example.com>"]


def test_pr_number_zero_never_exempts_a_record_only_commit(tmp_path):
    """`--pr-number 0` ("no PR context") must mean the exemption never
    applies -- omitting the flag entirely must keep this check exactly as
    strict as it was before this fix."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit(repo, "seed.txt", "seed\n", "seed")
    _commit(
        repo,
        "reviews/9/verifier.json",
        '{"pr": 9, "verdict": "AGREE"}\n',
        "record my own review",
        author=("Some Reviewer", "reviewer@example.com"),
    )

    original_check_root = check_mod.REPO_ROOT
    original_lanes_root = lwb_lanes.REPO_ROOT
    try:
        check_mod.REPO_ROOT = repo
        lwb_lanes.REPO_ROOT = repo
        findings = check_mod.check("HEAD~1..HEAD", 0)
    finally:
        check_mod.REPO_ROOT = original_check_root
        lwb_lanes.REPO_ROOT = original_lanes_root

    assert findings == ["Some Reviewer <reviewer@example.com>"]
