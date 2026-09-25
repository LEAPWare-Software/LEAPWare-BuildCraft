"""lwb_no_unauthorised_destructive_action: gate the four destructive actions
this repository's own conduct rules name -- generalized for a consuming repo
that has no "owner" baked into the plugin.

## The four destructive actions, and where they come from

`docs/handoff-protocol.md`'s "## Hard rules" section is this repository's
own, FINITE, already-enumerated destructive-action list, restated by
`docs/requirements/mission.md`'s quality-floor item 5 as the canonical
source ("Read the list there, not a copy of it here"):

  1. a repository settings change,
  2. a force-push,
  3. a history rewrite,
  4. deleting a remote ref -- EXCEPT a branch whose work is verified
     landed, which is ordinary cleanup.

Merging is explicitly carved OUT, since D19
(`docs/requirements/decisions.md`): "a merge that passed its gates is
authorised; the remaining three are not." This rule reuses that list
AS-IS. It does not add a fifth category. An earlier attempt at defining
"authorised" for this rule in this session's own history invented one and
was rejected for contradicting this repository's own no-left-behinds rule
-- see required-work item 10's note in `decisions.md`. Do not repeat that.

## Generalizing "authorised": the actual design problem

`docs/handoff-protocol.md`'s hard rules are framed around THIS repository's
delivery discipline, where "the owner" is a specific, named person. This
rule ships INSIDE the `lwb` plugin, for consuming repos that have no
concept of "the owner" baked into the plugin at all -- `core/lwb_core` does
no I/O and knows nothing about who runs a consuming repo. So this rule
generalizes the concept of authorisation, not the list of actions:

**An action on the list is authorised only when the consuming repo's own
policy explicitly allowlists it** -- `RuleConfig.options["allow"][category]
is True` -- mirroring exactly how every other `core/lwb_core` rule already
resolves configuration (see `lwb_proof_required.py`): a `Policy`/`RuleConfig`
an adapter built from the consuming repo's own committed policy file, never
a value this rule invents or infers about intent.

**Merging is authorised unconditionally**, mirroring the "merging is
ordinary work" carve-out verbatim: a `git merge` or `gh pr merge` command is
never even classified as one of the four categories, regardless of policy,
the same way `docs/handoff-protocol.md` never asks the owner about a merge.

**The verified-landed-branch-deletion carve-out is NOT auto-detected**, and
this is the genuinely unresolved part, recorded honestly rather than
papered over. `docs/handoff-protocol.md` verifies "landed" for THIS
repository by diffing a branch's tip against the squash commit it produced
-- real git-history-ancestry work requiring a subprocess or a repository
walk far beyond what `core/lwb_core`'s I/O-free, per-hook-event purity
budget allows (see `adapters/claude/repo_facts.py`'s "No subprocess, on
purpose"). Inventing an approximation here risks exactly the false
confidence this repository's culture explicitly rejects ("state what you
measured, state what you didn't, never claim more than you checked" --
`docs/maintainers/proof-of-completion-plan.md`). So this rule does not
claim to verify ancestry. Instead, `RuleConfig.options["verified_landed_branches"]`
lets a policy author name specific branches THEIR OWN process has already
verified as landed (their own diff-tip-against-squash check, their own CI
job, whatever it is) -- the authorisation is still coming from the
consuming repo's own explicit policy, per the same "authorised = the
repo's policy said so" design as every other category, just scoped to one
branch at a time rather than blanket. What is left genuinely unresolved:
automatic ancestry verification. A plugin maintainer who wants that needs
to build it as I/O in an adapter (a `RepoFacts` field, gathered the way
`adapters/claude/repo_facts.py` gathers `landed_unproven`) and is not
provided here.

## Mode

Honours `config.mode` -- D9 names this the plan's SECOND deny-capable rule
(alongside `lwb_proof_required`), because its signal (a command matches one
of four syntactic shapes) is a fact, not a judgement. `core/policy/default.json`
nevertheless ships it at `"warn"`, this repository's own "ship quiet, arm in
a separate change" discipline (see `lwb_proof_required.py`'s docstring):
arming it to deny is a LATER, separate build-plan item, not this one.

## Purity

`core/lwb_core` does no I/O. Command classification reads only
`event.tool_input`; authorisation reads only `config.options`. The one use
of `event.repo` is a presence/completeness gate, not a field this rule
consumes for its own logic (see "Repo facts" below).

## Repo facts: why `event.repo is None` stays silent

Consulted only to answer "did the adapter gather repository context at
all" -- mirroring `lwb_proof_required`'s discipline exactly, and for the
same reason: `event.repo is None` means the adapter was never taught to
collect facts (today: the Codex adapter), not that it looked and found
nothing. An adapter that has not opted into repo-facts collection must not
be the one place this rule behaves differently from every sibling rule in
`RULES`. `event.repo.facts_incomplete` gets the same silence, for the same
reason `lwb_proof_required` gives it: "could not check" must never share a
representation with "checked, nothing there."

## Parsing posture: UNDER-match, deliberately

Same bias as `lwb_proof_required`: a missed destructive command is one
warning that did not fire; a false positive trains people to ignore this
gate within a week, after which the next real violation passes unremarked
too. Every blind spot below is accepted and named, not left to be found
later as a bug.

Segment splitting, quote-blanking and heredoc-body-blanking are reused
verbatim from `lwb_proof_required` (`_strip_heredocs`, `_strip_quoted`,
`_SEGMENT_SPLIT`, `_NON_PUBLISHING_FLAGS`) so this rule and that one can
never disagree about where one shell command ends and the next begins.

Known, accepted blind spots (all under-matching):
  - `git -C <path> push --force`, an env-prefixed push, `git.exe push`, a
    push from inside a script or alias -- same blind spots
    `lwb_proof_required` already documents for `git push`, inherited here.
  - A destructive GitHub API call whose path is not one of the recognized
    settings shapes (`repos/<owner>/<repo>`, anything containing
    `rulesets`, a `.../branches/.../protection` path, or
    `.../actions/permissions`) is not recognized -- e.g. deleting a ref via
    `gh api -X DELETE repos/.../git/refs/heads/<branch>` is not seen as
    either a settings change or a ref deletion. Recognizing every mutating
    GitHub API shape would mean modelling the whole API surface, which this
    rule does not attempt.
  - `git branch -D` (a LOCAL branch delete) is out of scope: the hard rule
    is about a REMOTE ref, and a local delete does not touch one.
  - History-rewrite recognition is scoped to four common, well-known
    subcommands -- `git rebase`, `git filter-branch`, `git filter-repo`,
    `git commit --amend`, `git reset --hard` -- not every way git history
    can be altered (e.g. `git reflog expire --expire=now --all && git gc
    --prune=now` is not recognized).

See docs/rules/lwb-no-unauthorised-destructive-action.md for the
policy-author-facing description.
"""

from __future__ import annotations

import re
from typing import Iterator, List, Mapping, Optional, Tuple

from ..config import RuleConfig
from ..events import Event
from .lwb_proof_required import (
    _NON_PUBLISHING_FLAGS,
    _SEGMENT_SPLIT,
    _strip_heredocs,
    _strip_quoted,
)

rule_id = "lwb_no_unauthorised_destructive_action"

_TOOL_NAME = "Bash"
_COMMAND_KEY = "command"

#: The four categories this rule recognizes, verbatim from
#: `docs/handoff-protocol.md`'s "## Hard rules". Do not add a fifth --
#: see this module's docstring.
SETTINGS_CHANGE = "settings_change"
FORCE_PUSH = "force_push"
HISTORY_REWRITE = "history_rewrite"
DELETE_REF = "delete_ref"

_FORCE_FLAGS = frozenset({"--force", "-f"})
_FORCE_LEASE_PREFIX = "--force-with-lease"
_DELETE_FLAGS = frozenset({"--delete", "-d"})
_HISTORY_REWRITE_SUBCOMMANDS = frozenset({"rebase", "filter-branch", "filter-repo"})
_MUTATING_METHODS = frozenset({"PATCH", "PUT", "DELETE", "POST"})

#: `gh api repos/<owner>/<repo>` with nothing else appended -- the bare
#: settings/repo-delete endpoint. Deliberately narrow: two path segments
#: after `repos/`, no trailing sub-resource.
_BARE_REPO_PATH_RE = re.compile(r"^repos/[^/\s]+/[^/\s]+/?$")

#: Recognized destructive settings sub-resources. Kept as substrings rather
#: than a full path grammar -- see the "not every mutating API shape" blind
#: spot named in the module docstring.
_SETTINGS_PATH_MARKERS = ("rulesets", "/protection")

_ACTIONS_PERMISSIONS_RE = re.compile(r"(^|/)actions/permissions/?$")


def _segments(command: str) -> Iterator[List[str]]:
    """Yield each shell segment's tokens, skipping empty and non-publishing ones.

    Reuses `lwb_proof_required`'s quote/heredoc handling so the two rules
    read the same command the same way. `_NON_PUBLISHING_FLAGS`
    (`--dry-run`, `-n`, `--help`, `-h`) disqualifies a whole segment here
    exactly as it does there: a dry run or a help invocation performs no
    destructive action.
    """
    for segment in _SEGMENT_SPLIT.split(_strip_quoted(_strip_heredocs(command))):
        tokens = segment.split()
        if not tokens:
            continue
        if any(token in _NON_PUBLISHING_FLAGS for token in tokens):
            continue
        yield tokens


def _gh_api_method(tokens: List[str]) -> Optional[str]:
    """The HTTP method a `gh api ...` invocation names, uppercased, or None.

    None (the default GET) is never mutating, so a bare `gh api repos/x/y`
    is left untouched -- it reads settings, it does not change them.
    """
    for index, token in enumerate(tokens):
        if token in ("-X", "--method") and index + 1 < len(tokens):
            return tokens[index + 1].upper()
        if token.startswith("--method="):
            return token.split("=", 1)[1].upper()
    return None


def _looks_like_settings_path(token: str) -> bool:
    path = token.lstrip("/")
    if _BARE_REPO_PATH_RE.match(path):
        return True
    if any(marker in path for marker in _SETTINGS_PATH_MARKERS):
        return True
    if _ACTIONS_PERMISSIONS_RE.search(path):
        return True
    return False


def _classify_segment(tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """`(category, target)` for one segment's tokens, or `(None, None)`.

    `target` is populated only for `DELETE_REF` (the ref name being
    deleted), which is the one category whose authorisation can be scoped
    per-branch. Checks merge FIRST and unconditionally, ahead of every
    destructive category, so a squash-merge (which replaces a target
    branch's history in a sense) is never mistaken for a history rewrite,
    and `gh pr merge` is never mistaken for a settings change -- the
    "merging is ordinary work" carve-out, D19.
    """
    if not tokens:
        return None, None

    program = tokens[0]

    if program == "git" and len(tokens) >= 2 and tokens[1] == "merge":
        return None, None
    if program == "gh" and len(tokens) >= 3 and tokens[1] == "pr" and tokens[2] == "merge":
        return None, None

    if program == "git" and len(tokens) >= 2 and tokens[1] == "push":
        rest = tokens[2:]
        if any(t in _FORCE_FLAGS or t.startswith(_FORCE_LEASE_PREFIX) for t in rest):
            return FORCE_PUSH, None
        if any(t in _DELETE_FLAGS for t in rest):
            # The ref name is the LAST non-flag positional argument
            # regardless of where --delete/-d sits: git accepts both
            # `git push <remote> --delete <ref>` and `git push --delete
            # <remote> <ref>`, and in neither shape can a remote name be
            # told apart from a ref name syntactically -- the position is
            # the only signal git itself relies on.
            non_flags = [t for t in rest if not t.startswith("-")]
            target = non_flags[-1] if non_flags else None
            return DELETE_REF, target
        for token in rest:
            if token.startswith(":") and len(token) > 1:
                return DELETE_REF, token[1:]
        return None, None

    if program == "git" and len(tokens) >= 2:
        sub = tokens[1]
        if sub in _HISTORY_REWRITE_SUBCOMMANDS:
            return HISTORY_REWRITE, None
        if sub == "commit" and "--amend" in tokens[2:]:
            return HISTORY_REWRITE, None
        if sub == "reset" and "--hard" in tokens[2:]:
            return HISTORY_REWRITE, None
        return None, None

    if program == "gh" and len(tokens) >= 3 and tokens[1] == "repo" and tokens[2] in (
        "edit",
        "delete",
    ):
        return SETTINGS_CHANGE, None

    if program == "gh" and len(tokens) >= 2 and tokens[1] == "api":
        method = _gh_api_method(tokens)
        if method in _MUTATING_METHODS:
            for token in tokens[2:]:
                if token.startswith("-"):
                    continue
                if _looks_like_settings_path(token):
                    return SETTINGS_CHANGE, None
        return None, None

    return None, None


def _classify_command(command: str) -> Tuple[Optional[str], Optional[str]]:
    """The first destructive `(category, target)` found across all segments.

    A command chain (`&&`, `;`, ...) can carry more than one segment; the
    first destructive one found wins, matching `lwb_proof_required`'s own
    "first match" posture for a publish.
    """
    for tokens in _segments(command):
        category, target = _classify_segment(tokens)
        if category is not None:
            return category, target
    return None, None


def _allowed(category: str, target: Optional[str], options: Mapping) -> bool:
    """True when the consuming repo's own policy explicitly allowlists this.

    Two independent ways a policy can authorise, both explicit, neither
    inferred:

      - `options["allow"][category] is True` -- a blanket per-category
        allow, the general mechanism every category shares.
      - for `DELETE_REF` only, `target` named in
        `options["verified_landed_branches"]` -- a policy author's own
        per-branch declaration that THEIR OWN process already verified
        this branch's work landed. See the module docstring's "verified-
        landed-branch-deletion carve-out" section for why this is a named
        list rather than an automatic check.

    Anything malformed (not a mapping, not a list) is treated as "nothing
    declared" rather than raised -- this rule never lets a policy-authoring
    mistake turn into an exception that denies by accident.
    """
    allow = options.get("allow") if isinstance(options, Mapping) else None
    if isinstance(allow, Mapping) and allow.get(category) is True:
        return True

    if category == DELETE_REF and target:
        verified = options.get("verified_landed_branches") if isinstance(options, Mapping) else None
        if isinstance(verified, (list, tuple)) and target in verified:
            return True

    return False


_REASONS = {
    SETTINGS_CHANGE: "a repository settings change",
    FORCE_PUSH: "a force-push",
    HISTORY_REWRITE: "a history rewrite",
    DELETE_REF: "deleting a remote ref",
}


def evaluate(event: Event, config: RuleConfig):
    """Warn (or deny) on an unauthorised destructive command.

    Returns None -- silently, with no opinion -- for every event that is
    not a Bash command, every command that does not match one of the four
    categories (including every merge, per D19), and every match this rule
    cannot honestly judge because the adapter gathered no repo facts.
    """
    from ..engine import Finding  # local import: engine imports this module.

    if event.hook_event != "PreToolUse" or event.tool_name != _TOOL_NAME:
        return None

    command = event.tool_input.get(_COMMAND_KEY)
    if not isinstance(command, str) or not command.strip():
        return None

    category, target = _classify_command(command)
    if category is None:
        # The overwhelming majority of Bash calls land here, same as
        # lwb_proof_required -- and so does every merge, per D19.
        return None

    repo = event.repo
    if repo is None:
        # The adapter gathered no repo facts -- absence of evidence, not
        # evidence of absence. Same discipline as lwb_proof_required: an
        # adapter that has not been taught to collect repo facts (today:
        # Codex) must not warn on every destructive command forever.
        return None
    if repo.facts_incomplete:
        # "Could not check" must never share a representation with
        # "checked, found nothing" -- same posture as lwb_proof_required.
        return None

    if _allowed(category, target, config.options):
        return None

    claim = f" ('{target}')" if target else ""
    return Finding(
        rule_id=rule_id,
        mode=config.mode,
        reason=(
            f"unauthorised destructive action: {_REASONS[category]}{claim}. "
            f"docs/handoff-protocol.md's hard rules require the owner's explicit "
            f"instruction for this; a consuming repo authorises it by setting "
            f"policy options.allow.{category} to true"
            + (
                ", or by naming this branch in options.verified_landed_branches "
                "once your own process has confirmed its work landed"
                if category == DELETE_REF
                else ""
            )
            + ". See docs/rules/lwb-no-unauthorised-destructive-action.md"
        ),
    )
