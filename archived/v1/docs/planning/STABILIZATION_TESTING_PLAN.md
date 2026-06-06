# Stabilization Testing Plan

> After Layer 4 implementation, pause development and run this testing plan.
> Goal: validate the full pipeline end-to-end before starting Codebook Versioning.

---

## Active Model Configuration

**Before running any test, confirm which agent block is active in `eqd_config.yaml`.**

The `agents:` section has three commented/uncommented variants. Only one should be active at a time:

| Block | Coder | Comparator | Synthesizer | When to use |
|-------|-------|------------|-------------|-------------|
| **Gemini (active)** | gemini_flash_lite | gemini_flash_lite | claude-sonnet-4-5 | Default; cheapest; weakest structured output |
| **OpenRouter** | or_fast | or_fast | or_smart | Requires `OPENROUTER_API_KEY` in `.env`; **verify model IDs first** |
| **Anthropic Haiku** | haiku / haiku35 | haiku | sonnet | Reliable structured output; more expensive |

**To switch to a different block:**
1. Comment out the active `agents:` block in `eqd_config.yaml`
2. Uncomment the desired block
3. If switching to OpenRouter: verify `or_fast` / `or_smart` model IDs at https://openrouter.ai/models — the IDs in the YAML (`openai/gpt-5-nano`, `google/gemini-3-flash-preview`) are **unverified placeholders** and may not exist. Fix them before use.
4. If switching to OpenRouter: confirm `OPENROUTER_API_KEY` is set in `.env`

**To check which config is active during a run:** look at the first log lines — the `[CODER]` and `[TRIAGE]` lines will show model responses. OpenRouter requests appear in your OpenRouter dashboard; Google requests appear in Google AI Studio usage.

**Current recommendation for stabilization testing:** Switch to `gemini_flash` (non-lite) or Anthropic Haiku before running Phase 1.2+ runs. Gemini Flash Lite has shown structured output failures on the batch coder prompt (numeric ID leakage, unescaped IC names with spaces).

---

## Canonical Test Dataset

**IMPORTANT:** All stabilization runs use the same canonical dataset — the top 100 most-upvoted negative reviews from `dying_light_beast_negative_full.csv`, sorted by `votes_up` descending. Subsets are nested: 30 ⊂ 50 ⊂ 100 (the first 30 are always the same 30).

Dataset files (pre-generated in `data/`):
- `data/canonical_top30.csv` — top 30 most-upvoted negative reviews
- `data/canonical_top50.csv` — top 50 most-upvoted negative reviews
- `data/canonical_top100.csv` — top 100 most-upvoted negative reviews

Vote range: 943 (highest) to 9 (100th). This ensures runs are comparable — any metric changes are from pipeline behavior, not input variation.

**Random-sample robustness tests come later**, after the pipeline is stable on the canonical set.

---

## Phase 1: Automated Baseline (no HIL)

Establish that the pipeline runs clean at different scales before testing interactive features.

### 1.1 Small run — 30 reviews (regression check)
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv \
  --no-hil --db runs/canon_30.db --save-results runs/results_canon_30.json
```
**Check:**
- [x] Pipeline completes without errors ← **PARTIAL** — ran 2026-03-01, crashed in Layer 3 (see run log below)
- [x] S4 features fire: look for `[DISTINCT]` and `[SPLIT]` log lines ← ✅ fired correctly
- [ ] Layer 4 produces an analytical brief (results["layer4"] is not null) ← not reached (Layer 3 crash)
- [ ] Layer 4 brief prints to terminal (even in no-HIL mode)
- [ ] All 18 metrics computed (check Layer 3 output) ← not reached
- [ ] Thematic structure has categories → themes → ICs → quotes hierarchy
- [ ] **[NEW]** Coder reuse rate block appears in quality report — all four counters present (`coder_new_comp_new`, `coder_new_comp_merge`, `coder_new_comp_reject`, `coder_flagged_match`); none are all-zero for a 30-review run
- [ ] **[NEW]** Coder flip rate note fires if `coder_new_comp_merge / total_coder_new > 0.40` — check whether warning appears
- [ ] **[NEW]** Per-IC coverage block appears in quality report — shows mean/max coverage stats; flags ICs with >70% quote coverage
- [ ] **[NEW]** Reasoning log file is co-located with DB (same directory, not in `runs/runs/`) ← double-path bug fixed in c88eda3, verify

**Run log — 2026-03-01 (model: gemini_flash_lite via Google direct):**
- Layer 0: 30 docs → 30 segments ✅
- Layer 1: 217 ICs, 43 auto-merges, 2/295 candidates dropped (0.7%). 38 ICs refined. ✅
- Layer 1 anomalies:
  - Batch 3 sub-batch 5: coder sent `existing_code_match` as float ordinals (33.0, 46.0…) instead of IC ID strings — all skipped gracefully. **Model structured output failure.**
  - 3 ICs created with spaces in name instead of underscores — caused theme→IC assignment miss and orphan. **Model structured output failure.**
- Layer 2: 24 themes in 1 round. S4 distinctness revision fired (10 pairs → all sharpened). S4 splitting fired: 4 themes split → 28 themes. ✅
- Coherence gate: baseline 0.326, 0 themes flagged. ✅
- Orphan pass: 26 orphans (12%), 18 assigned, 7 isolated, 3 new thin themes. ✅
- Category synthesis: 8 categories. ✅
- **Layer 3 crash:** `AttributeError: 'QualityMetricsEngine' object has no attribute '_persist_metric'` in `compute_coder_confidence()`. **Fixed in commit 00dbe2c — remove the erroneous call.**
- IC refinement silently failing: `NameError` on `result.change_summary` → `refined_parsed.change_summary`. **Fixed in commit c88eda3.**
- Re-run after fix: **pending** — this is the first test to run.

### 1.2 Medium run — 50 reviews
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top50.csv \
  --no-hil --db runs/canon_50.db --save-results runs/results_canon_50.json
```
**Check:**
- [ ] Pipeline completes without errors
- [ ] More ICs discovered than 30-review run (codebook grows)
- [ ] Saturation curve shows progression (ITS decreasing over batches)
- [ ] Merge rate increases across batches (codebook stabilizing)
- [ ] Layer 4 brief identifies any new patterns vs 30-review run
- [ ] No theme has more than 15 ICs (magnet theme check)
- [ ] Category merge threshold: verify no obviously wrong merges (sim < 0.90 should not merge)

### 1.3 Large run — 100 reviews
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top100.csv \
  --no-hil --db runs/canon_100.db --save-results runs/results_canon_100.json
```
**Check:**
- [ ] Pipeline completes without errors or timeouts
- [ ] Saturation reached (ITS < 0.02 for 3 consecutive batches)
- [ ] Codebook size stabilizes (merge rate > 60% in final batches)
- [ ] Coherence gate fires on at least some themes (validates the gate works)
- [ ] S4 distinctness revision: did it merge or sharpen any themes?
- [ ] S4 split heuristic: did any magnet themes get flagged? Split?
- [ ] Layer 4 brief: is the interpretation reasonable and actionable?
- [ ] API costs: note total tokens/cost for budgeting

### 1.4 Cross-run comparison
```bash
.venv/bin/python scripts/compare_runs.py \
  runs/results_canon_30.json runs/results_canon_50.json runs/results_canon_100.json
```
**Check:**
- [ ] Do the same core themes emerge across all three runs?
- [ ] Do metrics improve with more data (higher convergence, lower singleton ratio)?
- [ ] Does Layer 4's assessment change meaningfully across scales?
- [ ] Are there any metrics that degrade with more data (could indicate bugs)?
- [ ] Distinctness: does overlap pair count grow proportionally or explosively?
- [ ] Coverage: does it stay above 90% at all scales?
- [ ] Convergence confidence: does it improve with more data?

### 1.5 Model comparison (optional)
Run the 100-review set with different coder models to isolate model effect on convergence:
```bash
# Edit eqd_config.yaml to switch coder_agent model, then:
.venv/bin/python scripts/run_pipeline.py data/canonical_top100.csv \
  --no-hil --db runs/canon_100_haiku.db --save-results runs/results_canon_100_haiku.json
```
Compare convergence confidence, merge rates, and IC creation rates across models.

---

## Phase 2: HIL Testing (Interactive Mode)

Test every human-in-the-loop checkpoint. Use 30 reviews to keep it manageable.

### 2.1 Layer 1: IC Review Loop
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv \
  --db runs/canon_hil.db
```

**Test each decision type:**
- [ ] **NEW (N):** Accept a new IC — verify it appears in codebook, quote is linked
- [ ] **MERGE (M):** Merge a candidate into existing IC — verify quote count increases
- [ ] **SELECT (S):** Select from multiple matches — verify correct IC gets the quote
- [ ] **REJECT (R):** Reject a candidate — verify it's logged but not in codebook
- [ ] **EDIT (E):** Edit a candidate before accepting — verify edited name/definition persists
- [ ] **QUIT (Q):** Quit mid-batch — verify pipeline handles gracefully

**Test edge cases:**
- [ ] Meta-IC filtering: if a meta-commentary IC is flagged, verify the warning displays and you can accept or reject
- [ ] Saturation checkpoint: if ITS triggers saturation, verify the prompt asks whether to continue
- [ ] Large batch: verify display is readable when 5+ candidates shown at once

### 2.1a New HIL Display and Commands

All commands added since the last plan revision. Run with the canonical_30 dataset in HIL mode.

**Quote block display (visual):**
- [ ] Quote block shows `────` separators above and below the quote line
- [ ] Span appears on its own line: `Span:     [14:210]`
- [ ] Coverage appears on its own line: `Coverage: 65%  (196 of 300 chars)`
- [ ] `⚠ high` flag appears on Coverage line when quote covers >70% of segment
- [ ] Segment ID shown in candidate header: `NEW IC CANDIDATE [1/12]  seg: seg_007`
- [ ] Surrounding context reads cleanly — no numbered list bleed, no newline artifacts

**Context expand `[C]`:**
- [ ] Default menu shows `[C] Expand context (currently: 130 chars)  e.g., C, C 300, C full`
- [ ] `C` alone → re-displays with full segment; ellipsis disappears; label changes to `(currently: full)`
- [ ] `C 300` → re-displays with 300-char window; `[ctx: 300 chars]` label appears on Span line
- [ ] `C full` → alias for bare `C`
- [ ] Invalid input (e.g., `C abc`) → prints usage hint, loops back — no crash
- [ ] Context window resets to 130 for the next candidate

**Top-K definition snippets:**
- [ ] Each top-K entry shows IC name, similarity score, and ≤85-char definition preview
- [ ] Definition longer than 85 chars shows `…` at end
- [ ] Newly created IC appearing in a subsequent top-K → no KeyError, definition entry gracefully absent or shown

**Reasoning truncation and `[?]` expand:**
- [ ] Reasoning longer than ~200 chars is truncated with `…` and `(type ? to expand)` hint
- [ ] Short reasoning (<200 chars) shows in full, no hint
- [ ] `?` → prints full reasoning, then full IC definitions for all top-K entries, then reprints action menu
- [ ] `?` when no top-K entries → only reasoning prints, no error
- [ ] After `?`, all normal commands (N, M, R, E, U, C, Q) still work

**Session stats in batch header:**
- [ ] Batch 1 header: codebook size, ITS (if available), candidate count — no session totals line (first batch)
- [ ] Batch 2+ header: session totals line shows `+N new  ↔ N merged  ✗ N rejected`
- [ ] Totals accumulate correctly across batches (verify against your own decisions)

**Undo `[U]`:**
- [ ] `[U]` not shown on first candidate of session (nothing to undo)
- [ ] `[U]` shown after a decision is made, with description: `UNDO last decision  (NEW: combat_sluggish)`
- [ ] Undo NEW: accept a new IC, then undo → IC absent from codebook, quote absent, `[U]` disappears
- [ ] Undo MERGE: merge a candidate into existing IC, then undo → quote removed, IC quote count decrements, `[U]` disappears
- [ ] Undo REJECT: reject a candidate, then undo → candidate re-presented for decision
- [ ] Double-undo prevented: after one undo, `[U]` is gone for that candidate
- [ ] After undo: current candidate re-displays fully (name, definition, quote block, top-K, reasoning)

**Merge confirmation:**
- [ ] `M1` → shows `→ Merging into: [1] <ic_name>` + `Confirm? [Y/N]:` before applying
- [ ] `N` at confirm → loops back to action prompt; no merge recorded
- [ ] `Y` at confirm → merge proceeds, quote count increases on target IC

### 2.2 Codebook Sign-Off (HIL Level 2)
**Test actions:**
- [ ] **View codebook:** scroll through all ICs, verify names/definitions/quote counts display correctly
- [ ] **Sign off (approve):** pipeline proceeds to Layer 2
- [ ] **Reject (don't sign off):** pipeline stops cleanly, DB state is preserved
- [ ] **Edit an IC:** change name or definition during sign-off, verify change persists
- [ ] **Delete an IC:** remove an IC during sign-off, verify it's deactivated and quotes are unlinked

### 2.3 Layer 2: Theme Review Loop
**Test actions:**
- [ ] **View themes:** all themes displayed with IC lists, coherence scores, distinctness warnings
- [ ] **Sign off (round 1):** accept themes, pipeline proceeds
- [ ] **Provide feedback:** give feedback on specific themes, verify revision happens
- [ ] **View diff:** after revision, verify old vs new theme comparison displays
- [ ] **Sign off (round 2):** accept revised themes
- [ ] **Max rounds:** reach round 3, verify pipeline auto-finalizes with warning

**Test feedback types:**
- [ ] Rename a theme → verify new name in output
- [ ] Request merge of two themes → verify they become one
- [ ] Request split of a theme → verify two themes replace it
- [ ] Flag an IC as misplaced → verify it moves to a different theme (or is noted)

### 2.4 Coherence Gate
- [ ] When a low-coherence theme is flagged, verify the display shows coherence score and IC list
- [ ] **Dissolve:** accept dissolution, verify ICs are redistributed to surviving themes
- [ ] **Keep:** reject dissolution, verify theme survives to final output
- [ ] Verify orphaned ICs (too far from any theme) are reported as unassigned

### 2.5 Layer 4 Brief
- [ ] Verify the analytical brief displays after Layer 3 metrics
- [ ] Read the brief: is the metrics interpretation accurate? (compare to raw numbers)
- [ ] Read the structural diagnostics: does it correctly identify the strongest/weakest themes?
- [ ] Read the recommendations: are config suggestions reasonable?
- [ ] Verify the confidence note mentions sample size limitations

---

## Phase 3: Robustness & Edge Cases

### 3.1 Empty/minimal data
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv \
  --limit 1 --no-hil --db runs/stab_1.db
```
- [ ] Pipeline handles 1 review without crashing
- [ ] Metrics that require 2+ data points return sensible defaults (not division by zero)

### 3.2 Duplicate data
- [ ] Run with a CSV that has duplicate reviews — verify deduplication works or is handled

### 3.3 Resume/re-run
- [ ] Run 30 reviews, then run again with the same DB — verify pipeline detects existing data
- [ ] What happens if you point to an existing DB with --limit 50? Does it crash, skip, or re-process?

### 3.4 Config variations
- [ ] Run with `category_merge_threshold: 0.90` — verify fewer/no category merges
- [ ] Run with `split_min_ics: 5` (lower) — verify more themes flagged for splitting
- [ ] Run with `distinctness_threshold: 0.80` (higher) — verify fewer pairs flagged
- [ ] **[NEW]** Run with `reasoning_log_mode: failures_only` — verify log file is created but only contains entries for failed structured output calls (not every call); compare log line count to `full` mode run on same data
- [ ] **[NEW]** Run with `reasoning_log_mode: full` (default) — verify every Coder and Comparator call writes a reasoning trace; confirm log is co-located with DB file

### 3.5 Save/load results
- [ ] Verify `--save-results` produces valid JSON
- [ ] Verify JSON can be loaded and contains all expected keys
- [ ] Verify Layer 4 brief is in the JSON output

---

## Phase 4: Output Quality Assessment

This is the qualitative part — you reading the output as a researcher.

### 4.1 IC quality
- [ ] Read 10 random IC definitions — are they specific and grounded?
- [ ] Check 5 singleton ICs — are they legitimate phenomena or noise?
- [ ] Check 3 high-quote ICs (5+ quotes) — are all quotes actually about the same thing?
- [ ] **[NEW]** Check confidence distribution in quality report: does mean confidence decrease over batches? (Early batches = sparse codebook = higher novelty confidence; late batches = dense codebook = lower novelty confidence expected)
- [ ] **[NEW]** Pick 3 ICs with high confidence (≥0.85) — are they genuinely distinct, first-of-their-kind concepts?
- [ ] **[NEW]** Pick 3 ICs with low confidence (≤0.5) — were they eventually merged with existing ICs, or accepted as distinct? Low confidence + accepted as NEW is a yellow flag (coder was uncertain but comparator agreed it was new)
- [ ] **[NEW]** Check per-IC coverage report: any ICs with >70% quote coverage? If so, read those ICs — are they legitimately broad (e.g., a general sentiment IC) or do they look like bundled phenomena (Split IC candidate)?

### 4.2 Theme quality
- [ ] Read each theme name + definition — does it accurately capture its ICs?
- [ ] For the lowest-coherence theme: read its ICs — should they be together?
- [ ] For the highest-IC theme: is it a genuine broad theme or a magnet?
- [ ] Check sentiment purity: for any mixed-sentiment theme, is the mix legitimate?

### 4.3 Category quality
- [ ] Do categories form meaningful high-level groupings?
- [ ] Is any category a catch-all (too many diverse themes)?
- [ ] Are any two categories really the same thing? (merge threshold too conservative?)

### 4.4 Layer 4 quality
- [ ] Does the metrics interpretation match your own reading of the numbers?
- [ ] Does the structural assessment identify the same issues you see?
- [ ] Are the recommendations actionable and specific (not generic)?
- [ ] Would you trust this brief enough to act on it without reading raw metrics?

---

## Phase 5: Performance & Cost

### 5.1 Timing
- [ ] Record wall-clock time for 30/50/100 review runs
- [ ] Identify bottleneck: is it Layer 1 (coder), Layer 2 (synthesizer), or Layer 3 (metrics)?
- [ ] Layer 4: how long do the 3 LLM calls take?

### 5.2 API costs
- [ ] Track token usage per layer (check logs for token counts)
- [ ] Estimate cost per review at current model configuration
- [ ] Is Haiku for coder/comparator cost-effective vs quality trade-off?

### 5.3 DB size
- [ ] Check DB file size at 30/50/100 reviews
- [ ] Are embeddings the dominant storage cost? (they will be)

---

## Known Issues from Previous Runs

Issues identified from the random-sample STAB_30/50/100 runs (pre-canonical dataset) and canon_30 run.

| # | Area | Issue | Severity | Status |
|---|------|-------|----------|--------|
| 1 | Layer 2 | Refinement too passive — 0 dissolutions, near-zero merges despite 22-38 overlapping pairs | High | Open |
| 2 | Layer 1 | Low convergence confidence (39-45%) — codebook not stabilizing, excessive new IC creation | High | Open — coder reuse rate diagnostic added (commit 9e3b0b6) to make this observable; root cause unaddressed |
| 3 | Layer 2 | Coherence degrades with scale (0.61→0.50) — no coherence-guided splitting | Medium | **Fixed** — S4 split heuristic implemented |
| 4 | Coverage | 17% unassigned ICs at 100 segments — mix of threshold issues and missing themes | Medium | Open |
| 5 | Layer 1 | IC reuse prompt too weak — coder creates duplicates that merge step cleans up | Medium | Open — diagnostic added (see #2); root cause unaddressed |
| 6 | Model | Gemini Flash Lite too weak for batch coder prompt | Medium | **Confirmed** — canon_30 run showed float-ordinal ID leakage and spaces in IC names. Switch to gemini_flash or Haiku before further runs. |
| 7 | Layer 3 | `compute_coder_confidence()` called non-existent `_persist_metric()` method | High | **Fixed** — commit 00dbe2c (2026-03-01) |
| 8 | Layer 1 | Coder sends `existing_code_match` as float ordinal (e.g. 33.0) instead of IC ID string — silently skipped | Medium | Open — targeted retry added for *missing* segments (commit 9e3b0b6) but float ordinal normalization not yet implemented |
| 9 | Layer 1 | Coder creates IC names with spaces instead of underscores — causes theme assignment miss | Low | Open — `name.replace(" ", "_")` normalization not yet added to IC creation path |
| 10 | Layer 1 | 82.5% singleton ratio in canon_30 — coder over-splits concepts across reviews | High | Open — likely model issue; retest with gemini_flash or Haiku |
| 11 | Layer 1 | IC refinement NameError: `result.change_summary` → `refined_parsed.change_summary` — all IC refinement passes silently failed | High | **Fixed** — commit c88eda3 (2026-03-01) |
| 12 | Pipeline | Reasoning log written to `runs/runs/` (double path) when `--db` points to `runs/foo.db` | Low | **Fixed** — commit c88eda3 (2026-03-01) |

---

## Done Criteria

The stabilization phase is complete when:
1. All Phase 1 automated runs pass without errors on canonical dataset
2. All HIL checkpoints tested at least once (Phase 2)
3. No critical bugs in the bug log
4. Layer 4 brief quality is "good enough to act on" (Phase 4.4)
5. Known issues from previous runs are addressed or have clear next steps
6. You have a clear list of issues/improvements for the next development sprint

---

*Created: 2026-02-23*
*Updated: 2026-02-25 — canonical dataset, known issues table, model comparison phase*
*Updated: 2026-03-01 — Model Configuration section; canon_30 run log (partial); Known Issues #7–10*
*Updated: 2026-03-03 — Added [NEW] checks for: coder reuse rate diagnostic, per-IC coverage metric, reasoning log path. Added Phase 2.1a (all new HIL commands: quote display separators, Span/Coverage lines, ⚠ flag, segment ID, C/C N context expand, top-K definition snippets, ? reasoning expand, session stats, U undo, merge confirmation). Added Phase 3.4 reasoning_log_mode config tests. Added Phase 4.1 novelty confidence quality checks. Known Issues: updated statuses #2/#5/#8; added #11 (IC refinement NameError, fixed) and #12 (double runs/ path, fixed).*
*Use after: Layer 4 implementation complete*
