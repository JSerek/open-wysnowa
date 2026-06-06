# V2 Roadmap — Evidence-Extraction Focus

> Status: **recorded, not ordered.** This file captures the deferred v2
> workstreams and decisions so they aren't lost. Build order and detailed design
> are an explicit later discussion — nothing here is committed to a sequence yet.
> See `V2_FOUNDATION.md` for the harvested L1 baseline this builds on.

---

## Scope of v2

v2 works on **L1 only**: verbatim quote extraction (the evidence base) and IC
naming (short abstraction-summary of each quote), with IC-naming consistency via
embeddings. Higher layers are shelved (`v1-full-pipeline` tag).

Priority ordering of *concerns* (user-stated):
1. **Evidence extraction** (quote quality) — highest leverage.
2. **IC naming** (consistent abstraction) — secondary, but still core.

---

## Deferred workstreams (no sequence assigned)

### A. Omitted-text second pass — *the headline idea*
Make the un-extracted portion of each review **explicit**. After the first
extraction pass, compute the complement of the captured spans (the omitted text),
re-feed the review to the LLM with omitted regions highlighted, and require an
explicit **keep / skip** decision per omitted region **with reasoning**. Persist
the decision + reasoning either way.

- Why: today we cannot distinguish "deliberately skipped (no evidence)" from
  "lost-in-the-middle (model bias)". This closes that gap and turns omission into
  a recorded, auditable decision.
- Net-new: `extraction_density` computes covered chars via span-union but never
  surfaces the *complement*. The omitted-span computation is the foundation here.
- Open design questions (later): granularity of omitted regions (sentence vs
  char-run), prompt design, how the second-pass keep/skip feeds the metrics, cost.

### B. Multi-model / multi-prompt leaderboard
A harness to run L1 over the canonical datasets across several models and prompt
variants, then rank them on the L1 metrics (`src/eval/l1_metrics.py`).

- Likely the **container** the other workstreams plug into, not a standalone
  feature.
- Net-new scaffolding required: per-run metadata (model id, prompt variant,
  embedding model, dataset) — v1's `compare_runs.py` (now in
  `archived/v1/scripts/`) reads JSON only and tracks no such metadata.
- Home reserved at `src/leaderboard/` (placeholder package on `main`).

### C. Embedding-model comparison + IC-naming-consistency metrics
v1 tested only `text-embedding-3-small`. Embedding swap is already pure-YAML
(`eqd_config.yaml` → `agents.embedding.model`), but nothing records which embedding
model produced a run, and there's no metric for IC-naming consistency quality.

- Add: per-run embedding-model tracking + new consistency metric(s) (e.g.
  duplicate-collapse rate, naming stability across runs), then compare embedding
  models head-to-head.

---

## Deferred decisions

- **Eval methodology / gold standard.** For *exploratory* analysis a
  human-annotated golden dataset is likely unnecessary; v2 starts **reference-free**
  (grounding, density, drop-rate, omitted-recovery, consistency). Revisit annotation
  only if a confirmatory need arises. **Do not build eval infra in the restructure.**
- **Leaderboard architecture** (storage schema, ranking, UI) — design later.
- **Build order** of A/B/C — decide once `main` is clean and the harvested L1
  foundation is in front of us.

---

## Out of scope for v2 (shelved in v1)

L2 theme synthesis (+ S4 gates), category synthesis, L3 full 18-metric suite,
L4 analyst brief, codebook versioning. All recoverable from `v1-full-pipeline`.
