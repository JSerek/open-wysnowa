# Stabilization Testing Plan

> After Layer 4 implementation, pause development and run this testing plan.
> Goal: validate the full pipeline end-to-end before starting Codebook Versioning.

---

## Phase 1: Automated Baseline (no HIL)

Establish that the pipeline runs clean at different scales before testing interactive features.

### 1.1 Small run — 30 reviews (regression check)
```bash
python scripts/run_pipeline.py dying_light_beast_negative_full.csv \
  --limit 30 --no-hil --db stab_30.db --save-results results_stab_30.json
```
**Check:**
- [ ] Pipeline completes without errors
- [ ] S4 features fire: look for `[DISTINCT]` and `[SPLIT]` log lines
- [ ] Layer 4 produces an analytical brief (results["layer4"] is not null)
- [ ] All 17 metrics computed (check Layer 3 output)
- [ ] Thematic structure has categories → themes → ICs → quotes hierarchy
- [ ] Compare thematic structure to previous 30-review run (test_fix_v1.db) — are results broadly similar?

### 1.2 Medium run — 50 reviews
```bash
python scripts/run_pipeline.py dying_light_beast_negative_full.csv \
  --limit 50 --no-hil --db stab_50.db --save-results results_stab_50.json
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
python scripts/run_pipeline.py dying_light_beast_negative_full.csv \
  --limit 100 --no-hil --db stab_100.db --save-results results_stab_100.json
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
**Check:**
- [ ] Compare results_stab_30.json vs results_stab_50.json vs results_stab_100.json
- [ ] Do the same core themes emerge across all three runs?
- [ ] Do metrics improve with more data (higher convergence, lower singleton ratio)?
- [ ] Does Layer 4's assessment change meaningfully across scales?
- [ ] Are there any metrics that degrade with more data (could indicate bugs)?

---

## Phase 2: HIL Testing (Interactive Mode)

Test every human-in-the-loop checkpoint. Use 30 reviews to keep it manageable.

### 2.1 Layer 1: IC Review Loop
```bash
python scripts/run_pipeline.py dying_light_beast_negative_full.csv \
  --limit 30 --db stab_hil.db
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
python scripts/run_pipeline.py dying_light_beast_negative_full.csv \
  --limit 1 --no-hil --db stab_1.db
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

## Bug/Issue Log

| # | Phase | Description | Severity | Status |
|---|-------|-------------|----------|--------|
| 1 |       |             |          |        |
| 2 |       |             |          |        |

Fill this in as issues surface during testing. Each row becomes a fix or design discussion.

---

## Done Criteria

The stabilization phase is complete when:
1. All Phase 1 automated runs pass without errors
2. All HIL checkpoints tested at least once (Phase 2)
3. No critical bugs in the bug log
4. Layer 4 brief quality is "good enough to act on" (Phase 4.4)
5. You have a clear list of issues/improvements for the next development sprint

---

*Created: 2026-02-23*
*Use after: Layer 4 implementation complete*
