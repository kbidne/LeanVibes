# GitHub Copilot Backlog Workflow Instructions

Copy and paste these instructions into GitHub Copilot Chat as needed.

---

## Session Start Prompt

Paste this at the beginning of a coding session:

```
I'm using the LeanVibes backlog workflow for this project. Please follow these guidelines:

1. **Fix now or file**: Fix a small defect now when its cause is confirmed, it needs no decision from me, and it won't derail the current task. Suggest adding it to the backlog instead when it needs my decision, has to wait, spans several PRs, its cause isn't understood yet, or it is an enhancement, optimization, technical debt or other scope I didn't ask for.

2. **Adding to Backlog**: Check for an existing issue first (gh issue list --search "<terms>"), then:
   gh issue create --title "[title]" --label backlog --label priority:[high/medium/low] --label type:[feature/bug/enhancement/debt] --body "[description]"
   For a bug, include a line "Introduced by: PR #N" (the PR that caused it, or "unknown").

3. **Issue References**: When working on a backlog item, include "Fixes #[number]" in commit messages and "Closes #[number]" in PR descriptions. For an issue that spans several PRs, use "Refs #[number]" and keep "fix: #[number]" out of the PR title.

4. **Viewing Backlog**: List every open issue, not only ones labelled backlog:
   gh issue list --state open --limit 500 --json number,title,labels
   Show issues with a waiting:* or "stays open" label as Parked, "epic" as Epics, and the rest by priority.
```

---

## Quick Commands

### View Backlog
```
Show me the current backlog by running:
gh issue list --state open --limit 500 --json number,title,labels

Group them: Parked (any waiting:* label, or "stays open"), Epics (epic), and Workable
(everything else, by priority high/medium/low/unprioritized). For waiting:date issues,
read the latest comment starting "Parked: waiting:date until YYYY-MM-DD" and flag it
as due if that date has passed.
```

### Add to Backlog
```
Create a backlog issue:
- Title: [TITLE]
- Priority: [high/medium/low]
- Type: [feature/bug/enhancement/debt]

Command: gh issue create --title "[TITLE]" --label backlog --label priority:[PRIORITY] --label type:[TYPE] --body "## Summary\n[TITLE]\n\n## Acceptance Criteria\n- [ ] Implementation complete\n- [ ] Tests pass\n- [ ] No regressions"
```

### Park an Issue
```
Park issue #[NUMBER] until [DATE]:
gh issue edit [NUMBER] --add-label waiting:date
gh issue comment [NUMBER] --body "Parked: waiting:date until [YYYY-MM-DD]
[Why it is waiting]"

Other reasons use waiting:decision ("Parked: waiting:decision"), waiting:issue
("Parked: waiting:issue on #N") or waiting:external ("Parked: waiting:external").
```

### Work on Issue
```
I want to work on issue #[NUMBER]. Please:
1. Fetch the issue and its comments: gh issue view [NUMBER] --comments
2. If it has a waiting:* label, tell me what it's waiting on before starting
3. Help me implement the acceptance criteria
4. Include "Fixes #[NUMBER]" in any commits we create
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
This seems like work that should be filed rather than done now. Consider adding to backlog:

Title: [brief description]
Priority: medium (suggested)
Type: enhancement
Why file it: [needs a decision / has to wait / scope expansion / ...]

To add: gh issue create --title "[title]" --label backlog --label priority:medium --label type:enhancement

Would you like to:
- Implement it now
- Add to backlog
- Skip it
```
