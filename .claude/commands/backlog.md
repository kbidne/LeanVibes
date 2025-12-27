# Backlog Management

Review and work on backlog items from GitHub Issues.

## Instructions

1. **Fetch open backlog issues** using `gh issue list --label backlog --state open --json number,title,labels,body --limit 50`

2. **Display issues organized by priority**:
   - **High Priority** (priority:high label)
   - **Medium Priority** (priority:medium label)
   - **Low Priority** (priority:low label)
   - **Unprioritized** (no priority label)

3. **Format each issue as**:
   ```
   #[number] [title]
   Type: [type label]
   [First 100 chars of body...]
   ```

4. **Ask the user**:
   ```
   Which issue would you like to work on?
   - Enter an issue number (e.g., "42")
   - Or say "suggest" for my recommendation based on priority
   ```

5. **If user says "suggest"**: Recommend the highest priority item, explaining why it should be tackled first.

6. **Once an issue is selected**:
   - Fetch full issue details: `gh issue view [number] --json title,body,labels,comments`
   - Parse the acceptance criteria from the issue body
   - Create a TodoWrite plan based on the acceptance criteria
   - **Display the active issue reminder**:
     ```
     Working on #[number]: [title]
     Commits will include: Fixes #[number]
     ```
   - Begin implementation

7. **When creating commits** for this issue:
   - Always include `Fixes #[number]` in the commit message body
   - Example:
     ```
     Add feature X

     Fixes #42

     🤖 Generated with [Claude Code](https://claude.com/claude-code)
     ```

8. **When creating PRs** for this issue:
   - Include `Closes #[number]` in the PR description
   - Reference the issue in the summary

9. **When work is complete**:
   - Ask user if they want to close the issue
   - If yes, run: `gh issue close [number] --comment "Completed via Claude Code"`
   - Note: If a PR was created with `Closes #[number]`, the issue will auto-close on merge

## Argument

If invoked with an issue number (e.g., `/backlog 42`), skip directly to step 6 with that issue.

Argument: $ARGUMENTS
