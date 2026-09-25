# Item 1.8 evidence: hook matcher name — 2026-09-25

Build plan item 1.8: "**Confirm the hook fires from `hooks.json`** — never
once observed in this product's life." This note narrows one specific
sub-question the earlier reviewer raised on that item, recorded in
`docs/maintainers/proof-of-completion-plan.md`'s finding 6: whether the
matcher name `plugins/claude/lwb/hooks/hooks.json` uses is even a live
tool name to filter on. It does not, and does not claim to, settle 1.8
itself — see "What this does NOT resolve" below.

## The risk as the earlier reviewer stated it (finding 6, quoted)

> **The shipped hook may match nothing at all — verify before 1.0.**
> `plugins/claude/lwb/hooks/hooks.json` uses `"matcher": "Agent"`. A
> `PreToolUse` matcher filters on the TOOL NAME. The docs check could not
> find a built-in tool documented as `Agent`, and named `Task` as the
> subagent-dispatch tool in the reference. If `Agent` is not a live tool
> name in the installed version, the only hook this product ships fires
> zero times — a seventh gate that cannot fail, and the one that would
> matter most to another repo installing this.

That finding also records that an in-session probe could not settle the
question (a mid-session edit to `.claude/settings.json` is never read by
the running session, so both a probe on `"Agent"` and a control probe on
the pre-existing matcher came back silent, which is uninformative rather
than a negative result).

## The resolution: checked against the official doc, twice, independently

On 2026-09-25 the specific naming question — is `Agent` a real, current
Claude Code tool name, or was the reviewer right that only `Task` exists —
was checked directly against Anthropic's own documentation,
`https://code.claude.com/docs/en/sub-agents.md`, via two independent
lookups (a research subagent's fetch, and a separate direct fetch of the
same URL from this session). Both returned the same text. The page's
section "Restrict which subagents can be spawned" states, verbatim:

> In version 2.1.63, the Task tool was renamed to Agent. Existing
> `Task(...)` references in settings and agent definitions still work as
> aliases.

**Correction (2026-09-25, same day, independent reviewer B's DISAGREE on
this PR's first head):** the version of this note first committed also
claimed that `sub-agents.md` itself contains a worked `PreToolUse`
hook-matcher example using `"matcher": "Agent"`. That claim was false —
reviewer B reproduced it (`grep -c -F '"matcher": "Agent"' sub-agents.md`
→ `0`, on two independently-fetched, identically-hashed copies of the
page) and this session independently re-confirmed the same negative
result before writing this correction. What sits next to the rename note
on that page is a `tools:` frontmatter allowlist example
(`tools: Agent(worker, researcher), Read, Bash`), not a hook matcher.

The correct citation for `Agent` as a matchable `PreToolUse` tool name is
`https://code.claude.com/docs/en/hooks.md`, its `PreToolUse` section,
verbatim (confirmed directly against the raw page fetched in this
session):

> Runs after Claude creates tool parameters and before processing the
> tool call. Matches on any tool name except `EndConversation`: built-in
> tools such as `Bash`, `PowerShell`, `Edit`, `Write`, `Read`, `Glob`,
> `Grep`, `Agent`, `Workflow`, `WebFetch`, `WebSearch`, `AskUserQuestion`,
> and `ExitPlanMode`, and any MCP tool names.

That page explicitly lists `Agent` as a built-in tool name `PreToolUse`
can match on — the same string `plugins/claude/lwb/hooks/hooks.json`
already ships. The rename-note citation stands unchanged; only the
hook-matcher-example citation is replaced.

## What this narrows

The earlier reviewer's specific fear — that `Agent` names no real tool at
all, so the hook's matcher is dead on arrival and the shipped hook "fires
zero times" by construction, independent of any Claude Code runtime
behavior — is resolved. `Agent` is the current, documented, canonical tool
name for subagent dispatch as of Claude Code 2.1.63+ (`sub-agents.md`),
and the hooks reference (`hooks.md`) explicitly lists `Agent` among the
built-in tool names its `PreToolUse` event matches on. `Task` still
works, per `sub-agents.md`, only as a backward-compatible alias. The
shipped `hooks.json` is not naming a nonexistent tool.

## What this does NOT resolve — still open

This is documentation evidence about a tool name, not an empirical
observation of the shipped hook firing inside a real, running Claude Code
session. Build plan Phase 6 ("Drive a real repo") reserves that question
for itself, in its own words: *"This phase settles the question open
since the product began: does the hook fire when Claude Code dispatches
it? ... In a real repo either it fires or it does not."* Nothing in this
note is evidence toward that empirical question one way or the other:

- No probe was run in this session. The prior probe's own conclusion
  stands unchanged: a mid-session `.claude/settings.json` edit is not
  read by the running session, so any probe attempted the same way would
  be uninformative for the same reason the earlier one was.
- Doc text describing what a matcher *should* match is not the same claim
  as a specific installed runtime actually dispatching the hook when
  `Agent` fires — version skew, packaging differences, or an
  installation-specific quirk could all still produce a silent
  zero-fire hook even with a correctly named matcher.
- This note makes no claim about whether the hook has ever fired in this
  product's life. Finding 6's opening sentence ("never once observed")
  is unchanged by anything here.

**Verdict: NARROWS the risk in finding 6 — the matcher names a real,
current, documented tool (`hooks.md`'s `PreToolUse` tool-name list), and
the rename from `Task` is independently confirmed (`sub-agents.md`) —
but does NOT close item 1.8. The empirical firing-observation question
stays open and is Phase 6's job to settle. An earlier version of this
note also cited a `PreToolUse` hook-matcher JSON example on `sub-agents.md`
that does not exist there; that citation is corrected above, and the
underlying conclusion (evidenced by `hooks.md` instead) is unchanged.**
