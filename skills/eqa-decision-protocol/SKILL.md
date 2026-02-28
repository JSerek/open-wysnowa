---
name: eqa-decision-protocol
description: |
  Guides design decision-making during EQD-AI pipeline development using
  structured AskUserQuestion options instead of prose. Use when a design
  choice, implementation approach, or architectural question requires a
  decision — especially when multiple valid options exist.
  Triggers: "should we", "what approach", "how should we handle",
  "which option", "decide", "I was thinking", "what do you think about
  implementing", "option A or B", "design choice", "tradeoff".
---

# EQA-AI Decision Protocol

## Objective

Ensure every meaningful design decision in the EQD-AI project gets a
structured, explicit answer — not a buried paragraph — and is logged
in the right place. Decisions made in prose get forgotten. Decisions
made through AskUserQuestion get a clear owner and a clear record.

## Process

1. **Classify the decision type** before presenting options:
   - **Architecture** — data model changes, layer redesigns, new pipeline stages
   - **Scope** — what to include/exclude in a sprint or feature
   - **Tooling** — library choice, provider choice, config approach
   - **Deferral** — whether to implement now vs add to IDEAS.md

2. **Surface ≥2 concrete options.** For each, include a one-sentence
   tradeoff note. Never present a single option framed as "the only way."

3. **Call AskUserQuestion** with the right selection mode:
   - Single-select for mutually exclusive choices (A or B, not both)
   - Multi-select for "pick all that apply" (e.g. sprint task selection)

4. **After the user responds,** confirm the decision in one sentence,
   then take the logging action appropriate to the type:
   - Architecture decision → note in `ARCHITECTURE.md`
   - Task or feature decision → add/update entry in `IDEAS.md`
   - Use the **`eqa-ideas-maintenance`** skill for the IDEAS.md step

## Output Format

AskUserQuestion call structure:
```
Header:   short label ≤12 chars — e.g. "Approach", "Scope", "Provider"
Question: one clear sentence ending with "?"
Options:  2-4 choices. Label = 1-5 words. Description = key tradeoff.
```

Concrete example — a tooling decision:
```
Header: "instructor"
Question: "instructor_mode controls how JSON is enforced. Which should we use?"
Options:
  - label: "json (MD_JSON)"
    description: "Embeds schema in system prompt. Works with any model — safer for OpenRouter."
  - label: "tool_call"
    description: "Uses native function-calling API. Cleaner but model-dependent."
  - label: "Keep current, revisit"
    description: "Leave as-is and decide after first live test run."
```

Post-decision confirmation format:
```
Decision: json (MD_JSON) — cross-model safety outweighs verbosity cost.
Logged to: eqd_config.yaml comment + IDEAS.md footer.
```

## Rules

- **NEVER pick without asking,** even if one option seems obviously correct.
  Unilateral decisions cause rework when context was missing.

- **NEVER present a single option** as the only path. Always surface the
  meaningful alternative, even if you consider it inferior. Label it
  honestly, not dismissively.

- **Don't add "Recommended"** unless the user explicitly asked for a
  recommendation. When they do ask, mark it clearly and explain why in
  one sentence.

- **Architecture decisions need a written record.** If a decision affects
  layer boundaries or data model invariants, document it in `ARCHITECTURE.md`,
  not just in the conversation.

- **Deferral is a valid outcome.** If the right answer is "not now," say
  so explicitly and add the item to IDEAS.md [design] or [later] rather
  than leaving it open.

> **Cross-reference:** After a decision, use `eqa-ideas-maintenance`
> to update IDEAS.md status and the Last updated footer.
