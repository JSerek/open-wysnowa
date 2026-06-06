# EQD-AI Design Principles

These principles govern architectural and implementation decisions across the project. They are non-negotiable constraints, not aspirational guidelines. Every PR, refactor, and new feature should be checked against them.

---

## 1. Raw data is immutable after extraction

ICs (Initial Codes) and their source quotes, once coded in Layer 1, are never modified by subsequent layers. Themes regroup them, categories regroup themes, analysts interpret them, lenses reframe them — but the observational ground truth stays untouched.

**Implication:** Any layer that transforms meaning (Layer 2+) operates on references to ICs, not on the IC content itself. If an IC is wrong, it gets flagged or excluded — never silently edited.

## 2. Every analytical transformation must be traceable

At any point, it must be possible to answer: "How did we get from raw reviews to this conclusion?" Every layer records its inputs, outputs, and decisions. Codebook versions, lens overlays, theme merges, and category assignments all leave an audit trail.

**Implication:** No in-place mutations of analytical artifacts. New versions sit alongside old ones. Comparison tooling (like `compare_runs.py`) is a first-class concern, not an afterthought.

## 3. Bottom-up first, interpretation second

The pipeline deliberately avoids imposing frameworks before the data speaks. Layers 1-3 are inductive (structure emerges from data). Layer 4 is evaluative (how robust is what emerged). Layer 5 applies human-directed lenses. This ordering is intentional — premature framing kills discovery.

**Implication:** No "seed themes" or predefined category lists in the default pipeline flow. If a user wants top-down framing, it enters through Layer 5 as an explicit reframing operation, clearly separated from the bottom-up analysis.

## 4. Human judgment is irreplaceable — AI scales the labor

The system automates what humans are slow at (reading 10,000 reviews, clustering codes) and preserves what humans are uniquely good at (defining business problems, judging relevance, asking better questions). HIL checkpoints exist where human judgment adds irreplaceable signal, not where it adds comfort.

**Implication:** Layer 5's consultant pattern exists because an LLM cannot know the stakeholder's real business problem. The pipeline never pretends AI interpretation substitutes for human sense-making — it provides structured material for humans to reason with.

## 5. Non-destructive iteration over replacement

We never overwrite — we version. Codebook versioning adds new versions alongside old ones. Lens overlays create parallel views, not replacements. Theme refinement records what was dissolved and why. If something needs to change, the old state remains accessible.

**Implication:** Results are stored as immutable artifacts per run. Lens reframings produce separate overlay files referencing the canonical run, never modifying it. Delete operations require explicit justification.

## 6. Provider agnosticism as a structural hedge

The system supports multiple LLM providers (OpenAI, Anthropic, Google, Ollama) through a unified config-driven interface. This is not convenience — it's a hedge against vendor lock-in, API deprecations, and pricing changes. Switching providers should require only a config change, not a code change.

**Implication:** No provider-specific logic in pipeline layers. Provider quirks (like Gemini's `instructor_mode: json`) are handled in `config.py`'s client factory, invisible to the rest of the codebase.

## 7. The pipeline must be transparent, not a black box

Every layer's output should be inspectable by a human reading the terminal or the results file. Layer 4's analytical brief prints in both HIL and no-HIL modes. Quality metrics are always computed, never skipped. If the system makes a decision, the reasoning is logged.

**Implication:** Silent failures are bugs. If a layer degrades gracefully (like Layer 4's non-fatal design), the degradation is logged explicitly. Terminal output is a feature, not a debug artifact.

---

*These principles were extracted from patterns observed across the codebase and design conversations during development. They should be updated as the project evolves — but changes to principles 1, 2, and 5 require strong justification, as they are load-bearing for the analytical integrity of the system.*
