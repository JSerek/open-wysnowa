# EQD-AI Development Skills

Four workflow skills for developing the EQD-AI pipeline with Claude.
Built to the format defined in `SKILL_CREATION_BEST_PRACTICES.md`.

## Skills

| Skill | Triggers on | Purpose |
|-------|-------------|---------|
| `eqa-decision-protocol` | "should we", "which option", "design choice" | Structured AskUserQuestion for design decisions |
| `eqa-ideas-maintenance` | "update IDEAS.md", "mark as done", "log this" | IDEAS.md status tags + footer discipline |
| `eqa-arch-review` | "review this plan", "Gemini suggested", "external plan" | Evaluates proposals against DESIGN_PRINCIPLES.md |
| `eqa-repo-standards` | "commit", "tests passing", "test failure" | Pre-commit checklist, message format, test protocol |

## Cross-references

```
eqa-decision-protocol  →  eqa-ideas-maintenance  (log the decision)
eqa-arch-review        →  eqa-ideas-maintenance  (log accepted/deferred items)
eqa-arch-review        →  eqa-decision-protocol  (for non-obvious trade-offs)
eqa-repo-standards     →  eqa-ideas-maintenance  (update IDEAS.md in same commit)
```

## Installation

### Cowork (current)

Copy each skill directory into the Cowork skills plugin folder and merge
`manifest.json` entries into the existing manifest:

```
~/Library/Application Support/Claude/local-agent-mode-sessions/
  skills-plugin/{plugin-uuid}/{session-uuid}/skills/
    eqa-decision-protocol/
    eqa-ideas-maintenance/
    eqa-arch-review/
    eqa-repo-standards/
```

### Claude Code

```bash
cp -r skills/eqa-* ~/.claude/skills/
```

After installation, restart the application and verify the skills appear
in the available skills list before testing trigger accuracy.

## Maintenance

Skills should be updated when:
- A new design principle is added to `DESIGN_PRINCIPLES.md`
- The IDEAS.md tag system changes
- A new commit convention is adopted
- A new test failure pattern is identified

Per SKILL_CREATION_BEST_PRACTICES.md: draft updates here first, review,
then install. Skills should not self-edit.
