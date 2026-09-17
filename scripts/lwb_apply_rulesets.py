#!/usr/bin/env python3
"""Apply (create or update) this repo's GitHub repository rulesets from JSON.

Reads every `*.json` file in `.github/rulesets/` and, for each one, either
creates a new ruleset (POST) or updates the existing one by name (PUT), via
`gh api`. `gh` carries the caller's auth, so this needs no token of its own
and works unchanged from any machine that has `gh auth login`'d.

Usage:
    python scripts/lwb_apply_rulesets.py                 # apply every ruleset
    python scripts/lwb_apply_rulesets.py --dry-run        # print the JSON, do nothing
    python scripts/lwb_apply_rulesets.py --repo OWNER/REPO --dry-run

Stdlib only (subprocess + json); shells out to the `gh` CLI, never to a
bare `curl`/token, so PAT scoping and 2FA stay exactly what `gh auth`
already enforces.

Ordering trap this script guards against: a ruleset that requires a merge
method GitHub doesn't return "invalid JSON", it returns a 422 naming the
method (e.g. a `pull_request` or `merge_queue` rule requiring `squash` when
the repo's own `allow_squash_merge` is still `false`). Before applying
anything, this script reads every ruleset's required merge method(s) and
checks them against `gh api repos/<repo>` -- if any required method isn't
enabled on the repo yet, it fails with the exact `gh api ... PATCH` command
that fixes it, and applies nothing. This was found the hard way on
LEAPWare-BuildCraft's own first apply (LWB-D0): the fix is to run the repo
settings PATCH first, which is what this check now forces.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULESETS_DIR = REPO_ROOT / ".github" / "rulesets"
DEFAULT_REPO = "LEAPWare-Software/LEAPWare-BuildCraft"


def _load_rulesets(rulesets_dir: Path) -> list[tuple[Path, dict]]:
    loaded = []
    for path in sorted(rulesets_dir.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if "name" not in data:
            raise ValueError(f"{path}: ruleset JSON is missing required key 'name'")
        loaded.append((path, data))
    return loaded


# GitHub ruleset merge-method spellings -> the repo settings field that must
# be true before a ruleset requiring that method can be created or updated.
_MERGE_METHOD_TO_SETTING = {
    "squash": "allow_squash_merge",
    "merge": "allow_merge_commit",
    "rebase": "allow_rebase_merge",
    # merge_queue.parameters.merge_method is spelled upper-case.
    "SQUASH": "allow_squash_merge",
    "MERGE": "allow_merge_commit",
    "REBASE": "allow_rebase_merge",
}


def _required_merge_settings(rulesets: list[tuple[Path, dict]]) -> dict[str, set[str]]:
    """Map repo setting name -> the ruleset file name(s) that need it true."""
    required: dict[str, set[str]] = {}
    for path, data in rulesets:
        for rule in data.get("rules", []):
            params = rule.get("parameters", {})
            methods: list[str] = []
            if rule.get("type") == "pull_request":
                methods.extend(params.get("allowed_merge_methods", []))
            elif rule.get("type") == "merge_queue" and "merge_method" in params:
                methods.append(params["merge_method"])
            for method in methods:
                setting = _MERGE_METHOD_TO_SETTING.get(method)
                if setting is None:
                    continue
                required.setdefault(setting, set()).add(path.name)
    return required


def _current_merge_settings(repo: str) -> dict[str, bool]:
    fields = "allow_squash_merge,allow_merge_commit,allow_rebase_merge"
    result = _run_gh(["api", f"repos/{repo}", "--jq", f"{{{fields}}}"])
    if result.returncode != 0:
        raise RuntimeError(f"gh api repos/{repo} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _check_merge_settings_or_die(repo: str, rulesets: list[tuple[Path, dict]]) -> None:
    """Fail fast, before touching any ruleset, if the repo's own merge-method
    settings don't yet allow what the rulesets require. This is the ordering
    check: repo settings (allow_squash_merge et al.) must be applied BEFORE
    a ruleset that requires that method, or GitHub returns a 422."""
    required = _required_merge_settings(rulesets)
    if not required:
        return
    current = _current_merge_settings(repo)
    missing = {setting: files for setting, files in required.items() if not current.get(setting)}
    if not missing:
        return

    lines = [
        f"apply_rulesets.py: repo settings are not ready for these rulesets on {repo}.",
        "Run the repo-settings PATCH first, then re-run this script:",
        "",
        f"  gh api -X PATCH repos/{repo} \\",
        "    -F allow_squash_merge=true \\",
        "    -F allow_merge_commit=false \\",
        "    -F allow_rebase_merge=false \\",
        "    -F allow_auto_merge=true \\",
        "    -F delete_branch_on_merge=true \\",
        "    -f squash_merge_commit_title=PR_TITLE \\",
        "    -f squash_merge_commit_message=PR_BODY",
        "",
        "Missing settings:",
    ]
    for setting, files in sorted(missing.items()):
        lines.append(f"  - {setting}=true, required by: {', '.join(sorted(files))}")
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(2)


def _run_gh(argv: list[str], input_json: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *argv],
        input=input_json,
        capture_output=True,
        text=True,
    )


def _existing_ruleset_id(repo: str, name: str) -> int | None:
    result = _run_gh(["api", f"repos/{repo}/rulesets", "--jq", ".[] | select(.name==\"%s\") | .id" % name])
    if result.returncode != 0:
        raise RuntimeError(f"gh api repos/{repo}/rulesets failed: {result.stderr.strip()}")
    output = result.stdout.strip()
    if not output:
        return None
    # If more than one id came back (shouldn't happen), take the first.
    return int(output.splitlines()[0])


def _apply_one(repo: str, path: Path, data: dict, dry_run: bool) -> None:
    body = json.dumps(data)
    if dry_run:
        print(f"--- {path.name} ({data['name']}) ---")
        print(json.dumps(data, indent=2))
        return

    existing_id = _existing_ruleset_id(repo, data["name"])
    if existing_id is None:
        argv = ["api", "--method", "POST", f"repos/{repo}/rulesets", "--input", "-"]
        action = "created"
    else:
        argv = ["api", "--method", "PUT", f"repos/{repo}/rulesets/{existing_id}", "--input", "-"]
        action = "updated"

    result = _run_gh(argv, input_json=body)
    if result.returncode != 0:
        print(f"FAILED applying {path.name}: {result.stderr.strip()}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: ruleset '{data['name']}' {action} ({path.name})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo (default: %(default)s)")
    parser.add_argument(
        "--dry-run", action="store_true", help="print each ruleset's JSON; call nothing"
    )
    args = parser.parse_args()

    if not RULESETS_DIR.is_dir():
        print(f"no rulesets directory at {RULESETS_DIR}", file=sys.stderr)
        return 1

    rulesets = _load_rulesets(RULESETS_DIR)
    if not rulesets:
        print(f"no *.json rulesets found in {RULESETS_DIR}", file=sys.stderr)
        return 1

    if not args.dry_run:
        _check_merge_settings_or_die(args.repo, rulesets)

    for path, data in rulesets:
        _apply_one(args.repo, path, data, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
