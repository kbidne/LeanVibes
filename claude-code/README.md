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

For the "fix now or file?" policy and backlog suggestions, copy and customize the example:

```bash
cp /path/to/LeanVibes/claude-code/CLAUDE.md.example /your/project/CLAUDE.md
```

This tells Claude when to fix a defect on the spot and when to suggest filing it instead.

### 4. Ignore the worktree directory

```bash
echo '.claude/worktrees/' >> .gitignore
```

`/backlog` creates one git worktree per issue under `.claude/worktrees/`, so several Claude sessions can work in the same repo without overwriting each other.

## Usage

### `/backlog` - View & Work on Backlog

```
/backlog              # List open issues: workable by priority, due, parked, epics
/backlog 42           # Start working on issue #42 in its own worktree
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

### `/review-loop` - Review, Fix, Re-review, Merge

```
/review-loop 57                    # review PR #57, fix blocking findings, merge if ready
/review-loop 57 --no-merge         # stop at the verdict
/review-loop 57 --ask-decisions    # never take its own recommendation on a decision
/review-loop 57 --level high       # deeper closing review (default: medium)
```

The loop ends in one of two verdicts: **`ready`** (merged unless `--no-merge`) or **`decision_needed`** (at most three questions, each with a recommended answer). The rules that make it terminate:

- **Blocking means reachable.** A finding blocks only if something in the repo today can trigger it.
- **Only confirmed blocking findings change code.** Style, simplification and unreachable findings go to a single ledger issue, never to a fixer.
- **Rounds 2+ review only the fix commits**, with a fresh reviewer that runs the code instead of only reading it.
- **Only a verified head merges:** reviewed clean, nothing pushed since, CI green.
- **Caps, not heuristics:** `--max-deltas` delta rounds, a per-round fix budget, at most two issues filed per PR.
- **Follow-ups of follow-ups** are flagged as a design problem instead of filing more.

Reviewers are fresh Opus agents running Claude Code's `/code-review`; where that skill is unavailable, `/review-fallback` stands in. Optional per-project settings (risky paths, lint and test commands, budgets) go in `.claude/review-loop.json`; copy `review-loop.json.example`. `.claude/scripts/review_loop_policy.py` applies the path rules (standard-library Python 3.8+).

## Parking Issues

An issue that can't move yet gets one `waiting:*` label and a comment whose first line says what it's waiting for:

```bash
gh issue edit 42 --add-label waiting:date
gh issue comment 42 --body "Parked: waiting:date until 2027-01-15
Need 30 days of data before reading the result."
```

`/backlog` lists parked issues apart from workable ones and moves them to **Due for a look** once the date passes (or, for `Parked: waiting:issue on #N`, once #N closes). See "Parking an issue" in `backlog.md` for all four formats.

## Fix Now or File?

With `CLAUDE.md` configured, Claude fixes a defect on the spot when its cause is confirmed, the fix is small, and it needs no decision from you. It suggests filing instead when the work:

- Needs your decision or a priority call
- Has to wait (a date, data accumulating)
- Spans several PRs
- Would derail a task that must finish first
- Has a cause that isn't understood yet
- Is scope expansion: tangential, an enhancement, technical debt, or something you said to do "later"

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
    ├── commands/
    │   ├── backlog.md            # /backlog command
    │   ├── backlog-add.md        # /backlog-add command
    │   ├── review-loop.md        # /review-loop command
    │   └── review-fallback.md    # reviewer used when /code-review is unavailable
    ├── scripts/
    │   └── review_loop_policy.py # risky / always-ask path rules
    ├── review-loop.json          # optional, from review-loop.json.example
    └── worktrees/                # Per-issue and per-PR worktrees (gitignored)
```

## More Information

See the [main LeanVibes README](../README.md) for general documentation.
