---
description: Review a PR, fix the findings, re-review the fixes, then merge it if the verdict is ready
argument-hint: <PR number> [--max-deltas N] [--level low|medium|high|xhigh|max] [--no-merge] [--ask-decisions]
---

# Review Loop

Run review → fix → re-review on one open PR, end with a **verdict**, and merge
the PR when the verdict is `ready`. A PR that needs a human gets at most three
numbered questions, each with a recommended default, and is not merged.

Needs: the `gh` CLI, the Agent tool (subagents), and Claude Code's built-in
`/code-review` skill. Where `/code-review` is missing, the loop uses
`.claude/commands/review-fallback.md` instead (see step 4).

## Arguments

- `$ARGUMENTS`: the PR number (required), then optional flags:
  - `--max-deltas N`: how many delta rounds (rounds 2+) may run before the
    closing review. Default 2.
  - `--level <level>`: the `/code-review` level for the closing review.
    Default `medium`. Round 1 always runs at `high`. `max` is by far the most
    expensive step; use it only when you want the deepest pass. Always pass a
    level to `/code-review`: without one it reuses the last level typed.
  - `--no-merge`: stop at the verdict and the `review:ready` label.
  - `--ask-decisions`: turn off default-accept (Terms). Every decision stops
    the loop at `decision_needed`.

## Project config

The loop reads `.claude/review-loop.json` if it exists (copy
`.claude/review-loop.json.example`). Every key is optional:

| Key | Default | Used for |
|---|---|---|
| `risky_paths` | `[]` | Paths where a missed bug is expensive (payments, auth, data). A risky PR gets the stronger fixer and always gets the closing review. Never blocks a merge. |
| `always_ask_paths` | `[]` (plus `.github/workflows/`, always) | A PR touching these never default-accepts a decision. |
| `lint_commands` | none | Run after every fix round. With none, read the CI workflow and run its lint steps. |
| `test_command` | none | `{tests}` is replaced with the test paths a fix touches. With none, use the project's usual runner. |
| `test_busy_exit_code` | `null` | If your test runner takes a lock (shared test DB) and exits with this code when busy, the loop waits and retries instead of failing. |
| `fix_budget_lines` | `150` | Most lines a single fix round may add outside `exclude_from_line_counts`. |
| `pr_size_warn_lines` | `600` | Report a PR above this as "split it next time". |
| `exclude_from_line_counts` | `["tests/","test/","docs/","*.md"]` | Not counted toward the two limits above. |
| `merge_method` | `squash` | `squash`, `merge` or `rebase`. |
| `ledger_issue_title` | `Review-loop ledger` | The issue that collects non-blocking notes. |

`.claude/scripts/review_loop_policy.py` applies `risky_paths` and
`always_ask_paths` to a changed-file list, so the rule is the same on every
run.

## Why the loop has rules

A plain "review until zero findings" loop doesn't end. On the project this
command came from, the first version ran on ten PRs:

- Every closing review found something. Only about a fifth of the findings
  changed code; the rest became follow-ups or were rejected. "Zero findings"
  was never reachable, so the loop ended on a round cap and flagged PRs for a
  human even when nothing was wrong.
- Each fix round wrote new code for the next review to find problems in.
  Nearly every blocking finding in a delta round was a bug in the previous
  fixer's code. A cosmetic fix in round 1 led to a real bug found in each of
  rounds 2, 3 and 4.
- PRs over about 1000 lines took 5 to 12 rounds; PRs under 400 took 3.
- Posting every finding inline put 35 to 120 comments on a PR, and filing a
  follow-up for each produced chains of follow-ups of follow-ups that nobody
  had asked to decide.
- The last fix commit was often never reviewed.

The rules below cut merge time from 2.4–37 hours to 0.6–2.4 hours:

1. **Blocking means reachable.** A finding blocks only if something that
   exists today can trigger it.
2. **Only confirmed blocking findings change code, in every round.**
   Everything else goes to the ledger. Rounds 2+ review only what the last
   round changed.
3. **Only a verified head merges:** a review of it confirmed nothing blocking
   and nothing was pushed since. The closing review runs once.
4. **Caps instead of heuristics:** `--max-deltas` delta rounds, a per-round
   fix budget, at most two issues filed per PR (one on a chain PR).
5. **One status comment per PR**, and inline comments only on findings that
   were fixed.
6. **The loop ends in a verdict**, not a label.
7. **A fixer runs only when there is something it could fix.**
8. **A follow-up of a follow-up is a design problem.** On a chain PR the loop
   files less and recommends a design pass on the chain's first issue.
9. **An issue has to be worth a PR.** File one only for a failure on a path
   that really runs (production, or the tooling the team runs daily). A real
   finding that only a dead script, a test helper or a docstring reaches goes
   to the ledger.

## Terms

**Blocking categories:** `correctness`, `test`, `test-coverage`, `security`,
and `conventions` when the convention is a written project rule (CLAUDE.md)
or a CI gate.

**Non-blocking categories:** `reuse`, `simplification`, `efficiency`,
`altitude`, `documentation`, `style`. These never go to a fixer. A category
on neither list goes to the fixer, which decides.

**Reachable:** a finding has a `reachable_via`: the file:line of a caller,
writer, query, config value, stored data or CI gate that can produce the
failure scenario today, in this repo. "A future caller could", "no current
writer produces this" and inputs no caller passes (a `str` subclass, an object
whose `__str__` raises) are not reachable, **except at a trust boundary**
(HTTP request bodies, third-party API payloads, user-edited config), where the
boundary itself is the path.

**Blocking finding:** a blocking category **and** reachable **and** confirmed
by the fixer. A finding that fails the reachability test is real but
non-blocking: it goes to the ledger.

**In scope:** the defect is in a line this PR changed, or this PR caused it,
**and** the fix stays within the issue's acceptance criteria. A fix that
would change a module the PR doesn't otherwise touch is out of scope. Tests
and docs the project's gates require are always in scope.

**Fix budget:** at most `fix_budget_lines` added lines per round (outside
`exclude_from_line_counts`). A fix that doesn't fit isn't written; it becomes
a `decision`.

**Verified head:** the head sha of a review that confirmed no blocking
findings, with nothing pushed afterwards. Recorded as `verified_head`.

**Chain PR:** the PR's linked issue was filed by this loop (its body contains
`Found by /review-loop on PR #`; search for it, don't test for the end of the
body). Follow those footers back (issue → PR → that PR's issue → ...) to the
first issue without one: the chain's **root issue**.

**Risky PR:** a changed file matches `risky_paths`. Risky picks the fixer's
model and keeps the closing review from being skipped. It does not stop a
merge.

**Verdict:**

| Verdict | Meaning |
|---|---|
| `ready` | The head is verified, the closing review has run (`closing_done`), CI is green on it, and no decision is open. Merges unless `--no-merge`. |
| `decision_needed` | A confirmed blocking finding is still open after the caps, or a fix would change behaviour in a way someone must accept. At most 3 questions, each with a recommended default. Not merged. |

**Every question carries a recommendation.** Whenever the loop asks the user
anything, it marks exactly one option **Recommended**, with a `because`
clause. Weigh, in this order: (1) what the issue's acceptance criteria ask
for; (2) which option leaves the least exposed on a risky path and is easiest
to undo; (3) the cost in added lines and review rounds (new code on a live
path has to earn its place with a reachable scenario). If two options are
close, recommend the cheaper, reversible one and say what fact would change
the call. Lead the final report with the first question and its
recommendation, so a one-word answer is enough.

**Default-accept.** Unless `--ask-decisions` is passed, when step 7 would end
the run at `decision_needed`, the loop takes each **Recommended** option
itself, without asking, only if all of these hold:

1. The PR's changed files pass the policy:
   ```bash
   git diff --name-only "origin/$BASE...HEAD" > "$STATE_DIR/files.txt"
   python3 .claude/scripts/review_loop_policy.py --files "$STATE_DIR/files.txt"
   ```
   Exit 0: allowed. Exit 1 or 2: ask (put its `reasons` in the report).
2. The recommended option does not leave a confirmed blocking finding open.
   "Merge with that finding ledgered" is never taken by default.
3. It does not close, retitle or re-scope the issue, file more than the issue
   cap, or override a CI gate.
4. No decision on this PR has been auto-accepted before (one cycle per PR).

If any decision fails a check, take none of them and end at
`decision_needed`. Otherwise apply each answer as step 3 applies an owner's
answer, record `auto_accepted: [{"question", "option", "because"}]` in the
state file, list them in the status comment under **Auto-accepted
decisions**, and go back to step 7. The closing review still runs, and step
10's conditions still decide the merge.

**Levels:**

| Pass | Level |
|---|---|
| Round 1, full PR | `high` |
| Rounds 2+, fix commits only | the loop's own fresh reviewer, which runs inputs (step 4) |
| Closing full review (once) | `medium`, or `--level`. Skipped on a non-risky PR when round 1's head is the verified head (step 8) |

Round 1 is the deep read. By the closing review every line the loop wrote
has had a delta review, so the closing pass is a confirmation; `medium`
reports fewer, surer findings. Never run `max` automatically: it can use most
of a usage window in an hour.

**Models** (pass `model` on every Agent spawn; never leave it to inherit):

| Role | Model |
|---|---|
| Orchestrator (this session) | Sonnet is enough: it runs commands, reads verdicts and posts. |
| Round 1, delta and closing reviewers | `opus`. `/code-review` runs as a fork of its caller, so the agent that invokes it must itself be Opus. |
| Fixer | `sonnet`; `opus` on a risky PR, where a wrong verify-or-scope call is costly |

Review is where quality comes from, so it never drops below Opus.

## Instructions

Shell variables (`$BASE`, `$MAIN`, `$W`, `$STATE_DIR`) don't persist between
Bash calls: set them again, or spell the values out, in each call that uses
them.

### 1. Load the PR and its scope

```bash
gh pr view <N> --json number,title,body,url,state,isDraft,headRefName,baseRefName,headRefOid,closingIssuesReferences,labels,additions,deletions
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
```

- Stop if the PR isn't open. Call its base `$BASE`; if it isn't the default
  branch, say so and ask whether to continue (recommend stopping if the base
  is another PR's branch that hasn't merged).
- Find the issue: `closingIssuesReferences`, else a `#N` in the body or the
  branch name. Read it: `gh issue view <issue> --json title,body,labels`.
  Write a **scope statement**: 2-4 lines on what the PR is meant to change
  and what it is not. Every in-scope call below is made against it. With no
  linked issue, build it from the PR body and say so in the report.
- **Chain PR?** Does the issue body contain `Found by /review-loop on PR #`?
  If so, follow the footers back to the root issue and record `chain: true`
  and `root_issue`.
- **Size.** If the PR adds more than `pr_size_warn_lines` outside
  `exclude_from_line_counts`, say so in the report: large PRs take far more
  rounds, and splitting before the loop is cheaper.
- **Risky?**
  ```bash
  git fetch -q origin "$BASE" "<head>"
  git diff --name-only "origin/$BASE...origin/<head>" | python3 .claude/scripts/review_loop_policy.py --files -
  ```
  Record `risky` and `risky_files` from the output in the state file.

### 2. Get a worktree on the PR branch

Never work in the main checkout: other sessions may be using it.

```bash
MAIN="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"   # the path may contain a space
git -C "$MAIN" fetch origin "<head>"
git -C "$MAIN" worktree list --porcelain | grep -B2 "branch refs/heads/<head>$"
```

- If a worktree already has `<head>` checked out, work there and run
  `git status`. Uncommitted changes there are the loop's own if the state
  file (step 3) shows a fix round with no `fixed_head`: an interrupted fixer
  left them; keep them and resume that round. Any other uncommitted changes
  aren't the loop's: stop, show `git status`, and ask, recommending a new
  worktree at `.claude/worktrees/pr-<N>-loop`. Otherwise
  `git pull --ff-only origin <head>`.
- Otherwise create one:
  ```bash
  W="$MAIN/.claude/worktrees/pr-<N>"
  git -C "$MAIN" worktree add "$W" -B "<head>" "origin/<head>"
  ```
  Symlink any gitignored files the tests need (`.env`, `node_modules`, a
  virtualenv) from `$MAIN`.

Do everything below inside that worktree.

### 3. Load or start the state file

The state lives in the worktree's private git dir, so it is never committed
and survives a new session:

```bash
STATE_DIR="$(git rev-parse --git-dir)/review-loop"; mkdir -p "$STATE_DIR"
cat "$STATE_DIR/lock" "$STATE_DIR/state.json" 2>/dev/null
```

**Take the lock first.** One loop per PR. `lock` holds `{"pid": <pid>,
"started_at": "..."}`, where `pid` is the Claude Code process (`$PPID` in a
Bash call). A lock whose pid is alive (`kill -0 <pid>`) and isn't this
session's means another loop is on this PR: stop, give the pid, start time
and lock path, and add "if that session is idle or stopped, delete the lock
and re-run". A dead pid, or this session's own pid (a resume), is stale:
`rm -f` it. Then write yours with noclobber so two starts can't both win:

```bash
(set -o noclobber; printf '{"pid": %s, "started_at": "%s"}\n' "$PPID" "$(date -u +%FT%TZ)" > "$STATE_DIR/lock")
```

If that fails, the other start won: re-read the lock and stop. Every stop of
this run removes the lock (`rm -f "$STATE_DIR/lock"`), except the stop
"another session holds the lock".

Shape:

```json
{"pr": 123, "issue": 120, "base": "main", "scope": "...", "max_deltas": 2,
 "risky": true, "risky_files": ["src/payments/charge.py"],
 "chain": false, "root_issue": null, "run": 1, "started_at": "2026-01-01T13:00:00Z",
 "status_comment_id": null, "ledger_comment_id": null,
 "verified_head": null, "closing_done": false, "closing_skipped": false,
 "reviewer": "code-review|fallback", "auto_accepted": [],
 "rounds": [
   {"n": 1, "kind": "full|delta|closing", "range": "origin/main...abc1234",
    "reviewed_head": "abc1234", "fixed_head": "def5678", "review_id": null,
    "started_at": "...", "ended_at": "...", "fixer_skipped": false, "ci_wait_minutes": 12.5,
    "findings": [
      {"path": "src/x.py", "line": 41, "category": "correctness",
       "reachable_via": "src/y.py:88", "blocking": true, "summary": "...",
       "verdict": "confirmed|rejected",
       "disposition": "fixed|decision|issue|ledger|rejected",
       "in_loop_code": false, "existing": false, "ref": "def5678 | #140 | ledger | evidence"}]}],
 "agents": [{"role": "round1|delta|fixer|closing", "round": 1, "model": "opus", "tokens": 143000, "minutes": 4.6}],
 "status": "running|ready|decision_needed|merged"}
```

`agents` gets one entry per Agent spawn when its result comes back: copy
`tokens` and `minutes` from the result's usage line; write `null` for a figure
it doesn't report, never an estimate. `in_loop_code` is true for a confirmed
blocking finding in a round 2+ or closing review whose line the loop's own
fix commits wrote (`git diff <round-1 reviewed_head>..<this reviewed_head>`).

- **No file:** start round 1 with `run: 1`.
- **An existing file:** add 1 to `run` first.
- **Last round has no `fixed_head` and undispositioned findings:** resume it
  at step 5.
- **`status` is `ready` or `merged`:** report it and stop, unless the PR head
  has moved since; then start a delta round on the new commits.
- **`status` is `decision_needed`:** if the user has answered (here or in a PR
  comment), record each answer and go to step 7. An answer that accepts a
  "leave it as is" option makes that finding a `ledger` line noted `accepted
  by owner: <option>`; an answer that picks a code option is a normal fix
  round (steps 5-6) whose commit gets a delta review. With no answer and no
  new commits, report the open questions again and stop.

A PR comment or review that isn't the loop's own (a human review,
`reviewDecision` `CHANGES_REQUESTED`) is a finding for this round's step 5.

**Resuming.** Running `/review-loop <N>` again is always safe; nothing
resumes on its own.

- An agent stopped on a usage limit in this same session: send it a message
  (SendMessage) to continue rather than starting a new one.
- A review in progress (round started, no findings recorded): run it again.
- A fixer in progress (findings recorded, no `fixed_head`): spawn a new fixer
  for the round and tell it the worktree may hold the previous fixer's
  uncommitted edits: check them against the findings, keep what's right,
  finish the rest. Never discard them with `git checkout --` or `git reset`.
- Posting half done: a round's review is saved as `review_id` as soon as it
  is posted, and the status comment is found by its marker. Never post a
  second review for a round that has a `review_id`.

**No local state (cloud or ephemeral sessions).** If the git dir won't
survive the session, also write the state into the status comment (step 6)
as a line `<!-- review-loop-state {...} -->` (escape `<` as `<` and `>`
as `>` in the JSON so finding text can't close the comment). With no
local file, look for that line first and resume from it.

### 4. Review

Reviewers return findings as JSON and **post nothing**; the orchestrator
posts once per round in step 6.

Every finding needs `path`, `line` (a line in the PR's diff), `category`, a
one-sentence `summary`, a concrete `failure_scenario` (inputs or state →
wrong output or crash), and `reachable_via` (file:line, or `null` if the
reviewer found none). No scenario, no finding.

**Which reviewer.** Use the `code-review` skill (`reviewer: "code-review"`).
If the Skill tool reports it missing or disabled, use
`.claude/commands/review-fallback.md` with the same arguments
(`reviewer: "fallback"`). Decide once, in round 1, record it, and use the same
one for the closing review. If neither can run, stop: an empty or failed
review is never a clean one, and the orchestrator never replaces a review by
reading the diff itself.

**Round 1: the whole PR, from a clean context.** Spawn a fresh agent
(`general-purpose`, `model: opus`) whose whole brief is: invoke the Skill
tool with skill `code-review` and args `high <N> --max-findings all` (or
follow `review-fallback.md` with `high <N>`), then return every finding as
`{"findings": [...]}` in the shape above, filling `reachable_via` from the
code (read the callers). Drop nothing. **Give it nothing else**: no scope
statement, no account of the change. `/code-review` runs as a fork and
inherits its caller's context; run from a session that wrote the PR, it would
start anchored on the author's reasoning. Without `--max-findings all` it caps
the count, and a capped round can look clean.

**Rounds 2+: only what the last round changed.** The range is the last
round's `reviewed_head..fixed_head`, plus anything pushed since. Spawn a
**fresh** reviewer agent (`general-purpose`, `model: opus`). Brief it with
exactly: the PR number and the scope statement; `git diff <reviewed_head>..HEAD`
to review and `git diff origin/$BASE...HEAD` as context only; and the previous
round's findings, one line each: `[category] path:line — summary —
disposition (ref)`. Its instructions:

1. For each previous finding marked `fixed`, check the fix removes the failure
   scenario. A fix that doesn't is a new finding: `[correctness] Fix for
   <path:line> does not hold: ...`.
2. Review the delta for correctness, test, security and convention bugs,
   including code the fixes changed by calling it.
3. **Run it, don't just read it.** For each new or changed function, find its
   real callers, then execute it in a scratch script (outside the checkout)
   with the values they pass and the boundary values around them: null,
   empty, zero, the largest the column or API allows, the types the caller
   really builds. Report what you ran. A fix for one input shape often breaks
   its near neighbour. Hostile inputs no caller builds are worth running only
   at a trust boundary.
4. **Check the new tests.** Does each fail without the fix it claims to pin
   (try it)? Is it hermetic: no files written into the checkout, no network,
   no dependence on the date, the time of day or test order? If the code
   under test branches on the hour or the date, a fixture built as
   `now - delta` fails at certain hours: it must use a fixed time. A test with
   threads, event loops or timers must survive many runs under CPU load.
5. Don't re-raise a finding marked `rejected` or `ledger` without new
   evidence; then label it `re-raised` and give the evidence.
6. Return JSON only: `{"findings": [...]}`.

Give it no account of why the fixes were made: it must judge them from the
code, not from the fixer's explanation. A reviewer handed the author's
framing tends to confirm it.

Record the round with its `reviewed_head`, start and end time.

### 5. Disposition every finding

No findings: the reviewed head is verified. Set `verified_head` and go to
step 7.

**Sort before spawning a fixer.** Every finding in a non-blocking category is
`ledger` now, in every round, written by the orchestrator from the
reviewer's line, unverified and unfixed. If nothing is left, set
`fixer_skipped`, set `verified_head` to the reviewed head, post (step 6) and
go to step 7.

Otherwise spawn a **fixer** (`general-purpose`; `model: sonnet`, or `opus` on
a risky PR) in the worktree. Give it the scope statement, the remaining
findings and the rules below, and no opinion of your own about them. It
commits and pushes, but posts nothing. For each finding, in order:

0. **Make the smallest fix that removes the failure scenario.** Every line it
   adds is reviewed again and is a new place for a bug. No new class, helper
   or abstraction unless the finding needs one. If the honest fix is
   narrowing a claim in a docstring or doc, do that instead.
1. **Verify it.** Read the cited code and walk the scenario. `confirmed` only
   if it really happens; otherwise `rejected` with evidence (a file:line, a
   query or a test showing it can't occur). "Looks fine" is not evidence.
2. **Check reachability.** Find `reachable_via` yourself from the callers,
   writers and data. A confirmed finding with no reachable path is not
   blocking, whatever its category.
3. **Confirmed, blocking, in scope, within budget:** `fixed`. For a bug, add
   or extend a test that fails before the fix (follow the project's
   regression-test rules if CLAUDE.md has them).
4. **Confirmed, blocking, in scope, but over budget or a behaviour trade-off
   someone must accept:** `decision`. Don't write the fix. Return a question,
   two or three options with what each costs, and a recommended default.
5. **Confirmed, blocking, out of scope:** `issue` only if (a) its
   `reachable_via` is a path that really runs (say which you checked), (b) no
   open issue covers it (search by file basename, function name and key
   terms; if one does, return that number as `existing` with the failure
   scenario as comment text), and (c) on a chain PR, it is on a risky path.
   Otherwise `ledger`. Don't change code; return a draft issue (title,
   priority, type, body with the scenario, a link to the file and line, the
   path checked, acceptance criteria). At most 2 new issues per PR, 1 on a
   chain PR; past that, `ledger`.
6. **Everything else confirmed** (non-blocking, or not reachable): `ledger`.
   Never change code for it. One line: `[category] path:line — summary`, plus
   `— not reachable: <why>` for a blocking-category finding that failed
   reachability.

If anything was fixed, the fixer then:

- Runs the tests the change touches with `test_command` (or the project's
  runner) in the background. If `test_busy_exit_code` is set and the run
  exits with it, wait a minute and retry, up to 30 times; never bypass the
  project's test lock.
- Runs every `lint_commands` entry (else the CI workflow's lint steps) and
  any gate scripts the CI workflow runs on changed files.
- Adds or updates the changelog entry / docs the project requires if the fix
  changed what they describe.
- Checks the budget: `git diff --numstat <reviewed_head>..HEAD`, excluding
  `exclude_from_line_counts`.
- Commits once for the round. The title says what changed, never
  `fix: #N` (that auto-closes issues): `Address review round <k> on PR #<N>: <what>`.
- Pushes with `git push origin HEAD:<head>`. Never force-push.

### 6. Check the fixer, post, file, wait for CI

- **Don't trust the fixer's report.** Re-run the lint commands, gates and the
  tests it names yourself on the pushed head. A failure here is part of this
  round: fix, commit, push.
- **Spot-check every `rejected` blocking-category finding.** Read the cited
  evidence. If it doesn't show the scenario can't occur, the finding is
  confirmed: fix it in this round. The fixer is grading its own work.
- **Post one review for the round**, with inline comments **only for `fixed`
  blocking findings**:
  `**[category] summary** Fixed in <sha>: <what changed>. Pinned by <test>.`
  ```bash
  gh api repos/{owner}/{repo}/pulls/<N>/reviews --method POST --input "$STATE_DIR/review.json"
  # {"commit_id": "<reviewed_head>", "event": "COMMENT",
  #  "body": "Review loop round <k> (<kind>): <n> findings, <b> fixed",
  #  "comments": [{"path": "...", "line": 41, "side": "RIGHT", "body": "..."}]}
  ```
  Build the JSON with a script, not an inline shell string (bodies are full of
  backticks and quotes). If GitHub rejects a line that isn't in the diff, move
  that finding into the review body. A round with nothing fixed posts no
  review. Save `review_id` at once.
- **Update the one status comment.** Its first line is the marker
  `<!-- review-loop-status -->`. Find it by the marker (create it in round 1),
  edit it in place
  (`gh api repos/{owner}/{repo}/issues/comments/<id> --method PATCH -F body=@<file>`),
  save `status_comment_id`. Content: the round table (step 9), then Fixed
  (blocking), Ledger, Rejected (with evidence), Issues filed.
- **File issues** for `issue` dispositions with the `/backlog-add` template
  (labels `backlog`, `priority:*`, `type:*`). End the body with
  `Found by /review-loop on PR #<N>, round <k>: <file and line link>`. Search
  first (`gh issue list --search "<terms>" --state open`, and
  `--state closed --limit 20`, since a fix may already be on the base branch).
  An open match: comment on it instead (scenario, link, PR), record `existing:
  true`; it doesn't count toward the cap. A closed match: re-check the finding
  on the base branch and `rejected` it with that evidence if it's fixed. Write
  bodies to a file and pass `--body-file`.
- **Write the ledger.** All `ledger` lines for the PR go into one comment on
  the issue titled `ledger_issue_title` (label `review:ledger`, labelled
  `stays open`; create it if missing). One comment per PR, headed
  `### PR #<N>`, one checkbox per line, grouped by file area, edited in place
  (`ledger_comment_id`). Nobody works ledger lines one at a time: read the
  unchecked lines on files you are about to touch, and promote one to an issue
  only when something fails the way it described.
- Save `fixed_head` and the dispositions. A round that confirmed nothing
  blocking and pushed nothing makes its `reviewed_head` verified. A round
  that pushed leaves `verified_head` unchanged until a later delta comes back
  clean.
- **Wait for CI** on the pushed head: `gh pr checks <N> --watch --fail-fast --interval 60`
  with `run_in_background`; record `ci_wait_minutes`. Keep the interval at
  60 s or more (GitHub's API rate limit). If a check fails, read the job log
  (`gh api repos/{owner}/{repo}/actions/jobs/<job-id>/logs | grep -E '##\[error\]'`).
  **Decide whether it's a flake before writing any fix:** likely when the
  failing test isn't in the diff **and** the same test failed on another
  recent run (`gh run list --branch "$BASE" --limit 10`, other open PRs).
  Re-run once (`gh run rerun <run-id> --failed`). Passes: the head is still
  verified; add a ledger line `[test] <test> — flaked in CI, passed on
  re-run`. Fails again: it's real; fix it in this round.
- **Start the next review while CI runs.** A CI fix commit falls inside the
  next round's range anyway.

### 7. Decide what runs next

| Situation | Next |
|---|---|
| Code was pushed this round | Delta round (step 4) if fewer than `--max-deltas` have run, else step 9 with `decision_needed` |
| Nothing pushed, head verified, closing review not yet run | Step 8 |
| Nothing pushed, head verified, closing review done | Step 9, `ready` |
| A `decision` is open | Finish the other findings, then apply **Default-accept**. Allowed: apply the answers and read this table again. Not allowed: step 9 with `decision_needed` |
| A decision was just resolved | Apply it (step 3), then read this table again |

A `decision_needed` verdict **postpones** the closing review, never skips
it: once answers are in, step 8 runs before the verdict can be `ready`.

The caps are the only stopping rules. Three blocking findings in one delta
and one in the next is not a reason to quit before the cap.

### 8. Closing full review (once)

Delta rounds trade breadth for speed: unchanged code got one full look, in
round 1. Once a head is verified, a fresh `opus` agent runs one more full
review the same way as round 1, at the closing level (default `medium`):
`<level> <N> --max-findings all`. Set `closing_done`.

**Skip it only on a non-risky PR whose round-1 head is the verified head**,
and never when `reviewer` is `fallback`. Then round 1 was already a full
`high` review of exactly what will merge: set `closing_done` and
`closing_skipped`, go to step 9 with `ready`. A pushed CI fix or an answered
decision that changed code is a push, so the closing review runs.

- **No confirmed blocking findings** (non-blocking ones go to the ledger and
  change nothing): still verified; step 9 with `ready`.
- **A confirmed blocking finding:** fix it as a normal round (steps 5-6), then
  run at most 2 delta rounds on that fix only. A clean delta makes the new head
  verified and the verdict `ready`; don't run the closing review again. If the
  second delta still confirms a blocking finding, the verdict is
  `decision_needed` and **never** default-accepts: take one more round, merge
  with that finding ledgered, or narrow the PR so the contested code leaves
  it. Give the scenario and `reachable_via`, and recommend one.

### 9. Verdict and report

Edit the status comment. Line 1 stays the marker; the verdict is the heading:

```markdown
<!-- review-loop-status -->
## Review loop: verdict ready (merged abc1234)    <- or: verdict decision_needed

**Decisions needed**   <- only for decision_needed, at most 3
1. <question in one sentence>
   - A: <option>, costs <...>   **Recommended** because <...>
   - B: <option>, costs <...>; better if <fact that would change the call>

| Round | Reviewed | Findings | Blocking (confirmed) | Fixed | Issue | Ledger | Rejected |
|---|---|---|---|---|---|---|---|
| 1 | whole PR (high) | 9 | 6 | 5 | 1 (#140) | 2 | 1 |
| 2 | delta | 2 | 0 | 0 | 0 | 2 | 0 |
| closing | whole PR (medium) | 4 | 0 | – | – | 4 | – |    <- or: skipped, round 1 head is final

**Auto-accepted decisions:** question, option taken, because (only if any)
**Default-accept refused:** the first policy reason (only on decision_needed)
**Issues filed:** #140 <title>
**Ledger:** 8 entries (link)
**Rejected blocking-class findings:** links, one line each
**Chain:** only on a chain PR: `Link <k> of a chain from #<root>. Recommended:
write a design note on #<root> before the next patch, because <the pattern the
chain's issues share>.` List the chain's open issues.
**PR size:** <added lines>; split before the loop if over <pr_size_warn_lines>
**CI:** green on <sha>
```

- On a chain PR, add `review:chain` to every issue filed this run and to the
  root issue.
- Set the PR label `review:ready` or `review:decision-needed`, removing the
  other. Create missing labels on the fly:
  `gh label create "review:ready" --color 0E8A16 2>/dev/null || true` (and
  `review:decision-needed` `D93F0B`, `review:chain` `FBCA04`,
  `review:ledger` `C2E0C6`).
- Set `status` in the state file.
- Report to the user. For `decision_needed`, lead with the first question and
  `Recommended: <option>, because ...`, then the table and the PR URL.

### 10. Merge

Only for verdict `ready`, and not with `--no-merge`. Check each condition
from GitHub, not from the state file. If any fails, don't merge, say which,
and leave the label at `review:ready`:

```bash
gh pr view <N> --json headRefOid,isDraft,mergeable,reviewDecision,baseRefName,labels,title
gh pr checks <N>
```

1. `headRefOid` equals `verified_head`. A commit pushed after the last clean
   review is unreviewed code.
2. Every check on that head passed; none pending or failing.
3. Not a draft, base unchanged, `mergeable` is `MERGEABLE`.
4. `reviewDecision` isn't `CHANGES_REQUESTED`, and no `hold` or
   `do-not-merge` label is present.
5. `closing_done` is true. Asked to merge a PR that stopped on a decision?
   Run step 8 first.
6. The PR body links its issue the way the author meant. The loop never edits
   it: `Closes #N` closes the issue on merge, `Refs #N` leaves it open. If the
   **title** carries a closing pattern (`fix: #N`) on a PR whose issue must
   stay open, stop and recommend the title edit: a squash title closes issues
   too.
7. `reviewer` is `code-review`, **or** it is `fallback`, the closing review
   ran, and the policy (step 1's command, re-run against this head) exits 0.
   Otherwise leave it at `review:ready`, set the heading to `verdict ready
   (reviewer: fallback, not merged: <first reason>)`, and tell the user the PR
   is theirs to merge.

Then `gh pr merge <N> --<merge_method>`.

- Never `--admin`, never `--auto`, never update the branch or resolve
  conflicts to make a merge go through: any push after verification makes the
  head unverified. If the merge is refused, report the exact error and what
  you'd do next (rebase and re-run the loop, wait for a required check), and
  stop.
- Read the state file one last time (step 11 needs it), then remove the
  worktree: `git -C "$MAIN" worktree remove "$W"` (remove your own symlinks
  first; never `--force`). Leave the remote branch alone unless the repo
  deletes merged branches itself.
- Check the CI run on the merge commit once
  (`gh run list --branch "$BASE" --limit 3`). Report a failure there; don't
  revert.

Edit the status heading to `verdict ready (merged <sha>)` or `verdict ready
(not merged: <reason>)` and report the same.

### 11. Metrics

Run this last, merged or not. Append one line to a log in the main repo's git
dir, so it outlives the worktree:

```bash
echo '<json>' >> "$(git rev-parse --path-format=absolute --git-common-dir)/review-loop-metrics.jsonl"
```

**One line per run, cumulative:** each invocation appends the PR's totals so
far with its `run` number; a reader keeps the highest `run` per PR.

```json
{"schema": 1, "type": "run", "run": 1, "date": "YYYY-MM-DD", "pr": 0, "issue": 0,
 "additions": 0, "deletions": 0, "risky": false, "chain": false, "root_issue": null,
 "closing_level": "medium", "reviewer": "code-review|fallback",
 "models": {"fixer": "", "reviewers": "opus"},
 "rounds": 0, "per_round": [{"n": 1, "kind": "full", "findings": 0, "blocking": 0,
   "fixed": 0, "issue": 0, "ledger": 0, "rejected": 0, "decision": 0,
   "in_loop_code": 0, "fixer_skipped": false, "ci_wait_minutes": 0}],
 "closing_skipped": false, "issues_filed": [], "ledger_entries": 0,
 "auto_accepted": 0, "verdict": "ready|decision_needed", "merged": false, "merge_sha": null,
 "wall_minutes": 0, "agent_tokens": {"total": 0}, "agent_runs": 0}
```

Token and minute figures come from the state file's `agents` entries, never
from memory; a `null` entry makes `total` `null`.

Release the lock (`rm -f "$STATE_DIR/lock"`; nothing to do if the worktree
went in step 10).

**Measuring quality.** What reviewers find is not the measure; what gets past
them is. An **escape** is a bug filed within 14 days of a loop-merged PR whose
`Introduced by: PR #M` line (see `/backlog-add`) names that PR. Count them
now and then:

```bash
gh issue list --state all --label type:bug --limit 200 --json number,title,body,createdAt \
  --jq '.[] | select(.body | test("Introduced by: PR #[0-9]+")) | "\(.number) \(.createdAt[:10]) \(.body | capture("Introduced by: PR #(?<pr>[0-9]+)").pr)"'
```

Judge each from the code it describes (`git log -L` or `git blame` on the
cited lines), not from the citation alone, and compare escapes per merged PR
before and after any change that cuts review cost. A cut that saves tokens
and raises the escape rate is not a saving.
