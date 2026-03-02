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

## Layer 4: Analyst Intelligence `[resolved]`

### Vision
An LLM-powered interpretive layer that sits on top of the structured pipeline output. Takes the full results dict + thematic structure + quality metrics and produces a written analytical brief — the same analysis we've been doing manually in conversation.

### Implemented
Layer 4 is live as `src/analyst_agent.py` (`AnalystAgent`). It runs automatically as the final pipeline step after Layer 3. Uses `or_smart` model (Sonnet-class). Input: full results dict with thematic structure, all 18+ quality metrics, and a confidence distribution summary. Output: structured `AnalyticalBrief` (Pydantic model) with metric flags, structural diagnostics, thematic interpretation per theme, and actionable recommendations. Persisted to DB and available in the pipeline results dict as `results["layer4"]`.

Confidence distribution passed as summary stats only (not per-IC raw data) to avoid token bloat while still giving the model enough signal.

### Remaining gaps / future improvements
- **Comparative analysis:** If previous run results exist, compare across runs (codebook growth, theme stability, metric trends). Depends on Codebook Versioning.
- **Deeper thematic interpretation:** Currently interprets themes at a structural level. More detailed IC-level interpretation would require more prompt engineering and token budget.
- **Interactive Q&A mode:** Layer 4 is currently one-shot. An interactive mode (analyst asks follow-up questions) is a future direction — requires session state management.

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
- **Immutability fix (bundle here):** `InitialCodeRepo.update_definition()` currently mutates IC definitions in place, violating DESIGN_PRINCIPLES.md #1 and #5. The correct fix is append-only IC rows with a `version: int` column and queries that always pull `latest active version`. This requires the versioning schema above to be meaningful — implement as part of this sprint, not standalone.

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

## Model Evaluation Harness / Leaderboard `[design]`

### Vision
A structured benchmark system for comparing model configurations across pipeline runs. Uses `canonical_30` as a fixed reference dataset. Produces a table where each row is a model configuration and columns are the 18 quality metrics — no single aggregate score, just the full profile.

### Leaderboard structure
- **Rows:** model configuration (e.g., `or_fast=gpt-5-nano, or_smart=gemini-3-flash-preview`)
- **Columns:** all 18 point-estimate metrics (grounding, drop_rate, extraction_density, singleton_ratio, triage_auto_rate, comparator_agreement, its_final, theme_coherence, theme_distinctness, sentiment_purity, thematic_coverage, cross_review_convergence, merge_rate, ic_stability, meaning_saturation_breadth, meaning_saturation_spread, coherence_normalized, coder_confidence_mean)
- **Reliability columns:** `coder_reliability`, `synthesizer_reliability`, `analyst_reliability` — populated only after N stability runs for that config; blank otherwise. Computed as SD of key layer metrics across N runs.
- **No aggregate score yet.** Read the full profile. Per-layer weighted aggregation is a later addition once we understand which metrics carry signal vs. noise.

### Stability-first methodology
Cross-model comparison is only meaningful once within-config variance is known. If model A scores 0.65 coherence and model B scores 0.70, the difference is uninterpretable without the SD of each. Correct workflow:
1. Pick a config. Run canonical_30 N times (3–5). Compute metric SDs → populate reliability columns.
2. Only then compare configs against each other.

### Metric co-variance — document, don't fight
Several metric pairs are structurally linked and must be read together, never in isolation:
- `extraction_density` ↔ `singleton_ratio`: high extraction → more unique codes → higher singleton ratio. A model that extracts aggressively will look worse on singleton_ratio regardless of quality.
- `merge_rate` ↔ `triage_auto_rate`: high auto-rate looks efficient but if merge_rate is near zero, the comparator is rubber-stamping everything as NEW. Read as a system, not separately.

### Sample size confound
`singleton_ratio` (and `cross_review_convergence`) are partly data-volume artifacts. At 30 reviews, almost any model will show high singleton_ratio — patterns haven't had enough repetition to consolidate. When scaling to 100+ reviews, these metrics will shift substantially. **30-review leaderboard scores are not directly comparable to 100-review scores for these metrics.** Hold sample size constant (canonical_30) across all leaderboard runs and document this limitation explicitly in any report.

### canonical_30 as permanent benchmark
All leaderboard runs against canonical_30 only. It's fixed, validated, and small enough to run cheaply. Never swap the benchmark dataset mid-leaderboard — that invalidates all historical rows.

---

## Category Agent Quality Gates `[design]`

### Current state
Category Agent pipeline: LLM proposal → programmatic centroid merge (overlapping categories) + singleton absorption → HIL sign-off → persist. Compared to the Theme layer, it lacks any post-proposal quality gate.

### What the Theme layer has that Category doesn't
- Coherence gate with dissolve option
- Distinctness revision pass (LLM merge/sharpen)
- Magnet theme detection + k-means split
- Orphan reassessment pass
- Live coherence + distinctness display in HIL loop

### Why the gap is acceptable for now
Categories are coarser by design — grouping 6 themes into 3 buckets is a well-constrained problem where IC-level coherence measurement doesn't directly apply. At current scale (3–8 categories), the risks are limited and the HIL sign-off provides sufficient manual oversight.

### What's worth adding eventually

**Category-level distinctness check:** Same risk of "magnet category" exists — one bucket catches everything, others are thin. A pairwise centroid similarity check (reusing existing `_merge_overlapping` logic) could flag categories above threshold before the HIL display. At category scale this is simpler than at theme scale because there are fewer pairs.

**Coverage review in HIL display:** Show which themes landed in which category, flag any category with only 1 theme (de facto singleton — equivalent of a thin theme). Currently the analyst sees category names and definitions but not the theme distribution at a glance.

**Sentiment purity gate at category level:** Layer 3 already computes per-theme sentiment purity. A mixed-sentiment category (e.g., one containing both "positive franchise comparisons" and "negative pricing" themes) is a signal worth surfacing — the category boundary may be wrong. Would reuse the same purity metric, just aggregated per category.

### What's NOT worth adding
Full coherence gate at category level — categories are intentionally broad, and measuring coherence across 2–3 themes is statistically weak. The distinctness and coverage checks above give enough signal without adding the full gate machinery.

### Prerequisites
Stable theme pipeline first. Category gates only make sense once the themes going into them are consistently well-formed.

---

## Next Up

### HIL: Terminal UX Improvements `[resolved]`
Five improvements shipped together:

**Top-K definition snippets:** Each similar existing code now shows a truncated (85-char) definition inline below its name and similarity score. Eliminates the need to memorise the codebook while reviewing candidates — the most common cognitive bottleneck in long sessions.

**`?` expand command:** Typing `?` at the action prompt prints the full LLM reasoning (untruncated) plus the full definitions of all top-K ICs. The action menu re-appears afterward. Useful when the 200-char reasoning preview or 85-char definition snippets don't settle the question.

**Reasoning truncation:** LLM reasoning is capped at 200 chars in the display. Long reasoning previously scrolled the quote off-screen. Truncated suffix shows a `?` hint.

**Single-step undo (`U`):** At the action prompt, `U` reverses the immediately previous decision — for NEW (hard-deletes IC + quote from DB, removes from deferred embed queue), MERGE (deletes quote), REJECT (no DB writes, instant). The current candidate is re-displayed with a clean decision slate. Only one level deep; prevents double-undo.

**Session stats in batch header:** Batch header now shows latest ITS value and running session totals (new/merged/rejected) from batch 2 onward. Gives orientation before each batch.

**Files:** `src/hil.py`, `src/orchestrator.py`, `src/db.py` (`InitialCodeRepo.hard_delete()`, `VerbatimQuoteRepo.delete_by_id()`).

### HIL: Quote Context — Sentence Boundaries `[resolved]`
Replace the current fixed 50-character context window around verbatim quotes with one full sentence before and one full sentence after the extracted span. Sentence boundaries are meaningful reading units; 50 chars of raw text is not. The actual stored quote (inside `[...]`) is unchanged — only the context display changes.

Edge cases: quote is the first sentence in the segment (no before), or last (no after) — display only what exists, no padding. Implemented via `_sentence_context()` helper in `hil.py`.

### HIL: Merge Confirmation Prompt `[resolved]`
After the analyst selects a merge target (e.g., `M1`), a confirmation step shows the full IC name and prompts Y/N before recording the decision. If N, returns to the action prompt. Prevents accidental merges as the codebook grows.

### HIL: Quote Span Editing — Bracket Slicer `[later]`
Extend `[E]` edit mode to allow interactive span adjustment using movable `[` `]` bracket markers. Target UX: display the quote ± one sentence of context, analyst moves bracket positions using arrow keys, presses Enter to confirm. System computes `span_start`/`span_end` from final bracket positions. Works for both trimming and expanding.

**Requires `prompt_toolkit`** — a well-maintained Python library (used by IPython) that gives full cursor control and key bindings in the terminal. Not achievable with bare `input()`. New dependency, real testing overhead on different terminal configs — hence `[design]` rather than `[ready]`.

**Interim fallback (numbered words):** While prompt_toolkit is not yet implemented, `[E]` could offer a numbered-word display where each token is prefixed with its index. Analyst types start and end word numbers; script finds character positions. Practical up to ~40 words, breaks down on long segments, has edge cases with punctuation and repeated words. Not worth implementing standalone — only as a stepping stone toward the bracket slicer.

**Rejected approach:** "Type the exact quote you want" (substring search). Rejected because it requires humans to recall verbatim text precisely, which is harder and more error-prone than LLM extraction. The bracket slicer or word-index fallback are both preferable.

**File:** `src/hil.py` — `prompt_edit_candidate()`, add span editing block after name/definition editing.

### Coder Agent Confidence — Redefinition `[resolved]`
Redefine what confidence measures: **how certain the coder is that this concept is not already covered by any existing IC in the codebook at the time of extraction.** Confidence in the novelty claim, not in span accuracy (covered by grounding) or definition quality (changes post-refinement).

This makes confidence stable (codebook state at creation is fixed), actionable (low confidence = model sensed borderline overlap with existing codes), and non-redundant with other checks.

**Implementation:** Updated `ICCandidate.confidence` and `InitialCode.confidence` field descriptions in `src/models.py`. Added rule #12 ASSESS NOVELTY CONFIDENCE to coder system prompt in `src/prompts.py` with explicit calibration scale (1.0 = clearly new, 0.5 = uncertain, 0.0 = near-duplicate). Updated few-shot example confidence scores to reflect novelty semantics.

### Coder Reuse Rate Diagnostic `[resolved]`
Track whether the Coder Agent actually reuses existing IC names when the codebook has entries, rather than always proposing new codes regardless of the injected codebook.

**Metric:** 2×2 matrix — coder flagged existing match (bypass comparator) vs coder said new × comparator decision (NEW / MERGE / REJECT). Reveals (a) whether codebook injection is working — a well-calibrated coder should flag more matches as the codebook grows; (b) coder–comparator agreement — systematic flip rate signals prompt misalignment.

**Implementation:** Four counters in `orchestrator.py`: `coder_flagged_match`, `coder_new_comp_new`, `coder_new_comp_merge`, `coder_new_comp_reject`. Passed through pipeline.py kwargs to `quality_metrics.compute_all()`, stored as `coder_reuse` in results. Displayed as CODER REUSE RATE block in `quality_report.py` with flip rate warning (>40% = ⚠ coder over-generates).

### Coder Agent Confidence Metric `[resolved]`
Metric collection in place (Layer 3 `coder_confidence` dict with mean/min/max/low_count/ratio). Low-confidence IC IDs now tracked in `layer1_summary["low_confidence_ic_ids"]` and passed to codebook sign-off, where they appear as ⚑ flags in the display with a summary warning. Threshold: confidence < 0.6.

### SUBCODE Deprecation `[resolved]`
Removed from `ComparatorRecommendation` enum, comparator prompt, and all downstream handlers. Committed in 364bb6b.

### Category Agent HIL Sign-Off `[resolved]`
Single HIL checkpoint after `_validate_proposals()`. Committed in d5462fb.

### Resume-from-Codebook Path `[resolved]`
`--skip-extraction` flag + `run_from_codebook()` + shared `_run_from_signoff()`. Committed in ecebb4d.

### Exhaustive Field descriptions `[resolved]`
All LLM-facing Pydantic model fields have instruction-style descriptions. Committed in ecebb4d.

### Category Merge Threshold Tuning `[resolved]`
`category_merge_threshold` raised from 0.85 to 0.90 in `eqd_config.yaml`. Committed in 5711ace.

### Category Merge LLM Rename `[resolved]`
`_llm_rename_merged()` in `category_agent.py` — Haiku call proposes unified name after merge. Committed in ecebb4d.

### thematic_structure Auto-Export `[resolved]`
`run_pipeline.py` auto-writes `{db_stem}_thematic_structure.json` at end of each run.

### Coder Agent Batch Fallback — Targeted Retry `[resolved]`
**Problem:** When a batch LLM call succeeds structurally but some segments are simply absent from the response (the LLM dropped them silently), the previous code only logged a warning and moved on — those segments got zero candidates extracted.

**Fix:** After batch result processing, compute `responded_ids = {sr.segment_id for sr in result.segment_results}`. For each segment missing from that set, call `_code_segment()` individually (uses the existing 3-attempt tenacity retry). Segments that were present in the batch result are unaffected. If the targeted retry finds candidates it logs "recovered N candidates"; if not it logs a warning. This is surgically targeted — only the truly missing segments are retried.

### Segment Faithfulness Scoring `[design]`
**Problem:** The pipeline drops candidates at span validation, but we don't know whether the coder agent is systematically hallucinating spans for certain types of text. A per-segment faithfulness score (verified_quotes / total_candidates) would reveal: (a) segments that consistently cause span errors, (b) whether certain text patterns (long sentences, slang, mixed language) cause more hallucination.

**Architecture:** Computed during Layer 1 as a byproduct of span validation. Aggregated as a new metric in Layer 3. Could feed into a "segment difficulty" heuristic that triggers slower/more careful coding for hard segments.

### Re-run Detection After Codebook Rejection `[design]`
**Problem:** When codebook sign-off is rejected (HIL Level 2), the ICs and quotes are already committed to the DB. If the analyst re-runs with "Build upon" instead of "Overwrite," the pipeline resumes with rejected data silently — it has no way to detect that the previous run ended in rejection.

**Fix:** Record pipeline exit state to DB (a lightweight `pipeline_events` table or a single status flag). On startup with an existing DB, if the last run ended in codebook rejection, surface a clear warning before proceeding. Prerequisite: the Resume-from-Codebook `--skip-extraction` flag (above) should land first, since it provides the proper "resume from codebook" path rather than "re-run from scratch."

---

## Custom UI for HIL `[explore]`

### Why and when
The terminal HIL works but has a hard ceiling: everything relies on `input()` blocking Python execution. A custom UI lifts that ceiling entirely. Prerequisite alignment: **stabilise the workflow first** — codebook versioning and Layer 5 need to be solid before investing in UI. The terminal improvements above extend the runway significantly. Sequence recommendation: terminal now → Textual TUI as stepping stone → full custom app when workflow is stable.

### Architectural prerequisite: async queue
All current HIL is built on blocking `input()`. A custom UI requires decoupling. The right pattern: pipeline writes candidates to a queue/DB table, UI reads and renders, decisions are written back, pipeline polls. This is a real architectural change but it's the correct one — and it's already noted in the Plugin/IDE Integration item.

### Phase 1 — Textual TUI (stepping stone) `[explore]`
**Textual** is a Python TUI framework (used by IPython's terminal interface). It gives proper two-panel layout, mouse support, keyboard bindings, and scrollable panels while staying in the Python stack with no web server. The `input()` → async event change is the only required architectural shift. A meaningful quality-of-life upgrade at fraction of a full web app's effort.

Key panels:
- **Left:** persistent codebook — all current ICs, scrollable, grouped by theme if themes exist. Clicking an IC shows its full definition + quote count without leaving the candidate review.
- **Right:** current candidate — name, definition, confidence, quote in context, top-K, LLM rec.
- **Bottom bar:** live ITS, codebook size, session new/merge/reject counts. Updates after each decision.

### Phase 2 — Full Custom App `[explore]`
Framework options: **FastAPI + React** (web, most flexibility), **Tauri** (desktop, offline-first, filesystem access). Either would work — Tauri is worth considering given the offline/local-data nature of the tool.

Key UX improvements over terminal that justify the investment:

**Persistent codebook panel.** Solves the biggest cognitive bottleneck — the analyst never has to remember what an IC means mid-decision. Click any top-K match to see its full card: definition, quote count, example quote, confidence histogram, creation timestamp.

**Quote highlighting in full segment.** Show the full segment text with the extracted span highlighted in color. Replaces `...before [quote] after...` with inline visual context. For long segments this is dramatically clearer.

**Decision history + undo.** Scrollable session log: `✓ NEW: combat_feedback_loop | ↔ MERGED: price_complaint → value_perception`. Click any past decision to review it. Multi-level undo (N decisions back) with cascade handling for merges. Lets the analyst spot their own patterns — "I've rejected 8 straight, is the model miscalibrated?"

**Batch preview card.** Before entering a batch: "Batch 5 | 8 candidates | 3 have high similarity to existing ICs (>0.65) | 1 flagged meta-commentary | ITS: 0.74". Analyst enters each batch with orientation.

**Structured decision annotations.** Instead of free-text notes: rejection reason dropdown (meta / duplicate / noise / insufficient evidence), merge confidence (certain / uncertain). Feeds future analytics on analyst decision patterns and prompt quality.

**Keyboard-first, mouse optional.** N/M/R shortcuts must stay. Mouse for IC browsing and codebook navigation. No pointer required for the decision loop itself.

### What NOT to build yet
- Real-time collaboration (multi-analyst) — significant complexity, wait until single-analyst flow is rock solid
- Cloud sync — keep it local/offline first
- Custom viz / dashboards — Layer 4 already provides interpretation; visualisation is additive, not prerequisite

---

## Reasoning Model Support — Parked Items

### Retry Effort Escalation `[later]`
When instructor retries a failed structured output call, the reasoning budget is consumed again at the same effort level. A smarter approach: start at `low` on first attempt, escalate to `medium` on retry 1, `high` on retry 2. This means cheap attempts for the common case, and heavier reasoning only for genuinely ambiguous outputs. Requires hooking into instructor's retry callback to modify `extra_body` between attempts. Park until reasoning models are the primary coder/comparator model and retry cost is measurable.

### Quote Coverage Per IC `[resolved]`
Per-IC evidence coverage: what fraction of a segment's characters are covered by each IC's grounding quote(s). For multiple quotes from the same segment, uses interval union (sorted merge of `[span_start, span_end]` intervals) to avoid double-counting. Quotes from different segments are independent. Coverage ratio = `union_chars / segment_char_count`. Flagged when >70%.

Implemented in `quality_metrics.py` as `compute_quote_coverage_per_ic()`, called from `compute_all()`. Display in `quality_report.py` shows overall mean/max, then lists flagged ICs (>70% coverage) or top-5 by max coverage if none flagged. HIL display also shows per-candidate coverage inline: `coverage: 65% (of 300 chars)` with ⚠ flag when >70%.

Note: prompt-level character count instructions deliberately omitted — LLMs do not reliably count characters mid-generation, and constraining extraction length would harm batch processing. Measurement-first: flag outliers, let empirical data calibrate thresholds over time.

### Production Reasoning Log Mode `[resolved]`
The `ReasoningLogger` already supports `mode="failures_only"` — switch it in `pipeline.py` before go-live. In production, logging every call (especially for non-reasoning models that log zeros) is low-value noise. Failures-only mode retains traces for debugging without per-call overhead. Implemented as `reasoning_log_mode` field in `eqd_config.yaml` (`full` / `failures_only`, default `full`), read in `pipeline.py` when constructing `ReasoningLogger`. Also added `reasoning_log_mode: str` to `ProcessingConfig` in `config.py`.

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

*Last updated: 2026-03-02 — Terminal HIL UX: top-K definitions, reasoning truncation+expand, single-step undo (U), session stats in batch header. Layer 4 status updated to [resolved] (AnalystAgent implemented). Custom UI section added [explore] with Textual TUI stepping stone + full custom app design. Remaining design: Segment Faithfulness Scoring, Re-run Detection After Codebook Rejection.*
