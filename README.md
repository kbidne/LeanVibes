# LeanVibes

A lightweight backlog management workflow for Claude Code + GitHub Projects. Create and manage GitHub Issues from your Claude Code conversations.

## Features

- **Quick Issue Creation** - Add items to backlog without leaving Claude Code
- **Proactive Suggestions** - Claude identifies deferrable work during conversations
- **Priority-Based Organization** - High, medium, low priority labels
- **GitHub Projects Integration** - Visual board for tracking progress

## Installation

### 1. Copy to Your Project

Copy the `.claude` directory to your project root:

```bash
cp -r /path/to/LeanVibes/.claude /your/project/
```

Or clone and copy:

```bash
git clone https://github.com/YOUR_USERNAME/LeanVibes.git
cp -r LeanVibes/.claude /your/project/
```

### 2. Run Setup Script

From your project root:

```bash
./.claude/scripts/setup-backlog.sh
```

This creates the required labels in your repo and a "Backlog" project board.

> **Note:** GitHub Projects (v2) are owned by users or organizations, not individual repositories. The setup script creates a user-level project that can include issues from any of your repos. Issues are still created in the specific repo where you run the commands.

### 3. Prerequisites

- [GitHub CLI](https://cli.github.com/) installed and authenticated
- **Project scope** enabled (for project board integration)

```bash
brew install gh
gh auth login
gh auth refresh -s project   # Enable project board access
```

## Usage

### `/backlog` - View & Work on Backlog

```
/backlog              # List all backlog items by priority
/backlog 42           # Start working on issue #42
/backlog suggest      # Get Claude's recommendation
```

### `/backlog-add` - Quick Add to Backlog

```
/backlog-add high feature Add user authentication
/backlog-add medium bug Fix mobile navigation
/backlog-add low enhancement Improve loading states
```

Format: `/backlog-add [priority] [type] [title]`

**Priorities:** `high`, `medium`, `low`

**Types:** `feature`, `bug`, `enhancement`, `debt`

## How It Works

During conversations, when Claude identifies work that could be deferred:

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
|  [backlog] - Add to backlog                              |
|  [backlog high/medium/low] - Add with priority           |
+----------------------------------------------------------+
```

## Labels Created

| Label | Color | Purpose |
|-------|-------|---------|
| `backlog` | Green | Identifies all backlog items |
| `priority:high` | Red | Urgent / blocking items |
| `priority:medium` | Yellow | Important but not urgent |
| `priority:low` | Blue | Nice to have / future work |
| `type:feature` | Cyan | New functionality |
| `type:bug` | Red | Defects to fix |
| `type:enhancement` | Purple | Improvements to existing features |
| `type:debt` | Tan | Technical debt / refactoring |

## File Structure

```
your-project/
└── .claude/
    ├── commands/
    │   ├── backlog.md          # /backlog command
    │   └── backlog-add.md      # /backlog-add command
    ├── scripts/
    │   └── setup-backlog.sh    # One-time setup script
    └── BACKLOG_WORKFLOW.md     # Detailed documentation
```

## Adding to CLAUDE.md (Optional)

For proactive backlog suggestions, add this to your project's CLAUDE.md:

```markdown
## Backlog Workflow

This project uses the LeanVibes backlog workflow.

When identifying work that could be deferred, present a backlog suggestion box.
Suggest adding to backlog when:
- Work is tangential to the main task
- It's an enhancement rather than a requirement
- It would significantly expand scope
- The user mentions "later" or "eventually"
- You identify technical debt or optimization opportunities
```

## License

MIT
