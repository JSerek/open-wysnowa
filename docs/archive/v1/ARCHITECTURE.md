# EQD-AI Architecture — Current State

> Living document. Describes the system **as implemented**, not as planned.
> For future features see `IDEAS.md`. For design philosophy see `DESIGN_PRINCIPLES.md`.
>
> Last updated: 2026-02-27 — reflects commit `d83d50f` (orphan reassessment pass)

---

## 1. What This System Is

EQD-AI is a multi-agent pipeline for **inductive qualitative thematic analysis** of user-generated text (reviews, interviews, survey responses). It operationalises Braun & Clarke (2006) thematic analysis methodology using LLMs at each analytical layer, with human-in-the-loop (HIL) checkpoints at analytically critical decisions.

The system is domain-agnostic by design. It has been validated on Steam game reviews (Dying Light: The Beast), but the methodology, prompts, and pipeline make no assumptions about domain.

**Core insight:** LLMs are good at reading and labelling meaning. They are unreliable as sole decision-makers on analytical questions requiring judgment. The architecture puts LLMs in the labour role (extract, group, label) and humans in the judgment role (approve, dissolve, redirect).

---

## 2. Pipeline Overview

Execution flows top-to-bottom. Each layer builds on the output of the previous.

```
Documents
    │
    ▼
[Layer 0]  Preprocessing
           text normalisation → Segments
    │
    ▼
[Layer 1]  IC Extraction
           Coder Agent (batch) → ICCandidates
           Span Validation (grounding check)
           Codebook Comparator + ITS Tracker → InitialCodes (codebook)
           HIL Level 1: grey-zone decisions
           HIL Level 2: codebook sign-off
    │
    ▼
[Layer 2]  Theme Synthesis
           Synthesizer Agent (round 1) → ThemeProposals
           HIL Level 3: feedback + revision (max 3 rounds)
           ─── Post-synthesis refinement (automated) ───
           [2a] Distinctness Revision Pass
           [2b] Theme Splitting Heuristic (k-means + LLM)
           Persist Themes + ThemeIC junctions
           ─── Post-persistence quality gate ───
           [2.5] Coherence Gate (dissolve incoherent themes)
                 → Embedding-based IC redistribution
           [2.6] Orphan Reassessment Pass (LLM)
    │
    ▼
[Category] Category Synthesis
           CategoryAgent → Categories → CategoryTheme junctions
    │
    ▼
[Layer 3]  Quality Metrics
           16 metrics computed, persisted to DB
    │
    ▼
[Layer 4]  Analyst Intelligence
           3 sequential LLM calls → AnalyticalBrief
           (non-fatal: pipeline completes even if Layer 4 fails)
```

Entry point: `scripts/run_pipeline.py` → `EQDPipeline.run(documents)`

---

## 3. Layer 0: Preprocessing

**File:** `src/preprocessing.py`

Raw `Document` objects are normalised into `Segment` objects. Currently one document = one segment (no chunking). Normalisation applies Unicode cleanup and whitespace standardisation. A SHA-256 `content_hash` is computed on `canonical_text` and stored — this is the immutability anchor for all downstream span references.

**Key design decision:** `canonical_text` is immutable after creation. All verbatim quotes reference it via character-level `span_start`/`span_end`. If the text changes, all spans are invalidated. This is enforced by never re-running preprocessing on a populated DB without overwriting.

---

## 4. Layer 1: IC Extraction

**Files:** `src/orchestrator.py`, `src/coder_agent.py`, `src/codebook_comparator.py`

### 4.1 Batching and Micro-batching

Segments are processed in **batches** (default 10 segments). Within each batch, the Coder Agent processes `segments_per_coder_call` segments per LLM call (default 2). This is the micro-batch: one call returns a `BatchCodingResult` containing `SegmentCodingResult` per segment.

### 4.2 Coder Agent

**Model:** `gemini_flash_lite` (temperature 0.2, max_tokens 4000)

Receives: `canonical_text` of N segments + full codebook context (all active ICs with definitions).

Produces: `ICCandidate` list per segment. Each candidate includes:
- `ic_name`: proposed code name (snake_case)
- `definition`: what this code means
- `quote_text`: exact verbatim substring
- `span_start` / `span_end`: character-level offsets into `canonical_text`
- `confidence`: 0.0–1.0
- `sentiment`: positive / negative / neutral / mixed
- `existing_code_match`: name of an existing IC if this is a match (or null for new)

**Grounding verification** (deterministic, no LLM): `canonical_text[span_start:span_end] == quote_text`. Candidates failing this check are dropped and logged. The drop rate is tracked as a quality metric.

### 4.3 Triage — Embedding Similarity Prefilter

Before calling the Codebook Comparator LLM, each new candidate is embedded and compared against the existing codebook using cosine similarity:

- `max_sim < auto_new_threshold (0.5)` → **auto-NEW**: skip comparator, create IC directly
- `max_sim > auto_merge_threshold (0.72)` → **auto-MERGE**: skip comparator, merge into best match
- Between thresholds → **grey-zone**: send to Comparator LLM for a judgment call

The `similarity_prefilter_k` (default 5) controls how many nearest neighbours are checked. Triage auto-rate (% of decisions that bypass the LLM) is tracked as a quality metric — healthy target is >60%.

### 4.4 Codebook Comparator

**Model:** `gemini_flash_lite` (temperature 0.1, max_tokens 2000)

Grey-zone candidates are evaluated against their `k` nearest neighbours. The Comparator returns a `ComparatorOutput` with one of four recommendations:
- `NEW`: different enough — create a new IC
- `MERGE`: same phenomenon — merge into the named existing IC
- `SUBCODE`: related but distinct — create new IC linked to parent
- `REJECT`: not analytically meaningful — discard

### 4.5 HIL Level 1: Grey-Zone Decisions

When `enable_hil=True`, the analyst can override any Comparator recommendation in real time. Overrides are logged to `decision_logs` with `decision_type=codebook_update`.

### 4.6 ITS Tracker — Saturation Monitoring

The `ITSTracker` in `orchestrator.py` tracks:

**ITS per batch:** `new_ics_created / ics_before`. Saturation is declared when ITS < `its_saturation_threshold (0.02)` for `its_consecutive_batches (3)` consecutive batches.

**Cumulative saturation curve:** For each segment, the tracker records which segment introduced each new IC. After Layer 1 completes, `build_saturation_curve()` produces a `List[SaturationPoint]` — a CDF from 0 → 1 showing codebook discovery over processing order. Layer 3 uses this to report "95% of the codebook was discovered by segment X of Y."

### 4.7 Embed-on-Write

Every new IC is embedded immediately after creation (OpenAI `text-embedding-3-small`). The embedding input is `"{ic.name} | {ic.definition}"`. Embeddings are stored as JSON arrays in `initial_codes.embedding_json`. This design means embeddings are always current and available synchronously for triage — no deferred batch.

### 4.8 HIL Level 2: Codebook Sign-Off

After all segments are processed, the analyst reviews the full codebook before proceeding to theme synthesis. The `CodebookSignoff` module (`src/codebook_signoff.py`) displays all active ICs and prompts for approval. Rejection stops the pipeline.

---

## 5. Layer 2: Theme Synthesis

**Files:** `src/synthesizer_agent.py`, `src/theme_hil.py`

### 5.1 Initial Synthesis (Round 1)

**Model:** `claude_sonnet` (temperature 0.2, max_tokens 16000, extended output beta enabled)

The Synthesizer Agent receives the full codebook (all active ICs with definitions and example quotes) and produces a `SynthesisOutput` containing `List[ThemeProposal]`. Each `ThemeProposal` has a name, definition, rationale, and list of `constituent_ic_names`.

The synthesis prompt encodes Braun & Clarke methodology: cluster by semantic proximity, name the pattern not the content, check distinctness, check coverage. Negative examples are included for common failure modes (mixed-sentiment themes, over-broad category-level groupings).

Each IC is passed with its name, definition, quote count, and **up to 3 example verbatim quotes** (from `_build_codebook_data()` in `synthesizer_agent.py`). This grounds the LLM's clustering in actual evidence rather than just definitions.

### 5.2 HIL Level 3: Iterative Feedback (max 3 rounds)

After each synthesis round, the analyst can:
- Sign off → proceed to refinement
- Provide structured feedback via `ThemeFeedbackOption`: SPLIT, MERGE, IC_MISASSIGNED, RENAME, REDEFINE, OVERLAP_CONFLICT, FREETEXT

Feedback drives a `RevisionOutput` call on the same model. Max 3 rounds enforced.

### 5.3 Post-Synthesis Refinement (automated, always runs)

Both passes run unconditionally after `_run_layer2()` returns, regardless of whether `enable_hil` is on or off. They operate on `List[ThemeProposal]` — the in-memory theme proposals, before any DB writes.

**[2a] Distinctness Revision Pass** (`_run_distinctness_revision`)

Computes pairwise centroid similarities across all theme proposals using IC embeddings. Pairs with similarity > `distinctness_threshold (0.70)` are flagged (max `max_overlap_pairs (10)` pairs). The LLM (`DistinctnessRevisionOutput`) receives the full theme list plus flagged pairs and decides: MERGE (same phenomenon) or SHARPEN (different phenomena, similar vocabulary). Returns the full revised theme list.

**[2b] Theme Splitting Heuristic** (`_run_split_heuristic`)

Detects "magnet themes" — themes that are attracting unrelated ICs — by checking all three conditions simultaneously:
- IC count ≥ `split_min_ics (8)`
- raw coherence < `split_max_coherence (0.50)`
- overlap pair count ≥ `split_min_overlaps (3)`

For each flagged theme: pure-Python k-means (k=2, cosine distance, 3 restarts, max 10 iterations) splits the ICs into two candidate clusters. The LLM (`SplitValidationOutput`) evaluates whether the split is semantically meaningful or a statistical artifact. If approved, the original theme is replaced by the two sub-themes.

### 5.4 Theme Persistence

`synthesizer.persist_themes(themes, round_number)` writes one `Theme` row per proposal (`id`, `name`, `definition`, `rationale`, `round_finalised=round_number`, `created_at`), then one `ThemeIC` junction row per IC in `constituent_ic_names`. IC names are resolved to IDs via a name→ID lookup on the active codebook — names with no matching active IC are skipped with a warning logged.

The `round_finalised` field is the key mechanism preventing multi-round duplication: `ThemeRepo.get_latest_round()` queries `MAX(round_finalised)` and returns only those themes. All downstream code (metrics, export, category synthesis) calls `get_latest_round()`, never raw `SELECT * FROM themes`.

The full analytical output — the Category → Theme → IC → Quote hierarchy — is generated by `export_thematic_structure()` at the end of `run()` and returned in the results dict. It is **not automatically written to a file**; it lives in memory and terminal output. The data to reconstruct it always exists in the DB.

---

## 6. Layer 2.5: Coherence Gate

**File:** `src/pipeline.py` (`_redistribute_orphaned_ics`)

After themes are persisted, the `QualityMetricsEngine` computes normalized coherence per theme. Two thresholds apply:
- Themes with ≥ 5 ICs: flagged if normalized coherence < `coherence_threshold (1.0)`
- Themes with < 5 ICs: flagged if normalized coherence < `coherence_threshold_small (0.90)`

Normalized coherence = `raw_coherence / max_possible_coherence` for that IC count and embedding model.

**With HIL:** Analyst is shown each flagged theme and chooses to dissolve or keep. **Without HIL:** All flagged themes are auto-dissolved.

**Dissolution** (`ThemeRepo.dissolve_theme`): removes all `theme_ics` junction rows. The `themes` row remains (audit trail). ICs become "orphaned" — active but without a theme assignment.

**Embedding-based redistribution** (`_redistribute_orphaned_ics`): For each orphaned IC from a dissolved theme, compute cosine similarity to the centroids of all surviving themes. The algorithm finds the **globally best-matching centroid** across all survivors, then only assigns if that best similarity ≥ `min_similarity (0.5)`. It is not "first above the threshold" — it is "best available, subject to a floor." If the best match is 0.43, the IC remains unassigned for the orphan reassessment pass.

---

## 7. Layer 2.6: Orphan Reassessment Pass

**File:** `src/pipeline.py` (`_run_orphan_reassessment`), `src/synthesizer_agent.py` (`reassess_orphans`)

Runs after the coherence gate. Catches **all** unassigned active ICs — both those whose theme was dissolved and could not be redistributed, and those that were simply never assigned during synthesis.

**Model:** `claude_sonnet` (same as synthesizer, same params)

**Three dispositions per orphan:**

- `assign_existing`: IC genuinely fits a surviving theme. Target theme name required. Executed by direct `ThemeRepo.assign_ic_to_theme()` call.
- `new_theme`: IC should be grouped with other orphans into a new thin theme. The LLM proposes full `ThemeProposal` objects in `OrphanReassessmentOutput.new_themes`. Requires minimum 2 valid orphan ICs — proposals with fewer are rejected and those ICs are isolated instead.
- `isolated`: IC is a genuine one-off. Logged, left unassigned. Analytically honest — not every code becomes a theme.

New thin themes are persisted via `synthesizer.persist_themes()` at `round_finalised=3` (max allowed). The category synthesis that follows sees all themes including new thin ones.

**Key design choice:** Forced assignment is rejected. The prompt explicitly frames isolation as the right answer when no fit exists. This avoids contaminating themes with weakly-related ICs just to hit full coverage.

---

## 8. Category Synthesis

**File:** `src/category_agent.py`

**Model:** `claude_sonnet` (temperature 0.2, max_tokens 16000)

After the final theme set is stable, the CategoryAgent groups themes into 4-8 higher-order categories. Each theme is passed with its name, definition, IC count, IC names, and one example quote per IC.

The LLM returns `CategorySynthesisOutput` → `List[CategoryProposal]`. Each proposal names a category and lists the `constituent_theme_names`. Categories are persisted as `Category` rows with `CategoryTheme` junction rows.

The final export (`export_thematic_structure`) produces a hierarchical structure: **Category → Theme → IC → VerbatimQuote**. Themes not assigned to any category appear under an "Uncategorized" node.

---

## 9. Layer 3: Quality Metrics

**File:** `src/quality_metrics.py` (~1,450 lines)

All metrics are computed after Layer 2 completes. They are **signals for the analyst, not pipeline gates** (except the coherence gate in Layer 2.5, which is a genuine gate). All metrics are persisted to `quality_metrics` table with `metric_type` and optional `entity_id`/`entity_type` for theme-level metrics.

| Metric | What It Measures | Healthy Range |
|---|---|---|
| **Grounding Rate** | % of verbatim quotes verified against source text | ≥ 95% |
| **Candidate Drop Rate** | % of LLM-proposed ICs dropped at span validation | ≤ 15% |
| **Extraction Density** | Mean % of segment text covered by IC quotes | 30–80% |
| **Singleton Ratio** | % of active ICs with only 1 supporting quote | ≤ 30% |
| **Merge Rate (final batches)** | % of candidates merged into existing ICs | 40–80% |
| **Triage Auto Rate** | % of triage decisions made without LLM | ≥ 60% |
| **ITS (final)** | Incremental Type Saturation in last batch | ≤ 5% |
| **Meaning Saturation** | Intra-IC quote diversity (embedding variance) | — |
| **Theme Coherence** | Mean intra-theme IC embedding similarity | ≥ 0.55 |
| **Theme Distinctness** | % of theme pairs with centroid sim > 0.70 | ≤ 25% |
| **IC Concentration** | Quote distribution across ICs (Gini coefficient) | — |
| **Cross-Theme IC Sharing** | % of ICs assigned to 2+ themes | — |
| **Coherence (normalized)** | Coherence adjusted for theme size + embedding model | — |
| **Thematic Coverage** | % of quotes belonging to ICs assigned to themes | ≥ 90% |
| **Cross-Review Convergence** | % of ICs supported by evidence from 2+ documents | ≥ 50% |
| **IC Stability** | Cosine similarity of IC embeddings before/after definition refinement | — |
| **Sentiment Purity** | Dominant-sentiment ratio per theme | ≥ 80% |

Reference ranges for all metrics are configurable in `eqd_config.yaml` under `analyst_guidelines`. These ranges are injected into the Layer 4 prompt so the LLM can contextualize values.

---

## 10. Layer 4: Analyst Intelligence

**File:** `src/analyst_agent.py`

**Model:** `claude_sonnet` (temperature 0.3, max_tokens 16000)

Three sequential LLM calls producing a structured `AnalyticalBrief`:

**Call 1 — Metrics Interpretation (`MetricsInterpretation`):** Receives all computed metrics with their reference ranges. Produces a `MetricAssessment` per metric (status: healthy / monitor / investigate + interpretation in context of this specific run) plus an overall data quality summary and saturation assessment.

**Call 2 — Structural Diagnostics (`StructuralDiagnostics`):** Receives the full thematic structure (categories → themes → ICs with quote counts and coherence scores). Produces a `ThemeDiagnostic` per theme (issue type: magnet_theme / weak_coherence / low_evidence / naming_unclear / sentiment_mixed / healthy) and a `CategoryDiagnostic` per category. Includes strongest/weakest theme lists and a structural summary.

**Call 3 — Synthesis and Recommendations (`AnalystSynthesis`):** Receives outputs of Calls 1 and 2 plus the config state and run summary. Produces integrative findings that only emerge from combining the metric and structural perspectives, plus prioritised config recommendations and next steps.

**Non-fatal design:** Layer 4 is wrapped in a try/except. If any call fails (schema validation exhausted, rate limit, etc.), the pipeline logs the error and continues. Layer 3 metrics and thematic structure are always available regardless of Layer 4 outcome.

---

## 11. Data Model

SQLite database, single file (`eqd_config.yaml` → `db_path`). Schema initialized idempotently via `Database.init_schema()`.

```
documents
  id, source_file, raw_text, metadata, created_at

segments  (1:N from documents)
  id, document_id, canonical_text, original_text,
  char_count, segment_index, normalization_rules,
  content_hash, created_at

initial_codes  (the codebook)
  id, name, definition, embedding_json,
  status (active|deprecated|merged), created_at, updated_at

verbatim_quotes  (N:1 to initial_codes, N:1 to segments)
  id, ic_id, segment_id, quote_text,
  span_start, span_end, is_verified, sentiment,
  quote_embedding_json

themes
  id, name, definition, rationale,
  round_finalised, created_at

theme_ics  (M:N junction: themes ↔ initial_codes)
  theme_id, ic_id, assigned_at

categories
  id, name, definition, created_at

category_themes  (M:N junction: categories ↔ themes)
  category_id, theme_id, assigned_at

decision_logs  (full audit trail)
  id, decision_type, ic_id, llm_recommendation,
  human_action, similarity_score, timestamp, notes, context

quality_metrics  (computed signals, not gates)
  id, metric_type, entity_id, entity_type, value, computed_at
```

**Key relationships:**
- A quote's span references `segments.canonical_text` — immutable after creation
- An IC can belong to many themes (M:N via `theme_ics`) — cross-theme sharing is measured
- Dissolved themes keep their `themes` row but have zero `theme_ics` rows
- `get_latest_round()` filters to `MAX(round_finalised)` — prevents multi-round theme duplication

---

## 12. Infrastructure

### ModelClient (`src/config.py`)

Thin wrapper that reads `eqd_config.yaml` and returns `(instructor_patched_client, model_id, AgentParams)` per agent. Supports four provider types:

- `anthropic`: native Anthropic SDK via `instructor.from_anthropic()`. Extended output beta header (`anthropic-beta: output-128k-2025-02-19`) sent globally for Sonnet calls.
- `openai_compatible`: OpenAI SDK + `instructor.from_openai()`. Covers OpenAI, Google (Gemini), Ollama, LMStudio.
- Google/Gemini specifically: must use `instructor_mode: json` because Gemini's tool-call mode generates multiple calls when Pydantic models contain `List` fields.

Clients are lazy-initialised and cached per provider. Switching providers or models requires only a `eqd_config.yaml` change.

**Current agent assignments:**

| Agent | Model | Rationale |
|---|---|---|
| Coder Agent | `gemini_flash_lite` | High volume, fast, cheap; extraction is well-defined |
| Codebook Comparator | `gemini_flash_lite` | Single-judgment calls, low latency matters |
| Synthesizer Agent | `claude_sonnet` | Requires deep reasoning across many ICs |
| Category Agent | `claude_sonnet` | Requires coherent grouping judgment |
| Analyst Agent | `claude_sonnet` | Interpretive depth needed |
| Embeddings | `text-embedding-3-small` (OpenAI) | Fast, cheap, locked per study |

### EmbeddingService (`src/embeddings.py`)

Wraps the embedding model for three purposes: IC embeddings (on IC creation), quote embeddings (deferred), and similarity computations (cosine distance in pure Python — no numpy dependency). `compute_theme_coherence(ic_ids)` computes mean pairwise cosine similarity across IC embeddings. Embeddings are locked per study (`embedding_model_locked: true` prevents changing mid-study, which would invalidate all stored similarity scores).

### Instructor + Pydantic

All LLM calls use the `instructor` library for structured output. Every agent has a dedicated Pydantic response model (`SegmentCodingResult`, `ComparatorOutput`, `SynthesisOutput`, etc.). Field validators with alias maps handle common LLM deviations (e.g., `"low_coherence"` → `"weak_coherence"` in Layer 4 schema). Char limit fields have explicit budget instructions in prompts to reduce validation retry exhaustion.

### HIL System (`src/hil.py`, `src/theme_hil.py`)

Terminal-based interaction. All HIL is gated behind `enable_hil: bool` so the pipeline can run fully automated (used in testing, batch mode). Three HIL levels:
- Level 1: Grey-zone triage overrides (during Layer 1 batch processing)
- Level 2: Codebook sign-off (between Layer 1 and Layer 2)
- Level 3: Theme feedback + revision (during Layer 2)

---

## 13. Configuration Reference

Key parameters in `eqd_config.yaml`:

```yaml
processing:
  batch_size: 10                        # segments per Layer 1 batch
  segments_per_coder_call: 2           # micro-batch: segments per Coder LLM call
  auto_new_threshold: 0.5              # max_sim below this → skip comparator, create IC
  auto_merge_threshold: 0.72           # max_sim above this → skip comparator, merge IC
  coherence_threshold: 1.0             # normalized coherence gate (themes ≥5 ICs)
  coherence_threshold_small: 0.90      # normalized coherence gate (themes <5 ICs)
  meta_ic_filter:                      # YAML-configurable meta-IC suppression
    name_patterns: []                  # e.g. ["overall_", "_verdict"]
    definition_signals: []             # e.g. ["overall experience"]

theme_refinement:
  distinctness_threshold: 0.70         # centroid sim above this → flag for revision
  split_min_ics: 8                     # minimum ICs to trigger split check
  split_max_coherence: 0.50            # coherence below this → split candidate
  split_min_overlaps: 3                # overlap pairs above this → split candidate
```

---

## 14. Testing

**Directory:** `tests/`

Tests use `pytest` with an in-memory SQLite database (`:memory:`) to avoid filesystem state. The `Database` class handles this transparently — `Database(":memory:")` keeps a single persistent connection (unlike file mode which opens/closes per operation).

Canonical test dataset: **30 Steam reviews** of Dying Light: The Beast (`data/`). Run via `scripts/run_pipeline.py` with `--db runs/canon_30.db`.

---

## 15. Known Design Gaps

Issues identified during architecture review — not blocking, but worth tracking:

**Confidence data evaporates.** `ICCandidate.confidence` (0–1, the coder's self-assessed certainty per extracted code) is collected but never stored on `InitialCode`, never aggregated into a metric, and never used in triage weighting. All confidence signal is discarded after the triage decision. A "mean confidence of accepted new ICs" metric and flagging low-confidence ICs for HIL review would be low-cost improvements.

**SUBCODE is functionally equivalent to MERGE.** `ComparatorRecommendation.SUBCODE` is emitted by the comparator (10 decisions in canon_30 — "zombie_grab_mechanic → grab_mechanic_ruins_game", "repetitive_weapon_repair_loop → weapon_durability_complaint", etc.) and recorded in `decision_logs`. However, `orchestrator.py` has no SUBCODE branch — it falls through and is treated identically to MERGE (candidate folded into parent, no hierarchy built). ICs were never hierarchical. The distinction between "sub-concept of" vs. "same concept as" is real semantically but produces identical pipeline outcomes. Should be deprecated: remove from enum, collapse comparator prompt to NEW / MERGE / REJECT, update comparator agreement metric which currently groups SUBCODE with MERGE anyway.

**Category Agent has no HIL checkpoint.** Unlike theme synthesis (3 rounds, feedback, revision), categories are proposed and automatically validated with no analyst sign-off before persistence. A single confirmation prompt before category DB writes would catch bad automatic merges.

**Category merge produces poor names.** When two categories merge programmatically, the code keeps the longer definition from either original — a heuristic that produces semantically disconnected name+definition pairs. A short LLM rename call post-merge would fix this.

**`thematic_structure` is not written to disk.** The Category → Theme → IC → Quote hierarchy is generated at run-end and returned in the results dict, but never serialised to a JSON file. The DB always contains the data to reconstruct it, but there is no `export_to_json()` utility. A crash after `run()` but before the caller captures results loses the structured export.

**No resume-from-codebook path.** HIL Level 2 rejection stops the pipeline, but the codebook is already in the DB. A `--skip-layer1 --db existing.db` flag in `run_pipeline.py` would let analysts restart at Layer 2 without re-running extraction.

## 16. What Is Not Yet Implemented

The following features are designed but not built. See `IDEAS.md` for full specs:

- **Codebook Versioning** — Discovery / Validation / Evolution modes, ClassifierAgent for locked-codebook runs, longitudinal analytics
- **Layer 5: Interactive Lensing** — Re-synthesize themes from analyst-defined analytical lenses without re-running Layers 0–1
- **Inter-Rater Reliability** — Three-layer reliability measurement (quote overlap → IC alignment → theme convergence) across multiple Discovery runs
- **Segment Faithfulness Scoring** — Per-segment hallucination rate for span accuracy
- **Plugin / IDE Agent Integration** — MCP server wrapping for Claude Code and Anygravity
