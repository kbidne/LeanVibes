# Add Item to Backlog

Quickly create a GitHub Issue and add it to the backlog.

## Arguments

Expected format: `[priority] [type] [title]`

Examples:
- `/backlog-add high feature Add user authentication`
- `/backlog-add medium bug Fix mobile navigation`
- `/backlog-add low enhancement Improve loading states`

Argument: $ARGUMENTS

## Instructions

0. **Should this be a fix instead?** If you (not the user) are about to file
   this, check the project's "Fix now or file?" policy in CLAUDE.md. By
   default: when the cause is confirmed, the fix is small, it needs no owner
   decision, and it won't derail the current task, fix it now (in a worktree,
   as its own PR) instead of filing it. File it when the user asked for an
   issue, or when any of these hold: it needs the owner's decision, it has to
   wait for something, it spans several PRs, the session is busy with work
   that must finish, the cause isn't understood yet, or it is scope expansion
   the user didn't ask for.

1. **Parse the arguments**:
   - Priority: `high`, `medium`, or `low` (default: `medium`)
   - Type: `feature`, `bug`, `enhancement`, `debt` (default: `feature`)
   - Title: Everything after priority and type

2. **If arguments are missing or unclear**, ask the user:
   ```
   What would you like to add to the backlog?
   - Title: [required]
   - Priority: high / medium / low
   - Type: feature / bug / enhancement / debt
   ```

3. **Generate the issue body** using this template:
   ```markdown
   ## Summary
   [Title provided by user]

   ## Context
   Added during Claude Code session.
   [Relevant context from the current conversation: what was seen, where
   (file paths), what is known vs. guessed. The issue must make sense to a
   reader who never saw this conversation.]

   Introduced by: PR #[N]
   [Bugs only; omit this line for other types. Find the PR that added the
   faulty lines with `git log -L <start>,<end>:<file> --format='%h %s'` or
   `git blame`, then the PR number from the squash commit's `(#N)`. Write
   `Introduced by: unknown` if it predates readable history or the cause
   isn't located yet. Name the PR whose change caused the bug, not one that
   only exposed it. Over time this line tells you which bugs got past review.]

   ## Why now
   [Optional. One or two sentences on what makes this worth doing soon: what
   it risks, what it blocks, a date it must land by. Omit the section when
   there is nothing to say.]

   ## Suggested Agent(s)
   [OPTIONAL. Include only if BOTH are true: (a) this project defines
   specialized subagent types (check for a `.claude/agents/` directory or
   subagent definitions in project config), AND (b) the work clearly maps
   to one or more of them. Omit the section entirely otherwise. Name each
   agent and which part of the work it owns, e.g.:
   - `<agent-name>` (<what it's for>) for: [...]]

   ## Acceptance Criteria
   - [ ] [Criterion based on the title/context]
   - [ ] Verify implementation works as expected
   - [ ] No regressions introduced

   ---
   *Created via LeanVibes backlog workflow*
   ```

4. **Create the issue**:
   ```bash
   gh issue create \
     --title "[title]" \
     --body "[generated body]" \
     --label "backlog" \
     --label "priority:[priority]" \
     --label "type:[type]"
   ```
   If the item is already known to be blocked, park it right away (see
   `/backlog` "Parking an issue"): add the `waiting:*` label and its
   `Parked:` comment.

5. **Add to the project board** (if configured):
   ```bash
   PROJECT_NUM=$(gh project list --owner @me --format json 2>/dev/null \
     | jq -r '[.projects[] | select(.title=="Backlog") | .number] | first // empty')
   [ -n "$PROJECT_NUM" ] && gh project item-add "$PROJECT_NUM" --owner @me --url [issue URL]
   ```

6. **Confirm to user**:
   ```
   Created backlog item #[number]: [title]
   Priority: [priority] | Type: [type]
   View: [issue URL]
   ```
