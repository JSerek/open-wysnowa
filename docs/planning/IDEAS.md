# Pipeline Ideas Backlog

Ideas that emerged from test runs or design discussions. Each entry has a
status tag:

- `[explore]` — interesting hypothesis, needs design thinking before implementation
- `[ready]` — well-scoped, implementation path is clear, no blockers
- `[in progress]` — actively being worked on
- `[done]` — implemented; kept for reference

> **v2 note (2026-06-06):** project pivoted to an L0–L1 evidence-extraction focus.
> This file is the active v2 backlog; the authoritative implementation plan is
> `L1_v2_evidence_extraction_plan.md` (all 3 phases done), and the harvested v1
> baseline is `L1_v2_foundation.md`. The **v2 Phase-3 follow-ups** section directly
> below is current; the older entries further down (Singleton Ratio, Comparator
> Prompt, Token Usage) are v1 test-run ideas, kept for reference.

---

## v2 P0 — Measurement Integrity `[done]`

**Origin:** research P0 #1–#3 (`docs/research/2026-09-llm-qda-landscape.md`) +
review notes P0-1…P0-3. Done 2026-09-24, `PIPELINE_VERSION = "v2-p0"`.

Judge failure status + `judge_failure_rate` (failed calls produce no AUC pairs);
`--no-hil` honours the judge's `merge_target_name` (unresolved → NEW +
`merge_target_unresolved_rate`); hard-gate grounding with drop classes
(`normalized_ws` / `case` / `ellipsis_stitch` / `unmatched`) logged per quote;
first-free occurrence for repeated phrases (`ambiguous_occurrence_rate`); hard
`verify()` before any insert; `grounding` → `span_integrity` (sanity check);
version-split leaderboard matrix. **Runs `v2-phase2` and older are biased —
re-run before comparing.** Spec/plan:
`docs/planning/P0_measurement_integrity_{design,plan}.md`.

---

## v2 Phase 3 — Leaderboard Follow-ups

**Origin:** Phase 3 leaderboard implementation (commit `39e47c8`) + the
`canonical_top10` live smoke (2026-06-08, or_smart vs or_fast × embed_openai,
k=1). Tiered by leverage: T1 = trustworthiness of the matrix, T2 = missing
decision axes, T3 = engineering hardening.

### T1 — `embedding_separation_auc` is gen-model-dependent, not a pure embedding score `[explore]`

**Problem:** In the smoke both columns shared one embedding
(`text-embedding-3-small`), yet AUC differed (0.938 gemini-3-flash vs 0.907
gpt-5-nano). The metric pairs the top-1 cosine with the **judge's** verdict, so it
conflates the embedding's separability with the verdicts a given generative model
produces. Comparing AUC *across* gen columns as if it scored the embedding is
wrong.

**Fix:** (a) add a caveat in `src/leaderboard/report.py` that AUC reads
*within-column*, not across gen models; (b) the real unlock is a second embedding
axis (see T2 entry) — only then does AUC compare embeddings as designed.

### T1 — k≥3 repetition run for variance + AUC confidence interval `[ready]`

**Problem:** Smoke was k=1, n=10 → point estimates, no error bars. Seed is
best-effort and temperature > 0, so runs vary; AUC over ~30–50 pairs is noisy.

**Fix:** run the harness with `-k 3` (architecture already threads
`k_repeat_index`; `report.py` already renders mean ± sd). Optionally add a
bootstrap CI to `compute_embedding_separation_auc` in `src/eval/l1_metrics.py` so
small `n_pairs` differences aren't over-read.

### T1 — pass-2 `accidental_omission_ratio` is self-assessed `[explore]`

**Problem:** Strongest discriminator in the smoke (0.37 gemini vs 0.79 gpt-5-nano)
but it measures what the model *says* about its own omissions, not ground truth —
gpt-5-nano may simply over-label "accidental".

**Fix:** explore a cross-model audit of pass-2 (a second model re-judges the
omitted fragments) or a calibration check; meanwhile label the metric
"self-assessed" in the rendered matrix so it isn't read as objective recall.

### T2 — second embedding axis + IC-naming-consistency metric `[explore]`

**Problem:** The embedding axis has only `embed_openai`, so the leaderboard can't
actually compare embeddings — the headline reason AUC exists.

**Fix:** add a second named embedding (e.g. `text-embedding-3-large` or an OSS
model) to `eqd_config.yaml` `models:`; the harness already varies
`agents.embedding.model`. Add an IC-naming-consistency metric (embedding-space
coherence of IC names) as a second embedding-quality column.

### T2 — multi-prompt axis (A/B coder/judge prompts) `[ready]`

**Problem:** The leaderboard varies models but not prompts, yet prompt wording is
a large lever on extraction quality.

**Fix:** the run manifest already carries `coder_prompt_hash` / `judge_prompt_hash`
— add a prompt-variant override to `src/leaderboard/harness.py` +
`scripts/run_leaderboard.py` so the matrix can vary prompt alongside model.

### T3 — hermetic eval-mode integration test `[ready]`

**Problem:** Phase 3 tests use a stub pipeline; only the live (billable) smoke ever
exercised the real `auc_pairs` flow comparator → summary → metrics.

**Fix:** add a `tests/` integration test that runs the real `Layer1Orchestrator`
in `eval_mode=True` with a mocked LLM + embedding, asserting `auc_pairs` are
collected and surface in the metrics. Locks the wiring without API cost.

### T3 — surface sample sizes (`n_pairs`) in the matrix `[ready]`

**Problem:** A reader can't tell how many candidates feed each cell; a metric over
3 pairs and over 300 look identical.

**Fix:** plumb `n_pairs` (already returned by `compute_embedding_separation_auc`)
into the matrix and show it in `src/leaderboard/report.py`, at least for AUC.

### T3 — `runs/` artifact retention policy `[explore]`

**Problem:** Per-run DBs + reasoning logs accumulate in `runs/` (gitignored); at
k=N × many model combos this grows fast.

**Fix:** define a retention/cleanup policy (e.g. keep manifests + metrics in the
registry, prune per-run DBs older than N runs, or a `--keep-run-db` flag).

---

## Singleton Ratio

### Post-refinement embedding re-check `[explore]`

**Origin:** canon-100 analysis discussion (2026-03-04)

**Idea:** After IC refinement (which rewrites IC names and definitions),
re-compute embeddings for all ICs and run a second similarity pass to catch
newly-similar pairs that might now be merge candidates. If merges happen,
run refinement again for the merged ICs.

**Potential value:** Refinement changes the semantic content of IC definitions,
which changes their position in embedding space. Two ICs that were distinct
before refinement might land close together after their definitions are
sharpened. Re-checking could catch these late-emerging duplicates.

**Known complications:**
- Circular dependency: merge → re-embed → merge → re-refine → ...
  Need a fixed-point termination criterion (e.g. max 2 rounds, or stop when
  zero new merges found).
- Adds latency: re-embedding 100+ ICs + N comparator calls per round.
- May introduce instability: late merges change IC coverage counts, which
  could affect Layer 2 theme assignment.

**Suggested path before implementing:**
- First test Saturation mode (which addresses over-creation upstream).
  If singletons fall to ≤ 30% under Saturation, the re-check may be
  unnecessary. If singletons persist, re-check becomes more compelling.
- Design the termination criterion before writing any code.

---

## Comparator Prompt — Threshold Calibration Bug + Top-5 Scored Neighbours `[ready]`

**Origin:** canon-100 analysis discussion (2026-03-04)

### Part A — Bug: comparator LLM guidance thresholds are miscalibrated `[ready]`

**The bug:** The comparator LLM prompt contains hardcoded decision guidance:
```
- Similarity > 0.85: strong merge signal
- Similarity 0.70–0.85: grey zone
- Similarity < 0.70: likely new
```
These thresholds are wrong. The triage system auto-merges candidates with
top-1 similarity > 0.65 and auto-news candidates below 0.55. This means the
comparator LLM is **only ever called for candidates in the 0.55–0.65 range**.
The ">0.85 strong merge" guidance will never apply — those candidates never
reach the comparator. The prompt is describing a decision space the model
cannot be in.

**Fix:** Update the comparator LLM prompt to reflect the actual triage range:
```
- Similarity 0.60–0.65: lean toward merge — concepts are very close;
  merge unless there is a clear, specific distinction
- Similarity 0.55–0.60: genuine grey zone — read definitions carefully;
  merge if the core concept overlaps, new if it extends meaningfully
- (candidates below 0.55 or above 0.65 never reach this prompt)
```
Also update the prompt to note the current `auto_merge_threshold` and
`auto_new_threshold` values so that if config changes, the discrepancy is
visible.

**Files to change:** `src/prompts.py` — `build_comparator_user_prompt()` or
wherever the decision criteria text lives.

---

### Part B — Improvement: inject top-5 scored neighbours into comparator `[ready]`

**Current state of the two agents:**
- **Coder** (extraction pass): sees a segment + the full codebook (all active
  ICs, names + definitions, no scores). Extracts evidence, assigns to existing
  ICs or flags as NEW candidates. This pass is correct as-is — the full
  codebook is needed so the coder can genuinely reuse concepts it has seen.
- **Comparator** (decision pass): receives grey zone NEW candidates from
  triage. Already sees top-5 nearest neighbours with similarity scores.
  However, the guidance around those scores is miscalibrated (see Part A).

**What's missing:** The comparator already has the right information
(top-5 with scores) but its decision guidance doesn't match the actual
similarity range it operates in. The fix in Part A is the main unlock.

**Improvement beyond the bug fix:** Make the top-5 block more prominent and
structured in the comparator prompt. Currently the scores are present but
buried. Reorder the prompt so the scored neighbours appear *before* the
decision question, forcing the model to process them as its primary signal.

**Expected effects:**
- Lower singleton ratio — comparator makes better-calibrated merge decisions
- Higher triage auto-rate — not directly, but fewer grey zone candidates
  re-emerging as singletons after the comparator pass
- flip_rate signal becomes more meaningful once thresholds are honest

**Risks:**
- Over-merging if the 0.55–0.60 guidance is too aggressive. Testable
  immediately in Phase 1.2 run; if IC count drops sharply or thematic
  coverage degrades, loosen the lower bound.

**Files to change:** `src/prompts.py`

**Test plan:** Run Phase 1.2 (canon-50) with this fix applied after the
config changes (auto_merge 0.65, auto_new 0.55). Compare singleton ratio,
flip_rate, and IC count to the canon-100 baseline. If over-merging is
detected, widen the grey zone guidance.

**Prerequisite:** Apply config threshold changes first (done — commit 7a0ef64),
then fix the prompt, then run Phase 1.2.

---

## Token Usage Tracking `[ready]`

**Origin:** canon-100 analysis discussion (2026-03-04)

**Idea:** Capture token usage (prompt_tokens, completion_tokens) from every
LLM API call and aggregate it per layer in the results JSON and quality report.
Required for cost-per-review estimates and model comparison economics.

**Implementation path:**
1. All OpenRouter and Google API responses include a `usage` field.
   Capture it in the agent base class or in each agent's `_call_llm()` method.
2. Aggregate as `token_usage: {layer1: {prompt: N, completion: N}, layer2: {...}, ...}`
   in the results JSON (add to `run_metadata` or as a top-level key).
3. Add a summary line to the quality report:
   `Total tokens: N prompt / N completion (~$0.00N at current model pricing)`
4. The pipeline-test-analysis skill's output_template.md needs a new row in
   Section 1 (Run Configuration) for token usage, and a note in Section 5
   (Layer 3 Metrics Dashboard) or a new section for cost data.

**Notes:**
- Pricing varies by model; store raw token counts, not cost estimates, in
  JSON (cost is derived at report time from config).
- Embedding token counts should also be captured (text-embedding-004 charges
  per token).
- The skill update (output_template.md + metric_reference.md) should happen
  alongside or just after the code change, not separately.

**v2 leaderboard addendum (2026-06-08):** this is now a first-class leaderboard
axis, not just a report line. The Phase-3 smoke showed gemini-3-flash ~6m40s vs
gpt-5-nano ~15m40s on 10 reviews (2.3× slower) — cost/latency weighs as much as
quality in a "which model" decision, and the matrix captures neither today. Plan:
capture per-run **wall-clock latency** + **token usage** (`usage` field on each
OpenRouter/OpenAI response) into the run manifest/`run_metrics`, then add
cost/latency columns to `src/leaderboard/report.py`. The long-format registry
already supports this with no schema change. Touch points: agent `_call_llm`
methods (token capture), `EQDPipeline.run` (wall-clock), `pipeline._flatten_metrics`.

---

*Created: 2026-03-04*
*Last updated: 2026-09-24 — Added "v2 P0 — Measurement Integrity" [done] entry
(judge failure status, merge-target resolution, drop-class diagnostics,
occurrence selection, v2-p0 version split).*
