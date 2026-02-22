#!/bin/bash
# ──────────────────────────────────────────────────────────
# EQD-AI Git Snapshot — Quick commit of current state
# Usage:
#   bash scripts/git_snapshot.sh "what you changed"
#   bash scripts/git_snapshot.sh                      # auto-generates message
# ──────────────────────────────────────────────────────────

set -e

# Check we're in the right directory
if [ ! -d ".git" ]; then
    echo "ERROR: No git repo found. Run scripts/git_init.sh first."
    exit 1
fi

# Show what changed
echo ""
echo "── Changes since last commit ──────────────────────────"
git status --short
echo ""

# Check if there are actually changes to commit
if git diff --quiet HEAD 2>/dev/null && git diff --cached --quiet 2>/dev/null && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "No changes to commit."
    exit 0
fi

# Stage all tracked + new project files (respects .gitignore)
git add \
    src/ \
    tests/ \
    scripts/ \
    eqd_config.yaml \
    .gitignore \
    IDEAS.md \
    2>/dev/null || true

for f in requirements.txt README.md pyproject.toml setup.py setup.cfg; do
    [ -f "$f" ] && git add "$f" 2>/dev/null || true
done

# Determine commit message
if [ -n "$1" ]; then
    MSG="$1"
else
    # Auto-generate message from changed files
    CHANGED=$(git diff --cached --name-only | head -5 | tr '\n' ', ' | sed 's/,$//')
    TOTAL=$(git diff --cached --name-only | wc -l | tr -d ' ')
    MSG="Snapshot: ${TOTAL} files changed (${CHANGED})"
fi

# Commit
git commit -m "$MSG"

echo ""
echo "── Snapshot saved ✓ ───────────────────────────────────"
git log --oneline -3
echo ""
echo "Rollback if needed:  git reset --soft HEAD~1"
echo ""
