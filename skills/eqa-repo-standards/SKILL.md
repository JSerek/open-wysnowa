---
name: eqa-repo-standards
description: |
  Enforces EQD-AI repository quality standards: syntax verification,
  test confirmation, selective staging, commit message format, and
  documentation updates. Use when preparing to commit code, after
  completing a sprint task, or when diagnosing a test failure.
  Triggers: "commit", "push", "all tests green", "tests passing",
  "tests failing", "test failure", "git add", "ready to commit",
  "let's commit", "do commit".
---

# EQA-AI Repository Standards

## Objective

Every commit to EQD-AI should leave the repository in a known-good state:
syntax clean, tests green, only relevant files staged, message intelligible
to a future reader, and documentation updated. This is not ceremony — it
is the mechanism by which future sessions can orient without re-reading
the full history.

## Process

1. **AST-check all modified Python files** before anything else:
   ```bash
   python3 -c "
   import ast, sys
   for f in ['src/models.py', 'src/pipeline.py']:  # list modified files
       try:
           ast.parse(open(f).read())
           print(f'  OK  {f}')
       except SyntaxError as e:
           print(f'  ERR {f}: {e}')
   "
   ```
   Fix any syntax errors before proceeding.

2. **Confirm tests are green.** The user runs this locally:
   ```bash
   python -m pytest tests/ -x -q
   ```
   Do not commit until you have "N passed" confirmation from the user.
   If tests fail, diagnose before fixing — see test failure protocol below.

3. **Stage specific files by name.** Never `git add .` or `git add -A`:
   ```bash
   git add src/models.py src/category_agent.py scripts/run_pipeline.py
   git status  # verify staged set before committing
   ```

4. **Write the commit message** using the heredoc format:
   ```bash
   git commit -m "$(cat <<'EOF'
   <prefix>(<scope>): short imperative summary (≤72 chars)

   Body: explain WHY, not just what. Reference relevant design
   principles or architectural decisions if applicable. List
   key changes if the commit covers multiple concerns.

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   EOF
   )"
   ```

5. **Update IDEAS.md** for completed sprint items — remove from [ready]
   or archive. Use the `eqa-ideas-maintenance` skill for this step.
   Bundle the IDEAS.md update in the same commit as the code change.

6. **Run `git log --oneline -5`** after committing to verify the message
   reads clearly in context.

## Commit Prefix Reference

| Prefix | When to use |
|--------|-------------|
| `feat` | New capability added |
| `fix` | Bug or incorrect behavior corrected |
| `refactor` | Code restructured without behavior change |
| `chore` | Config, docs, dependency, or maintenance updates |
| `test` | Tests added or updated |
| `fix(tests)` | Stale or broken test corrected |

## Test Failure Protocol

When a test fails after a code change, diagnose before patching:

**Stale test** (test references removed behavior):
- Update the test to reflect the intentional change
- If a feature was removed: convert the positive assertion to a negative one
  (e.g. `assert "SUBCODE" not in prompt` — do not just delete the test)

**Broken code** (new code breaks existing contract):
- Fix the code, not the test
- If the test was wrong: fix the test AND explain why in the commit body

**Test environment gap** (test bypasses `__init__`, missing attribute):
- Add a `hasattr` guard or a `MagicMock` in the test setup
- Document why the guard is there — it's information about the design

## Rules

- **NEVER commit with failing tests.** A red test suite means the code
  is in an unknown state. Fix the root cause, not the symptom.

- **NEVER use `git add .` or `git add -A`.** Large repos accumulate junk
  (debug files, .env fragments, binary artifacts). Name each file explicitly.

- **NEVER commit `.env` or any file containing API keys or credentials.**
  Even if the key has been rotated, the habit of never committing credentials
  is more valuable than the one-off convenience.

- **Co-Authored-By footer is non-negotiable.** Every commit written with
  AI assistance gets the footer. This is a transparency commitment, not
  optional metadata.

- **Always use the heredoc format** for commit messages with a body.
  Inline `-m "..."` breaks on special characters and forces one-liners.

- **When removing a feature: add a negative assertion to tests.**
  `assert "SUBCODE" not in prompt` is more informative than deleting
  `assert "SUBCODE" in prompt`. The negative assertion documents the
  removal was deliberate.

- **Verify model names, API versions, and library versions via web search**
  before asserting them in code or config. Don't guess — ask the web.

> **Cross-reference:** After committing, use `eqa-ideas-maintenance` to
> update IDEAS.md status for completed tasks.
