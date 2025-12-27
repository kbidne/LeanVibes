# LeanVibes

A lightweight backlog management workflow for AI coding assistants + GitHub Projects. Create and manage GitHub Issues from your conversations with AI.

## Supported Tools

| Tool | Status | Folder |
|------|--------|--------|
| [Claude Code](claude-code/) | Full support | `claude-code/` |
| [Cursor](cursor/) | Full support | `cursor/` |
| [GitHub Copilot](github-copilot/) | Instructions only | `github-copilot/` |

## Core Features

- **Quick Issue Creation** - Add items to backlog without leaving your AI assistant
- **Proactive Suggestions** - AI identifies deferrable work during conversations
- **Priority-Based Organization** - High, medium, low priority labels
- **GitHub Projects Integration** - Visual board for tracking progress
- **Automatic Issue Linking** - Commits and PRs auto-reference the issue being worked on

## How It Works

1. **Setup** - Run the shared setup script to create labels and project board
2. **Add Items** - Use tool-specific commands to add backlog items
3. **Work on Items** - Pull items from backlog, AI tracks the issue
4. **Auto-Link** - Commits include `Fixes #X`, PRs include `Closes #X`
5. **Auto-Close** - Issues close automatically when code merges

## Quick Start

### 1. Prerequisites

- [GitHub CLI](https://cli.github.com/) installed and authenticated
- Project scope enabled for project board integration

```bash
brew install gh
gh auth login
gh auth refresh -s project
```

### 2. Run Setup Script

From your project root:

```bash
# Download and run the setup script
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash
```

Or clone and run:

```bash
git clone https://github.com/kbidne/LeanVibes.git
./LeanVibes/scripts/setup-backlog.sh
```

This creates labels in your repo and a "Backlog" project board.

> **Note:** GitHub Projects (v2) are owned by users or organizations, not individual repositories. The setup script creates a user-level project that can include issues from any of your repos.

### 3. Install Tool-Specific Files

Choose your AI coding assistant and follow the instructions in that folder:

- **[Claude Code](claude-code/)** - Copy `.claude/` folder and `CLAUDE.md`
- **[Cursor](cursor/)** - Copy `.cursorrules` file
- **[GitHub Copilot](github-copilot/)** - Use the provided prompt instructions

### 4. Try the Example Project (Optional)

New to LeanVibes? Check out the **[example project](example/)** - a fake auth system with a guided walkthrough to practice the workflow.

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

## Contributing

Want to add support for another tool? PRs welcome! Each tool needs:

1. A folder with the tool name
2. A README with installation instructions
3. Tool-specific configuration files
4. Instructions for proactive backlog suggestions

## License

MIT
