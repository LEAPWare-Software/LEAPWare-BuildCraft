"""Unit tests for scripts/lwb_check_commit_identity.py's allow-list logic.

Uses synthetic name/email pairs (not real commit data) so this test does
not depend on this repo's own history staying a particular shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lwb_check_commit_identity as check_mod  # noqa: E402


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
