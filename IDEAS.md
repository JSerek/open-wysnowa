# EQD-AI — Ideas & Roadmap

Status legend: `[ready]` = spec clear, can implement next · `[design]` = needs design decisions · `[explore]` = needs research/prototyping · `[later]` = future vision, park for now

---

## Current Sprint — Improvements to Layers 1–3

### P1: Synthesizer Prompt Granularity Fix `[ready]`

**Problem:** The synthesizer produces category-level groupings and calls them themes. "Core Mechanics Quality" with 15 ICs is a category, not a theme. This collapses the Braun & Clarke IC → Theme → Category hierarchy into IC → Category.

**Root cause:** The prompt emphasizes parsimony ("fewer is better"), and the LLM interprets this as creating 8–12 broad themes.

**Fix:**
- Remove parsimony framing from synthesizer prompt
- Add explicit IC-count guidance: "Each theme should contain 3–6 ICs. A theme with 8+ ICs likely needs splitting."
- Reference pipeline architecture: "Your themes will later be grouped into categories. Create mid-level themes that capture specific patterns of meaning, not broad domains."
- Add: "Two themes can share the same domain (e.g., both about combat) if they describe distinct experiential phenomena."
- Expected outcome: 15–20 themes for a 69-IC codebook instead of 10, feeding better into category synthesis

**Downstream effects:** More themes → more pairs → distinctness metric becomes more informative. Coherence should improve per-theme. Category agent has real work to do.

---

### P2: Meta-IC Filtering — YAML Configurable `[ready]`

**Problem:** Current heuristic patterns (`biggest_disappointment`, `worst_game`, `game_of_the_year`) are domain-specific (game reviews). Won't generalize to healthcare, fintech, etc.

**Fix:**
- Move patterns to `eqd_config.yaml` under a `meta_ic_filter` section
- Provide domain-agnostic defaults: `["overall_", "_verdict", "_summary_opinion", "overrated", "underrated"]`
- Allow empty list (no heuristic filtering) — useful for first runs when user doesn't know what to exclude
- Keep prompt rule #9 as the primary defense (domain-agnostic by design)
- Users add domain-specific patterns as they learn their data

**Config structure:**
```yaml
meta_ic_filter:
  enabled: true
  name_patterns: ["overall_", "_verdict", "_summary_opinion"]
  definition_signals: ["overall experience", "general impression"]
```

---

### P3: Coherence Gate Improvements `[ready]`

Three linked fixes:

**3a. Orphaned IC redistribution:** After dissolving a theme, redistribute its ICs to the next-closest theme by embedding similarity. If no theme exceeds a minimum similarity threshold (e.g., 0.5), park ICs in an explicit "Unassigned" section in the output. This prevents analytical data loss.

**3b. Dissolved theme annotation in Layer 3:** Exclude dissolved themes from downstream coherence/distinctness display, or annotate them as `[dissolved]`. Currently a dissolved theme shows 2.56x normalized coherence (trivially coherent, 0 ICs) which is misleading.

**3c. Adaptive coherence threshold:** Scale threshold by IC count:
- Themes with <5 ICs: threshold = 0.90 (lenient — small sample, high variance)
- Themes with 5+ ICs: threshold = 1.0 (standard)
- Configurable in YAML as `coherence_threshold` (base) + `coherence_threshold_small_theme` (override)

---

### P4: New Metrics `[ready]`

**4a. Orphaned IC Count**
After dissolution, count ICs not assigned to any theme. Simple: count ICs in codebook minus ICs in theme_ics table. Report as part of coherence gate results.

**4b. Thematic Coverage Ratio**
What fraction of total quotes are reachable through the thematic structure? After dissolution, some quotes become orphaned (their IC has no theme). Formula: `quotes_in_themed_ICs / total_quotes`. Tells you how much evidence the themes actually account for. Target: >95%.

**4c. IC Stability Index**
Measures how much IC definitions changed during refinement. During `_refine_ic_definitions()`, capture old embedding before update, compute cosine similarity with new embedding after re-embedding. Per-IC drift score (1.0 = unchanged, 0.7 = major rewrite). Aggregate: mean stability across refined ICs, count of ICs with stability < 0.85 ("substantially rewritten"). Interpretation: high stability (~0.95+) = coder agent's initial extraction was precise, refinement is polish. Low stability (~0.80) = initial definitions were imprecise, refinement is corrective.

**4d. Cross-Review Convergence**
For each IC, count unique source documents (not segments) that contributed quotes. An IC confirmed by 8 reviews is robust; an IC from 1 review is unconfirmed. Report: mean docs-per-IC, % of ICs in 2+ docs ("confirmed ratio"), % in 3+ docs ("strong convergence"). This is an inter-rater reliability proxy — independent data sources arriving at the same concept. Requires joining quotes → segments → documents to trace provenance.

---

### P5: Coder Agent Prompt Refinement `[design]`

**Problem:** The coder sometimes produces ICs at inconsistent granularity — some very specific (`button_mapping_conflict_gameplay`), some very broad (`gameplay_not_fun_overall`). The broad ones end up as theme-level concepts polluting the codebook.

**Fix ideas:**
- Add explicit guidance: "Each IC should describe a single experiential phenomenon, not a domain. 'combat_feels_sluggish' is good. 'gameplay_not_fun_overall' is too broad — identify the specific aspects that aren't fun."
- Add negative examples to the prompt showing over-broad vs. well-scoped ICs
- Consider adding a post-extraction check: if an IC's definition contains multiple distinct complaints, flag for splitting

---

## Layer 4: Analyst Intelligence `[design]`

### Vision
An LLM-powered interpretive layer that sits on top of the structured pipeline output. Takes the full results dict + thematic structure + quality metrics and produces a written analytical brief — the same analysis we've been doing manually in conversation.

### What it would do
- **Metric interpretation:** Read all 12+ metrics, flag anomalies, explain what they mean in context of this specific dataset/run
- **Structural diagnostics:** Identify magnet themes, weak coherence, orphaned ICs, saturation signals, catch-all categories
- **Thematic interpretation:** For each theme, assess: is it well-defined? Does it have sufficient evidence? Are its ICs cohesive? Does the theme name accurately reflect its content?
- **Comparative analysis:** If previous run results are available, compare across runs (codebook growth, theme stability, metric trends)
- **Actionable recommendations:** Suggest specific next steps — "split this theme," "merge these ICs," "run 20 more reviews before trusting saturation," "lower auto_merge_threshold"

### Architecture
- Runs as a final pipeline step after Layer 3
- Input: full results dict (JSON-serializable)
- LLM call with structured prompt + all metric data
- Output: structured analytical brief (markdown or structured dict)
- Could use Sonnet 4.5 for interpretive depth

### Key design decisions needed
- How much context to feed (full thematic structure = large prompt)
- Whether to chunk analysis (metrics → structure → recommendations) or single-pass
- Output format: markdown report vs. structured JSON vs. interactive Q&A
- Whether to persist the analytical brief to DB

---

## Layer 5: Interactive Lensing `[explore]`

### Vision
Re-synthesize themes from different analytical perspectives without re-running Layers 0–1. The codebook and quotes are stable empirical foundation. Theme synthesis (Layer 2) can be re-run with different prompts/lenses.

### Example lenses
- **Default:** General thematic analysis (current behavior)
- **UX Friction:** "Focus on user experience pain points — moments of frustration, confusion, or friction in the interaction flow"
- **Emotional Response:** "Focus on emotional reactions — disappointment, anger, satisfaction, nostalgia, betrayal"
- **Comparative:** "Focus on comparisons with predecessors, competitors, or expectations — what changed, what's missing, what's better"
- **Value Perception:** "Focus on perceived value — price, content quantity, quality relative to cost, willingness to pay"
- **Design Philosophy:** "Focus on design decisions and their consequences — what was intentional, what feels accidental, what trade-offs were made"

### Architecture
- CLI flag: `--lens emotional_response` or `--lens custom:"Focus on X"`
- Skips Layers 0–1 (loads existing codebook from DB)
- Re-runs Layer 2 with lens-modified synthesizer prompt
- Re-runs Layer 3 metrics on new thematic structure
- Layer 4 interprets the new lens

### Key considerations
- Each lens produces a different thematic structure from the same ICs
- Multiple lens results could be stored in DB (tagged by lens name + timestamp)
- Comparison across lenses would itself be analytically valuable — "which ICs appear in themes across all lenses?" (robust findings) vs. "which only appear under one lens?" (perspective-dependent)
- This is methodologically sound: in qualitative research, the same data legitimately supports multiple thematic readings depending on the research question

---

## Other Ideas (Parking Lot)

### Codebook Versioning
Track codebook state across pipeline runs. When running on new data batches, load existing codebook and continue building. Currently the DB accumulation bug forces fresh DBs each time. Proper versioning would allow incremental analysis.

### Quote Network Visualization
Build a graph: ICs as nodes, edges weighted by quote co-occurrence (two ICs sharing quotes from the same segment). Visualize which concepts cluster in the raw data vs. how themes group them. Could reveal natural clustering that the synthesizer missed.

### Segment Difficulty Scoring
Some segments consistently produce more drops, lower-confidence ICs, or more grey-zone decisions. Scoring segments by "coding difficulty" could help identify: (a) reviews that are poorly written/ambiguous, (b) reviews that contain novel concepts the codebook hasn't captured, (c) reviews that are outliers vs. mainstream sentiment.

### Embedding Model Comparison
Run the same codebook through different embedding models and compare: how do similarity scores change? Do triage decisions flip? Which themes gain/lose coherence? This would help calibrate whether results are robust to embedding choice or artifacts of a specific model.

### Export Formats
- ATLAS.ti / NVivo compatible export (for researchers who want to continue in traditional QDA tools)
- Interactive HTML report with collapsible theme hierarchy
- JSON-LD for semantic web / knowledge graph integration

### Multi-Dataset Analysis
Run the pipeline on multiple datasets (e.g., reviews for Game A, Game B, Game C) and compare thematic structures. Which themes are universal? Which are game-specific? This moves from single-product analysis to cross-product insights.

---

*Last updated: 2026-02-21 — Session: 30-review run with meta-IC filter + coherence gate + Sonnet 4.5*
