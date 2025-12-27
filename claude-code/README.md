# LeanVibes for Claude Code

Backlog management workflow for [Claude Code](https://claude.ai/code) using slash commands.

## Installation

### 1. Run Setup Script

First, run the shared setup script to create labels and project board:

```bash
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
```

### 2. Copy Files to Your Project

Copy the `.claude` directory to your project root:

```bash
cp -r /path/to/LeanVibes/claude-code/.claude /your/project/
```

### 3. Add CLAUDE.md (Optional but Recommended)

For proactive backlog suggestions, copy and customize the example:

```bash
cp /path/to/LeanVibes/claude-code/CLAUDE.md.example /your/project/CLAUDE.md
```

This tells Claude to suggest adding items to the backlog when it identifies deferrable work.

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

## Automatic Issue Linking

When you work on a backlog item using `/backlog [number]`, Claude automatically:

1. **Includes `Fixes #[number]` in commit messages** - Links commits to the issue
2. **Includes `Closes #[number]` in PR descriptions** - Auto-closes the issue when PR merges

Example commit:
```
Add user authentication

Fixes #42

🤖 Generated with Claude Code
```

## Proactive Suggestions

With `CLAUDE.md` configured, Claude will suggest deferring work when:

- Work is tangential to the main task
- It's an enhancement rather than a requirement
- It would significantly expand scope
- You mention "later" or "eventually"
- Claude identifies technical debt or optimization opportunities

Example suggestion:
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

## File Structure

```
your-project/
├── CLAUDE.md                     # Project instructions (optional)
└── .claude/
    └── commands/
        ├── backlog.md            # /backlog command
        └── backlog-add.md        # /backlog-add command
```

## More Information

See the [main LeanVibes README](../README.md) for general documentation.
