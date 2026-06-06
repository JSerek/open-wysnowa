# Pipeline Ideas Backlog

Ideas that emerged from test runs or design discussions. Each entry has a
status tag:

- `[explore]` — interesting hypothesis, needs design thinking before implementation
- `[ready]` — well-scoped, implementation path is clear, no blockers
- `[in progress]` — actively being worked on
- `[done]` — implemented; kept for reference

> **v2 note (2026-06-06):** project pivoted to an L0–L1 evidence-extraction focus.
> Active v2 backlog lives in `docs/v2/V2_ROADMAP.md`; harvested L1 baseline in
> `docs/v2/V2_FOUNDATION.md`. Entries below are v1 test-run ideas, kept for reference.

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

---

*Created: 2026-03-04*
