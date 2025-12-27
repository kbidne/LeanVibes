# GitHub Copilot Backlog Workflow Instructions

Copy and paste these instructions into GitHub Copilot Chat as needed.

---

## Session Start Prompt

Paste this at the beginning of a coding session:

```
I'm using the LeanVibes backlog workflow for this project. Please follow these guidelines:

1. **Proactive Suggestions**: When you notice work that could be deferred (enhancements, optimizations, technical debt, nice-to-haves), suggest adding it to the backlog instead of implementing immediately.

2. **Adding to Backlog**: Use this command:
   gh issue create --title "[title]" --label backlog --label priority:[high/medium/low] --label type:[feature/bug/enhancement/debt] --body "[description]"

3. **Issue References**: When working on a backlog item, always include "Fixes #[number]" in commit messages and "Closes #[number]" in PR descriptions.

4. **Viewing Backlog**: gh issue list --label backlog --state open --json number,title,labels
```

---

## Quick Commands

### View Backlog
```
Show me the current backlog by running:
gh issue list --label backlog --state open --json number,title,labels

Organize results by priority (high, medium, low).
```

### Add to Backlog
```
Create a backlog issue:
- Title: [TITLE]
- Priority: [high/medium/low]
- Type: [feature/bug/enhancement/debt]

Command: gh issue create --title "[TITLE]" --label backlog --label priority:[PRIORITY] --label type:[TYPE] --body "## Summary\n[TITLE]\n\n## Acceptance Criteria\n- [ ] Implementation complete\n- [ ] Tests pass\n- [ ] No regressions"
```

### Work on Issue
```
I want to work on issue #[NUMBER]. Please:
1. Fetch the issue: gh issue view [NUMBER]
2. Help me implement the acceptance criteria
3. Include "Fixes #[NUMBER]" in any commits we create
```

### Create Linked Commit
```
Create a commit message for these changes that:
1. Summarizes what was done
2. Includes "Fixes #[NUMBER]" to link to the issue
3. Follows conventional commit format
```

---

## Backlog Suggestion Format

When suggesting deferred work, use this format:

```
This seems like work that could be deferred. Consider adding to backlog:

Title: [brief description]
Priority: medium (suggested)
Type: enhancement

To add: gh issue create --title "[title]" --label backlog --label priority:medium --label type:enhancement

Would you like to:
- Implement it now
- Add to backlog
- Skip it
```
