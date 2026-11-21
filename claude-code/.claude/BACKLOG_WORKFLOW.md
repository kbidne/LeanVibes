# Claude Code + GitHub Projects: Backlog Management Workflow

A lightweight workflow for managing requirements and backlogs using Claude Code and GitHub Projects, providing Jira-like functionality with minimal setup.

## Overview

This workflow enables:
- **Fix now or file** - Claude fixes small, confirmed defects on the spot and files the rest
- **Proactive backlog suggestions** - Claude identifies deferrable work during conversations
- **Quick issue creation** - Add items to backlog without leaving the conversation
- **Prioritized work selection** - Work through backlog items systematically
- **Parking** - `waiting:*` labels plus a `Parked:` comment so blocked issues resurface when they come due
- **Per-issue worktrees** - parallel AI sessions never trample each other's work
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
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
```

This creates (or updates):
- Labels: `backlog`, `priority:*`, `type:*`, `waiting:*`, `epic`, `stays open`
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
/backlog              # List open issues: workable by priority, due, parked, epics
/backlog 42           # Start working on issue #42 (in its own worktree)
/backlog suggest      # Get Claude's recommendation (workable and due issues only)
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
| `backlog` | `#0E8A16` | Provenance only: filed by a LeanVibes command. `/backlog` lists every open issue |
| `priority:high` | `#D73A4A` | Urgent / blocking items |
| `priority:medium` | `#FBCA04` | Important but not urgent |
| `priority:low` | `#0075CA` | Nice to have / future work |
| `type:feature` | `#A2EEEF` | New functionality |
| `type:bug` | `#D73A4A` | Defects to fix |
| `type:enhancement` | `#7057FF` | Improvements to existing features |
| `type:debt` | `#FEF2C0` | Technical debt / refactoring |
| `waiting:date` | `#C5DEF5` | Parked until a date passes or a sample size is reached |
| `waiting:decision` | `#C5DEF5` | Parked until the owner makes a named decision |
| `waiting:issue` | `#C5DEF5` | Parked until another open issue lands |
| `waiting:external` | `#C5DEF5` | Parked on a vendor, third party or outside demand |
| `epic` | `#3E4B9E` | Tracking issue grouping related work items |
| `stays open` | `#BFD4F2` | Kept open on purpose (tracker); not a work item |

### Parking

A parked issue carries one `waiting:*` label **and** a comment whose first
line has a fixed format, so `/backlog` can tell when it comes due:

| Label | First line of the comment |
|---|---|
| `waiting:date` | `Parked: waiting:date until YYYY-MM-DD` |
| `waiting:decision` | `Parked: waiting:decision` (question on the next line) |
| `waiting:issue` | `Parked: waiting:issue on #N` |
| `waiting:external` | `Parked: waiting:external` (who and what on the next line) |

`/backlog` lists a `waiting:date` issue as **due** once its date passes, and a
`waiting:issue` issue as **may be unblocked** once #N closes. To push a date
back, post a new `Parked:` comment; the latest one wins.

---

## Issue Template

When Claude creates backlog items, it uses this format:

```markdown
## Summary
[One-line description of the requirement]

## Context
[Why this came up - conversation context, user request, or identified need]

Introduced by: PR #[N]
[Bugs only - the PR whose change caused the bug, or `unknown`]

## Why now
[Optional: what it risks, what it blocks, a date it must land by]

## Suggested Agent(s)
[Optional - only when the project defines specialized subagent types
(e.g. under `.claude/agents/`) AND the work clearly maps to one or more
of them. Names each agent and which part of the work it owns. See
"Suggested Agent(s) — Routing to Specialized Subagents" below.]

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

## Suggested Agent(s) — Routing to Specialized Subagents

If your project defines specialized subagent types (custom agents under
`.claude/agents/`, each scoped to a particular kind of work — e.g. a
read-only research agent vs. one that writes code and runs experiments),
`/backlog`'s default flow has no way to know they exist: its instructions
are agent-agnostic and just implement issues directly in a generic
session.

`/backlog-add`'s template includes an optional `## Suggested Agent(s)`
section for exactly this. When the work an issue describes clearly maps
to one of your project's subagent types, name it there — e.g.:

```markdown
## Suggested Agent(s)
- `research-agent` (read-only, cites sources) for: investigating the
  underlying question before implementation
- `build-agent` (writes code, runs tests) for: implementing the change
  and verifying it
```

`/backlog` checks for this section when an issue is picked up and, if
present, uses the Agent/Task tool to invoke the named subagent(s) for
their part of the work instead of doing it directly. Leave the section
out entirely for ordinary issues — it's meant for the subset of work
that genuinely benefits from a specialized agent, not as boilerplate on
every issue.

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

Copy [`claude-code/CLAUDE.md.example`](../CLAUDE.md.example) into your
project's CLAUDE.md. It contains:

- **Fix now or file?** - fix small, confirmed defects in the session as
  their own PR; file an issue only when the work needs the owner, has to
  wait, spans several PRs, the session is busy, the cause isn't understood,
  or it is scope expansion the user didn't ask for.
- **The backlog suggestion box** for the file-instead cases.
- **Concurrent sessions** - work in `.claude/worktrees/`, never the main checkout.
- **Labels** and **commit/PR linking** rules, including the multi-PR title trap.

---

## File Structure

```
your-repo/
├── .claude/
│   ├── commands/
│   │   ├── backlog.md          # /backlog command
│   │   └── backlog-add.md      # /backlog-add command
│   ├── worktrees/              # Per-issue worktrees (gitignored)
│   └── BACKLOG_WORKFLOW.md     # This documentation
├── .gitignore                  # Add: .claude/worktrees/
└── CLAUDE.md                   # Project context (add backlog section)
```

---

## Copying to Other Projects

To use this workflow in another repository:

1. **Copy the `.claude` directory** to your new repo
2. **Run the setup script** in the new repo
3. **Add the backlog section** to that project's CLAUDE.md

```bash
# From your new project root
cp -r /path/to/LeanVibes/claude-code/.claude .
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
echo '.claude/worktrees/' >> .gitignore
```

---

## Tips & Best Practices

### For Users

1. **Be decisive** - When Claude suggests backlog, quickly say "do it" or "backlog medium"
2. **Use priorities consistently** - High = this week, Medium = this month, Low = someday
3. **Groom regularly** - Run `/backlog` periodically to review and reprioritize
4. **Close completed work** - Let Claude close issues when work is done

### For Claude (AI Context)

1. **Fix before filing** - A small, confirmed defect gets fixed now, not filed (see "Fix now or file?")
2. **Provide context** - Issue descriptions should be actionable without conversation history
3. **Suggest priority** - Always recommend a priority level with reasoning
4. **Link related items** - Reference existing issues when relevant
5. **Route to specialized subagents when relevant** - If the project defines subagent types under `.claude/agents/` and an issue's work clearly maps to one, add a `## Suggested Agent(s)` section naming it (see "Suggested Agent(s) — Routing to Specialized Subagents" above). Skip it for ordinary issues.

---

## Troubleshooting

### "gh: command not found"

Install GitHub CLI:
```bash
brew install gh
gh auth login
```

### Labels already exist

The setup script updates existing labels' color and description - this is fine,
and re-running it is how an older install picks up new labels.

### A label shows "Failed"

The script prints the `gh` error. Usually it is auth (`gh auth status`) or
missing write access to the repo.

### Issues missing from `/backlog`

Older LeanVibes versions only listed issues labelled `backlog`. The current
`/backlog` lists every open issue; update `.claude/commands/backlog.md`.

### Project board not linking

Ensure you're in the correct repository and the project name matches exactly.

---

## Contributing

This workflow is open for improvements. Key areas:
- [ ] Review loop (review -> fix -> re-review -> verdict)
- [ ] Sprint runner over the backlog
- [ ] Milestone/sprint integration
- [ ] Automated priority aging
- [ ] Cross-repo backlog views

---

*Workflow version 1.1 - Designed for Claude Code*
