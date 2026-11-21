# Backlog Management

Review and work on items from GitHub Issues.

## Argument

- `$ARGUMENTS` - Optional: an issue number (e.g. `42`) to skip straight to step 4, or `suggest`.

Argument: $ARGUMENTS

## Instructions

1. **If an issue number is provided**, skip to step 4 with that issue.

2. **Fetch every open issue**, not only those labelled `backlog`. The
   `backlog` label only records that a LeanVibes command filed the issue;
   issues filed by hand or by other tools belong in the backlog too, so
   nothing filters on it.
   ```bash
   gh issue list --state open --limit 500 --json number,title,labels,body \
     --jq '.[] | {number, title, labels: [.labels[].name], body: .body[:100]}'
   ```
   `gh` stops at `--limit` without a warning. If exactly 500 issues come
   back, say the list may be cut off and re-run with a higher limit.

   Put each issue in the **first** group it matches, so nothing is listed or
   counted twice:
   1. **Parked:** any `waiting:*` label, or `stays open`.
   2. **Epics:** label `epic`.
   3. **Workable:** everything else.

   Then check which `waiting:date` and `waiting:issue` issues are due, from
   the first line of each one's latest `Parked:` comment. Run one plain
   command per issue, not a `for` loop: a command that starts with `for`
   doesn't match a `gh` allow rule, so an unattended run can deny it.
   ```bash
   gh issue view [number] --comments
   ```
   Comments print oldest first, with no dates (see step 4), so the latest
   `Parked:` comment is the last one whose body starts with `Parked:`.
   - `Parked: waiting:date until YYYY-MM-DD`, with that date today or
     earlier: **due**.
   - `Parked: waiting:issue on #N`, with #N closed
     (`gh issue view N --json state`): **may be unblocked**.
   - No `Parked:` line, or the output was cut off (the newest comments are
     the missing part, so the last `Parked:` seen may be stale): leave it
     parked and note it in the display.

   Due and may-be-unblocked issues move to their own group.

3. **Display the workable issues organized by priority**:

   **High Priority:**
   - `#[number] [title]` ([type label]) - [first 100 chars of body]...

   **Medium Priority:** / **Low Priority:** / **Unprioritized:** (same format)

   **Due for a look ([count]):** one line per issue
   - `#[number] [priority] [title]`: [the date that passed, or "#N closed"]

   Then the rest without bodies. Parked issues get one line per reason, its
   issues in priority order:

   **Parked ([count]):**
   - `waiting:date`: `#[number] [high] [title]`, `#[number] [low] [title]`, ...
   - `waiting:decision`: ...
   - `waiting:issue`: ...
   - `waiting:external`: ...
   - `stays open`: ...

   **Epics:** one line per epic, `#[number] [title]`. Work an epic owes
   itself (a verdict, a close-out) should be a child issue, so it shows up
   as Workable or Parked. If an epic's body lists owed work that no child
   issue holds, say so.

   Ask: "Which issue would you like to work on? (enter a number, or 'suggest' for a recommendation)"

   A `suggest` recommendation comes from **Workable** and **Due for a look**
   only. Recommend the highest-priority item and say why.

4. **When an issue is selected**:
   - Fetch full details first. The direct `/backlog <n>` path arrives here
     without labels, and a parked issue's reason is usually in a comment:
     ```bash
     gh issue view [number] --json title,body,labels
     gh issue view [number] --comments
     ```
     The second command prints every comment, oldest first, each under an
     `author:` header block, with no dates: the last block is the newest.
     The latest `Parked:` comment is the last one whose body starts with
     `Parked:`. No output means no comments. If the output is cut off, the
     newest comments are the missing part: say so rather than guess.
     Keep it a plain command. The earlier `--jq` version with `\(...)`
     string interpolation was denied in an unattended run under a
     permission allowlist, while plain `gh` commands were allowed.
   - Then check its labels:
     - `waiting:*`: say what it is waiting on (the latest `Parked:`
       comment, else the body) and whether that has happened. Confirm with
       the user before starting. If the wait is over, the first step is
       removing the label.
     - `stays open`: say it's a tracker kept open on purpose, not a work
       item, and ask whether there's a specific task under it. That task
       usually gets its own issue.
     - `epic`: suggest picking one of its child issues instead.
   - Check the body for a `## Suggested Agent(s)` section. If present, it
     names specialized subagent type(s) (from this project's
     `.claude/agents/` or equivalent) the author intended to do parts of the
     work: use the Agent/Task tool to invoke them for their part rather than
     doing it directly. If absent, proceed as a normal implementation session.
   - Extract the acceptance criteria and create a TodoWrite plan from them.
   - Display the reminder:
     ```
     Working on #[number]: [title]
     Commits will include: Fixes #[number]
     ```

5. **Set up an isolated worktree** before touching any files.

   Several AI sessions may run against the same repo at once. The main
   checkout's index, HEAD and stash are shared by every process in that
   directory, so a `git stash`, `git checkout --` or plain edit there can
   destroy another session's uncommitted work. Work in a per-issue worktree:

   Run these one at a time, writing the values you get back literally into
   the next command (quote paths with spaces). Permission allowlists match
   command text, so `VAR=$(...)` lines and `&&`/`||` chains get denied in
   unattended runs:

   ```bash
   git worktree list --porcelain
   git symbolic-ref --short refs/remotes/origin/HEAD
   git -C "<main>" fetch origin
   git -C "<main>" worktree add "<main>/.claude/worktrees/[number]" -b fix/[number]-[short-slug] <base>
   ```

   `<main>` is the first `worktree` line of the list (the main checkout,
   even when you run this from another worktree). `<base>` is the second
   command's output, e.g. `origin/main`; use `origin/main` if it fails.

   - **Always pass the remote default branch as the base ref** (after a
     fetch). A bare `worktree add <path> -b ...` branches from whatever the
     main checkout's HEAD is, which may be another session's half-finished
     feature branch; the new PR then carries that branch's whole diff.
   - Gitignored files (`.env`, `node_modules`, a virtualenv) don't come
     along. Symlink each one the project needs, one command each:
     `ln -s "<main>/.venv" "<main>/.claude/worktrees/[number]/.venv"`
   - Then work in the worktree: `git -C "<worktree>"` and absolute paths,
     not `cd <worktree> && ...`.
   - If a worktree for this issue already exists (`worktree add` says so),
     work in it and continue from its current state. Don't create a
     duplicate or reset it.
   - `.claude/worktrees/` should be in `.gitignore`. If it isn't, say so.
   - If the project has no remote, or the user asks to work in place, skip
     this step and say so.

6. **During implementation**:
   - Follow the acceptance criteria.
   - Include `Fixes #[number]` in the commit message body:
     ```
     feat: implement [feature name]

     Fixes #[number]
     ```

7. **Before opening the PR**:
   - **Size check.** Count added lines outside tests and docs, e.g.
     `git diff --numstat <base>...HEAD -- . ':!tests' ':!docs'`. Over about
     600, split the change into PRs that each stand on their own before
     opening any of them. Large PRs take far more review rounds than small
     ones.
   - **Run what CI runs.** Read the CI workflow (`.github/workflows/*.yml`)
     and run its lint/format/type-check steps locally, plus the tests the
     change touches. A review round spent on import order is a wasted round.
   - **Changelog fragments.** If the project keeps a changelog, prefer one
     new file per PR in a fragments directory (e.g. `docs/changelog.d/<issue>-<slug>.md`)
     over editing one shared `CHANGELOG.md`, which makes every pair of open
     PRs conflict. Follow the project's convention if it has one.
   - **Fixed clocks in tests.** If the code under test branches on the time
     or date, build fixtures at a fixed time, never `now - delta`, or the test
     fails at certain hours.

8. **When creating the PR**:
   - Include `Closes #[number]` in the description.
   - ⚠️ **Multi-PR issues:** GitHub also closes issues from the squash
     commit's **title**. A title like `fix: #42 ...` matches the closing
     pattern even when the body says only `Refs #42`. For an issue that must
     stay open across several PRs, keep the closing word next to the number
     out of the title (`fix: part 1 of #42` is safe; `fix: #42 part 1` is not)
     and use `Refs #42` in the body.

9. **On completion**:
   - If a PR with `Closes #[number]` was created, the issue auto-closes on
     merge. Otherwise ask whether to close it:
     `gh issue close [number] --comment "Completed via LeanVibes"`
   - After the PR merges, remove the worktree:
     `git -C "<main>" worktree remove "<main>/.claude/worktrees/[number]"`

## Parking an issue

When an issue can't move until something outside the work changes, add one
`waiting:*` label and a comment whose **first line** has the exact format
below, so step 2 can tell when it comes due. Explain on the lines after it.

| Label | Use when | First line of the comment |
|---|---|---|
| `waiting:date` | A date has to pass or a sample has to grow | `Parked: waiting:date until YYYY-MM-DD`. For a sample size, the earliest date worth checking |
| `waiting:decision` | The owner has to choose before work can start | `Parked: waiting:decision`, with the question on the next line |
| `waiting:issue` | Another open issue has to land first | `Parked: waiting:issue on #N` |
| `waiting:external` | A vendor, a third party or outside demand | `Parked: waiting:external`, with who and what is owed on the next line |

```bash
gh issue edit [number] --add-label "waiting:date"
gh issue comment [number] --body "Parked: waiting:date until 2027-01-15
Need 30 days of data after the change ships before reading the result."
```

Remove the label when the wait ends. To push a date back, post a new
`Parked:` comment; step 2 reads the latest one.

Don't park an issue because it needs a design call an agent could propose in
its PR, or because it's large. `stays open` marks trackers and issues the
owner keeps open on purpose.
