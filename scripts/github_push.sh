#!/bin/bash
# ──────────────────────────────────────────────────────────
# EQD-AI → GitHub: Create private repo and push all code
#
# Prerequisites (both must be installed on your Mac):
#   brew install gh git
#
# Usage:
#   1. cd /path/to/eqa_ai
#   2. bash scripts/github_push.sh
# ──────────────────────────────────────────────────────────

set -e

REPO_NAME="eqd-ai"
REPO_DESC="EQD-AI: Exploratory Qualitative Data Analysis pipeline (Braun & Clarke)"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  EQD-AI → GitHub"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. Check prerequisites ────────────────────────────────
if ! command -v gh &>/dev/null; then
    echo "ERROR: GitHub CLI not installed."
    echo "  brew install gh"
    exit 1
fi
if ! command -v git &>/dev/null; then
    echo "ERROR: git not installed."
    echo "  brew install git"
    exit 1
fi
if [ ! -f "eqd_config.yaml" ] || [ ! -d "src" ]; then
    echo "ERROR: Run from the eqa_ai project root."
    echo "  cd /path/to/eqa_ai && bash scripts/github_push.sh"
    exit 1
fi

# ── 2. GitHub auth ────────────────────────────────────────
echo "Checking GitHub auth..."
if ! gh auth status &>/dev/null; then
    echo "Not authenticated. Logging in..."
    gh auth login
fi
GH_USER=$(gh api user --jq '.login')
echo "Authenticated as: $GH_USER ✓"
echo ""

# ── 3. Init git if needed ─────────────────────────────────
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
    git checkout -b main 2>/dev/null || true
fi

# ── 4. Update .gitignore to exclude data + secrets ────────
cat > .gitignore << 'GITIGNORE'
# Secrets
.env
*.env.*

# Data files (potentially sensitive / large)
*.csv
*.db

# Python artifacts
__pycache__/
*.pyc
*.pyo
.pytest_cache/
htmlcov/
*.egg-info/
dist/
build/
.mypy_cache/
.venv/

# OS
.DS_Store
Thumbs.db

# Results / exports (generated, not source)
*.json
GITIGNORE

echo ".gitignore updated ✓"

# ── 5. Stage all source files ─────────────────────────────
echo "Staging files..."

# Core source
git add src/ tests/ scripts/ eqd_config.yaml .gitignore

# Docs if present
for f in requirements.txt IDEAS.md PLAN.md EQD_AI_Architecture_v0.1.docx \
         EQD_AI_Metrics_Reference.docx EQD_AI_Testing_Plan.md \
         LLM_AGENTS_BEST_PRACTICES_GUIDE.md README.md pyproject.toml setup.py; do
    [ -f "$f" ] && git add "$f" && echo "  + $f" || true
done

# .env.example is safe (no real keys)
[ -f ".env.example" ] && git add ".env.example" && echo "  + .env.example" || true

echo ""
git status --short
echo ""

# ── 6. Commit ─────────────────────────────────────────────
# Only commit if there are staged changes
if ! git diff --cached --quiet; then
    git commit -m "EQD-AI v0.2: synthesizer granularity + coherence gate + 4 new metrics

Changes since v0.1:
- F1: Meta-IC filtering (YAML configurable, domain-agnostic defaults)
- F2: Post-synthesis coherence gate with IC redistribution
- F3: Model upgrade — synthesizer + category on Sonnet 4.5
- P1: Synthesizer prompt specificity fix (3-6 ICs/theme, not fewer-is-better)
- P2: Adaptive coherence threshold (0.90 for <5 ICs, 1.0 for 5+)
- P3: Orphaned IC redistribution after dissolution, dissolved themes excluded from metrics
- P4: 4 new metrics — IC stability index, cross-review convergence,
      thematic coverage ratio, orphaned IC count (16 metrics total)
- Git setup scripts added"
    echo "Commit created ✓"
else
    echo "Nothing new to commit — using existing commits."
fi

echo ""
git log --oneline
echo ""

# ── 7. Create GitHub repo ─────────────────────────────────
echo "Creating private GitHub repository: $REPO_NAME..."

if gh repo view "$GH_USER/$REPO_NAME" &>/dev/null; then
    echo "Repo $GH_USER/$REPO_NAME already exists — skipping creation."
else
    gh repo create "$REPO_NAME" \
        --private \
        --description "$REPO_DESC" \
        --source=. \
        --remote=origin \
        --push
    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  Repo created and pushed ✓"
    echo "  https://github.com/$GH_USER/$REPO_NAME"
    echo "═══════════════════════════════════════════════════════"
    exit 0
fi

# ── 8. Push to existing repo ──────────────────────────────
REMOTE_URL=$(gh repo view "$GH_USER/$REPO_NAME" --json sshUrl --jq '.sshUrl' 2>/dev/null \
    || gh repo view "$GH_USER/$REPO_NAME" --json url --jq '.url')

if ! git remote get-url origin &>/dev/null; then
    git remote add origin "$REMOTE_URL"
fi

git push -u origin main

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Pushed ✓"
echo "  https://github.com/$GH_USER/$REPO_NAME"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Future snapshots:"
echo "  bash scripts/git_snapshot.sh \"what changed\""
echo "  git push"
echo ""
