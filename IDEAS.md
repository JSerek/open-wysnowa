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

### S4: Distinctness-Aware Revision Pass `[resolved]`
Post-synthesis step: compute pairwise theme centroid similarities, flag pairs above threshold (0.70), ask LLM to MERGE (same phenomenon) or SHARPEN (different phenomena, similar vocabulary). Runs on ThemeProposal objects before persistence. Configurable via `theme_refinement.distinctness_threshold` and `max_overlap_pairs` in `eqd_config.yaml`.

### S4: Theme Splitting Heuristic (k-means + LLM) `[resolved]`
Detect "magnet themes" meeting three criteria: IC count ≥ 8, raw coherence < 0.50, overlap pairs ≥ 3. Run pure-Python k-means (k=2, cosine distance, 3 restarts) on IC embeddings to produce candidate clusters. LLM validates whether the split is semantically meaningful or a statistical artifact. If approved, original theme replaced by two sub-themes. Configurable via `theme_refinement.split_min_ics`, `split_max_coherence`, `split_min_overlaps`.

**Pipeline insertion point:** Both features run between `_run_layer2()` return and `persist_themes()` — distinctness revision first (may merge), then splitting (may split remaining magnets).

### S1: Sentiment Analysis at IC Creation `[resolved]`
Added `sentiment` field (positive/negative/neutral/mixed) to `ICCandidate` and `InitialCode` models, assessed by the coder agent on each verbatim quote. New `Sentiment` enum in models. New metric: **Theme Sentiment Purity** — dominant sentiment ratio per theme, flagged when <0.70. 30-review test confirmed avg purity 0.96. Sentiment treated as a metric/signal, not a gate.

### S2: Coder Agent Specificity Guidance `[resolved]`
Added rule #10 to coder system prompt: "SPECIFICITY MATCHES THE TEXT — Be as specific as the text allows, no more. If the segment identifies a specific system or feature, name it. If the segment expresses general dissatisfaction without identifying specific causes, create an IC that captures the general nature of the experience — never fabricate specifics that aren't in the text." Gives explicit permission for general ICs when the text is general.

### S3: Negative Examples in All Agent Prompts `[resolved]`
Added negative examples (BAD → diagnosis → corrected) to three agents. Coder: 3 error types — fabricated specificity, meta-commentary, wrong sentiment assignment. Comparator: over-merging counter-example showing when MERGE is wrong despite surface similarity. Synthesizer: mixed-sentiment theme and over-broad category-level grouping counter-examples. Format uses `BAD:` / `WRONG:` labels for clear boundary definition.

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

### Three analysis modes (explicit upfront selection)
The analyst selects mode at pipeline start. The system enforces availability based on DB state.

**Discovery mode** — fully open codebook (current behaviour). Available always. Used for initial exploration and codebook building. After completion, analyst can save a codebook checkpoint (named + timestamped freeze).

**Validation mode** — codebook is locked, no new ICs. Only available when a named checkpoint exists. This is **deductive coding / content analysis / classification** — applying an existing framework to new data. Major pipeline simplification: skips IC triage, IC refinement, comparator agent, codebook sign-off. Coder agent replaced by a dedicated **ClassifierAgent** (see below). Key outputs: coverage ratio (% of segments matched), gap analysis (unmatched segments), per-IC frequency shifts.

**Evolution mode** — core codebook is locked, but new ICs can emerge in a separate "emerging" holding area. Only available when a named checkpoint exists. At sign-off, analyst sees: "Your codebook had 38 ICs. This run encountered 5 segments that didn't fit any existing code. Here are the proposed new ICs — promote each to your core codebook or dismiss."

**Guardrails:** If DB is empty or no checkpoint exists → only Discovery is available. Validation and Evolution are greyed out with explanation.

### ClassifierAgent (Validation mode)
A dedicated agent separate from the Coder — the classification task is fundamentally different from extraction. The Coder generates ICs from open-ended reading; the ClassifierAgent assigns segments to existing ICs from a fixed codebook.

**Prompt structure:** Each IC gets few-shot examples (positive: existing verbatim quotes from Discovery; negative: near-miss quotes from comparator reject decisions). Full codebook included as context (~4K tokens for 38 ICs). For large codebooks (100+ ICs), pre-filter candidate ICs per segment using embedding similarity (top-10 nearest).

**Model choice:** Start with Haiku for cost efficiency — classification is simpler than generation. Track classification confidence per assignment. If confidence drops below threshold on specific ICs, escalate those segments to Sonnet. This gives Haiku's cost for the ~80% clear cases, Sonnet's judgment for the ambiguous ~20%.

**Processing:** One segment at a time. Output: list of matched IC IDs with confidence scores.

### Session-start UX
Pipeline opens with mode selection. If a checkpoint exists: "You have codebook 'v1_launch_reviews' from [date] (38 ICs). Select mode: Discovery (fresh start) / Validation (classify new data) / Evolution (extend codebook)." If no checkpoint: "No codebook checkpoint found. Starting in Discovery mode."

### Longitudinal analytics (version diff report)
Compare codebook v1 vs v2 across runs:
- **IC frequency trends:** which ICs gain/lose evidence over time (quote count delta)
- **IC lifecycle:** "confirmed" (present in all versions), "emerging" (new in latest), "declining" (fewer quotes), "deprecated" (no new evidence)
- **Cross-version stability:** is this concept still being expressed in newer data? (Different from refinement stability — this asks about temporal stability)
- **Theme evolution:** which themes persist, which fragment, which new ones emerge
- **Practical value:** for a game getting patches, does `parkour_unresponsive` weaken in post-patch reviews? That's a direct measure of patch effectiveness.

---

## Inter-Rater Reliability (Discovery Mode) `[design]`

### Vision
Run Discovery mode N times on identical data to measure system reliability. Analogous to inter-coder reliability in qualitative research — using the LLM as multiple independent coders.

### Three-layer reliability measurement

**Layer 1: Quote overlap (evidence stability).** For each segment, compare extracted text spans across runs. Use span overlap ratio (≥70% character overlap = "same evidence") rather than exact match — the coder may extract slightly different boundaries. Pure string computation, no LLM calls. Metric: **Evidence Agreement Rate** — % of quotes with a cross-run match.

**Layer 2: IC alignment (interpretation stability).** After quote matching, check whether matched quotes are grouped under semantically similar ICs. Alignment via embedding similarity (threshold ≥0.85 = "same IC", 0.70–0.84 = "related"), supplemented by LLM validation for borderline pairs ("Are these two ICs describing the same phenomenon?"). Metric: **Coding Agreement** — Krippendorff's alpha on the segment × aligned-IC assignment matrix.

**Layer 3: Theme alignment (structural stability).** Do aligned ICs end up in similar themes across runs? Weakest signal — themes are the most subjective layer. Metric: **Thematic Convergence** — proportion of aligned ICs that co-occur in similar theme groupings.

### Coding agreement — how it works
Build a binary matrix: rows = segments, columns = aligned ICs (matched across runs). Each cell = 1 if that run assigned that IC to that segment, 0 otherwise. Krippendorff's alpha computed on this matrix accounts for chance agreement (unlike raw % agreement). Alpha > 0.80 = strong reliability, 0.67–0.80 = acceptable, < 0.67 = needs investigation.

### Practical output
A reliability report: "Across 3 runs: 90% evidence overlap (quote level), alpha = 0.78 (IC assignment level), 65% thematic convergence." Each layer tells you where variability enters — extraction vs. interpretation vs. organization.

### Design decisions still open
- **Codebook reconciliation after multiple Discovery runs:** Deferred for now. Complex merging logic (which ICs to keep, how to reconcile conflicting interpretations). Current flow needs more testing before adding this weight. Revisit after Codebook Versioning is stable.
- **Cross-model reliability:** Running different LLMs across iterations to measure inter-model agreement. Separate from intra-model reliability — answers a different question. Parked for future exploration.

---

## Next Up

### Coder Agent Confidence Metric `[ready]`
**Problem:** `ICCandidate.confidence` (0–1, the coder's self-assessed certainty) is collected during Layer 1 but never stored on `InitialCode`, never aggregated, and never visible in Layer 3 metrics. All confidence signal evaporates after the triage decision.

**Fix:** (1) Add a `mean_coder_confidence` metric to Layer 3 — mean confidence across all accepted new IC candidates. (2) Flag low-confidence new ICs (< 0.6) for HIL review even if they pass the auto-triage threshold. (3) Include per-IC confidence in the codebook sign-off display so analysts know which codes the model was uncertain about.

### SUBCODE Deprecation `[ready]`
**Problem:** `ComparatorRecommendation.SUBCODE` exists in the enum and may appear in comparator prompts, but has no handling branch in orchestrator.py. ICs are not hierarchical and never were. SUBCODE is dead code that creates confusing prompt signals.

**Fix:** Remove `SUBCODE` from `ComparatorRecommendation` enum. Update the comparator system prompt to only output `NEW`, `MERGE`, or `REJECT`. Update the comparator agreement metric in `quality_metrics.py` (currently lumps SUBCODE with MERGE). Simple, low-risk.

### Category Agent HIL Sign-Off `[ready]`
**Problem:** Unlike theme synthesis (3 rounds, feedback, analyst sign-off), the Category Agent proposes and auto-validates categories with zero analyst input before DB persistence. If automatic merges or absorptions produce wrong categories (as seen in canon_30 where Core Gameplay Mechanics + World Design merged), there is no correction path without re-running.

**Fix:** Add a single HIL checkpoint after `_validate_proposals()` and before `persist()`: display proposed categories with their constituent themes, prompt for approval or abort. If HIL is disabled, auto-confirm. One prompt, no feedback loop needed — categories are high-level enough that a simple yes/no gate is sufficient.

### Resume-from-Codebook Path `[ready]`
**Problem:** HIL Level 2 codebook rejection stops the pipeline. The codebook is already in the DB, but the only recovery path is re-running Layers 0–1 from scratch — expensive and wasteful.

**Fix:** Add `--skip-extraction` flag to `run_pipeline.py` that jumps directly to the codebook sign-off check, using an existing DB. About 20 lines of code. This is a partial, lightweight precursor to Codebook Versioning's Discovery → Validation flow — useful now, not just when versioning lands.

### Segment Faithfulness Scoring `[design]`
**Problem:** The pipeline drops candidates at span validation, but we don't know whether the coder agent is systematically hallucinating spans for certain types of text. A per-segment faithfulness score (verified_quotes / total_candidates) would reveal: (a) segments that consistently cause span errors, (b) whether certain text patterns (long sentences, slang, mixed language) cause more hallucination.

**Architecture:** Computed during Layer 1 as a byproduct of span validation. Aggregated as a new metric in Layer 3. Could feed into a "segment difficulty" heuristic that triggers slower/more careful coding for hard segments.

### Category Merge Threshold Tuning `[ready]`
**Problem:** The 30-review test run merged "Core Gameplay Mechanics" + "World Design & Content Structure" at sim=0.867 with threshold 0.85. These are analytically distinct categories. The threshold is too aggressive.

**Fix:** Raise `category_merge_threshold` from 0.85 to 0.90 in `eqd_config.yaml`. Consider making category merging HIL-gated (analyst confirms merges) rather than fully automated.

### Category Merge LLM Rename `[ready]`
**Problem:** When the Category Agent merges two overlapping categories, it keeps "the longer definition" heuristically and picks the longer name. The result is often a poorly named merged category — it inherits one parent's name without reflecting the combined concept.

**Fix:** After a merge, make a short LLM call (haiku, ~200 tokens) with: "Category A: {name_a} — Category B: {name_b} — Definition: {combined_def}. Propose a concise name (≤8 words) that covers both." Replace the heuristic with the LLM-proposed name. Applies only to merged categories, not absorbed singletons.

### thematic_structure Auto-Export `[ready]`
**Problem:** The full thematic structure (JSON: categories → themes → ICs → quotes) is built at the end of each run and held in memory, but never written to disk automatically. It is only available during the live terminal session. The analyst must manually request the export or the data is lost when the process exits.

**Fix:** Auto-write `thematic_structure.json` to the run directory at the end of each pipeline run (next to the `.db` file). Optionally, write a human-readable `thematic_structure.md` with indented hierarchy. ~5 lines of code in `pipeline.py` or `run_pipeline.py`.

### Re-run Detection After Codebook Rejection `[design]`
**Problem:** When codebook sign-off is rejected (HIL Level 2), the ICs and quotes are already committed to the DB. If the analyst re-runs with "Build upon" instead of "Overwrite," the pipeline resumes with rejected data silently — it has no way to detect that the previous run ended in rejection.

**Fix:** Record pipeline exit state to DB (a lightweight `pipeline_events` table or a single status flag). On startup with an existing DB, if the last run ended in codebook rejection, surface a clear warning before proceeding. Prerequisite: the Resume-from-Codebook `--skip-extraction` flag (above) should land first, since it provides the proper "resume from codebook" path rather than "re-run from scratch."

---

## Other Ideas (Parking Lot)

### Knowledge Graph / Quote Network Visualization `[later]`
Build a graph: ICs as nodes, edges weighted by quote co-occurrence (two ICs sharing quotes from the same segment). Visualize which concepts cluster in the raw data vs. how themes group them. Community detection (Louvain/Leiden) could reveal natural clusters the synthesizer missed. Centrality metrics (betweenness, PageRank) identify bridge ICs and hub codes. Temporal graph analysis becomes powerful with codebook versioning.

**Honest assessment:** At current scale (30–100 reviews, 40–80 ICs), most graph algorithms won't find patterns invisible in a sorted similarity matrix. Graph algorithms shine at 1000+ nodes. Visualization risks producing "hairball" graphs that look impressive but communicate poorly. Co-occurrence signal can be noisy (long segments produce spurious edges). **Prioritize after codebook versioning** — versioning creates the temporal dimension that makes graph analysis genuinely powerful. Without multiple runs/versions, it's a static snapshot.

**Tech if we build it:** NetworkX (Python, fits our stack), pyvis or D3.js for interactive HTML output. Edge weights: Jaccard similarity or PMI (controls for IC frequency) rather than raw co-occurrence count.

### Segment Difficulty Scoring `[later]`
Some segments consistently produce more drops, lower-confidence ICs, or more grey-zone decisions. Scoring segments by "coding difficulty" could help identify: (a) reviews that are poorly written/ambiguous, (b) reviews that contain novel concepts the codebook hasn't captured, (c) reviews that are outliers vs. mainstream sentiment.

### Embedding Model Comparison `[later]`
Run the same codebook through different embedding models and compare: how do similarity scores change? Do triage decisions flip? Which themes gain/lose coherence? This would help calibrate whether results are robust to embedding choice or artifacts of a specific model. Could extend to cover coder agent model comparison (related to inter-rater reliability cross-model idea).

### Visual Segment Inspection UI `[later]`
**Idea:** After Layer 1, display each segment with its extracted quotes highlighted inline (coloured spans), IC names annotated, and sentiment labels. Lets the analyst visually verify that the coder agent is extracting the right text from the right places — catches hallucinated spans, missed evidence, and sentiment errors faster than reading raw logs.

**Implementation options:** (a) Static HTML report per run, generated from verbatim_quotes + segments tables. (b) Interactive terminal UI (rich/textual). (c) Notebook cell (pandas + ipywidgets). Option (a) is fastest to implement and most shareable. The data is already in the DB — span_start/span_end + quote_text + sentiment + ic_id per segment. No new pipeline logic needed, just a renderer.

**Note on span overlaps:** In canon_30, only 1 of 30 segments has overlapping spans (3.3%, 236 chars total). At current scale the overlap rate is near-zero in normal operation. Adding a span_overlap_ratio metric is low-value until we see this become a problem with denser review types.

### Alternative Qualitative Methodologies `[later]`
**Applicable with current workflow (codebook + quote extraction architecture):**

- **Framework Analysis:** Use a predefined analytical framework (e.g., Capability Approach, PERMA model) as the synthesis lens. Instead of open thematic synthesis, the Synthesizer maps ICs to predefined framework categories. The coder stage is unchanged; only the synthesizer prompt changes. Immediately possible via Layer 5 Interactive Lensing.
- **Content Analysis (frequency-based):** Shift from grounded/interpretive to frequency-based analysis. Count IC occurrences per review rather than semantic grouping. Thematic coverage metric already approximates this. Would need a "count mode" report.
- **Discourse Analysis (surface):** Focus the coder prompt on language patterns (metaphors, hedging, escalation language) rather than topics. The IC extraction architecture supports this — only the prompt framing changes.

**Not applicable without major rearchitecting:**
- Phenomenological analysis (requires bracketing and epoché — fundamentally incompatible with automated coding)
- Narrative analysis (requires story arc / temporal structure per review — the pipeline treats reviews as bags of segments)
- Ethnography / conversation analysis (requires multi-participant interaction data)

### Overlapping Span Rate Diagnostic `[later]`
**Idea:** After Layer 1, measure what fraction of character positions within each segment are covered by 2+ verbatim quote spans — i.e. the coder extracted overlapping evidence for different ICs from the same text.

**Empirical baseline (canon_30):** 1 of 30 segments has any overlapping spans (3.3%, totalling 236 characters). Near-zero in normal operation. Signal may grow with denser, multi-topic reviews. Should surface as a diagnostic in the Layer 4 analyst brief rather than a hard Layer 3 metric — flag when overlap rate exceeds some threshold (e.g., >10% of segments). Not worth implementing until we see this become meaningful in real data.

### Plugin / IDE Agent Integration `[later]`
Package EQD-AI as an installable plugin for agent-enabled IDEs — specifically Claude Code (Anthropic) and Anygravity (Google's IDE with agents). The pipeline's tool surface maps naturally to the MCP (Model Context Protocol) primitive: expose `run_analysis`, `get_codebook`, `get_themes`, `get_metrics`, and `reassess_orphans` as callable tools, letting analysts drive the workflow conversationally rather than via terminal scripts.

**Prerequisite:** Complete codebook versioning and Layer 5 first — the plugin becomes genuinely useful only when the full workflow is stable and the HIL gates are well-defined.

**Key architectural changes needed:**
- Replace blocking `input()` HIL gates with tool response round-trips (the conversation mediates feedback instead of the terminal)
- Add explicit session/project management so tool calls know which DB to operate on
- The `enable_hil=False` automated path is already almost plugin-ready — a single `run_analysis` MCP tool could wrap it today with minimal changes
- The richer interactive path (feedback loops, coherence gate approvals) requires rearchitecting the gate logic into stateful, resumable steps

**Honest scope estimate:** Automated mode as MCP plugin: ~1-2 days. Full interactive HIL via conversation: medium effort (week+). Packaging + marketplace listing: low, once MCP layer exists.

### Export Formats `[later]`
- ATLAS.ti / NVivo compatible export (for researchers who want to continue in traditional QDA tools)
- Interactive HTML report with collapsible theme hierarchy
- JSON-LD for semantic web / knowledge graph integration

### Multi-Dataset Analysis `[later]`
Run the pipeline on multiple datasets (e.g., reviews for Game A, Game B, Game C) and compare thematic structures. Which themes are universal? Which are game-specific? This moves from single-product analysis to cross-product insights. Depends on codebook versioning being stable.

---

*Last updated: 2026-02-28 — SUBCODE removed from codebase (models.py, prompts.py, orchestrator.py, hil.py, codebook_comparator.py, quality_metrics.py) — comparator now uses NEW/MERGE/REJECT only. Added to Next Up: Coder Agent Confidence Metric, Category Merge LLM Rename, thematic_structure Auto-Export, Re-run Detection After Codebook Rejection. Added to Other Ideas: Visual Segment Inspection UI, Overlapping Span Rate Diagnostic (baseline: near-zero), Alternative Qualitative Methodologies. IC sentiment not stored on initial_codes — quote-level sentiment + Theme Sentiment Purity covers the signal.*
