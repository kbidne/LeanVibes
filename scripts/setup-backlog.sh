#!/bin/bash

# LeanVibes backlog setup script
# Run once per repository to create labels and the "Backlog" project board.
# Safe to re-run: existing labels get their color and description updated.

set -e

PROJECT_TITLE="Backlog"

echo "========================================"
echo "  LeanVibes Backlog Setup"
echo "========================================"
echo ""

# Check for gh CLI
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo ""
    echo "Install it with:"
    echo "  brew install gh"
    echo ""
    echo "Then authenticate:"
    echo "  gh auth login"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub CLI."
    echo ""
    echo "Run:"
    echo "  gh auth login"
    exit 1
fi

# Get repo info
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null)
if [ -z "$REPO" ]; then
    echo "Error: Not in a GitHub repository."
    exit 1
fi

echo "Repository: $REPO"
echo ""

# ========================================
# Create Labels
# ========================================

echo "Creating labels..."

EXISTING_LABELS=$(gh label list --limit 500 --json name -q '.[].name')
LABEL_FAILURES=0

create_label() {
    local name=$1
    local color=$2
    local description=$3
    local verb="Created"
    local err

    if printf '%s\n' "$EXISTING_LABELS" | grep -Fxq "$name"; then
        verb="Updated"
    fi

    # --force updates color/description on a label that already exists, so a
    # re-run brings an old install up to date. A real failure (auth, network,
    # permissions) is reported, not mistaken for "already exists".
    if err=$(gh label create "$name" --color "$color" --description "$description" --force 2>&1); then
        echo "  + $verb: $name"
    else
        echo "  ! Failed:  $name ($err)"
        LABEL_FAILURES=$((LABEL_FAILURES + 1))
    fi
}

# Provenance (nothing filters on it; /backlog lists every open issue)
create_label "backlog" "0E8A16" "Filed by a LeanVibes command (provenance only; /backlog lists every open issue)"

# Priority labels
create_label "priority:high" "D73A4A" "High priority - address this week"
create_label "priority:medium" "FBCA04" "Medium priority - address this month"
create_label "priority:low" "0075CA" "Low priority - someday/maybe"

# Type labels
create_label "type:feature" "A2EEEF" "New feature or functionality"
create_label "type:bug" "D73A4A" "Bug or defect"
create_label "type:enhancement" "7057FF" "Enhancement to existing feature"
create_label "type:debt" "FEF2C0" "Technical debt or refactoring"

# Parked labels (each paired with a "Parked:" comment; see /backlog "Parking an issue")
create_label "waiting:date" "C5DEF5" "Parked until a date passes or a sample size is reached; the issue says when"
create_label "waiting:decision" "C5DEF5" "Parked until the owner makes a decision the issue names"
create_label "waiting:issue" "C5DEF5" "Parked until another open issue lands"
create_label "waiting:external" "C5DEF5" "Parked on a vendor, third party, or outside demand"

# Structure labels
create_label "epic" "3E4B9E" "Tracking issue grouping related work items"
create_label "stays open" "BFD4F2" "Kept open on purpose (tracker or owner's call); not a work item to pick up"

echo ""

if [ "$LABEL_FAILURES" -gt 0 ]; then
    echo "  ! $LABEL_FAILURES label(s) failed. Check 'gh auth status' and that you can write to $REPO."
    echo ""
fi

# ========================================
# Create Project Board
# ========================================

echo "Setting up project board..."

find_project_number() {
    gh project list --owner @me --format json 2>/dev/null \
        | jq -r --arg t "$PROJECT_TITLE" '[.projects[] | select(.title == $t) | .number] | first // empty'
}

if ! command -v jq &> /dev/null; then
    echo "  ! jq is not installed; skipping project board setup."
    echo "    Install it with: brew install jq"
elif ! gh project list --owner @me &>/dev/null; then
    echo "  ! Missing 'project' scope for GitHub CLI"
    echo ""
    echo "  To enable project board integration, run:"
    echo "    gh auth refresh -s project"
    echo ""
    echo "  Then re-run this script."
else
    OWNER=$(gh api user --jq '.login' 2>/dev/null)
    PROJECT_NUM=$(find_project_number)

    if [ -n "$PROJECT_NUM" ]; then
        echo "  - Project '$PROJECT_TITLE' already exists"
    elif gh project create --owner @me --title "$PROJECT_TITLE" >/dev/null 2>&1; then
        echo "  + Created project: $PROJECT_TITLE"
        PROJECT_NUM=$(find_project_number)
    else
        echo "  ! Could not create project (may require manual setup)"
        echo "    Visit: https://github.com/$OWNER?tab=projects"
    fi

    if [ -n "$PROJECT_NUM" ]; then
        PROJECT_URL="https://github.com/users/$OWNER/projects/$PROJECT_NUM"
        echo "    URL: $PROJECT_URL"
    fi
fi

echo ""

# ========================================
# Summary
# ========================================

echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Labels:"
echo "  - backlog (provenance only)"
echo "  - priority:high, priority:medium, priority:low"
echo "  - type:feature, type:bug, type:enhancement, type:debt"
echo "  - waiting:date, waiting:decision, waiting:issue, waiting:external"
echo "  - epic, stays open"
echo ""
echo "Next steps:"
echo "  1. Add the backlog section to your CLAUDE.md (or .cursorrules)"
echo "  2. Add '.claude/worktrees/' to your .gitignore"
echo "  3. Start using /backlog and /backlog-add"
if [ -n "${PROJECT_URL:-}" ]; then
    echo "  4. Optionally configure board columns at: $PROJECT_URL"
fi
echo ""
echo "Documentation: https://github.com/kbidne/LeanVibes"
echo ""
