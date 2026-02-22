#!/bin/bash
# ──────────────────────────────────────────────────────────
# EQD-AI Git Setup Script
# Run from your Mac terminal inside the eqa_ai project folder:
#   cd /path/to/eqa_ai && bash scripts/git_init.sh
# ──────────────────────────────────────────────────────────

set -e  # Exit on any error

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  EQD-AI — Git Repository Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. Check we're in the right directory ─────────────────
if [ ! -f "eqd_config.yaml" ] || [ ! -d "src" ]; then
    echo "ERROR: Run this script from the eqa_ai project root."
    echo "  cd /path/to/eqa_ai && bash scripts/git_init.sh"
    exit 1
fi

# ── 2. Check if git is already initialized ────────────────
if [ -d ".git" ]; then
    echo "Git repository already exists."
    echo ""
    git status --short
    echo ""
    echo "To create a snapshot of current state, run:"
    echo "  bash scripts/git_snapshot.sh \"your commit message\""
    exit 0
fi

# ── 3. Initialize git repo ────────────────────────────────
echo "Initializing git repository..."
git init
echo ""

# ── 4. Verify .gitignore ─────────────────────────────────
if [ -f ".gitignore" ]; then
    echo ".gitignore found ✓"
else
    echo "WARNING: No .gitignore found — creating one"
    cat > .gitignore << 'GITIGNORE'
.env
__pycache__/
*.pyc
*.db
*.json
.pytest_cache/
htmlcov/
*.egg-info/
dist/
build/
.mypy_cache/
.venv/
.DS_Store
GITIGNORE
fi

# ── 5. Stage all project files ────────────────────────────
echo ""
echo "Staging project files..."
git add \
    src/ \
    tests/ \
    scripts/ \
    eqd_config.yaml \
    .gitignore \
    requirements.txt \
    IDEAS.md \
    2>/dev/null || true

# Also add any other top-level files that aren't ignored
for f in README.md pyproject.toml setup.py setup.cfg; do
    [ -f "$f" ] && git add "$f" 2>/dev/null || true
done

echo ""
echo "Files staged:"
git status --short
echo ""

# ── 6. Initial commit ────────────────────────────────────
echo "Creating initial commit..."
git commit -m "Initial commit: EQD-AI pipeline v0.2

4-layer qualitative analysis pipeline (Braun & Clarke):
- Layer 0: Document → Segment preprocessing
- Layer 1: IC extraction with coder agent + codebook comparator + HIL
- Layer 2: Theme synthesis with coherence gate + IC redistribution
- Layer 2.5: Category synthesis
- Layer 3: 16 quality metrics across 5 domains

Key features:
- Meta-IC filtering (YAML configurable)
- Adaptive coherence threshold (0.90 small / 1.0 standard)
- IC stability index, cross-review convergence metrics
- Thematic coverage ratio, orphaned IC tracking
- Full audit trail + decision logging"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Git initialized ✓"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  • Snapshot after changes:  bash scripts/git_snapshot.sh \"message\""
echo "  • View history:            git log --oneline"
echo "  • View changes:            git diff"
echo "  • Rollback last commit:    git reset --soft HEAD~1"
echo ""
