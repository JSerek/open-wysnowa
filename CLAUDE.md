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

For the harvested L1 knowledge and the deferred v2 plan, read **`docs/v2/`**:
`V2_FOUNDATION.md` (data model, extraction flow, metrics, empirical learnings) and
`V2_ROADMAP.md` (deferred workstreams + eval decision).

---

## Package layout (v2)

```
src/
  core/            # models, db, config, embeddings, reasoning_log
  preprocessing/   # segmentation.py + grounding.py (re-exported via __init__)
  extraction/      # coder_agent, codebook_comparator, orchestrator,
                   #   codebook_signoff, hil, prompts (L1), pipeline (L0+L1)
  eval/            # l1_metrics.py — L1MetricsEngine
  leaderboard/     # placeholder — deferred v2 leaderboard harness
scripts/
  run_pipeline.py        # CLI: L0 + L1 + L1 metrics
  load_steam_reviews.py  # CSV → Document
  init_db.py
  compare_runs.py        # cross-run JSON comparison (reads results JSON)
tests/                   # L0–L1 + infra + test_l1_metrics.py
docs/v2/                 # V2_FOUNDATION.md, V2_ROADMAP.md
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

## L1 thresholds (still in force)

```yaml
processing:
  auto_new_threshold: 0.55     # sim < 0.55 → auto-NEW
  auto_merge_threshold: 0.65   # sim > 0.65 → auto-MERGE
                               # 0.55–0.65 → grey zone → LLM comparator call
```

(`distinctness_threshold`, `coherence_threshold`, `cat_merge_sim_threshold` were
L2+ concerns and no longer apply on `main`.)

---

## L1 metrics (`src/eval/l1_metrics.py` — `L1MetricsEngine`)

Reference-free signals, never gates:
- **grounding** — quotes where `canonical_text[span]==quote_text` (deterministic)
- **extraction_density** — per-segment char coverage via merged span-union
- **candidate_drop_rate** — candidates rejected by 3-tier span validation
- **ic_concentration** — singleton ratio
- **merge_rate**, **triage_efficiency**, **comparator_agreement**
- **coder_confidence**, **quote_coverage_per_ic**, **ITS** (passed in)
- **cross_review_convergence** — judgment-call L1/L2 metric (kept; revisit scope)

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

## Deferred (recorded in docs/v2/V2_ROADMAP.md, not yet built)

- **Omitted-text second pass** — explicit keep/skip + reasoning over the
  un-extracted portion of each review (the headline v2 idea).
- **Multi-model / multi-prompt leaderboard** — rank models/prompts on L1 metrics.
- **Embedding-model comparison + IC-naming-consistency metrics.**
- **Eval methodology** — exploratory → reference-free for now; no golden dataset
  unless a confirmatory need arises.
