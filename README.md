<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-light.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/logo.svg">
    <img src="docs/logo.svg" alt="LeanVibes logo" width="120">
  </picture>
</p>

# LeanVibes

> **[Visit the documentation site](https://kbidne.github.io/LeanVibes/)**

A lightweight backlog management workflow for AI coding assistants + GitHub Projects. Create and manage GitHub Issues from your conversations with AI.

## Supported Tools

| Tool | Status | Folder |
|------|--------|--------|
| [Claude Code](claude-code/) | Full support | `claude-code/` |
| [Cursor](cursor/) | Full support | `cursor/` |
| [GitHub Copilot](github-copilot/) | Instructions only | `github-copilot/` |

## Core Features

- **Quick Issue Creation** - Add items to backlog without leaving your AI assistant
- **Fix Now or File** - AI fixes small, confirmed defects on the spot and suggests filing the rest
- **Priority-Based Organization** - High, medium, low priority labels
- **Parking** - `waiting:*` labels park blocked issues; `/backlog` resurfaces them when they come due
- **Per-Issue Worktrees** - Parallel AI sessions each work in their own git worktree
- **GitHub Projects Integration** - Visual board for tracking progress
- **Automatic Issue Linking** - Commits and PRs auto-reference the issue being worked on
- **Backlog Sprint** *(Claude Code)* - `/backlog-sprint` triages the backlog by value, you approve the queue once, then it builds each fix and runs `/review-loop` on it
- **Review Loop** *(Claude Code)* - `/review-loop <PR>` reviews, fixes, re-reviews and merges a PR, ending in a verdict instead of an endless "until zero findings"

## How It Works

1. **Setup** - Run the shared setup script to create labels and project board
2. **Add Items** - Use tool-specific commands to add backlog items
3. **Work on Items** - Pull items from backlog; AI works in a per-issue worktree and tracks the issue
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

This creates labels in your repo and a "Backlog" project board. It is safe to re-run: existing labels get their color and description updated, so re-running is how an older install picks up new labels.

> **Note:** GitHub Projects (v2) are owned by users or organizations, not individual repositories. The setup script creates a user-level project that can include issues from any of your repos.

### 3. Install Tool-Specific Files

Choose your AI coding assistant and follow the instructions in that folder:

- **[Claude Code](claude-code/)** - Copy `.claude/` folder and `CLAUDE.md`
- **[Cursor](cursor/)** - Copy `.cursorrules` file
- **[GitHub Copilot](github-copilot/)** - Use the provided prompt instructions

Installed files don't update themselves. To pick up a new version, re-copy them: see [Updating](claude-code/README.md#updating) for Claude Code, and the [release notes](#release-notes) for what changed.

### 4. Try the Example Project (Optional)

New to LeanVibes? Check out the **[example project](example/)** - a fake auth system with a guided walkthrough to practice the workflow.

## Labels Created

| Label | Color | Purpose |
|-------|-------|---------|
| `backlog` | Green | Provenance only: filed by a LeanVibes command (`/backlog` lists every open issue) |
| `priority:high` | Red | Urgent / blocking items |
| `priority:medium` | Yellow | Important but not urgent |
| `priority:low` | Blue | Nice to have / future work |
| `type:feature` | Cyan | New functionality |
| `type:bug` | Red | Defects to fix |
| `type:enhancement` | Purple | Improvements to existing features |
| `type:debt` | Tan | Technical debt / refactoring |
| `waiting:date` | Light blue | Parked until a date passes or a sample size is reached |
| `waiting:decision` | Light blue | Parked until the owner makes a named decision |
| `waiting:issue` | Light blue | Parked until another open issue lands |
| `waiting:external` | Light blue | Parked on a vendor, third party or outside demand |
| `epic` | Indigo | Tracking issue grouping related work items |
| `stays open` | Pale blue | Kept open on purpose (tracker); not a work item |

Each `waiting:*` label is paired with a comment whose first line is `Parked: waiting:date until YYYY-MM-DD` (or `Parked: waiting:decision`, `Parked: waiting:issue on #N`, `Parked: waiting:external`). That is how `/backlog` knows when a parked issue is due.

### Review-loop labels (optional)

Created with `--review-loop` (or by `/review-loop` on first use):

```bash
curl -sL https://raw.githubusercontent.com/kbidne/LeanVibes/main/scripts/setup-backlog.sh | bash -s -- --review-loop
```


| Label | Purpose |
|-------|---------|
| `review:ready` | Verdict: verified head, CI green, mergeable |
| `review:decision-needed` | Stopped on a question for a human |
| `review:chain` | A chain of loop-filed follow-ups; needs a design pass on the root issue |
| `review:ledger` | The issue that collects non-blocking review notes |

### Sprint labels (optional)

Created with `--sprint` (which implies `--review-loop`):

| Label | Purpose |
|-------|---------|
| `sprint:keep` | Queue a low-priority loop-filed issue despite the value floor |
| `design:patch-separately` | A design note says to patch this chain follow-up on its own |

## Release Notes

### Unreleased

- **`/backlog` reads comments with plain `gh issue view N --comments`** ([#8](https://github.com/kbidne/LeanVibes/pull/8), Claude Code). The `--jq` interpolation and the `for` loop that fetched comments could be denied under a permission allowlist in unattended runs. Cut-off output now leaves a parked issue parked instead of guessing. To update, re-copy `.claude/commands/backlog.md` ([Updating](claude-code/README.md#updating)); no new labels.
- **Updating instructions** for Claude Code installs ([Updating](claude-code/README.md#updating)).

### v1.2.0

- **Parking and a wider `/backlog`** ([#4](https://github.com/kbidne/LeanVibes/pull/4)). `/backlog` lists every open issue, not only `backlog`-labelled ones, grouped into Workable, Due, Parked and Epics. Blocked issues get a `waiting:*` label and a `Parked:` comment, and come back on their own when the date passes or the blocking issue closes. Your AI now fixes small confirmed defects on the spot and files the rest. Each issue gets its own worktree. `/backlog-add` records `Introduced by: PR #N` and a `## Why now` section. `setup-backlog.sh` finds the project board by title, updates existing labels, and reports real failures. Cursor, Copilot and the docs were updated to match.
- **`/review-loop`** ([#5](https://github.com/kbidne/LeanVibes/pull/5), Claude Code). Reviews a PR, fixes only blocking findings something can reach, re-reviews each fix, and ends in a verdict: `ready` (merged once the head is verified and CI is green) or `decision_needed`. Non-blocking notes go to one ledger issue. Uses `/code-review` where available and `/review-fallback` otherwise. Optional settings live in `.claude/review-loop.json`. `setup-backlog.sh --review-loop` creates its labels.
- **`/backlog-sprint`** ([#6](https://github.com/kbidne/LeanVibes/pull/6), Claude Code). Triages the backlog by value, you approve the queue once, then each item gets an implementer PR and a review loop in the same session. Chains of follow-ups get one design note on the root issue instead of more patches. The report leads with decisions waiting on you and compares issues filed against issues closed. `setup-backlog.sh --sprint` creates its labels.
- **Unattended runs.** Every shell step in the new commands is a single command (`.claude/scripts/workflow_state.py` handles locks, worktrees, metrics and lint and test runs), so they work under a permission allowlist and in `claude -p`. A GitHub Actions check runs the script tests and `bash -n` on every PR.

## Contributing

Want to add support for another tool? PRs welcome! Each tool needs:

1. A folder with the tool name
2. A README with installation instructions
3. Tool-specific configuration files
4. Instructions for proactive backlog suggestions

## License

MIT
