# EQD-AI v2 — Project Context for Claude Code

## What this project is (v2)

EQD-AI is a qualitative research pipeline. **As of the v2 pivot (2026-06), the
project focuses exclusively on the evidence-extraction layer** — turning raw text
reviews into a grounded codebook of verbatim quotes (the evidence) + initial codes
(ICs, short abstraction-summaries of each quote), with IC-naming consistency
enforced via embeddings.

Why: the evidence layer has the largest compounding effect on all downstream
exploratory-qual noise, and v1 stacked higher layers on top before this layer was
solid. v2 isolates it and gets it right first.

Active layers on `main`:
- **L0** — preprocessing (normalization + segmentation)
- **L1** — IC extraction + codebook building (coder agent + embedding/LLM comparator triage) + optional HIL codebook sign-off
- **L1 metrics** — reference-free evidence-extraction quality metrics

> **v1 is shelved, not deleted.** The full L0–L4 pipeline (theme synthesis,
> category synthesis, the 18-metric suite, analyst brief) lives in the
> `v1-full-pipeline` git tag and the `archive/full-pipeline` branch. Recover any
> shelved file with `git show v1-full-pipeline:src/<file>`.

For the L1 v2 work, read **`docs/planning/`**:
`L1_v2_evidence_extraction_plan.md` (authoritative 3-phase implementation plan, all
phases done — current state + design contract), `L1_v2_foundation.md` (harvested v1
baseline: data-model contract + empirical learnings), and `IDEAS.md` (active
backlog + Phase-3 follow-ups).

---

## Package layout (v2)

```
src/
  core/            # models, db, config, embeddings, reasoning_log
  preprocessing/   # segmentation.py + grounding.py (re-exported via __init__)
  extraction/      # coder_agent, codebook_comparator, orchestrator,
                   #   codebook_signoff, hil, prompts (L1), pipeline (L0+L1)
  eval/            # l1_metrics.py — L1MetricsEngine
  leaderboard/     # registry, harness, report (Phase 3 model leaderboard)
scripts/
  run_pipeline.py        # CLI: L0 + L1 + L1 metrics
  load_steam_reviews.py  # CSV → Document
  init_db.py
tests/                   # L0–L1 + infra + test_l1_metrics.py
docs/planning/           # L1_v2_evidence_extraction_plan.md, L1_v2_foundation.md, IDEAS.md
archived/v1/             # all v1 full-pipeline artifacts (docs, skills, scripts)
```

Imports use explicit submodule paths (`from src.core.models import InitialCode`,
`from src.extraction.orchestrator import Layer1Orchestrator`), except
`src.preprocessing` which re-exports its submodules (`from src.preprocessing import
preprocess_documents, verify_quote`).

The SQLite schema in `src/core/db.py` is left intact — L2–L4 tables exist but go
unused in v2 (no migration in the pivot).

---

## Active model config

Block: **orSmart** (in `eqd_config.yaml` under `agents:`)

| Agent | Model | Provider |
|-------|-------|----------|
| coder_agent | `google/gemini-3-flash-preview` | OpenRouter |
| codebook_comparator | `google/gemini-3-flash-preview` | OpenRouter |
| embedding | `text-embedding-3-small` | OpenAI |

Requires `OPENROUTER_API_KEY` (+ `OPENAI_API_KEY` for embeddings) in `.env`.
Run with `.venv/bin/python`. (The synthesizer/analyst agent configs remain in the
YAML but are unused in v2.)

---

## L1 triage — single decision track (no thresholds)

Phase 1 removed the threshold-based triage. Every candidate now goes through one
track: embedding `find_similar_ics(top_k)` (ranking only, no cutoff) → LLM judge
returns NEW / MERGE / REJECT. The only shortcut is an empty codebook → NEW without
an LLM call. `auto_new_threshold` / `auto_merge_threshold` /
`merge_conflict_similarity_threshold` and the meta-IC filter are gone (see
`docs/planning/L1_v2_evidence_extraction_plan.md` Phase 1.4 + Appendix C).

(`distinctness_threshold`, `coherence_threshold`, `cat_merge_sim_threshold` were
L2+ concerns and no longer apply on `main`.)

---

## L1 metrics (`src/eval/l1_metrics.py` — `L1MetricsEngine`)

Reference-free signals, never gates:
- **span_integrity** — sanity check: persisted quotes still satisfy `canonical_text[span]==quote_text`; 1.0 expected, < 1.0 = bug (renamed from `grounding`, which was 1.0 by construction)
- **quote_hallucination_rate** + drop classes (`normalized_ws` / `case` / `ellipsis_stitch` / `unmatched`) and **unmatched_quote_rate** — raw, non-circular quote fidelity (hard gate, nothing repaired)
- **judge_failure_rate**, **merge_target_unresolved_rate** — judge reliability; failed judge calls produce no AUC pair
- **ambiguous_occurrence_rate** — accepted quotes whose phrase repeats in the review (span = first free occurrence)
- **extraction_density** — per-segment char coverage via merged span-union
- **candidate_drop_rate** — candidates rejected by 3-tier span validation
- **ic_concentration** — singleton ratio
- **merge_rate**, **triage_efficiency**, **comparator_agreement**
- **coder_confidence**, **quote_coverage_per_ic**, **ITS** (passed in)
- **cross_review_convergence** — judgment-call L1/L2 metric (kept; revisit scope)

Leaderboard runs are tagged `pipeline_version`; `RunRegistry.load_matrix()` shows only
the current version (`v2-p0`) by default. Runs before `v2-p0` are biased (merge to
top-1 in `--no-hil`, judge failures counted as NEW + AUC pairs) — see
`docs/planning/P0_measurement_integrity_design.md`.

---

## Canonical test datasets

Nested subsets of negative *Dying Light: The Beast* reviews, sorted by `votes_up`:
`data/canonical_top{10,30,50,100}.csv` (30 ⊂ 50 ⊂ 100). `*.csv`, `*.db`, `runs/`,
and `linkedin/` are gitignored.

---

## Running

```bash
# Automated L1 extraction + metrics
.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv --db runs/smoke.db --no-hil

# Interactive (HIL codebook sign-off)
.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv

# Tests
.venv/bin/python -m pytest tests/ -v
```

---

## Deferred (live backlog in docs/planning/IDEAS.md)

The headline v2 ideas are now **built**: omitted-text second pass (Phase 2) and the
multi-model leaderboard with threshold-free embedding AUC (Phase 3). What remains
deferred (see `IDEAS.md` Phase-3 follow-ups for detail):

- **Second embedding axis + IC-naming-consistency metric** — only one embedding
  model so far, so the leaderboard can't yet compare embeddings head-to-head.
- **Multi-prompt axis** — vary coder/judge prompts alongside model in the harness.
- **Eval methodology** — exploratory → reference-free for now; no golden dataset
  unless a confirmatory need arises.
