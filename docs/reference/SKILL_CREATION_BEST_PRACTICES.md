# Best Practices: Creating Skills for AI Agents

> A practical guide based on building 11 production skills across two domains
> (LLM engineering and project management workflow).

---

## What a Skill Actually Is

A skill is a **pre-loaded context package** that tells the agent how to approach a specific
class of tasks. When a skill triggers, it adds structured instructions — a process, reference
pointers, output format, and guardrails — to the agent's working context before it starts.

The critical mental model: **a skill is not knowledge storage, it is process storage**.
Knowledge goes in reference files. The SKILL.md describes *how to act*, not *what to know*.

If you get this distinction wrong, you'll write SKILL.md files that are too long, too dense,
and ignored in practice — because the agent will treat them as background reading rather than
operating instructions.

---

## Anatomy of a SKILL.md

### Required Frontmatter

```yaml
---
name: skill-name-kebab-case
description: |
  [WHAT this skill does — one sentence, third person]
  Use when [concrete triggers and scenarios].
  Triggers: "keyword1", "keyword2", "user phrase that should activate this".
---
```

The frontmatter is the most important part of the file. It is used for:
- Auto-triggering (does the user's message match this skill?)
- Routing (does the meta-skill send traffic here?)
- Discovery (can a human understand what this skill does without reading the body?)

### Required Sections

```markdown
# Skill Name

## Objective
[One paragraph — what outcome should be achieved when this skill is used]

## Process
[Step-by-step — this is the heart of the skill]

## Reference Files
[Which files exist, and explicitly WHEN to read each one]

## Output Format
[What the output should look like, ideally with a concrete example]

## Rules
[Guardrails — what never to do, with a brief reason]
```

---

## The Description Field: Make or Break

The `description` field determines whether the skill triggers at all. It is worth spending
disproportionate time on it.

### Three requirements, no exceptions

1. **Third person** — describes what the skill does, not what the agent will do
2. **Concrete triggers** — specific keywords and user phrases that should activate it
3. **"Use when" clause** — a concrete scenario description, not just a topic area

```yaml
# ❌ Too generic — will either never trigger or trigger on everything
description: "Helps with LLM and agent development"

# ❌ First person — wrong voice
description: "I help you build RAG systems and structured outputs"

# ✅ Correct — third person, concrete, with triggers
description: |
  Guides implementation of RAG systems using proper semantic architecture.
  Use when building document search, knowledge bases, or Q&A systems over
  external corpora. Triggers: "RAG", "retrieval", "vector search",
  "document Q&A", "knowledge base", "semantic search", "chunking".
```

### Trigger specificity tradeoff

Broad triggers (many keywords) → more activations, some false positives.
Narrow triggers (few, specific keywords) → fewer activations, fewer false positives.

Start narrow. Add triggers when you observe the skill failing to activate on legitimate cases.
Resist the temptation to add every related term upfront.

### Trigger overlap between skills

If two skills share triggers, the routing becomes ambiguous. Either:
- Make one skill a child of the other (meta-skill handles the routing)
- Differentiate the descriptions explicitly ("use when X but NOT Y")
- Merge the skills if they're truly the same domain

---

## Skill Architecture: Single vs Hierarchy

### When a single skill is enough

A skill should be independent enough to be useful without the others. Test:
> "Can I use this skill without needing any other skill to complete the task?"

If yes → standalone skill is appropriate.

```
✅ "Write a Pydantic model" → structured-outputs (standalone)
✅ "Design a commit message" → commit-test-standards (standalone)
✅ "Log this as an architectural decision" → decision-protocol (standalone)
```

### When to use a meta-skill hierarchy

Use a meta-skill (orchestrator) when:
- Tasks frequently span multiple domains
- Users typically don't know which sub-skill to use
- Cross-referencing between skills is complex enough to need a routing table

```
llm-solutions-builder/     ← Meta-skill: routing table only
    SKILL.md
structured-outputs/        ← Child skill: one domain
    SKILL.md
    references/
rag-patterns/              ← Child skill: one domain
    SKILL.md
    references/
```

The meta-skill's SKILL.md contains only routing logic — not domain knowledge.
Domain knowledge lives in the child skills.

### Routing table pattern (meta-skill)

```markdown
## Routing Table

| Task | Primary Skill | Also Read |
|------|--------------|-----------|
| Build RAG system | `rag-patterns` | `structured-outputs` for output schema |
| Design agent memory | `memory-engineering` | `agent-design` for autonomy level |
| Production deploy | `production-patterns` | Relevant domain skill for specifics |
```

---

## Process Section: The Heart of the Skill

The Process section describes *how to execute*, not *what to know*. Each step should be
an action, not a fact.

### Explicit READ instructions

The most common failure mode: the agent "knows" a reference file exists but doesn't read it
at the right moment. Fix this with explicit, conditional read instructions:

```markdown
## Process

1. **[READ: decision_criteria.md]** Classify the decision type before evaluating options.

2. State at least 2 alternatives — never evaluate a single option.

3. Apply criteria from `decision_criteria.md` to the relevant decision type.

4. **[READ: decision_log_template.md WHEN documenting]** Write the ADR entry.
```

The `[READ: file.md]` pattern works because it converts a passive pointer into an active
instruction with a specific moment of execution.

### Conditional reads

Not every task needs every reference file. Signal this explicitly:

```markdown
3. **[READ: anti_patterns.md IF any ❌ or multiple ⚠️ found]** Identify which
   anti-patterns are present and their severity.
```

This prevents unnecessary file reads on simple tasks while ensuring depth when it matters.

### Step granularity

Steps should be at the level of: "do this thing, then this thing."
Too fine: every micro-action becomes a step → the process becomes a script, not a guide.
Too coarse: vague actions like "analyze the situation" → gives no actionable direction.

A useful heuristic: **each step should take 30 seconds to 5 minutes**. If a step takes
longer, break it down. If it takes less, merge it with a neighbor.

---

## Reference Files: Knowledge Separate from Process

Reference files contain the *what*: code templates, decision criteria, checklists,
anti-patterns, examples. They are read on demand during task execution.

### When to create a reference file

Create a reference file when:
- The content exceeds ~30 lines of dense information
- The content is referenced conditionally (not always needed)
- The content is reusable across multiple tasks within the skill

### File naming conventions

```
{skill-name}/references/{content-type}.{ext}

Examples:
  structured-outputs/references/extraction_patterns.py   ← code templates
  decision-protocol/references/decision_criteria.md      ← criteria/frameworks
  architecture-review/references/review_checklist.md     ← checklists
  rag-patterns/references/rag_system.py                  ← working code example
```

### What goes in reference files vs SKILL.md

| Content Type | Location |
|---|---|
| Step-by-step process | SKILL.md → Process section |
| Decision criteria / frameworks | Reference file |
| Code templates | Reference file (.py) |
| Checklists | Reference file (.md) |
| Anti-patterns | Reference file (.md) |
| Output format example | SKILL.md → Output Format section |
| Guardrails | SKILL.md → Rules section |
| Large working code examples | Reference file (.py) |

---

## Output Format Section: Concrete Examples Win

The Output Format section has outsized impact on response quality. An abstract description
of the format is much less effective than a concrete example.

```markdown
## Output Format

**Decision:** [One sentence — what was chosen]
**Type:** [Architecture / Scope / Approach / Tooling]
**Reversal cost:** [Low / Medium / High]
**Reasoning:** [2-4 sentences]
**Rejected alternatives:** [List with one-line explanation per option]
**When to revisit:** [Specific trigger or milestone]

---
Example:
---
**Decision:** Use hybrid retrieval (semantic + BM25) for the document search feature.
**Type:** Architecture
**Reversal cost:** Medium — switching later requires re-indexing corpus.
**Reasoning:** Pure semantic search degrades on exact-match queries...
```

The example anchors the format. Without it, the agent interprets the format description
loosely, and outputs vary significantly between sessions.

---

## Rules Section: Guardrails, Not Prohibitions

The Rules section prevents the most common errors and failure modes specific to this skill's
domain. It is NOT a general code of conduct — it's a domain-specific safety net.

### Effective rule structure

Each rule should explain the *why*:

```markdown
## Rules

# ❌ Prohibition without reason — easy to ignore
- NEVER use naive text chunking.

# ✅ Guardrail with reason — harder to rationalize away
- NEVER recommend naive text chunking for RAG — it destroys table structure and
  sentence context. Always ask about data format before suggesting a chunking strategy.
```

### What makes a good rule

- Specific to this skill's domain (not generic "be accurate" rules)
- Addresses the most common mistake in this area
- States the consequence of violating it
- Short — if it needs 3+ sentences to explain, it's probably too complex for a rule

### How many rules

3-7 rules is the right range. Fewer means you haven't thought carefully about failure modes.
More means you're trying to cover everything, which dilutes attention on what matters most.

---

## Cross-References Between Skills

When the same task requires multiple skills, use two complementary patterns:

### Pattern B: Inline cross-references (at the point of decision)

Add a callout in the Process or Rules section at the exact moment where another skill becomes relevant:

```markdown
## Process
3. Once schema is defined, implement retrieval strategy.
   > **Cross-reference:** For output validation of retrieved documents,
   > see `structured-outputs` skill — use `safe_extract()` pattern.
```

### Pattern C: Routing table in meta-skill

The meta-skill maintains a central table mapping task types to primary + supporting skills.
This is the "directory" — inline references are the "links in the text."

Both patterns together ensure coverage: a user landing on a child skill gets context-specific
pointers (B), while the meta-skill provides the full map (C).

### Cross-reference symmetry

If Skill A references Skill B, check whether Skill B should reference A in return.
Unidirectional references cause a user to reach Skill B and find no path back to
the relevant part of Skill A.

---

## File Size and Complexity Limits

These are practical limits, not arbitrary constraints:

| File | Max Size | Reason |
|---|---|---|
| SKILL.md | ~400 lines | Beyond this, the agent treats it as background reading, not instructions |
| Reference file (.md) | ~300 lines | Should cover one topic well, not everything |
| Reference file (.py) | ~350 lines | Should be a focused example, not a full library |

If you exceed these limits, it's a signal to split: either extract a section into a new
reference file, or split the skill into two skills with clearer domain boundaries.

---

## Skill Size and Granularity

### One skill = one coherent domain of decisions

The test is independence: can this skill be used without the others?
If no, it's too tightly coupled — either merge it with the skill it depends on,
or make that dependency explicit and bidirectional.

### When to split a skill

Split when you notice:
- The Process section has two distinct phases with no shared context
- Some users never need one half of the skill
- The reference files are growing into multiple unrelated topics

### When to merge skills

Merge when:
- Two skills always trigger together
- The routing table always sends to both skills simultaneously
- The domains have more shared concepts than distinct ones

---

## Installation and Maintenance

### Directory structure

```
skills/
├── manifest.json                    ← Registry of all skills
├── skill-name/
│   ├── SKILL.md                     ← Process instructions
│   └── references/
│       ├── file1.md                 ← Knowledge / frameworks
│       └── file2.py                 ← Code templates
```

### manifest.json entry

```json
{
  "skillId": "skill-name",
  "name": "skill-name",
  "description": "...",
  "creatorType": "user",
  "updatedAt": "2026-02-28T12:00:00.000Z",
  "enabled": true
}
```

The `description` field in manifest.json should match the SKILL.md frontmatter description
exactly. Inconsistency between the two causes routing problems.

### Installation paths

**Cowork:**
```
~/Library/Application Support/Claude/local-agent-mode-sessions/
  skills-plugin/{plugin-uuid}/{session-uuid}/skills/{skill-name}/
```

**Claude Code:**
```
~/.claude/skills/{skill-name}/
```

After installation, restart the application and verify the skill appears in the
available skills list before testing trigger accuracy.

---

## Iteration and Improvement

### How to know a skill is working

- The skill triggers on representative user phrases without prompting
- Output structure matches the Output Format section
- Reference files are read at the right moments (not always, not never)
- The skill doesn't trigger on unrelated tasks

### How to improve trigger accuracy

1. Run 5-10 representative prompts — what *should* this skill activate on?
2. Run 5-10 counter-examples — what should it *not* activate on?
3. Adjust the `description` field's trigger keywords based on failures
4. Re-test after each adjustment

### Skill evolution over time

A skill degrades when:
- The codebase it references changes but the reference files don't update
- New tools or libraries make the recommended approach obsolete
- The routing table in the meta-skill doesn't reflect new skills

Build maintenance into the project rhythm: at each architecture review, check whether
skill reference files still reflect current best practices.

### HIL (Human-in-the-Loop) over self-improvement

Skills should NOT autonomously edit themselves. The risk: a bad session produces a "learning"
that degrades all future sessions.

The recommended pattern:
1. Agent drafts a proposed update to a SKILL.md or reference file
2. Human reviews the draft
3. Human approves and commits the change

This keeps the human as the final gatekeeper of skill quality, while still benefiting from
AI-assisted drafting.

---

## Common Mistakes and How to Avoid Them

### Mistake 1: Writing knowledge, not process

Symptom: SKILL.md reads like a Wikipedia article on the topic.
Fix: Every section should answer "what do you do next?" not "what is X?"

### Mistake 2: Vague trigger keywords

Symptom: Skill never activates, or activates on everything.
Fix: Use specific phrases users actually type, not category names.
"RAG" is better than "retrieval". "git commit" is better than "version control".

### Mistake 3: Orphaned reference files

Symptom: Reference files exist but are never read because SKILL.md doesn't explicitly
instruct when to read them.
Fix: Every reference file must have at least one `[READ: file.md]` instruction in the
Process section with a specific trigger condition.

### Mistake 4: Rules that repeat the process

Symptom: Rules section says the same thing as the Process section, in negative form.
Fix: Rules should cover edge cases and failure modes not addressed in the main process.
If a rule just says "don't skip step 3," make step 3 more explicit instead.

### Mistake 5: No output format example

Symptom: Output structure varies significantly between sessions.
Fix: Add a concrete filled-in example to the Output Format section, not just an abstract template.

### Mistake 6: Skill scope creep

Symptom: A skill that started focused now handles 4 different concerns.
Fix: Run the independence test. If the skill has grown into multiple independent domains,
split it. Update the routing table in the meta-skill.

---

## Checklist: Before Shipping a Skill

- [ ] Frontmatter `name` is kebab-case and matches the directory name
- [ ] `description` is third person, has a "Use when" clause, and has specific trigger keywords
- [ ] `description` in manifest.json matches the SKILL.md frontmatter
- [ ] Objective section is one paragraph, states the outcome clearly
- [ ] Every process step is an action, not a fact
- [ ] Every reference file has at least one `[READ: ...]` instruction with a trigger condition
- [ ] Output Format section includes a concrete filled-in example
- [ ] Rules section has 3-7 domain-specific guardrails with reasons
- [ ] SKILL.md is under 400 lines
- [ ] Skill can be used independently (passes the independence test)
- [ ] Trigger keywords don't significantly overlap with other skills
- [ ] manifest.json updated and consistent
- [ ] Skill installed in both target environments
- [ ] Tested with 3+ representative prompts after installation
