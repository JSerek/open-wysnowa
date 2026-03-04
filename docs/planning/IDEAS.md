# Pipeline Ideas Backlog

Ideas that emerged from test runs or design discussions. Each entry has a
status tag:

- `[explore]` — interesting hypothesis, needs design thinking before implementation
- `[ready]` — well-scoped, implementation path is clear, no blockers
- `[in progress]` — actively being worked on
- `[done]` — implemented; kept for reference

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

## Coder Prompt — Top-K Neighbour Exposure `[explore]`

**Origin:** canon-100 analysis discussion (2026-03-04)

**Current state:** The coder agent sees *all* active ICs (100-150) as a flat
name+definition list with no similarity scores. It decides NEW vs EXISTING
by implicit text matching and assigns a "novelty confidence" (0–1) from
reasoning alone. The comparator (downstream) sees top-5 nearest neighbours
*with* similarity scores, but only after the coder has already flagged the
candidate as NEW.

**Idea:** Show the coder its top-3 nearest neighbours with similarity scores
*before* it decides whether a candidate is new. The coder would then have to
explicitly argue against merging rather than defaulting to NEW by failing to
find a match in a list of 100+ definitions.

**Expected effect:**
- Fewer false-new assignments from coder → lower singleton ratio
- Lower comparator workload (fewer candidates escalated to it)
- flip_rate may increase (more coder self-merges) but this is expected and correct

**Risks:**
- Over-suppression: coder becomes too conservative and under-creates
  genuinely new ICs. Testable by comparing IC count and IC diversity
  across runs.
- Implementation requires retrieving top-K embeddings before the coder
  call, which adds one similarity search per candidate.

**Prerequisite:** First test auto_merge_threshold change (0.72→0.65) in
Phase 1.2 run. If singleton ratio improves significantly, this may not be
needed. If it doesn't move, coder prompt change is the next lever.

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
