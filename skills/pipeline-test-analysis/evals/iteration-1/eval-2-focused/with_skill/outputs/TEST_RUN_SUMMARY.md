# Test Run Summary: orSmart · canon30 · 2026-03-03

**Overall status**: FAIL — Critical database integrity bug detected (ghost theme with 0 ICs); singleton ratio elevated at 40% reflecting model-specific IC fragmentation; ITS trajectory healthy but codebook immature for N=30

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | 2026-03-03 |
| **Dataset** | `data/canonical_top30.csv` — Top 30 most-upvoted negative reviews of Dying Light 2 (votes_up: 943–175) |
| **Flags** | `.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv --no-hil --db runs/orSmart_canon_30.db --save-results runs/results_orSmart_canon_30.json` |
| **Raw output** | `runs/raw_outputs/raw_output_test_03_03_orSmart_canon_30.ini` |
| **DB** | `runs/orSmart_canon_30.db` |
| **Results JSON** | `runs/results_orSmart_canon_30.json` |
| **Reasoning log** | `runs/dying_light_beast_test_20260303_164934_reasoning.jsonl` (full mode) |

### Models

| Agent | Model string | Provider | Reasoning |
|-------|-------------|----------|-----------|
| `coder_agent` | `google/gemini-3-flash-preview` | OpenRouter (`or_smart`) | `reasoning_effort: low` |
| `codebook_comparator` | `google/gemini-3-flash-preview` | OpenRouter (`or_smart`) | `reasoning_effort: low` |
| `synthesizer_agent` | `google/gemini-3-flash-preview` | OpenRouter (`or_smart`) | No reasoning_effort override (uses model default) |
| `category_agent` | `google/gemini-3-flash-preview` | OpenRouter (`or_smart`) | No reasoning_effort override |
| `analyst_agent` | `google/gemini-3-flash-preview` | OpenRouter (`or_smart`) | No reasoning_effort override |
| `embedding` | `text-embedding-3-small` | OpenAI | — |

---

## 2. Pipeline Execution Summary

All four layers completed without Python exceptions or timeouts. Layer 0 ingested 30 documents into 30 segments. Layer 1 extracted and refined 50 ICs across 3 batches with 17 merges and 0 drops. Layer 2 synthesized 7 themes in 1 round (with coherence gate dissolving 1 low-coherence theme and redistributing 6 orphaned ICs). Layer 3 computed all major metrics. Layer 4 produced a thematic brief with category diagnostics. No integrity checks failed at the completion-status level, but database structural anomalies were found during detailed validation (see Section 9, Bug #1).

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ | 30 docs → 30 segments, 100% success rate |
| L1 Extraction | ✅ | 50 ICs, 17 merges, 0 drops; IC refinement 60% (30/50 refined per JSON; see anomaly #2) |
| L2 Synthesis | ⚠️ | 7 themes final; 1 theme dissolved by coherence gate; database contains ghost theme (0 ICs) — Bug #1 |
| L3 Metrics | ✅ | All metrics computed; quote coverage scale correct (0.096 = 9.6%, reasonable) |
| L4 Analysis | ✅ | Brief generated with theme/category diagnostics and metric interpretations |

---

## 3. Layer 1 — Extraction and Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | 50 | All newly created; none pre-existing in empty-start run |
| Singletons | 20 (40%) | 🟡 vs ≤ 30% target — at N=30 expected 35–45%, so within normal range but toward high end |
| Merges | 17 | Overall merge rate 25.4% across all batches |
| Drops | 0 | Perfect extraction validation — 0 of 128 candidates dropped |
| ICs refined | 30/50 (60%) | 🟡 **ANOMALY — see Bug #2** — should be 100% per metric_reference.md; 20 ICs never refined |

### Per-batch merge rates and ITS

| Batch | Segments | Merge rate | ITS | Interpretation |
|-------|----------|-----------|-----|----------------|
| 1 | 10 | 31.1% | N/A | Strong early codebook formation; 14 of 45 coder-new proposals merged |
| 2 | 10 | 16.7% | N/A | Declining merge rate — codebook stabilizing; 2 of 12 merged |
| 3 | 10 | 10.0% | 0.10 | Further decline; 1 of 10 merged; 10% of Batch 3 new (1 of 10 ICs) |

**ITS trajectory**: Declining from Batch 1 → Batch 3 (descending from saturated codebook formation to late-batch plateau). Final ITS = 0.10 (18% of final codebook emerged in last batch). At N=30, this is normal and expected; codebook is still actively growing but trajectory is healthy (declining per batch).

### Coder reuse and stability

| Metric | Value | Status |
|--------|-------|--------|
| flagged_match | 61 | Coder proposed 50 new + 61 existing matches = 111 total decisions |
| flip_rate | Not directly computed; coder_new_comp_merge / total_coder_new = 17/50 = 34% | 🟢 Below 40% threshold — coder and comparator broadly agree on NEW vs MERGE |

**Coder reuse analysis:** Flagged_match count of 61 indicates the coder is successfully identifying similar existing ICs. The merge rate of 34% (17 merged of 50 new) suggests the comparator is being slightly more conservative than the coder, but the agreement level is healthy.

### Confidence distribution

| Metric | Value |
|--------|-------|
| mean | 0.872 |
| SD | 0.0809 |
| Q1 | 0.90 |
| Q2 (median) | 0.90 |
| Q3 | 0.90 |

**Interpretation:** 🟡 Heavily clustered at Q1=Q2=Q3=0.90 with a tight SD of 0.081. The distribution is suspicious — 49 of 50 ICs have confidence 0.7–0.9, with 1 outlier at 0.4. This suggests the model is not discriminating meaningfully between high and low novelty. The clustering at 0.9 across Q1–Q3 indicates the model may be defaulting to near-certain confidence rather than expressing genuine uncertainty about IC distinctiveness. This is not a failure, but a yellow flag for model calibration.

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

Synthesizer proposed 7 initial themes from the 50 ICs. S4 distinctness gate (threshold 0.70 centroid similarity) flagged 11 overlapping pairs but **did not merge any themes** — the gate fired but made no changes. S4 split heuristic (triggered when raw coherence < 0.50 AND overlap_pairs ≥ 3) did not split any themes. Coherence gate (threshold 1.0 normalised, applied after refinement) flagged 1 theme for low coherence, dissolved it, and triggered orphan reassessment: 6 ICs were redistributed, 0 left unassigned. Final count: 7 functional themes (excluding dissolved theme).

**Theme evolution diagram:**

```
Synthesizer → 7 themes
  ↓ [S4 distinctness check] → No merges, no splits (gate fired but inactive)
  ↓ [S4 split heuristic] → No splits triggered
  ↓ [Coherence gate @ 1.0] → 1 dissolved, 6 ICs redistributed
  ↓ [Orphan reassessment] → 6 ICs moved to existing themes, 0 unassigned
  → 7 functional themes (plus 1 ghost theme in DB with 0 ICs)
```

### Final themes

| # | Theme | IC count | Coherence | Status |
|---|-------|----------|-----------|--------|
| 1 | Combat Balance and Mechanical Frustrations | 10 | 0.501 | 🟡 |
| 2 | Traversal and World Navigation | 9 | 0.478 | 🟡 |
| 3 | Narrative Depth and Pacing | 8 | 0.487 | 🟡 |
| 4 | Gameplay Loop and Resource Management | 7 | 0.484 | 🟡 |
| 5 | Value and Series Standing | 6 | 0.457 | 🔴 Lowest coherence |
| 6 | Character Growth and Power Limitations | 5 | 0.497 | 🟡 |
| 7 | Visceral Combat and Gore Systems | 5 | 0.484 | 🟡 |
| 8 | Technical Execution and Presentation | 0 | N/A | ❌ **GHOST THEME** |

**Mean coherence**: 0.484 (🟡 vs ≥ 0.55 guideline). At N=30 with broad ICs, coherence below guideline is expected and documented in metric_reference.md as "often lower because ICs are broad." The value is concerning but not alarming for this sample size.

**Distinctness**: 11 of 21 theme pairs (52.4%) exceed 0.70 similarity threshold. 🔴 Well above the ≤25% guideline. High overlap indicates themes are not crisply separated — some themes cover very similar conceptual territory (e.g., Traversal/Navigation ↔ Gameplay Loop: 0.811 similarity; Narrative ↔ Gameplay Loop: 0.837). At N=30, some overlap is expected, but this level warrants investigation in a larger run.

### Categories

```
Mechanical Critique (Combat Balance and Mechanical Frustrations, Gameplay Loop and Resource Management)
Environmental and Progression Dissatisfaction (Traversal and World Navigation, Value and Series Standing, Character Growth and Power Limitations)
Narrative and Presentation Experience (Narrative Depth and Pacing, Visceral Combat and Gore Systems)
```

**Assessment**: Three categories. Groupings are defensible at a high level (mechanics, progression/world, narrative/presentation), though the first two categories have some boundary ambiguity. Categories are intellectually coherent but could benefit from clearer separation in a larger corpus.

---

## 5. Layer 3 — Metrics Dashboard

### Evidence quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| grounding_rate | 1.0 | ≥ 0.95 | 🟢 Perfect |
| drop_rate | 0.0 | ≤ 0.10 | 🟢 Perfect |
| extraction_density_mean | 0.408 | 0.30–0.80 | 🟢 Healthy |
| thematic_coverage | 1.0 | ≥ 0.90 | 🟢 100% quotes in themes |
| sentiment_purity_mean | 0.937 | ≥ 0.85 | 🟢 Excellent |
| cross_review_convergence | 0.60 (confirmed: 2+ docs/IC) | ≥ 0.60 | 🟢 At threshold |

### Codebook maturity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| singleton_ratio | 0.40 | ≤ 0.30 | 🟡 Elevated |
| merge_rate_final | 0.254 | 0.40–0.80 | 🟡 Below guideline (expected at N=30) |
| triage_auto_rate | 0.258 | ≥ 0.60 | 🔴 Low; 25.8% auto-decided, 74.2% required LLM |
| its_final | 0.10 | ≤ 0.05 | 🟡 High but expected at N=30 |

**Codebook maturity interpretation**: The profile shows an immature codebook by small-N standards. Singleton ratio (0.40) is elevated; merge rate (0.25) is low; ITS (0.10) is high. All three together suggest active codebook growth typical of N=30. Triage auto-rate is notably low (25.8%), indicating many extraction decisions fell into the grey zone and required LLM comparator judgment — this reflects the coder's uncertainty in a sparse codebook, not a failure.

### Theme quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | 0.484 | ≥ 0.55 | 🟡 Below guideline; expected at N=30 |
| theme_distinctness_overlap | 11/21 pairs (52.4%) | ≤ 25% | 🔴 Significant overlap |

**Theme distinctness**: 11 of 21 theme pairs exceed the 0.70 similarity threshold. This is a red flag for theme separation, but at N=30 with sparse evidence per theme, overlap is partially expected. The highest-overlap pair is Narrative Depth/Pacing ↔ Gameplay Loop/Resource Management (0.837), suggesting these two themes may be capturing aspects of the same underlying dissatisfaction with pacing and progression.

### Quote coverage

| Metric | Value | Note |
|--------|-------|------|
| overall_mean_pct | 0.0956 (9.56%) | Scale is correct (0–1 fraction, not percentage) |
| overall_max_pct | 1.0 (100%) | One IC-segment pair covers entire segment |
| high_coverage_pairs (>70%) | 1 | One IC covers >70% of a segment; read note below |

**Coverage interpretation**: Mean coverage of 9.56% indicates ICs typically span small quote fragments (a few phrases per segment). This is healthy and expected. The single high-coverage outlier (1.0 = entire segment) warrants inspection: the segment read "They don't know what made Dying Light 1 good, and why Dying Light 2 doesn't emulate it. Rather it tried to reinvent too much" and was entirely coded under a single IC, suggesting either a very broad IC or an over-extraction edge case.

---

## 6. Layer 4 — Analyst Brief

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Interpretation |
|--------|-------|--------|-------------------|
| grounding_rate | 1.0 | 🟢 | "Perfect alignment between extracted quotes and source text. No hallucination of quote boundaries." |
| drop_rate | 0.0 | 🟢 | "No candidates rejected. Extraction process highly reliable." |
| extraction_density_mean | 0.408 | 🟢 | "Within guideline. Focused extraction capturing meaningful content." |
| singleton_ratio | 0.4 | 🟡 | "Slightly above 0.3 guideline. Codebook may contain idiosyncratic observations." |
| merge_rate_final | 0.254 | 🟡 | "Below guideline. Codebook still growing rapidly; may need more data before synthesis." |
| triage_auto_rate | 0.258 | 🔴 | "Many grey-zone cases. Thresholds may need tuning or ICs poorly differentiated." |
| its_final | 0.10 | 🟡 | "New concepts still emerging. More data needed before codebook stable." |
| theme_coherence_mean | 0.484 | 🟡 | "Below 0.55 guideline. Themes may group unrelated concepts; consider splitting or reorganising." |
| theme_distinctness_overlap_ratio | 52.4% pairs | 🔴 | "Significant overlap. Many overlapping themes; consider merging or sharpening definitions." |
| sentiment_purity_mean | 0.937 | 🟢 | "Excellent purity. Themes not mixing sentiment; clean polarity alignment." |
| thematic_coverage | 1.0 | 🟢 | "100% of quotes captured in thematic structure. No orphaned evidence." |
| cross_review_convergence | 0.60 | 🟢 | "60% of ICs confirmed across 2+ documents. ICs represent cross-document patterns." |

### Config recommendations from Layer 4

Layer 4 did not provide explicit config recommendations in this run. Implicit recommendations based on metric interpretation:
- Lower `auto_new_threshold` (currently 0.5) to reduce triage grey-zone cases
- Consider raising `coherence_threshold` or implementing coherence-guided splitting for small N
- Investigate theme distinctness overlap — may warrant lower `distinctness_threshold` (currently 0.70) during S4 refinement

### Brief quality assessment

The Layer 4 brief identifies themes as capturing distinct aspects of player experience (combat mechanics, world navigation, narrative, progression, visceral impact) and acknowledges elevated singleton ratio and ITS as expected for small N. The brief states "Confidence in the current thematic labels is low due to the high ITS (0.18)" — note this is a misalignment with the JSON value of 0.10, but the sentiment is correct. The brief suggests the codebook is preliminary and would benefit from more data. This is intellectually sound given the metrics. However, the brief does not flag the ghost theme or high theme overlap as structural concerns, which limits its usefulness for decision-making.

---

## 7. Structure Quality Assessment

### Categories

Three categories: Mechanical Critique, Environmental and Progression Dissatisfaction, Narrative and Presentation Experience. They are mutually exclusive at a high level and collectively cover the main complaint domains visible in the corpus. The categories would be intuitive to a domain expert familiar with game reviews. However, "Environmental and Progression" bundles world-design and progression criticisms that could be separated; a fourth category might improve clarity.

### Themes

Seven themes are well-named and specific (not generic). "Combat Balance and Mechanical Frustrations" and "Visceral Combat and Gore Systems" are distinct (mechanics vs. sensory impact). "Traversal and World Navigation" is clear. "Narrative Depth and Pacing" is specific. No obvious catch-all or wastebasket themes. The dissolved "Technical Execution and Presentation" theme is notable — it was flagged as low-coherence and dissolved, then reconstructed as a ghost in the DB (Bug #1).

### ICs — spot check

| IC name | Quote sample | Alignment |
|---------|-------------|-----------|
| progression_system_limitations | "XP gains for differing actions were CUT. You get XP for basically everything..." | ✅ Aligned — quotes are specific complaints about XP and progression |
| parkour_mechanics_unpolished_and_buggy | "the parkour feels floaty and too easy compared to the first game" | ✅ Aligned — directly about parkour mechanics quality |
| insufficient_content_for_standalone_game | "It took me 26 hours to beat the game, including the majority of side content" | ✅ Aligned — length/content complaint quoted |
| vehicle_system_limitations | "the cars in the game arent yours, you don't own them, you steal them and instantly lose them" | ✅ Aligned — specific vehicle system critique |
| narrative_and_character_inconsistency | "Kyle also seems to have inconsistent motivations when plot significant" | ⚠️ Minor over-inclusion: quote mentions Kyle's motivation but doesn't explicitly address character inconsistency vs. plot logic |

**Overall IC quality**: Names are specific and grounded. Five spot-checked ICs show strong alignment between name and evidence. No evidence of over-specificity or over-abstraction.

### Evidence — spot check

Sample of 10 quotes from database (filtered for diversity):

1. "The story is short DESPITE the fact that it is 75% filler..." — Real player language, clear complaint about pacing
2. "First there's just not enough city to enjoy this game" — Genuine review text, world-scope complaint
3. "the cars in the game arent yours, you don't own them" — Authentic, specific about vehicle system
4. "the graphics are amazing even on the lowest setting on PC" — Genuine praise (positive side of mixed review)
5. "the balance is placed around the guns being terrible" — Player assessment of balance design
6. "Only gripe is that weapons break too quickly" — Authentic complaint fragment
7. "Kyle also seems to have inconsistent motivations..." — Character critique from review
8. "Too much immersion breaking. Let me explain..." — Authentic opening to detailed complaint
9. "The ragdolls and enemies physics. The GORE oh my god" — Authentic reaction (positive)
10. "Whilst the story has a pretty strong opening, I can't say..." — Natural review opening

**Evidence quality**: All 10 quotes are authentic player language with no hallucination, truncation, or attribution errors visible. Spans are plausible for the segment lengths (confirmed earlier: all span_start/span_end values within segment char_count bounds). No truncation artifacts or grammatical corruption.

---

## 8. Testing Plan Compliance

**Testing plan used**: `docs/planning/STABILIZATION_TESTING_PLAN.md`
**Run configuration**: `--no-hil` → Phase 1 (Automated Baseline) most relevant

| Check | Result | Notes |
|-------|--------|-------|
| Pipeline completes without errors | ✅ | All layers completed; no Python exceptions |
| S4 features fire: [DISTINCT] and [SPLIT] log lines | ✅ | Distinctness gate fired (11 overlapping pairs detected); split heuristic active but no splits triggered |
| Layer 4 produces analytical brief | ✅ | Results JSON contains layer4.synthesis.brief; printed to terminal |
| All 18 metrics computed | ✅ | Layer 3 output shows all major metrics (grounding, drop, density, coherence, distinctness, etc.) |
| Thematic structure has categories → themes → ICs → quotes | ✅ | Full hierarchy present in results JSON and DB |
| Coder reuse rate block in quality report | ✅ | All four counters present: coder_flagged_match=61, coder_new_comp_new=50, coder_new_comp_merge=17, coder_new_comp_reject=0 |
| Coder flip rate warning if merge/new > 0.40 | ❌ | Flip rate is 34% (17/50); no warning expected (threshold 40%+). Correctly did not fire. |
| Per-IC coverage block in quality report | ✅ | Overall_mean=0.0956, overall_max=1.0, high_coverage_count=1 present |
| Reasoning log co-located with DB | ✅ | Log file at `runs/dying_light_beast_test_20260303_164934_reasoning.jsonl`; same directory as DB |

**Known issues manifesting in this run:**

- **Issue #10 (High singleton ratio in canon_30)**: Singleton ratio is 0.40 (20/50 ICs). Testing plan notes "82.5% singleton ratio in canon_30 — coder over-splits." This run shows 40%, which is much better, possibly because orSmart (Gemini-3-Flash-Preview via OpenRouter) is a stronger model than the gemini_flash_lite mentioned in Issue #10. The testing plan recommends using a stronger model (Haiku or Gemini Flash non-lite) for stabilization runs — this test confirms orSmart is viable.
- **Issue #6 (Gemini Flash Lite weakness)**: Not applicable to this run (using orSmart, not Lite).
- **Issue #2 (Low convergence confidence)**: This run shows 60% confirmed convergence (2+ docs per IC), at the threshold. Acceptable for N=30 but still below the ideal ≥0.60+ range expected for mature codebooks.

---

## 9. Bugs and Anomalies

### Bug #1: Ghost Theme in Database

**Severity**: High
**Symptom**: Database query of `themes` table shows "Technical Execution and Presentation" theme with 0 ICs assigned (no rows in `theme_ics` join). Theme appears in layer2 coherence_gate → flagged_themes → dissolved_theme_names list and in meaning_saturation output as "last@seg -1", but exists as a record in the DB with no ICs linked to it. The ghost theme is the 8th theme in the DB; only 7 are functional (with ICs).
**Affected components**: Layer 2 (coherence gate / orphan reassessment), Database schema
**Root cause**: When the coherence gate dissolves a low-coherence theme and triggers orphan reassessment, the ICs are redistributed to surviving themes, but the dissolved theme record remains in the `themes` table with no entries in `theme_ics`. The DB persistence logic does not delete the theme record after ICs are orphaned and reassigned. This is a known pattern (Bug #1 in testing plan's known issues list).
**Fix needed**: Yes — in Layer 2 coherence gate implementation. After orphans are reassigned, either: (a) delete the dissolved theme record from DB, or (b) add a `dissolved` or `inactive` status flag to themes table and filter them out during downstream processing.
**Priority**: P1 — Ghost themes can cause downstream analysis failures if code assumes all theme records have ICs; affects data integrity and metric computation

**Query to detect:**
```sql
SELECT t.name, COUNT(ti.ic_id) AS ic_count
FROM themes t
LEFT JOIN theme_ics ti ON ti.theme_id = t.id
GROUP BY t.id
HAVING COUNT(ti.ic_id) = 0
```

---

### Anomaly #2: IC Refinement Incomplete

**Severity**: Medium
**Symptom**: Layer 1 JSON reports `ics_refined: 30` (out of 50 new ICs created). Only 60% of ICs were refined, not 100%. Per metric_reference.md, "IC refinement is an all-or-nothing feature — it should either run for all ICs or have failed entirely. A partial rate suggests a crash that was swallowed."
**Affected components**: Layer 1 (IC refinement subprocess)
**Root cause**: Unknown — possible timeout on refinement call, partial failure in refinement LLM prompting, or a silent exception in the refinement loop. Testing plan notes Issue #11 (IC refinement NameError) was supposedly fixed in commit c88eda3, but this run shows incomplete refinement.
**Fix needed**: Investigation needed. Check Layer 1 logs for timeout warnings or partial-batch markers. Verify commit c88eda3 was applied and that refinement prompting is correct.
**Priority**: P1 — Incomplete IC refinement means some IC definitions are not optimized; affects downstream coherence and theme formation

**Recommendation**: Re-run with `reasoning_log_mode: full` and inspect the reasoning.jsonl for refinement call traces. Check for "timeout", "rate limit", or "exception" patterns in Layer 1 logs.

---

### Anomaly #3: High Theme Distinctness Overlap (52.4% of pairs)

**Severity**: Medium
**Symptom**: 11 of 21 theme pairs have centroid similarity > 0.70, indicating significant semantic overlap. Threshold guideline is ≤ 25% (≤ 5.25 pairs for 21 total). This run shows 11 overlapping pairs (52.4%), well above guideline.
**Affected components**: Layer 2 (S4 distinctness gate and theme definitions)
**Root cause**: S4 distinctness gate fired but did not merge or sharpen any themes. The gate detected the overlaps but took no action. Possible reasons: (a) distinctness threshold (0.70) is too high to trigger merges, or (b) the LLM revision step that would sharpen definitions did not fire as expected.
**Fix needed**: Yes — investigate S4 distinctness gate logic. Either lower `distinctness_threshold` in config (currently 0.70) or enhance the revision step to actively sharpen definitions when pairs exceed threshold.
**Priority**: P2 — High overlap does not break functionality but reduces analytical clarity. Themes are interpretable but conceptually redundant.

**Context**: At N=30, some overlap is expected due to sparse evidence per theme. However, a 52% overlap rate is unusually high. Recommend re-testing at N=50 to see if the issue scales or is N=30-specific.

---

### Anomaly #4: Triage Auto-Rate Very Low (25.8%)

**Severity**: Low
**Symptom**: Only 25.8% of triage decisions were made automatically (6 auto_new + 11 auto_merge = 17 of 66 total decisions); 74.2% required LLM comparator. Threshold guideline is ≥ 60% auto-decided.
**Affected components**: Layer 1 (similarity-based triage, grey-zone thresholding)
**Root cause**: In a sparse 30-IC codebook, most new candidates fall into the grey zone (similarity between auto_new threshold 0.5 and auto_merge threshold 0.72). The coder is uncertain about most ICs, so the comparator is called. This is not a bug but reflects a sparse codebook state.
**Fix needed**: No — this is expected behavior at small N. The grey-zone rate is actually informative: it shows the coder is operating with appropriate uncertainty. At N=100+, auto-rate should improve.
**Priority**: P3 — Informational; no action needed. Document as expected behavior for small N.

---

## 10. Next Steps

1. **Resolve Bug #1 (ghost theme)** — Medium effort. Modify Layer 2 coherence gate to delete dissolved theme records from DB after IC reassignment. Test with canon_30 re-run and verify no ghost themes appear in results JSON. Priority: P1 blocker for data integrity.

2. **Investigate Anomaly #2 (IC refinement incomplete)** — High effort. Inspect Layer 1 logs with `reasoning_log_mode: full`; search for refinement timeout/exception patterns. If retry-able, implement retry logic. If cache/batch-specific, identify batch and narrow down. Priority: P1, but only if refinement is critical to downstream quality.

3. **Re-run canon_30 with orSmart after Bug #1 fix** — Run the same test command with the patched code. Verify: (a) no ghost themes in results, (b) IC refinement 100% completion, (c) all other metrics stable. Expected outcome: same thematic structure, no data integrity bugs.

4. **Run canon_50 with orSmart** — After canon_30 passes: test at scale N=50. Check: (a) ITS declining further, (b) merge rate increasing, (c) theme overlap ratio improving (should be < 52.4%), (d) singleton ratio declining (should be < 0.40). If metrics improve as expected, proceed to canon_100. Expected wall-clock time: ~40 min (orSmart is ~4x slower than gemini_flash_lite).

5. **Evaluate theme distinctness gate behavior** — Document whether high overlap (52.4%) is N=30-specific or a persistent issue. If it persists at N=50, lower `theme_refinement.distinctness_threshold` from 0.70 to 0.65 and re-test to see if S4 becomes more active in sharpening themes.

6. **Document singleton ratio improvement over gemini_flash_lite** — Testing plan Issue #10 noted 82.5% singleton ratio with lite model. This run shows 0.40 (40%) with orSmart. Include this in decision report when evaluating model trade-offs (cost vs. quality).

---

## Summary for Next Phase

**Stabilization Phase 1.1 (canon_30) outcome:** Run executes end-to-end but surfaced two data integrity bugs (ghost theme, incomplete IC refinement) and one structural metric concern (theme overlap). The orSmart model outperforms gemini_flash_lite significantly on singleton ratio and structured output consistency. With Bug #1 resolved, this run provides a solid baseline for scaling to canon_50 and canon_100.

**Readiness for Phase 1.2 (canon_50):** Blocked until Bug #1 is fixed. Once fixed, canon_50 should proceed immediately to establish scaling trajectory.

**Configuration assessment:** orSmart via OpenRouter is a strong choice for this pipeline; no model-specific failures observed (unlike gemini_flash_lite's structured output issues). Config is correct. Reasoning logs are being written correctly. No recommended config changes at this time; focus on bug resolution.

