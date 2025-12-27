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

3. **Generate issue body** using this template:
   ```markdown
   ## Summary
   [Title provided by user]

   ## Context
   Added during Claude Code session.
   [If there's relevant context from the current conversation, include it]

   ## Acceptance Criteria
   - [ ] [Criterion based on the title/context]
   - [ ] Verify implementation works as expected
   - [ ] No regressions introduced

   ---
   *Created via Claude Code backlog workflow*
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

5. **Add to project board** (if configured):
   ```bash
   gh issue edit [number] --add-project "Backlog"
   ```

6. **Confirm to user**:
   ```
   Created backlog item #[number]: [title]
   Priority: [priority] | Type: [type]
   View: [issue URL]
   ```
