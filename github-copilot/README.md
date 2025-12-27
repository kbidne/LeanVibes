# LeanVibes for GitHub Copilot

Backlog management workflow for [GitHub Copilot Chat](https://github.com/features/copilot).

> **Note:** GitHub Copilot doesn't have a persistent instruction file like Claude Code or Cursor. You'll need to include context in your prompts or use the instructions as a reference.

## Installation

### 1. Run Setup Script

First, run the shared setup script to create labels and project board:

```bash
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
```

### 2. Reference Instructions (Optional)

Keep `INSTRUCTIONS.md` in your project for reference, or paste relevant sections into Copilot Chat when needed.

## Usage

GitHub Copilot Chat uses natural language. Here are example prompts:

### View Backlog

```
Run this command and show me the results organized by priority:
gh issue list --label backlog --state open --json number,title,labels
```

### Add to Backlog

```
Create a GitHub issue with these details:
- Title: [your title]
- Labels: backlog, priority:medium, type:enhancement
- Body: Include a summary and acceptance criteria

Use: gh issue create --title "..." --body "..." --label backlog --label priority:medium --label type:enhancement
```

### Work on Backlog Item

```
Fetch issue #42 and help me implement it:
gh issue view 42 --json title,body,labels

Remember to include "Fixes #42" in any commits we create.
```

### Commit with Issue Reference

```
Create a commit message for this change that includes "Fixes #42" to link it to the issue.
```

## Prompt Templates

### Starting a Session

Paste this at the start of a session to enable backlog awareness:

```
I'm using the LeanVibes backlog workflow. When you notice work that could be deferred (enhancements, optimizations, nice-to-haves), suggest adding it to the backlog instead of implementing immediately.

To add items: gh issue create --label backlog --label priority:[high/medium/low] --label type:[feature/bug/enhancement/debt]

When working on a backlog item, always include "Fixes #[number]" in commit messages.
```

### Suggesting Backlog Items

When Copilot should suggest deferring work:

```
This seems like it could be deferred. Should we add it to the backlog?

To add: gh issue create --title "[description]" --label backlog --label priority:medium --label type:enhancement
```

## Limitations

Unlike Claude Code and Cursor, GitHub Copilot:
- Doesn't have persistent project instructions
- Requires manual prompting for backlog workflow
- May need reminders to include issue references in commits

## Workarounds

1. **VS Code Tasks** - Create tasks that run common `gh` commands
2. **Snippets** - Create snippets for common prompts
3. **GitHub CLI Aliases** - Set up `gh alias` for frequent operations:
   ```bash
   gh alias set backlog-add 'issue create --label backlog'
   gh alias set backlog-list 'issue list --label backlog --state open'
   ```

## More Information

See the [main LeanVibes README](../README.md) for general documentation.
