---
name: eqa-arch-review
description: |
  Reviews external architecture plans or implementation suggestions against
  EQD-AI's DESIGN_PRINCIPLES.md. Use when an outside agent (Gemini, another
  LLM, team member) proposes changes to the pipeline design, data model,
  or implementation approach.
  Triggers: "review this plan", "what do you think of this design",
  "Gemini suggested", "another agent proposed", "architecture proposal",
  "external plan", "evaluate this", "assess this implementation",
  "what do you make of this".
---

# EQA-AI Architecture Review

## Objective

Evaluate external proposals systematically against EQD-AI's DESIGN_PRINCIPLES.md
so that good ideas get captured in IDEAS.md, bad ideas get explicitly rejected
(with reasons), and the project doesn't drift from its architectural commitments
through accumulated convenience decisions.

## Process

1. **[READ: references/principles_checklist.md]** Load the 7 principles
   in compact form before evaluating any suggestion.

2. **Parse the proposal** into discrete, independently assessable suggestions.
   If the proposal is monolithic prose, break it into items before evaluating.

3. **Evaluate each item** against the checklist:
   - Which principles does it touch?
   - Does it conflict with any critical principle (P1, P2, P5)?
   - Is the conflict fundamental, or could a modified version avoid it?

4. **Assign a rating** to each item:
   - **✅ Accept** — implement; add to IDEAS.md with [ready] or [design] tag
   - **🔜 Defer** — right direction, wrong time; add to IDEAS.md [design] with precondition
   - **❌ Reject** — conflicts with a design principle; state the principle by number

5. **[READ: references/principles_checklist.md IF any ❌ found]** Re-verify
   rejected items against the full principle text before finalizing.

6. **Update IDEAS.md** for all ✅ Accept and 🔜 Defer items. Use the
   `eqa-ideas-maintenance` skill for the update.

7. **Present the review summary** in the table format below.

## Output Format

```
## Architecture Review: [Source — e.g. "Gemini 2.5 Pro" or "team discussion"]

| Suggestion | Rating | Principle | Action |
|---|---|---|---|
| Jinja2 templates for prompts | ❌ Reject | P6 — adds provider-coupled dependency for no gain | None |
| Exhaustive Field descriptions | ✅ Accept | None | IDEAS.md [ready] |
| ICStatus.SUPERSEDED enum | 🔜 Defer | P5 — right direction; needs Codebook Versioning sprint first | IDEAS.md [design] under Codebook Versioning |
| Append-only IC rows | 🔜 Defer | P1+P5 — correct approach; bundle with Codebook Versioning | IDEAS.md [design] |
| SUBCODE as parent_id | ❌ Reject | P2 — reintroduces removed concept; creates traceability ambiguity | None |
| Coder Agent Batch Fallback | ✅ Accept | None | IDEAS.md [ready] |

**Summary:** 2 accepted (immediate [ready]), 2 deferred (bundle into Codebook Versioning sprint),
2 rejected.

**Narrative:** The proposal's strongest contribution is the Field descriptions suggestion —
high signal-to-effort ratio with zero behavior change. The immutability direction is sound
but premature without the versioning schema. Jinja2 and SUBCODE reversals contradict
deliberate prior decisions.
```

## Rules

- **NEVER accept a suggestion that conflicts with P1, P2, or P5** without
  explicit analyst consent AND a written rationale in ARCHITECTURE.md.
  These are load-bearing principles — bending them has compounding costs.

- **ALWAYS cite the principle by number** when rejecting. "This feels wrong"
  is not a rejection. "Conflicts with P2 — no audit trail for this mutation" is.

- **NEVER reject without checking if a modified version works.** If the core
  idea is sound but the implementation conflicts, offer the modified version
  as the ✅ Accept path.

- **"Defer" is not a soft reject.** Defer means you believe the proposal
  will be implemented — just not now. State the specific precondition that
  must be true first (e.g. "after Codebook Versioning sprint lands").

- **All accepted/deferred items must land in IDEAS.md** — not just the
  conversation. Ideas not written down are ideas that will be re-invented
  in a future session.

- **Don't reverse deliberate prior decisions without flagging it.** If a
  proposal re-introduces something that was explicitly removed (e.g. SUBCODE,
  seed themes), note the history before evaluating.

> **Cross-reference:** After completing the review, use `eqa-ideas-maintenance`
> to add accepted/deferred items to IDEAS.md. Use `eqa-decision-protocol` if
> any suggestion requires a non-obvious choice between alternatives.
