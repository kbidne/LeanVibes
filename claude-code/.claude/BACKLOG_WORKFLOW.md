# Claude Code + GitHub Projects: Backlog Management Workflow

A lightweight workflow for managing requirements and backlogs using Claude Code and GitHub Projects, providing Jira-like functionality with minimal setup.

## Overview

This workflow enables:
- **Proactive backlog suggestions** - Claude identifies deferrable work during conversations
- **Quick issue creation** - Add items to backlog without leaving the conversation
- **Prioritized work selection** - Work through backlog items systematically
- **GitHub Projects integration** - Visual board for tracking progress

## Quick Start

### 1. Install Prerequisites

```bash
# Install GitHub CLI
brew install gh

# Authenticate
gh auth login
```

### 2. Run Setup Script

```bash
# From your repo root
./.claude/scripts/setup-backlog.sh
```

This creates:
- Required labels (`backlog`, `priority:high/medium/low`, `type:feature/bug/enhancement/debt`)
- GitHub Project board named "Backlog"

### 3. Add to CLAUDE.md

Add the backlog workflow section to your project's CLAUDE.md (see template below).

---

## How It Works

### During Conversations

When Claude identifies work that could be deferred, it will prompt:

```
+----------------------------------------------------------+
|  BACKLOG SUGGESTION                                      |
|                                                          |
|  "Add responsive breakpoints to the dashboard"           |
|                                                          |
|  This enhancement isn't blocking current work.           |
|                                                          |
|  - Type: enhancement                                     |
|  - Suggested Priority: medium                            |
|                                                          |
|  [do it] - Implement now                                 |
|  [backlog] - Add to backlog (I'll ask for priority)      |
|  [backlog high/medium/low] - Add with specific priority  |
+----------------------------------------------------------+
```

**Your responses:**
- `do it` or `now` → Claude implements immediately
- `backlog` → Claude asks for priority, then creates issue
- `backlog high` → Claude creates high-priority issue directly

### Slash Commands

#### `/backlog` - View and Work on Backlog

```
/backlog              # List all backlog items by priority
/backlog 42           # Start working on issue #42
/backlog suggest      # Get Claude's recommendation
```

#### `/backlog-add` - Quick Add to Backlog

```
/backlog-add high feature Add user authentication
/backlog-add medium bug Fix mobile navigation overlap
/backlog-add low enhancement Add dark mode toggle
```

---

## Label Structure

| Label | Color | Purpose |
|-------|-------|---------|
| `backlog` | `#0E8A16` | Identifies all backlog items |
| `priority:high` | `#D73A4A` | Urgent / blocking items |
| `priority:medium` | `#FBCA04` | Important but not urgent |
| `priority:low` | `#0075CA` | Nice to have / future work |
| `type:feature` | `#A2EEEF` | New functionality |
| `type:bug` | `#D73A4A` | Defects to fix |
| `type:enhancement` | `#7057FF` | Improvements to existing features |
| `type:debt` | `#FEF2C0` | Technical debt / refactoring |

---

## Issue Template

When Claude creates backlog items, it uses this format:

```markdown
## Summary
[One-line description of the requirement]

## Context
[Why this came up - conversation context, user request, or identified need]

## Acceptance Criteria
- [ ] [Specific, testable criterion]
- [ ] [Another criterion]
- [ ] Verify no regressions introduced

## Technical Notes
[Optional: Implementation hints, relevant files, dependencies]

---
*Created via Claude Code backlog workflow*
```

---

## GitHub Project Board Setup

### Recommended Columns

| Column | Purpose | Automation |
|--------|---------|------------|
| **Backlog** | All new issues | Auto-add issues with `backlog` label |
| **Ready** | Refined, ready to work | Manual move when criteria clear |
| **In Progress** | Currently being worked | Auto-move on PR link |
| **In Review** | PR submitted | Auto-move on PR review request |
| **Done** | Completed | Auto-move on issue close |

### Views

1. **Board View** - Kanban-style for daily work
2. **Table View** - Sortable list for backlog grooming
3. **Priority View** - Grouped by priority label

---

## CLAUDE.md Template

Add this section to your project's CLAUDE.md:

```markdown
## Backlog Workflow

This project uses the Claude Code + GitHub Projects backlog workflow.

### Proactive Suggestions

When identifying work that could be deferred, present a backlog suggestion:

\`\`\`
+----------------------------------------------------------+
|  BACKLOG SUGGESTION                                      |
|                                                          |
|  "[description of the work]"                             |
|                                                          |
|  [reason why it could be deferred]                       |
|                                                          |
|  - Type: [feature/bug/enhancement/debt]                  |
|  - Suggested Priority: [high/medium/low]                 |
|                                                          |
|  [do it] - Implement now                                 |
|  [backlog] - Add to backlog                              |
|  [backlog high/medium/low] - Add with priority           |
+----------------------------------------------------------+
\`\`\`

### When to Suggest Backlog

Proactively suggest adding to backlog when:
- Work is tangential to the main task
- It's an enhancement rather than a requirement
- It would significantly expand scope
- The user mentions "later" or "eventually"
- You identify technical debt or optimization opportunities

### Commands

- \`/backlog\` - View and select backlog items to work on
- \`/backlog-add [priority] [type] [title]\` - Quick-add an item
```

---

## File Structure

```
your-repo/
├── .claude/
│   ├── commands/
│   │   ├── backlog.md          # /backlog command
│   │   └── backlog-add.md      # /backlog-add command
│   ├── scripts/
│   │   └── setup-backlog.sh    # One-time setup script
│   └── BACKLOG_WORKFLOW.md     # This documentation
└── CLAUDE.md                    # Project context (add backlog section)
```

---

## Copying to Other Projects

To use this workflow in another repository:

1. **Copy the `.claude` directory** to your new repo
2. **Run the setup script** in the new repo
3. **Add the backlog section** to that project's CLAUDE.md

```bash
# From your new project root
cp -r /path/to/source/.claude .
./.claude/scripts/setup-backlog.sh
```

---

## Tips & Best Practices

### For Users

1. **Be decisive** - When Claude suggests backlog, quickly say "do it" or "backlog medium"
2. **Use priorities consistently** - High = this week, Medium = this month, Low = someday
3. **Groom regularly** - Run `/backlog` periodically to review and reprioritize
4. **Close completed work** - Let Claude close issues when work is done

### For Claude (AI Context)

1. **Be selective** - Don't suggest backlog for every small thing
2. **Provide context** - Issue descriptions should be actionable without conversation history
3. **Suggest priority** - Always recommend a priority level with reasoning
4. **Link related items** - Reference existing issues when relevant

---

## Troubleshooting

### "gh: command not found"

Install GitHub CLI:
```bash
brew install gh
gh auth login
```

### Labels already exist

The setup script skips existing labels - this is fine.

### Project board not linking

Ensure you're in the correct repository and the project name matches exactly.

---

## Contributing

This workflow is open for improvements. Key areas:
- [ ] Milestone/sprint integration
- [ ] Time tracking
- [ ] Automated priority aging
- [ ] Cross-repo backlog views

---

*Workflow version 1.0 - Designed for Claude Code*
