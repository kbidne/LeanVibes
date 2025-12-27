#!/bin/bash

# Claude Code + GitHub Projects Backlog Setup Script
# Run this once per repository to set up labels and project board

set -e

echo "========================================"
echo "  Backlog Workflow Setup"
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

create_label() {
    local name=$1
    local color=$2
    local description=$3

    if gh label create "$name" --color "$color" --description "$description" 2>/dev/null; then
        echo "  + Created: $name"
    else
        echo "  - Exists:  $name"
    fi
}

# Backlog identifier
create_label "backlog" "0E8A16" "Backlog item managed by Claude Code"

# Priority labels
create_label "priority:high" "D73A4A" "High priority - address this week"
create_label "priority:medium" "FBCA04" "Medium priority - address this month"
create_label "priority:low" "0075CA" "Low priority - someday/maybe"

# Type labels
create_label "type:feature" "A2EEEF" "New feature or functionality"
create_label "type:bug" "D73A4A" "Bug or defect"
create_label "type:enhancement" "7057FF" "Enhancement to existing feature"
create_label "type:debt" "FEF2C0" "Technical debt or refactoring"

echo ""

# ========================================
# Create Project Board
# ========================================

echo "Setting up project board..."

# Check if project exists
PROJECT_EXISTS=$(gh project list --owner @me --format json | grep -c '"title":"Backlog"' || true)

if [ "$PROJECT_EXISTS" -gt 0 ]; then
    echo "  - Project 'Backlog' already exists"
else
    # Create the project
    PROJECT_URL=$(gh project create --owner @me --title "Backlog" --format json 2>/dev/null | grep -o '"url":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$PROJECT_URL" ]; then
        echo "  + Created project: Backlog"
        echo "    URL: $PROJECT_URL"
    else
        echo "  ! Could not create project (may require manual setup)"
        echo "    Visit: https://github.com/$REPO/projects"
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
echo "Labels created:"
echo "  - backlog"
echo "  - priority:high, priority:medium, priority:low"
echo "  - type:feature, type:bug, type:enhancement, type:debt"
echo ""
echo "Next steps:"
echo "  1. Add the backlog section to your CLAUDE.md"
echo "  2. Start using /backlog and /backlog-add commands"
echo "  3. Optionally configure project board columns at:"
echo "     https://github.com/$REPO/projects"
echo ""
echo "Documentation: .claude/BACKLOG_WORKFLOW.md"
echo ""
