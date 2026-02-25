# Codebook Versioning — Full Design Document

> This document captures the complete design for Codebook Versioning, including three analysis modes,
> the ClassifierAgent for Validation mode, inter-rater reliability metrics, and all schema/pipeline changes.
> Written so that implementation can proceed from this spec alone.

---

## 1. Overview

Codebook Versioning transforms EQD-AI from a single-run analysis tool into a multi-run platform.
The analyst can checkpoint a codebook after Discovery, then apply it to new data (Validation),
extend it (Evolution), or re-run Discovery for reliability testing.

---

## 2. Three Analysis Modes

### 2.1 Mode Selection (Pipeline Entry Point)

The analyst selects mode at pipeline start via CLI flag (`--mode discovery|validation|evolution`)
or interactive prompt. The system enforces availability based on DB state.

**Guardrails:**
- DB empty / no checkpoint → only Discovery available
- Checkpoint exists → all three modes available
- CLI flag `--mode validation` with no checkpoint → error with explanation

**Session-start UX (HIL enabled):**
```
┌─────────────────────────────────────────────────────────┐
│ Codebook: 'v1_launch_reviews' (38 ICs, 2026-02-20)     │
│                                                          │
│ Select analysis mode:                                    │
│   [1] Discovery   — fresh codebook, open exploration     │
│   [2] Validation  — classify data against locked codebook│
│   [3] Evolution   — locked codebook + emerging ICs       │
└─────────────────────────────────────────────────────────┘
```

**Session-start UX (no checkpoint):**
```
No codebook checkpoint found. Starting in Discovery mode.
```

### 2.2 Discovery Mode

Current pipeline behaviour — fully open codebook. No changes to existing flow.

**Addition:** After pipeline completion, prompt to save checkpoint:
```
Pipeline complete. Save codebook checkpoint?
  Name: [user enters, e.g. "v1_launch_reviews"]
  Notes: [optional description]
```

**What gets checkpointed:**
- All active ICs (frozen snapshot: id, name, definition, embedding, status)
- All verbatim quotes linked to those ICs
- IC count + timestamp
- The `eqd_config.yaml` settings used for this run (for reproducibility)

### 2.3 Validation Mode (Deductive Coding / Classification)

Codebook is locked. No new ICs. The goal is to classify new data against an existing framework.

**Pipeline simplification — what gets SKIPPED:**
- IC triage (no new ICs to compare)
- Comparator agent (no merge decisions)
- IC refinement (codebook is frozen)
- Codebook sign-off (nothing changed)
- Theme synthesis, category synthesis (optional — analyst decides whether to re-synthesize
  themes from new evidence distribution or keep existing theme structure)

**Pipeline flow in Validation mode:**
```
Layer 0: Preprocessing (unchanged)
    ↓
Layer 1V: Classification (ClassifierAgent replaces Coder+Comparator)
    - For each segment: which existing ICs does it evidence?
    - Output: new verbatim quotes linked to existing ICs
    - Track: coverage ratio, unmatched segments
    ↓
Layer 2V: Theme re-synthesis (optional)
    - If analyst wants: re-run synthesis with updated quote distributions
    - If analyst doesn't: keep existing themes, just update quote counts
    ↓
Layer 3V: Quality metrics + Validation-specific metrics
    - Coverage ratio: % segments with at least one IC match
    - Gap analysis: list of unmatched segments (the interesting ones)
    - Per-IC frequency shift: compare quote counts vs checkpoint
    - Classification confidence distribution
```

### 2.4 Evolution Mode

Core codebook locked, but new ICs can emerge in a separate holding area.

**Pipeline flow in Evolution mode:**
```
Layer 0: Preprocessing (unchanged)
    ↓
Layer 1E: Mixed coding
    - ClassifierAgent runs first (match against existing codebook)
    - Unmatched segments → Coder agent (open extraction, same as Discovery)
    - New candidates go to "emerging" holding area (status: EMERGING)
    - Comparator runs only on emerging ICs (against each other, not locked codebook)
    ↓
Codebook Evolution Sign-Off (HIL):
    "Your codebook had 38 ICs. This run found 5 new candidate ICs.
     For each: Promote to codebook / Dismiss"
    ↓
Layer 2: Theme synthesis (on full codebook: locked + promoted)
    ↓
Layer 3: Quality metrics (unchanged)
```

---

## 3. Schema Changes

### 3.1 New Table: `codebook_versions`

```sql
CREATE TABLE IF NOT EXISTS codebook_versions (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    notes       TEXT,
    ic_count    INTEGER NOT NULL,
    config_snapshot TEXT,          -- JSON dump of eqd_config.yaml at checkpoint time
    created_at  TEXT NOT NULL
);
```

### 3.2 New Table: `codebook_version_ics`

Snapshot of which ICs belong to each version (many-to-many, since ICs can persist across versions).

```sql
CREATE TABLE IF NOT EXISTS codebook_version_ics (
    version_id  TEXT NOT NULL REFERENCES codebook_versions(id),
    ic_id       TEXT NOT NULL REFERENCES initial_codes(id),
    ic_name     TEXT NOT NULL,         -- frozen name at checkpoint time
    ic_definition TEXT NOT NULL,       -- frozen definition at checkpoint time
    PRIMARY KEY (version_id, ic_id)
);
```

### 3.3 Modified Table: `initial_codes`

Add two columns:
```sql
ALTER TABLE initial_codes ADD COLUMN introduced_in_version TEXT REFERENCES codebook_versions(id);
ALTER TABLE initial_codes ADD COLUMN last_seen_version TEXT REFERENCES codebook_versions(id);
```

- `introduced_in_version`: which checkpoint first included this IC (NULL for pre-versioning ICs)
- `last_seen_version`: last checkpoint where this IC had new evidence (for lifecycle tracking)

### 3.4 New Table: `pipeline_runs`

Track each pipeline execution for reliability comparison.

```sql
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          TEXT PRIMARY KEY,
    mode        TEXT NOT NULL CHECK(mode IN ('discovery', 'validation', 'evolution')),
    version_id  TEXT REFERENCES codebook_versions(id),  -- NULL for Discovery
    data_hash   TEXT,                    -- hash of input data (for reliability matching)
    started_at  TEXT NOT NULL,
    completed_at TEXT,
    results_json TEXT,                   -- full results dict
    config_snapshot TEXT                 -- JSON dump of config used
);
```

### 3.5 Modified Table: `verbatim_quotes`

Add column to track which run produced this quote:
```sql
ALTER TABLE verbatim_quotes ADD COLUMN run_id TEXT REFERENCES pipeline_runs(id);
```

---

## 4. ClassifierAgent (Validation Mode)

### 4.1 Design Rationale

The classification task is fundamentally different from extraction:
- **Coder (Discovery):** "Read this segment. What phenomena do you observe?" — open-ended generation
- **Classifier (Validation):** "Which of these N ICs does this segment evidence?" — constrained selection

Different prompt structure, different output schema, different model requirements.

### 4.2 Prompt Structure

**System prompt:**
```
You are a qualitative data classifier. You have a fixed codebook of Initial Codes (ICs).
For each text segment, identify which ICs the segment provides evidence for.

Rules:
1. Only assign ICs where the segment contains clear, direct evidence
2. A segment may match zero, one, or multiple ICs
3. Extract the specific quote (verbatim text span) that evidences each IC
4. Rate your confidence for each assignment (high/medium/low)
5. If no IC fits the segment, return an empty list — do NOT force-fit

Codebook:
{for each IC: name, definition, 2-3 example quotes (positive), 1 near-miss quote (negative)}
```

**User prompt:**
```
Classify this segment:
---
{segment.canonical_text}
---
```

### 4.3 Output Model

```python
class ClassificationCandidate(BaseModel):
    """Single IC assignment for a segment."""
    ic_name: str                           # must match existing codebook IC name
    quote_text: str                        # verbatim span from segment
    span_start: int                        # character offset
    span_end: int                          # character offset
    confidence: Literal["high", "medium", "low"]
    reasoning: str = Field(max_length=200) # brief justification

class SegmentClassificationResult(BaseModel):
    """Classification output for one segment."""
    segment_id: str
    assignments: List[ClassificationCandidate]  # may be empty (gap)
    is_gap: bool = Field(description="True if no ICs matched this segment")
```

### 4.4 Few-Shot Example Generation

After codebook checkpoint, auto-generate per-IC examples from existing data:
- **Positive examples:** Top 2-3 verbatim quotes by confidence/representativeness
- **Negative examples:** Near-miss quotes from comparator REJECT decisions for this IC
  (quotes that looked similar but were assigned to a different IC)
- If no reject examples exist, use quotes from the IC with highest embedding similarity
  (the "confusable" IC)

### 4.5 Model Selection & Escalation

- Default: Haiku (cost-efficient for classification)
- Track confidence per assignment
- If a segment gets all "low" confidence assignments OR is flagged as a gap:
  re-process with Sonnet for the ambiguous cases
- Configurable via `eqd_config.yaml`:
  ```yaml
  classifier_agent:
    model: haiku
    escalation_model: sonnet
    confidence_escalation_threshold: "low"  # escalate if any assignment is this or below
    max_ics_in_prompt: 50                   # for large codebooks: top-N by embedding similarity
  ```

### 4.6 Large Codebook Optimization

For codebooks with 100+ ICs, including all in the prompt is expensive and noisy.
Pre-filter per segment:
1. Embed the segment text
2. Compute cosine similarity to all IC embeddings
3. Include top-K ICs (default K=10) in the classification prompt
4. Always include a "none of the above" option

---

## 5. Inter-Rater Reliability

### 5.1 When It Runs

After 2+ Discovery runs on identical data (same documents, same config).
Triggered by CLI: `python run_pipeline.py --reliability-compare run_id_1 run_id_2 [run_id_3]`

### 5.2 Three-Layer Measurement

**Layer 1: Quote Overlap (Evidence Stability)**

For each segment, compare extracted text spans across runs.

```python
def compute_span_overlap(quote_a: VerbatimQuote, quote_b: VerbatimQuote) -> float:
    """Span overlap ratio: intersection / union of character ranges."""
    if quote_a.segment_id != quote_b.segment_id:
        return 0.0
    start = max(quote_a.span_start, quote_b.span_start)
    end = min(quote_a.span_end, quote_b.span_end)
    intersection = max(0, end - start)
    union = (
        (quote_a.span_end - quote_a.span_start) +
        (quote_b.span_end - quote_b.span_start) -
        intersection
    )
    return intersection / union if union > 0 else 0.0
```

Threshold: ≥0.70 overlap = "same evidence"
Metric: **Evidence Agreement Rate** = matched_quotes / total_unique_quotes

**Layer 2: IC Alignment (Interpretation Stability)**

1. For each pair of runs, build IC alignment via:
   a. Embedding cosine similarity (≥0.85 = "same IC", 0.70-0.84 = "related")
   b. LLM validation for borderline pairs (optional, for accuracy)

2. Build segment × aligned-IC binary matrix per run:
   ```
                 IC_combat  IC_graphics  IC_story  IC_price
   Seg 1 Run A:     1           0           1         0
         Run B:     1           0           1         0     ← full agreement
   Seg 2 Run A:     1           1           0         0
         Run B:     1           0           0         0     ← partial agreement
   ```

3. Compute Krippendorff's alpha on this matrix:
   - Alpha > 0.80 = strong reliability
   - 0.67-0.80 = acceptable
   - < 0.67 = needs investigation

Implementation note: use `krippendorff` Python package or implement from scratch
(it's ~50 lines for binary nominal data).

**Layer 3: Theme Alignment (Structural Stability)**

For aligned ICs, check if they co-occur in similar themes across runs.
Metric: **Thematic Convergence** = proportion of aligned IC pairs that share
theme membership across runs.

### 5.3 Reliability Report Output

```
═══════════════════════════════════════════════════
  Inter-Rater Reliability Report (3 runs)
═══════════════════════════════════════════════════

Layer 1 — Evidence Stability
  Total unique quotes: 142 (across 3 runs)
  Matched quotes (≥70% overlap): 128 (90.1%)
  Unmatched: 14 (9.9%)
  → Evidence Agreement Rate: 0.901

Layer 2 — Coding Agreement
  Aligned ICs: 35 of 38/41/39 (avg match rate: 89%)
  Unaligned ICs per run: 3 / 6 / 4
  Krippendorff's alpha: 0.782 (acceptable)
  Per-IC alpha range: 0.45 — 1.00
  Weakest ICs:
    - "general_disappointment" (α=0.45) ← ambiguous concept
    - "value_for_money" (α=0.52) ← overlaps with multiple ICs

Layer 3 — Thematic Convergence
  Theme overlap score: 0.65
  Stable theme clusters: 4 of 6
  Divergent themes: 2 (different IC groupings across runs)

Summary: Strong evidence extraction (90%), acceptable coding
agreement (α=0.78), moderate thematic convergence (65%).
Recommendation: refine definitions for low-alpha ICs before
proceeding to Validation mode.
═══════════════════════════════════════════════════
```

---

## 6. Longitudinal Analytics (Version Diff Report)

Available after 2+ codebook checkpoints. Compares IC lifecycle across versions.

### 6.1 IC Lifecycle States

- **Confirmed:** present in all versions with evidence
- **Emerging:** new in latest version (introduced_in_version = current)
- **Declining:** quote count decreased >50% vs previous version
- **Deprecated:** no new evidence in latest version (last_seen_version ≠ current)
- **Stable:** quote count within ±20% of previous version

### 6.2 Version Diff Metrics

- IC count delta (net new, deprecated, total)
- Per-IC quote count shift (absolute + %)
- Theme stability: which themes persist, fragment, or emerge
- Coverage trend: does the codebook explain more or less of the data over time?

---

## 7. Implementation Plan (Phased)

### Phase 1: Schema + Discovery Checkpoint (smallest useful increment)
- Add `codebook_versions`, `codebook_version_ics`, `pipeline_runs` tables
- Add `introduced_in_version`, `last_seen_version` to `initial_codes`
- Add `run_id` to `verbatim_quotes`
- Implement checkpoint save after Discovery completion
- CLI: `--save-checkpoint "name"`
- No changes to pipeline flow

### Phase 2: Mode Selection + Validation Mode
- Pipeline entry point: mode selection logic with guardrails
- ClassifierAgent: new agent class, prompts, output models
- Validation pipeline flow (Layer 0 → Layer 1V → metrics)
- Validation-specific metrics: coverage, gaps, frequency shifts
- Config: `classifier_agent` section in YAML

### Phase 3: Evolution Mode
- Mixed coding flow (ClassifierAgent first, then Coder for gaps)
- "Emerging" IC status + holding area
- Evolution sign-off HIL
- Promote/dismiss workflow

### Phase 4: Inter-Rater Reliability
- Quote overlap computation
- IC alignment (embedding + optional LLM validation)
- Krippendorff's alpha implementation
- Thematic convergence metric
- Reliability report display
- CLI: `--reliability-compare run1 run2 [run3]`

### Phase 5: Longitudinal Analytics
- Version diff report
- IC lifecycle classification
- Theme stability tracking
- Coverage trend analysis

---

## 8. Files to Create/Modify

### New Files
- `src/classifier_agent.py` — ClassifierAgent class
- `src/reliability.py` — inter-rater reliability computation
- `src/version_diff.py` — longitudinal analytics
- `tests/test_classifier_agent.py`
- `tests/test_reliability.py`
- `tests/test_codebook_versioning.py`

### Modified Files
- `src/db.py` — new tables, new repos (CodebookVersionRepo, PipelineRunRepo)
- `src/models.py` — ClassificationCandidate, SegmentClassificationResult,
  CodebookVersion, PipelineRun, ICLifecycleState
- `src/pipeline.py` — mode selection, conditional flow, checkpoint logic
- `src/config.py` — ClassifierAgentConfig, add to EQDConfig
- `eqd_config.yaml` — classifier_agent section
- `scripts/run_pipeline.py` — CLI flags: --mode, --save-checkpoint, --reliability-compare

---

*Document version: 1.0 — 2026-02-23*
*Based on discussions in sessions: codebook versioning UX, classification agent,
inter-rater reliability metrics, knowledge graph assessment*
