---
description: Triage eligible backlog issues into a queue you approve once, then build each fix in a fresh worktree, open a PR and run /review-loop on it
argument-hint: [--max-prs N] [--issue N] [--new] [--ask-decisions]
---

# Backlog Sprint

A thin orchestrator over `/backlog` and `/review-loop`. It triages the open
issues into a queue, asks you to approve the queue **once**, then works it one
issue at a time: an implementer agent builds the fix in a fresh worktree by
following `/backlog`'s steps and opens a PR; then this session runs
`/review-loop` on that PR, which merges it when the verdict is `ready`. A
`decision_needed` PR stays open and its questions go into the end-of-sprint
report, along with each PR's outcome and cost.

The sprint re-implements nothing from either command. Worktree setup, the
implementation rules and the pre-PR checks are `/backlog` steps 4-8; review,
fixing, the verdict, the merge and the metrics line are `/review-loop`. To
change those steps, change them there.

Needs: everything `/review-loop` needs, plus `jq`.

## Arguments

- `--max-prs N`: stop cleanly after N queued items reach a final status.
  Default 3 (or `sprint.max_prs` in the config). The next run continues the
  queue.
- `--issue N`: skip triage and approval and run that one issue. Naming it is
  the approval.
- `--new`: ignore an unfinished sprint and start fresh (the old state file is
  renamed, not deleted).
- `--ask-decisions`: passed through to every `/review-loop` run, which then
  stops at every decision instead of taking its own recommendation.

## Config

Reads `.claude/review-loop.json` (the same file `/review-loop` reads). The
sprint uses `risky_paths` and an optional `sprint` object:

| Key | Default | Used for |
|---|---|---|
| `sprint.max_prs` | `3` | Default for `--max-prs` |
| `sprint.skip_labels` | `[]` | Issues with any of these labels are never queued (e.g. a platform you don't run, `needs-design`) |
| `sprint.evidence_labels` | `[]` | Labels that mark an issue as seen failing for real (`incident`, `customer-reported`) |
| `sprint.evidence_patterns` | `[]` | Regexes in an issue body that count as evidence (`Sentry-\d+`, `Found by /eod-review`) |
| `sprint.implementer_model` | `opus` | Model for the implementer agent |

## Why the sprint has rules

These come from running the original version of this command for a few
weeks on a busy repo:

- **One issue in flight at a time.** A one-round issue cost roughly 0.7-0.8M
  tokens all-in, a multi-round one two to three times that. One lane keeps the
  usage window predictable and means two PRs never build on the same files at
  once.
- **The loop merges.** Running the sprint is the authorisation for
  `/review-loop` to merge `ready` PRs; its own checks (verified head, CI
  green, no `hold`/`do-not-merge` label) are the gate. The sprint adds none.
- **No branch update once the loop starts.** The loop never updates a branch
  to make a merge go through, and any push after verification makes the head
  unverified. So the sprint checks for a file overlap with the base branch
  once, right before the loop, and only then updates.
- **Follow-ups of follow-ups are design problems.** Over half the eligible
  issues one week were filed by the loop itself, in chains (issue → PR →
  follow-up → PR → follow-up ...). Depth-1 issues (filed on a PR whose issue
  a person wrote) are worked; depth 2+ is skipped and listed per root issue
  for a **design pass**: one note that retires a set of follow-ups beats
  patching them one PR at a time.
- **A value floor.** In the same period 44% of loop-merged PRs fixed issues
  the loop had filed, and many were `priority:low`. A loop-filed, low-priority
  issue with no due date, risky path, evidence or dependents is not queued
  unless a person vouches for it.
- **The loop runs in this session, not in an agent.** `/review-loop` spawns
  its reviewers and fixer as agents, and an agent cannot spawn agents. Handed
  to a loop-runner agent, the loop either reviewed on the wrong model with no
  fresh reviewer, or stopped without reviewing. Run from here, the reviewers
  are still fresh Opus agents that see only the PR.

## Terms

**Eligible issue:** a clear code fix: `type:bug`, `type:debt` or
`type:enhancement` with an `## Acceptance Criteria` checklist (`- [ ]`). Not:
features, epics, parked issues (`waiting:*`, `stays open`), the ledger issue,
`sprint.skip_labels`, anything another session owns (a worktree or open PR
carrying its number), chain depth 2+ (except a `priority:high` follow-up on a
risky path, kept with a warning), and not a **low-value** follow-up.

`.claude/scripts/backlog_sprint_triage.py` applies these rules and orders the
rest by value per review round:

| Tier | Meaning |
|---|---|
| 0 | **Due**: an ISO date on a line that says due, deadline, no later than, must land or land by, from 30 days ago to 14 days ahead |
| 1 | A **risky path** (the body cites a `risky_paths` match) **with evidence** (`Introduced by: PR #N`, an evidence label or pattern) |
| 2 | One of risky path, evidence or **unblocks** (open issues parked `waiting:issue on #N` for it) |
| 3 | The rest |

Within a tier: priority, type (bug, debt, enhancement), files cited (fewer
first), number. Each issue prints a `why now:` line with those facts and its
`## Why now` section, if `/backlog-add` wrote one. A small risky-path bug with
evidence outranks a large one labelled high, because review cost is rounds and
small PRs take far fewer.

**Low value:** a loop-filed issue (chain depth 1) whose highest priority is
`priority:low`, that is tier 3, and has no `sprint:keep` label or `## Why now`
note. Listed under **Low value, not queued**, oldest first. Raising the
priority, adding evidence or adding `sprint:keep` queues it again.

**Stop rule:** when every eligible issue is tier 3, there is no design pass
and no late follow-up, and none has a `## Why now` note or `priority:high`,
triage prints a `STOP:` line and the sprint recommends an empty queue.

**Chain depth:** the number of `Found by /review-loop on PR #M` footers
followed from the issue back to one without a footer (the root). Depth 1 is
eligible; depth 2+ is not, unless it has the `design:patch-separately` label
(a person adds it when the root's design note says to patch it on its own).
A follow-up filed **after** its root's latest design note is listed under
**Filed after the root's design note** for a per-issue choice, since no later
pass replans it.

**Design pass:** an item for a chain root with at least one skipped depth-2+
follow-up, and two or more counting warned risky-path ones kept eligible. The
sprint posts one design note on the root issue and opens no PR (step 3d).

**Design plan:** what a design pass returns beside its note: one action per
follow-up: `patch` (add `design:patch-separately`), `close_fixed`,
`close_not_worth`, or `check` (can't tell). The agent changes nothing; step 4
asks once and applies the plan you approve. A `close_fixed` carries one
evidence line per acceptance criterion (or per item of the body's own list of
failures when it has no checklist), each a file:line or test path on the base
branch that the agent opened. Any item without an evidence line makes it
`check`, never `close_fixed`: closing on a one-line summary when most items
were unverified is how issues get wrongly closed. A `close_not_worth` needs
one evidence line too: the fact it rests on.

**Bundle:** two or three eligible issues citing the same code file, built in
one PR that closes all of them. Each extra PR on the same file is another
chance for review to file the next follow-up. A bundle is one queue item: the
lead's number is the item, the others ride in `bundle`. The cap is the
implementer's PR-size limit, not the issue count.

**Final statuses:** `merged`, `ready`, `decision_needed`, `blocked`,
`failed`, `locked`, `design_posted`. **In flight:** `implementing`,
`pr_open`, `loop_running`, `designing`, `stopped`.

**Sprint state:** `<sd>/state.json`, where `<sd>` is
`<main>/.git/backlog-sprint`, in the main
repository's git dir so it outlives worktrees and sessions:

```json
{"sprint_id": "2026-06-15T20:14Z", "started_at": "...", "max_prs": 3,
 "triage": {"skipped_chains": {"40": [52, 57]}, "skipped_ages": {"52": 12},
            "late_follow_ups": {"61": {"root": 40, "choice": "patch", "at": "..."}}},
 "queue": [
   {"issue": 48, "kind": "issue|design", "title": "...", "follow_ups": [], "bundle": [],
    "status": "queued|implementing|pr_open|loop_running|stopped|designing|merged|ready|decision_needed|blocked|failed|locked|design_posted",
    "pr": null, "branch": null, "worktree": null, "head": null, "updated_from_base": false,
    "implementer": {"model": "opus", "tokens": null, "minutes": null, "agent": null},
    "design": {"tokens": null, "minutes": null, "agent": null, "comment_url": null,
               "recommended": null, "plan": [], "plan_applied": null},
    "verdict": null, "merge_sha": null, "rounds": null,
    "decisions": [], "auto_accepted": [], "issues_filed": [], "note": null}]}
```

Agent `tokens` and `minutes` are copied from the Agent result's usage line,
never estimated; `null` when it doesn't report them. Read and write the file
with the Read and Write tools (whole file each time), and take times from
`python3 .claude/scripts/workflow_state.py now`, never from memory.

**Models** (pass `model` on every Agent spawn; never leave it to inherit):

| Role | Model |
|---|---|
| Orchestrator (this session) | Sonnet is enough; start a fresh session with `/model sonnet` |
| Implementer | `sprint.implementer_model`, default `opus`. A better first draft is cheap: the implementer is a small share of a PR's tokens, and PRs whose round 1 found nothing to fix cost far less in review |
| `/review-loop` | runs in this session (step 3c); it picks its own reviewer and fixer models |
| Branch updater (only on a file overlap) | `sonnet` |
| Design pass | `opus`; it reads, writes one comment, changes no file |

## Instructions

Run from the main checkout or any worktree; the sprint itself edits no
tracked file.

**One command per Bash call, values spelled out.** Permission allowlists
match command text, so a call that starts with `VAR=...`, uses `$(...)`,
chains with `&&`, or writes into `.git/` with `mkdir`, `rm`, `mv` or `>>` is
denied in unattended runs, and the sprint can't start. Get the values once
and write them literally (quoted when a path has a space) in every later
call:

```bash
python3 .claude/scripts/workflow_state.py paths
python3 .claude/scripts/workflow_state.py statedir backlog-sprint --common
```

`paths` gives `<main>` (the main checkout) and `<base>` (the default
branch); `statedir` creates and prints `<sd>`. If a step below is denied
anyway, don't stop: say which command was denied and do the step with
`workflow_state.py`, `git -C`, or the Read and Write tools.

### 1. Lock, then load or start the sprint

**Take the sprint lock first**, the same way `/review-loop` takes its lock:

```bash
python3 .claude/scripts/workflow_state.py lock acquire backlog-sprint --common
```

It replaces a lock whose pid is dead or this session's own. Exit 3: another
sprint is running; stop and say so with the holder's pid, start time and the
lock path, and add "if that session is idle or stopped, close it or delete
the lock and run again". **Every stop of the run releases the lock**, except
that one:

```bash
python3 .claude/scripts/workflow_state.py lock release backlog-sprint --common
```

Then read `<sd>/state.json` with the Read tool, if it exists.

- **An unfinished sprint** (any item not final) and no `--new`: resume it.
  Say which items are in flight and carry on at step 3 with the same queue;
  `--max-prs` counts only items finished in this run. First, if `ListAgents`
  shows an agent of this sprint still running in this session, wait for its
  notification rather than spawning a second one on the same item. Re-run the
  triage script (step 2, no approval) and mark any `queued` issue item that is
  now closed or `in_progress` elsewhere as `blocked` with that note; for a
  queued bundle, drop members that are closed or in progress, and say which. A
  queued design item is `blocked` only if its root is no longer in the
  script's `design_passes`. These don't count toward `--max-prs`.

  Rebuild each in-flight item's truth from GitHub, not the file:
  - `implementing`: `gh pr list --head "<branch>" --state open --json number,headRefName`
    (else `gh pr list --search "head:fix/<issue>-"`). A PR exists: move to
    `pr_open` and record `pr`, `branch` and `worktree` (from
    `workflow_state.py worktree find <branch>`; else `<main>/.claude/worktrees/<issue>`).
    No PR but the worktree exists: spawn a new implementer (step 3a) and tell
    it the worktree may hold a previous implementer's uncommitted work: keep
    what matches the criteria, finish the rest, never `git checkout --` or
    `git reset` it. No worktree either: a fresh implementer.
  - `designing`: look on the root for a comment headed
    `## Design note (/backlog-sprint <sprint_id>)`. Found: `design_posted`
    with its URL. Not found: spawn the design agent again (step 3d).
  - `pr_open`: step 3b. `loop_running` or `stopped`: step 3b's overlap check,
    then step 3c; `/review-loop` resumes itself from its own state file.
- **`--new`, or every item is final:** write the old file's content to
  `<sd>/state.<sprint_id>.json` (Write tool) and start a new sprint with a fresh `sprint_id`
  (UTC, minute precision) and `max_prs`.
- **`--issue N`:** the queue is that one issue. With an unfinished sprint and
  no `--new`, resuming wins: say so and ask for `--new`. Otherwise start a new
  sprint with a one-issue queue. Still run the triage script so the report can
  say whether the issue would have been skipped and why, but don't ask for
  approval.

### 2. Triage and approve the queue

```bash
python3 .claude/scripts/backlog_sprint_triage.py --repo "<main>" --out "<sd>/triage.json"
```

Exit 2 is a failure (a config error or a `gh` call): show the error and stop.
Otherwise show the output as is: design passes, the eligible list in queue
order with each `why now:` line, bundle candidates, "may already be fixed",
the ledger sweep, chain roots with their skipped follow-ups, and the other
groups.

- **May already be fixed:** for each eligible issue listed, read the commit
  (`git -C "<main>" show -s <sha>`) before asking, say which look fixed, and
  leave those out of the recommended queue. The list is a prompt: a squash
  body also names issues it only refers to.
- **Ledger sweep:** say which lines, if any, describe a failure that has
  actually happened, and offer to promote them with `/backlog-add`.
- **Filed after the root's design note:** ask about these first, with
  AskUserQuestion, one question per follow-up (at most four per call), options
  `patch`, `close_fixed`, `close_not_worth`, `check`, naming the root, the
  note's date and the follow-up's age. No option is recommended: no plan
  covers these. Apply the answers before the queue question:
  - `patch`: `gh issue edit N --add-label design:patch-separately`, and offer
    it at the end of the queue question if it has an acceptance-criteria
    checklist.
  - `close_fixed` / `close_not_worth`: the owner's answer isn't evidence.
    Open the files first and put the evidence lines the Design plan requires
    in the closing comment (`gh issue close N --reason completed|"not planned" --comment ...`,
    saying the owner chose it in sprint `<sprint_id>`). An item with no
    evidence stays open and is treated as `check`.
  - `check`: park it so it isn't asked about every sprint:
    `gh issue edit N --add-label waiting:decision` and a comment whose first
    line is exactly `Parked: waiting:decision`, with what to check on the next
    line.
  Record each answer in `triage.late_follow_ups`.
- **Low value, not queued:** if any listed issue is 7 or more days old, ask
  once (AskUserQuestion, multiSelect, the four oldest; say how many more are
  listed) which to close as not worth it. No option is recommended. Skip one
  the "may already be fixed" list names: read its commit first. Close each
  pick with `gh issue close N --reason "not planned" --comment ...` giving the
  fact it rests on. Never queue one unless the owner names it (then add
  `sprint:keep`).
- **STOP line:** the recommended option below is an empty queue; end the
  sprint after step 4's report with `0 of 0 worked`, unless the owner names
  items.

Then ask **once**, with AskUserQuestion: approve the design passes followed by
the eligible list as the queue, with bundles as printed (**recommended**,
because the order is by value per review round and the cap limits the run),
or the same without bundles, or name the items to run in order (`48+51` for a
bundle, `design #40` for a design pass, a bare number for an issue).

Record the approved queue with every item `queued` and its `kind`. A design
item's `issue` is the root and it carries `follow_ups` and
`eligible_follow_ups`; a bundle's `issue` is its lead and it carries
`bundle`. Copy the triage file's `chains` into `triage.skipped_chains` and
`chain_ages` into `triage.skipped_ages`. An item triage printed with a
`WARNING:` gets `note: "chain follow-up of #R: read its design note first"`.
Issues the loop files during this sprint are not added to the queue; they show
up in the report.

### 3. Work the queue, one item at a time

Take the first item that isn't final: design items before issue items, each
kind in queue order. Stop when `--max-prs` items have reached a final status
in this run, or when an agent stopped on a usage limit. Never start a second
item while one is in flight. A `design` item goes to 3d; an `issue` item to
3a.

#### 3a. Implement

Set the item `implementing`, record `started_at` and `implementer.model`, and
spawn a **fresh** `general-purpose` agent (not a fork: it must not inherit
this session's reading of the issue) with `model` from `implementer_model`.
Its brief, verbatim apart from the numbers and paths:

> You are the implementer for backlog issue #N in a sprint. Do all work in
> one worktree, `<main>/.claude/worktrees/N`; never touch the main checkout or
> any other worktree.
>
> 1. Invoke the Skill tool with skill `backlog` and args `N`, and follow its
>    steps 4 to 8 exactly: read the issue and its last comments, extract the
>    acceptance criteria, make the plan, create the worktree on a branch
>    `fix/N-<slug>` off `origin/<base>` with one command,
>    `python3 .claude/scripts/workflow_state.py worktree add N fix/N-<slug> --start origin/<base> --link .venv`
>    (one `--link` per gitignored file the tests need), implement, write the tests, run the
>    size check, lint and tests, then open the PR with
>    `gh pr create --head <branch> --base <base> --title ... --body-file ...`.
>    The body says `Closes #N` (or `Refs #N` when the issue says it must stay
>    open) and ends with the line `Opened by /backlog-sprint`.
> 2. Never ask a question. Where `/backlog` would ask, take the option the
>    issue recommends, else the smallest reversible one, and list it in the PR
>    body under `## Decisions made by the implementer`.
> 3. Scope is the acceptance criteria. A criterion that needs a design
>    decision nobody has made: implement the others and list it under
>    `## Not done`.
> 4. A bug fix lands with a test that fails without the fix. A test on code
>    that branches on the hour or date uses a fixed time, never `now - delta`.
> 5. Stop and return `blocked` instead of opening a PR when: the worktree
>    exists with changes you did not make (unless this brief says a previous
>    implementer left them); the issue needs production data, credentials or
>    a manual production step; the change can't stay under about 600 added
>    lines outside tests and docs without a split; or the acceptance criteria
>    contradict the code as it is today. Say which in `note`.
> 6. Do not run `/review-loop`, do not merge, do not add labels, do not
>    comment on the issue.
> 7. The PR title must not match `fix: #N` (GitHub closes issues from the
>    squash title); say what changed instead.
> 8. Run every shell step as one command with literal paths: `git -C <path>`,
>    never `cd <path> && ...`; no `VAR=...` or `$(...)`; commit with
>    `-m "..."` arguments, not a heredoc; write the PR body with the Write
>    tool to `<sd>/pr-body-N.md` (never inside the worktree: an untracked
>    file there blocks its removal) and pass it with `--body-file`. Run lint
>    and tests with
>    `python3 .claude/scripts/workflow_state.py check lint --worktree <worktree>`
>    and `... check test --worktree <worktree> --tests <paths>` (exit 2: none
>    configured, use the project's runner). Unattended runs deny the rest.
>
> Return JSON only:
> `{"status": "pr_open|blocked|failed", "issue": N, "pr": M, "url": "...",
> "branch": "...", "worktree": "...", "head": "<sha>", "tests_run": [...],
> "decisions": [...], "not_done": [...], "note": "..."}`

- **An item whose `note` starts `chain follow-up of #R`:** add after item 1:
  "This issue is a chain follow-up of #R: read #R's latest `## Design note`
  comment (if any) before planning, and say in the PR body what it changed in
  your plan."
- **A bundle item:** add after item 1: "This PR also closes #M1 (and #M2).
  Read each issue and its criteria first. The body says `Closes #N`,
  `Closes #M1` (one per line). Build them in order, each with its own test. If
  the combined change would pass ~600 added lines outside tests and docs, stop
  at the member that would cross it, open the PR with the members done so far,
  and list the rest under `## Not done` and in `not_done`."

When the result comes back, record `implementer.tokens`, `minutes` and the
`agent` id. Then **check the claims from GitHub**:
`gh pr view <M> --json headRefOid,headRefName,body,state,isDraft` must show an
open, non-draft PR on the branch with `Closes #N`/`Refs #N` (and a `Closes`
for each bundle member not in `not_done`) and the `Opened by /backlog-sprint`
line. A missing or wrong PR is `failed` (note why), final, not retried this
run. `blocked` is final too, with its note. Otherwise set `pr_open`, `pr`,
`branch`, `worktree`, `head`.

#### 3b. Check for a file overlap with the base branch

The base branch may have moved since the branch point, mostly on a resumed
sprint:

```bash
python3 .claude/scripts/workflow_state.py overlap <base> --worktree "<worktree from the state>"
```

- **No common file** (`files` is empty): leave the branch alone.
- **A common file:** spawn a `general-purpose` agent, `model: sonnet`, in that
  worktree: merge `origin/<base>` into the branch (`git merge`, no rebase, no
  force-push), resolve conflicts keeping the PR's intent, re-run the PR's tests
  and lint, commit, `git push origin HEAD:<branch>`, and return
  `{"merged_base": true, "head": "<sha>", "conflicts": [...]}`. Record
  `updated_from_base: true` and the new `head`. This runs only here, never
  after the loop has started: the loop's round 1 then reviews the merged state.

#### 3c. Check the loop's lock, then run the loop

```bash
python3 .claude/scripts/workflow_state.py lock show review-loop --worktree "<worktree from the state>"
```

`alive` and not `ours`: another session's loop is
on this PR. Set the item `locked` (final), note the pid, start time and lock
path, add "if that session is idle or stopped, delete the lock and re-run
`/review-loop <M>` from the PR's worktree", count it toward `--max-prs`, and
move on. A dead pid, this session's own, or no lock: proceed; the loop
reclaims the lock itself.

Set `loop_running` and save the state. Then invoke the Skill tool with skill
`review-loop` and args `M` (plus `--ask-decisions` if the sprint got it)
**in this session**, from the PR's worktree, and follow it to the end: every
round, the verdict, the merge when `ready`, and its metrics line. Never spawn
an agent to run the loop. Give each reviewer only the brief the loop gives
it: nothing from this session's reading of the issue or the implementer's
report. While the loop runs its rules apply; when it ends, carry on here:

- Where the loop would stop to ask you something, don't ask: record the
  question with its recommendation in the item's `decisions` and treat the
  loop as ended. A `decision_needed` verdict is a normal end.
- A usage limit mid-loop: set the item `stopped`, note it, and **end the run
  now** (step 4). It's the one case where starting the next item is wrong.
  The loop resumes from its own state file when run again.

When the loop ends, **check from GitHub**, not from what the loop printed:
`gh pr view <M> --json state,mergedAt,mergeCommit,labels`. Merged: `merged`
and `merge_sha`. Open with `review:decision-needed`: `decision_needed`, copy
the loop's decisions. Open with `review:ready`, not merged: `ready`, note the
loop's reason. Anything else (no `review:*` label and no usage limit: the loop
ended unfinished or crashed): `failed` with what happened; it is final, and
`/review-loop <M>` resumes it by hand. Also record the issues the loop filed,
its `auto_accepted` decisions and `rounds`, and save the state.

Read the loop's metrics line for this PR (the highest `run`):

```bash
python3 .claude/scripts/workflow_state.py metrics-show --pr <M>
```

Go back to the top of step 3.

#### 3d. Design pass on a chain root

Set the item `designing` and spawn a **fresh** `general-purpose` agent with
`model: opus` (judgment over several issues' worth of code). Its brief,
verbatim apart from the numbers:

> Root issue #R has these open follow-ups filed by /review-loop on the PRs
> that fixed it: #A, #B, .... (If the item has `eligible_follow_ups`, add:
> "Also read #X, which is queued separately for its own PR; use it as context
> but do not plan it or give it a `plan` entry.") Read the root, every
> follow-up, and the merged PRs their footers name (`gh issue view`,
> `gh pr view --json body,files,mergeCommit`), then the code they touch at
> `origin/<base>`. Do not change any file and do not open a PR.
>
> Write one design note, at most 60 lines, and post it as a comment on #R with
> `gh issue comment R --body-file <sd>/design-R.md` (write the file with the
> Write tool; one command per Bash call, no `cd ... &&`), headed
> `## Design note (/backlog-sprint <sprint_id>)`. It says: (1) the pattern the
> follow-ups share, in two or three sentences, with file:line evidence; (2) one
> change that would retire most of them, with the files it touches and the
> follow-ups it closes by number; (3) which follow-ups it would not close and
> why; (4) a recommended next step with a `because`, choosing between that
> change, patching the follow-ups one at a time, and closing some as not worth
> it. No label changes, no edits to the follow-ups.
>
> Then give every follow-up one action in the JSON `plan`. `patch`: fix it on
> its own. `close_fixed`: `origin/<base>` already does what every acceptance
> criterion asks; give one `evidence` line per criterion, each a file:line or
> test path you opened (a merged PR is not evidence by itself: a PR can close
> fewer items than its issue lists). With no checklist, one evidence line per
> item in the body's own list of failures, each starting with that item's
> text. If any criterion or item has no evidence line, the action is `check`.
> `close_not_worth`: say what would make it worth reopening, and give one
> evidence line, the fact it rests on. `check`: you could not tell; say what to
> look at. Two follow-ups that touch the same code and should be one PR: give
> both `patch` and set `bundle_with` on each to the other's number.
>
> Return JSON only: `{"root": R, "comment_url": "...", "retires": [...],
> "keeps": [...], "recommended": "...", "plan": [{"issue": N, "action":
> "patch|close_fixed|close_not_worth|check", "why": "...", "evidence": [...],
> "bundle_with": []}]}`

When it returns, record `design.tokens`/`minutes`/`agent`, check the comment
exists (`gh issue view R --json comments`), and set the item `design_posted`
(final) with `comment_url`, `recommended` and `plan`. Before storing the plan:
make any `close_fixed` or `close_not_worth` entry with empty evidence, or
fewer evidence lines than the issue has criteria (or list items), a `check`;
and drop any entry whose issue isn't in the item's `follow_ups`, noting it, so
step 4 never closes an issue queued on its own. Count it toward `--max-prs`.
No comment: if the agent stopped on a usage limit, leave it `designing` and
**end the run now**; otherwise `failed` with the agent's note.

### 4. Report

Print the report and save it to `<sd>/report.<sprint_id>.md` with the Write tool, then release the
lock.

```markdown
## Sprint <sprint_id>: <n> of <queue length> worked, <merged> merged, <decision_needed> waiting on you

**Decisions waiting on you**    <- first, one block per decision_needed PR
- PR #M (#N <title>): <question>. Recommended: <option>, because <...>. <status comment URL>

| Issue | PR | Verdict | Merged | Rounds | Implementer (tokens / min) | Loop (runs / tokens / min) |
|---|---|---|---|---|---|---|

**Accepted on your behalf:** one line per `auto_accepted` entry: PR, question, option taken, because.
**Design notes posted:** root, comment URL, the recommended next step, and its plan grouped by action, each follow-up with its one-line `why`.
**Not worked:** blocked/failed/locked/stopped items with their notes; queued items left for the next run.
**Issues filed by the loops this sprint** (not queued): #..., #...
**Inflow:** <F> filed by the loops, <C> closed (each merged item whose PR said `Closes`, plus bundle members not in `not_done`). F at or above C means the sprint added as many issues as it closed.
**Triage:** chain roots and their skipped follow-ups with ages (`#52 (15d)`); late follow-ups and the choice made for each.
**Worktrees:** the loop removes a merged PR's worktree; list the ones still present with their paths.
```

Loop figures come from the metrics line (`agent_runs`, `agent_tokens.total`,
`wall_minutes`).

**Apply the design plans.** If any `design_posted` item has a plan and its
`plan_applied` is null, ask once with AskUserQuestion, after the report is
printed: apply every plan as written (**recommended**), apply only the
`patch` labels, or apply nothing. On approval: add `design:patch-separately`
to each `patch` issue, and close each `close_fixed` and `close_not_worth`
issue with a comment carrying its `why` and, for `close_fixed`, its evidence
lines (`gh issue close N --reason completed|"not planned" --comment ...`).
`check` issues are listed and left alone. Set `plan_applied` to the answer
(`all`, `patch_only` or `none`) and the time. A pair with `bundle_with` is
only listed: to build it as one PR, name it `A+B` at the next approval.
Closing is outward-facing: it happens only on this approval, never from the
agent.

Then stop. Nothing resumes on its own and nothing is scheduled; run
`/backlog-sprint` again to continue the queue.

### Stopping on a usage limit

If the orchestrator itself is about to hit the usage window, finish the
current step's bookkeeping (state file first), print the report for what has
finished, release the lock, and stop. An agent that stopped on a usage limit
in this same session is continued with SendMessage rather than re-spawned; in
a new session, step 1 re-spawns the implementer or re-runs `/review-loop <M>`
from the state.
