# V2 Foundation — Harvested L1 Evidence-Extraction Knowledge

> **Purpose.** This document consolidates everything learned about the L1
> evidence-extraction layer during v1, so v2 starts from accumulated knowledge
> rather than a blank slate. The full v1 pipeline (L0–L4) is preserved in the
> `v1-full-pipeline` git tag and the `archive/full-pipeline` branch.
>
> v2 focus: **verbatim quote extraction** (the evidence base) + **IC naming** (a
> short abstraction-summary of each quote), with IC-naming consistency enforced
> via embeddings. Everything above L1 is shelved.

---

## 1. Why the pivot

The basic evidence layer has the largest compounding effect on all downstream
exploratory-qual noise. In v1 it was never improved to a "green light" quality bar
before higher layers were stacked on top. v2 stops, isolates L1, and gets it right.

Concrete trigger: `extraction_density` tells us *how much* of a review was captured
as evidence, but **not** whether the un-captured remainder was deliberately skipped
(no real evidence) or lost-in-the-middle (model bias). v1 has no explicit LLM
decision about the omitted portion. Making that decision explicit is a headline v2
workstream (see `V2_ROADMAP.md`).

---

## 2. Data model (the evidence contract)

From `src/models.py`. These are the load-bearing types for L1; they carry over to
v2 largely intact.

- **`Segment`** — preprocessed unit of analysis.
  - `canonical_text` is **IMMUTABLE** after creation; every span references it.
  - `content_hash` = SHA-256 of `canonical_text`; `verify_integrity()` checks it.
  - `original_text` retained pre-normalization; `char_count`, `segment_index`.
- **`VerbatimQuote`** — exact substring of `canonical_text` with a char-level span.
  - Ground-truth check (no LLM): `canonical_text[span_start:span_end] == quote_text`
    via `verify(canonical_text)` → sets `is_verified`.
  - `span_end > span_start` enforced by validator. Optional `sentiment`,
    `quote_embedding_json`.
- **`InitialCode` (IC)** — codebook entry / lowest analytical unit.
  - `name` (1–120 chars), `definition` (5–600 chars), `status` (active/…),
    `confidence` (coder's *novelty* confidence 0–1 at creation, then frozen).
  - **Embed-on-write**: `embedding_input_text()` returns `f"{name} | {definition}"`
    — this is the text used for all IC similarity/consistency work.

The chain: `Document → Segment → VerbatimQuote → InitialCode`. Quotes are the
immutable evidence; ICs are the abstraction over them.

---

## 3. Extraction flow (L0 → L1)

```
preprocess (L0)        coder (L1)              triage (L1)
Document ──► Segment ──► ICCandidate[] ──► CodebookComparator ──► InitialCode + VerbatimQuote
            (immutable)  (per batch)         (embedding + LLM)      (codebook)
```

- **L0 preprocessing** (`src/preprocessing.py`): NFKC normalization, whitespace
  collapse, zero-width strip. **No** lowercasing, **no** punctuation removal
  (case/punctuation preserved so spans match exactly). 1:1 Document→Segment today
  (splitting is a future hook). `content_hash` for integrity.
- **Coder agent** (`src/coder_agent.py`): per-batch LLM call (`instructor`,
  structured output) → IC candidates with `ic_name`, `definition`, `quote_text`,
  `span_start/end`, `confidence`, optional `sentiment`, optional
  `existing_code_match`.
- **3-tier span validation** (in coder agent, helper in `src/grounding.py`):
  1. **strict** — `canonical_text[start:end] == quote_text`;
  2. **realign** — find `quote_text` elsewhere in the segment, correct offsets;
  3. **fuzzy** — strip punctuation/whitespace or trim boundaries, accept a
     substantial (≥10 char) substring. Candidates failing all three are dropped
     (tracked as `candidate_drop_rate`).
- **Embedding triage** (`src/codebook_comparator.py`): embed candidate as
  `name | definition`; find top-K similar active ICs by cosine; then
  - `max_sim < auto_new_threshold (0.55)` → **auto-NEW** (no LLM);
  - `max_sim > auto_merge_threshold (0.65)` → **auto-MERGE** to top-1 (no LLM);
  - `0.55 ≤ max_sim ≤ 0.65` → **grey zone** → LLM comparator call returns
    NEW / MERGE / REJECT + reasoning.
- **IC-naming consistency** is currently *emergent* from the `name | definition`
  embedding + triage thresholds. v2 makes this a first-class, measured concern
  (and compares embedding models).

> ⚠️ Thresholds as of 2026-03-04: `auto_new=0.55`, `auto_merge=0.65`,
> `distinctness=0.80`, `coherence=0.5×baseline`, `cat_merge=0.90`. (Distinctness /
> coherence / cat_merge are L2+ and shelved in v2.)

---

## 4. L1 metrics (what v2 keeps and measures)

In v1 these live inside `src/quality_metrics.py` (mixed with L2–L4). v2 extracts
them into `src/eval/l1_metrics.py`. Reference-free unless noted.

| Metric | v1 method | What it measures |
|---|---|---|
| Grounding | `compute_grounding` | fraction of quotes where `canonical_text[span]==quote_text` (deterministic) |
| Extraction density | `compute_extraction_density` (+`_merge_spans`) | per-segment `covered_chars / char_count` via merged span-union; distribution + flags |
| Candidate drop rate | (in density) | candidates rejected by all 3 span tiers — coder hallucination signal |
| Coder confidence | `compute_coder_confidence` | mean/SD/quartiles of new-IC novelty confidence |
| IC concentration | `compute_ic_concentration` | singleton ratio (ICs with one quote) — unconfirmed-IC signal |
| Merge rate | `compute_merge_rate` | per-batch merge/candidate ratio — codebook maturity |
| Triage efficiency | `compute_triage_efficiency` | (auto_new+auto_merge)/total — threshold tuning quality |
| Comparator agreement | `compute_comparator_agreement` | LLM vs embedding direction agreement in grey zone |
| Quote coverage per IC | `compute_quote_coverage_per_ic` (+`_interval_union`) | per-IC per-segment coverage |
| ITS | passed via `its_history`/`BatchITS` | incremental type saturation curve across batches |
| Cross-review convergence* | `compute_cross_review_convergence` | *judgment call* — ICs with evidence from ≥2 documents |

\* `cross_review_convergence` straddles L1/L2 (it's about evidence-source
diversity). **Confirm with user** whether it belongs in the v2 L1 set.

**Shelved (L2+) metrics** (stay with the archived file): meaning_saturation_v2,
theme_coherence, theme_distinctness, coherence_normalized, cross_theme_ic_sharing,
ic_stability, orphaned_ic_count, thematic_coverage, sentiment_purity.

Storage in v1: single floats → `quality_metrics` SQLite table (`QualityMetricRepo`)
+ full breakdowns in `runs/results_*.json`. v2 will (later) add per-run
model/prompt/embedding metadata for the leaderboard — see `V2_ROADMAP.md`.

---

## 5. Empirical learnings from v1 stabilization runs

Canonical nested datasets (negative *Dying Light: The Beast* reviews, sorted by
`votes_up` desc): `canonical_top{10,30,50,100}.csv` — 30 ⊂ 50 ⊂ 100.

Distilled from `archived/v1/docs/testing/TEST_RUN_SUMMARY_*` and
`archived/v1/docs/planning/STABILIZATION_TESTING_PLAN.md`:

- **Saturation reached** by N=100 (ITS_final 0.029 🟢); N=50 still unsaturated
  (0.154 🔴). Evidence base grows then plateaus as expected.
- **Comparator↔embedding agreement declines with scale**: N=30 ≈79% → N=50 ≈62%
  → N=100 ≈56%. Watch in v2 (more candidates ⇒ denser similarity space ⇒ more
  genuine grey-zone disagreement). v1 action threshold was <50%.
- **Coherence gate inactive at small N** (relative 0.5×baseline floor never fires)
  — an L2 issue, but a reminder that *relative* thresholds can silently no-op.
- **Threshold recalibration (2026-03-04)** moved auto_new 0.50→0.55, auto_merge
  0.72→0.65, distinctness 0.70→0.80 to widen/retune the grey zone.

See the v1 tag for the full run summaries and the original
`STABILIZATION_TESTING_PLAN.md`.

---

## 6. What carries over vs what's shelved

**Carries to v2 `main` (L0–L1 + infra):** `preprocessing.py`, `grounding.py`,
`coder_agent.py`, `codebook_comparator.py`, `orchestrator.py`,
`codebook_signoff.py`, `hil.py`, `models.py`, `db.py`, `config.py`,
`embeddings.py`, `reasoning_log.py`, the L1 subset of `prompts.py`, and the L1
metrics extracted to `src/eval/l1_metrics.py`.

**Shelved in `v1-full-pipeline` (L2–L4):** `synthesizer_agent.py`, `theme_hil.py`,
`category_agent.py`, `analyst_agent.py`, the L2–L4 remainder of
`quality_metrics.py`, `quality_report.py` (L3/L4 parts), the L2–L4 prompts, and
the full L0–L4 `pipeline.py`.

> To recover any shelved file: `git show v1-full-pipeline:src/<file>` or check out
> `archive/full-pipeline`.
