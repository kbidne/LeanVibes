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

### Park an Issue
- "Park #42 until January 15"
- "Park #42 until #40 is done"

Cursor adds a `waiting:*` label and a `Parked:` comment, and the backlog view flags the issue as due once the date passes or #40 closes.

## Fix Now or File?

With `.cursorrules` configured, Cursor fixes a small defect on the spot when its cause is confirmed and it needs no decision from you. It suggests filing instead when the work:

- Needs your decision, has to wait, or spans several PRs
- Has a cause that isn't understood yet
- Is scope expansion: tangential, an enhancement, technical debt, or something you said to do "later"

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
