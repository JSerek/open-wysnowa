# EQD-AI — Ideas & Roadmap

Status legend: `[ready]` = spec clear, can implement next · `[design]` = needs design decisions · `[explore]` = needs research/prototyping · `[later]` = future vision, park for now · `[resolved]` = implemented

---

## Resolved — Implemented Features

### P1: Synthesizer Prompt Granularity Fix `[resolved]`
Replaced "FEWER IS BETTER" principle with "SPECIFICITY OVER PARSIMONY" — targets 3–6 ICs/theme, references category layer, allows two themes in same domain. Updated few-shot example to show 7 specific themes instead of 5 broad ones. Updated redundancy check to merge only same-phenomenon, not same-domain themes.

### P2: Meta-IC Filtering — YAML Configurable `[resolved]`
Moved hardcoded patterns to `eqd_config.yaml` under `meta_ic_filter` section. Defaults to empty lists (domain-agnostic). Users add domain-specific patterns as they learn their data. Prompt rule #9 remains the primary defense.

### P3: Coherence Gate Improvements `[resolved]`
- **3a. Orphaned IC redistribution:** After dissolving a theme, redistributes ICs to nearest surviving theme by embedding similarity (min 0.5 threshold), or marks as unassigned.
- **3b. Dissolved theme annotation:** Dissolved themes (0 ICs) excluded from coherence, distinctness, and normalized coherence computation.
- **3c. Adaptive coherence threshold:** 0.90 for themes with <5 ICs, 1.0 for 5+ ICs. Configurable via `coherence_threshold` + `coherence_threshold_small`.

### P4: New Metrics `[resolved]`
- **IC Stability Index:** Cosine similarity between pre/post refinement embeddings. Mean stability + count of substantially rewritten ICs (<0.85).
- **Orphaned IC Count:** Active ICs not assigned to any theme after dissolution.
- **Thematic Coverage Ratio:** `quotes_in_themed_ICs / total_quotes`. Target >95%.
- **Cross-Review Convergence:** Unique documents per IC. Reports confirmed (2+ docs) and strong convergence (3+ docs) ratios.

### Model Upgrade `[resolved]`
Synthesizer and category agents on Sonnet 4.5 (`claude-sonnet-4-5-20250929`). Coder and comparator on Haiku for cost efficiency.

---

## Current Sprint

### S1: Sentiment Analysis at IC Creation `[ready]`
**Problem:** Themes can contain a mix of positive and negative ICs, making them harder to interpret. "Combat Mechanics" might aggregate "combat is fluid" and "combat is broken" — analytically useless.

**Fix:** Add `sentiment` field to `ICCandidate` (positive/negative/neutral/mixed). Assessed by the coder agent on the verbatim quote. New metric: **Theme Sentiment Purity** — dominant sentiment count / total ICs in theme. Flagged when purity < 0.70. Display per-theme sentiment distribution in pipeline output.

**Design:** Sentiment is a metric/signal, NOT a gate. Mixed-sentiment themes may be legitimate contested phenomena.

### S2: Coder Agent Specificity Guidance `[ready]`
**Problem:** Coder sometimes produces over-broad ICs like `gameplay_not_fun_overall`. But pushing too hard toward specificity would miss reviews that express general dissatisfaction without identifying specific causes.

**Fix:** Add prompt guidance: "Be as specific as the text allows, no more. If the segment doesn't identify a specific system or feature, create an IC that captures the general nature of the experience — never fabricate specifics that aren't in the text." This gives explicit permission for general ICs when the text is general.

### S3: Negative Examples in All Agent Prompts `[ready]`
**Problem:** Positive-only few-shot examples teach the LLM what to do but not where to stop. Negative examples define conceptual boundaries.

**Fix per agent:**
- **Coder:** Counter-examples for fabricated specificity, meta-commentary, wrong sentiment
- **Comparator:** Counter-example for over-merging distinct phenomena that sound similar
- **Synthesizer:** Counter-examples for mixed-sentiment themes and category-level groupings

Format: bad output → diagnosis → corrected output.

---

## Layer 4: Analyst Intelligence `[design]`

### Vision
An LLM-powered interpretive layer that sits on top of the structured pipeline output. Takes the full results dict + thematic structure + quality metrics and produces a written analytical brief — the same analysis we've been doing manually in conversation.

### What it would do
- **Metric interpretation:** Read all 16+ metrics, flag anomalies, explain what they mean in context of this specific dataset/run
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

## Codebook Versioning `[design]`

### Vision
Track codebook state across pipeline runs for longitudinal analysis. When the product evolves (patches, updates) and data accumulates over time, the analyst needs to compare codebooks across versions — not just run fresh each time.

### Schema additions
- `codebook_versions` table: `id`, `name` (e.g., "v1_launch_reviews"), `created_at`, `ic_count`, `notes`
- `version_id` foreign key on `initial_codes` (`introduced_in_version`)
- `last_seen_version` on `initial_codes` (tracks when an IC was last supported by evidence)
- Run mode stored in config as a session parameter, not a permanent setting

### UX design (action-based, not mode-based)
Instead of asking users to declare a "mode" upfront — which is too abstract — the system uses two natural user actions:

**Action 1: "Save codebook checkpoint"** — the analyst explicitly names and freezes the current codebook. This is a deliberate act with a meaningful name (e.g., "v1_launch_reviews"), not a technical operation.

**Action 2: "Run on new data"** — when new data arrives, the pipeline asks one plain-language question: "Do you want to use your existing codebook as-is, or allow new codes to emerge from this data?" That single question derives the internal mode:

- "Use as-is" → **Validation mode:** codebook is locked. New data only matches to existing ICs. Key output: coverage ratio (how much new data fits existing codebook) and gap analysis (segments that produced no matches).
- "Allow new codes" → **Evolution mode:** core codebook is locked. New ICs are created in a separate "emerging" holding area. At sign-off, the analyst sees: "Your codebook had 38 ICs. This run encountered 5 segments that didn't fit any existing code. Here are the proposed new ICs — promote each to your core codebook or dismiss."
- First run (no checkpoint exists) → **Discovery mode:** fully open codebook, current behaviour.

### Session-start UX
If the database already contains a named checkpoint, the pipeline opens with: "You have a saved codebook 'v1_launch_reviews' from [date] (38 ICs). Load it, or start fresh?" That's the only decision point. Everything else flows from there.

### Longitudinal analytics (version diff report)
Compare codebook v1 vs v2 across runs:
- **IC frequency trends:** which ICs gain/lose evidence over time (quote count delta)
- **IC lifecycle:** "confirmed" (present in all versions), "emerging" (new in latest), "declining" (fewer quotes), "deprecated" (no new evidence)
- **Cross-version stability:** is this concept still being expressed in newer data? (Different from refinement stability — this asks about temporal stability)
- **Theme evolution:** which themes persist, which fragment, which new ones emerge
- **Practical value:** for a game getting patches, does `parkour_unresponsive` weaken in post-patch reviews? That's a direct measure of patch effectiveness.

---

## Other Ideas (Parking Lot)

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

*Last updated: 2026-02-22 — Session: sentiment analysis + negative examples + codebook versioning design*
