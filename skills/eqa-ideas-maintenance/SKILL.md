---
name: eqa-ideas-maintenance
description: |
  Maintains IDEAS.md for the EQD-AI project — adding new entries,
  updating status tags, and keeping the Last updated footer accurate.
  Use when a sprint task is completed, a decision is made, a new idea
  surfaces, or an item's status changes.
  Triggers: "add to IDEAS.md", "update IDEAS.md", "mark as done",
  "move to ready", "log this idea", "add to next iteration",
  "this is ready to implement", "park this for later", "note this".
---

# EQA-AI IDEAS.md Maintenance

## Objective

Keep IDEAS.md as the single source of truth for what's planned, what's
possible, and what's been deliberately deferred in EQD-AI development.
A stale IDEAS.md is a navigation failure — future sessions can't orient
without it. Every sprint and every significant decision should leave a
footprint here.

## Process

1. **Read the current IDEAS.md** (`eqa_ai/IDEAS.md`) to locate the
   relevant section before making any change.

2. **Identify the action type:**
   - NEW ENTRY → place in the correct section with the correct tag
   - STATUS CHANGE → update an existing entry's tag in place
   - FOOTER UPDATE → update "Last updated" with date + summary of change

3. **Choose the right tag** based on the state of the idea:

   | Tag | Meaning | Criteria |
   |-----|---------|----------|
   | `[ready]` | Implementation-ready | Design settled, scope clear, can be picked up next sprint |
   | `[design]` | Direction known, not fully specced | Concept validated but architecture or scope still open |
   | `[later]` | Good idea, not now | Deliberately deferred — post-v1, blocked, or low priority |

4. **Place new entries in the right section:**
   - Active development candidates → "Next Up" (ordered by priority)
   - Architectural decisions still being designed → "Design Questions"
   - Future exploration → "Other Ideas / Later"

5. **Update the Last updated footer** — always. Format:
   ```
   *Last updated: YYYY-MM-DD — [one-sentence summary of what changed].*
   ```

6. **Bundle the IDEAS.md update in the same commit** as the related code
   change. Never create a standalone IDEAS.md-only commit unless the
   change is a major planning session with no accompanying code.

## Output Format

When adding a new [ready] entry:
```markdown
### My Feature Name `[ready]`
**Problem:** One sentence on what pain this solves.

**Fix:** One paragraph on the implementation approach. Mention the
specific file(s) and method(s) affected. Note any known risks or
dependencies.
```

When updating a status tag in place:
```
Changed: "Category Merge LLM Rename [ready]" → removed (implemented in ecebb4d)
Changed: "Codebook Versioning [design]" → added immutability note to existing entry
```

When updating the footer:
```
*Last updated: 2026-02-28 — Completed sprint: Field descriptions, --skip-extraction,
Category Merge LLM Rename. Added [ready]: Coder Agent Batch Fallback.*
```

## Rules

- **[ready] ≠ "good idea."** Only use [ready] when the implementation
  approach is clear enough to start coding in the next session without
  a design discussion first.

- **Never let completed tasks linger as [ready].** Once a sprint item is
  done and committed, remove it from the Next Up section or archive it.
  A cluttered Next Up erodes trust in the document.

- **Never create a standalone IDEAS.md commit** when there's related code
  to bundle it with. The commit history should show cause and effect
  together — not scattered maintenance noise.

- **The Last updated footer must always be touched.** A footer with a
  stale date signals that the document may not reflect current state.
  Even a minor tag change warrants a footer update.

- **Don't summarize removed features without a trace.** When something
  is deliberately removed from the codebase (e.g. SUBCODE), note it in
  the footer so future sessions know it was intentional, not forgotten.

> **Cross-reference:** After a sprint, run `eqa-repo-standards` to verify
> tests pass before committing. Use `eqa-decision-protocol` before making
> significant tag promotions (e.g. [design] → [ready]).
