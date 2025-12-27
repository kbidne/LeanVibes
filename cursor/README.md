# LeanVibes for Cursor

Backlog management workflow for [Cursor](https://cursor.sh) using `.cursorrules`.

## Installation

### 1. Run Setup Script

First, run the shared setup script to create labels and project board:

```bash
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
```

### 2. Copy .cursorrules to Your Project

```bash
cp /path/to/LeanVibes/cursor/.cursorrules /your/project/
```

Or download directly:

```bash
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/cursor/.cursorrules > .cursorrules
```

## Usage

Unlike Claude Code's slash commands, Cursor uses natural language. Ask the AI:

### View Backlog
- "Show me the backlog"
- "What's in the backlog?"
- "List backlog items by priority"

### Add to Backlog
- "Add to backlog: Fix the login timeout bug"
- "Backlog this as a medium priority enhancement"
- "Create a backlog item for adding dark mode"

### Work on Backlog Item
- "Work on issue #42"
- "Start working on the highest priority backlog item"
- "What should I work on next from the backlog?"

## Automatic Issue Linking

When working on a backlog item, Cursor will:

1. Display "Working on #X" reminder
2. Include `Fixes #[number]` in commit messages
3. Include `Closes #[number]` in PR descriptions

## Proactive Suggestions

With `.cursorrules` configured, Cursor will suggest deferring work when:

- Work is tangential to the main task
- It's an enhancement rather than a requirement
- It would significantly expand scope
- You mention "later" or "eventually"
- Cursor identifies technical debt

Example interaction:
```
You: Can you also add responsive breakpoints while you're at it?

Cursor:
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
|  Reply with:                                             |
|  - "do it" to implement now                              |
|  - "backlog" to add to backlog                           |
+----------------------------------------------------------+

You: backlog

Cursor: Created backlog item #15: Add responsive breakpoints
        Priority: medium | Type: enhancement
```

## File Structure

```
your-project/
└── .cursorrules    # Cursor AI instructions
```

## More Information

See the [main LeanVibes README](../README.md) for general documentation.
