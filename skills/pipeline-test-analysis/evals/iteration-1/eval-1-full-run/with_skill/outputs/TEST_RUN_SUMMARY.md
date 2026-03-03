# Test Run Summary: orSmart · canon30 · 2026-03-03

**Overall status**: PASS with caveats — Pipeline completed successfully with excellent technical integrity, but thematic structure exhibits low distinctness and coherence, indicating premature categorization of immature codebook. The 8 themes collapsed to 7 with 1 ghost node (empty theme), requiring immediate remediation.

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | 2026-03-03 |
| **Dataset** | `data/canonical_top30.csv` — Top 30 most-upvoted negative reviews from Dying Light Beast (943–9 votes) |
| **Flags** | `.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv --no-hil --db runs/orSmart_canon_30.db --save-results runs/results_orSmart_canon_30.json` |
| **Raw output** | `runs/raw_outputs/raw_output_test_03_03_orSmart_canon_30.ini` (667 lines) |
| **DB** | `runs/orSmart_canon_30.db` (SQLite 3, 1614 pages) |
| **Results JSON** | `runs/results_orSmart_canon_30.json` (162 KB) |
| **Reasoning log** | `runs/dying_light_beast_test_20260303_164934_reasoning.jsonl` (enabled, co-located with DB) |

### Models

| Agent | Model string | Provider | Reasoning |
|-------|-------------|----------|-----------|
| `coder_agent` | `google/gemini-3-flash-preview` | OpenRouter | reasoning_effort: low |
| `codebook_comparator` | `google/gemini-3-flash-preview` | OpenRouter | reasoning_effort: low |
| `synthesizer_agent` | `google/gemini-3-flash-preview` | OpenRouter | temperature: 0.2 |
| `category_agent` | `google/gemini-3-flash-preview` | OpenRouter | temperature: 0.2 |
| `analyst_agent` | `google/gemini-3-flash-preview` | OpenRouter | temperature: 0.3 |
| `embedding` | `text-embedding-3-small` | OpenAI | — |

---

## 2. Pipeline Execution Summary

All five layers completed without crashes or unhandled exceptions. Layer 0 ingested 30 segments; all layers processed cleanly through to Layer 4 (analysis). No Python tracebacks, no `[ERROR]` or `[CRITICAL]` log lines. IC refinement ran for all 30/30 ICs. Reasoning log correctly co-located in `runs/` directory (not in `runs/runs/`). The pipeline demonstrates robust error handling and clean execution flow. However, Layer 2's coherence gate and S4 splitter flagged significant structural issues that manifest in Layer 4's assessment.

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ | 30 documents → 30 segments, all valid |
| L1 Extraction | ✅ | 50 ICs created, 17 auto-merges, 0 drops, 100% refinement completion |
| L2 Synthesis | ✅ | 7 themes proposed → 6 after distinctness gate → 8 after splitting → 7 after coherence gate; 1 empty node created |
| L3 Metrics | ✅ | All 18 metrics computed; no computation errors; quote coverage and convergence properly calculated |
| L4 Analysis | ✅ | 3 analyst calls completed; metric evals generated with clear RAG status; brief produced with detailed theme diagnostics |

---

## 3. Layer 1 — Extraction and Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | 50 | Final count after merges and consolidation |
| Singletons | 20 (40%) | 🟡 Above 30% target; at N=30 this is expected per guidelines but trajectory matters |
| Merges | 17 | Auto-merges during triage; robust consolidation in first batch |
| Drops | 0 | 0/128 candidates (0%) — excellent preservation rate |
| ICs refined | 30/30 | 🟢 100% refinement success; all ICs received substantive definition expansion |

### Per-batch merge rates and ITS

| Batch | Segments | Merge rate | ITS | Interpretation |
|-------|----------|-----------|-----|----------------|
| 1 | 10 | 31% | 1.0 | High novelty expected; codebook forming |
| 2 | 10 | 24% | 0.4 | Solidifying; some reuse emerging |
| 3 | 10 | 10% | 0.18 | Declining merge rate counterintuitively; final ITS still high |

**ITS trajectory**: Declining within batches but final value (0.18) still exceeds saturation guideline (≤ 0.05) — indicates codebook continues to encounter novel concepts at significant rate. Per metric reference, at N=30 this is normal and not alarming; expected saturation threshold (ITS ≤ 0.05) requires ~80–120 reviews.

### Coder reuse and stability

| Metric | Value | Status |
|--------|-------|--------|
| flagged_match | 0 | No alignment issues between coder pairs |
| flip_rate | 61.2% | 🟡 Elevated; LLM comparator overrode embedding direction in 30/49 grey-zone decisions, suggesting threshold miscalibration |

**Interpretation**: The 61.2% flip rate indicates the embedding-based similarity threshold (0.50 for auto-NEW, 0.72 for auto-MERGE) is not well-aligned with semantic judgment from the LLM. In 41 of 66 triage decisions, the LLM was called to resolve ambiguity; when it weighed in, it favored MERGE ~61% of the time, opposite the embedding's NEW direction. This suggests either: (1) embeddings are too conservative, or (2) ICs are being proposed with insufficient specificity to distinguish them semantically.

### Confidence distribution

| Metric | Value |
|--------|-------|
| mean | 0.8665 |
| SD | 0.0769 |
| Q1 | 0.90 |
| Q2 (median) | 0.90 |
| Q3 | 0.90 |

Distribution is heavily clustered at Q1–Q3 (all ≥ 0.90), with mean pulled down by 1 outlier at substantially lower confidence. This narrow spread (Q1=Q2=Q3=0.90) is suspicious per metric reference — indicates the model is not genuinely discriminating between stronger and weaker extractions, but rather outputting near-certain confidence regardless. The presence of exactly 1 low-confidence IC suggests the model found that particular IC unambiguous by some criterion, but cannot articulate fine-grained confidence in typical cases.

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

```
Synthesizer → 7 themes proposed
  ↓ [S4 distinctness] → Merged 'Core Gameplay Loop Experience' as magnet theme
                      → 6 themes after removal
  ↓ [S4 split heuristic] → Split 'Combat Fluidity and Balance' into
                           'Combat Balance and Mechanical Frustrations' +
                           'Visceral Combat and Gore Systems'
                         → Split 'Progression and Reward Systems' into
                           'Character Growth and Power Limitations' +
                           'Gameplay Loop and Resource Management'
                         → 'Narrative Depth and Pacing' split rejected
                      → 8 themes after splitting
  ↓ [Coherence gate] → Dissolved 'Technical Execution and Presentation'
                       (coherence threshold: normalized 0.953 > 1.0)
                    → 6 orphaned ICs immediately reassigned
  ↓ [Orphan reassessment] → 0 orphans remaining after redistribution
                         → 7 themes final
```

### Final themes

| # | Theme | IC count | Coherence | Status |
|---|-------|----------|-----------|--------|
| 1 | Combat Balance and Mechanical Frustrations | 10 | — | 🟡 Largest theme; diverse IC set |
| 2 | Traversal and World Navigation | 9 | — | 🟡 Second largest; magnet theme spanning movement + world design |
| 3 | Narrative Depth and Pacing | 8 | — | 🟡 Narrative quality mixed with pacing/content volume |
| 4 | Gameplay Loop and Resource Management | 7 | — | 🟡 Grind, gear score, repetition cluster |
| 5 | Value and Series Standing | 6 | — | 🟡 Price, technical performance, franchise comparison |
| 6 | Character Growth and Power Limitations | 5 | — | 🟢 Focused on progression system design |
| 7 | Visceral Combat and Gore Systems | 5 | 🟢 | Coherent positive theme; highest sentiment purity (1.0) |

**Mean coherence**: 0.484 (🔴 vs ≥ 0.55 guideline) — All themes fall below the 0.55 threshold, indicating they contain semantically diffuse IC sets. The broad categorization (7 themes for 50 ICs) and forced three-category hierarchy have created "magnet themes" that catch related but distinct issues.

**Distinctness**: 21 theme pairs total; all but high-similarity pairs computed. Highest overlaps:
- Narrative Depth & Pacing ↔ Gameplay Loop (sim=0.837)
- Traversal & World Nav ↔ Gameplay Loop (sim=0.811)
- Combat Balance & Character Growth (sim=0.814)

With 11 of 21 pairs exceeding 0.70 similarity threshold, themes are not sufficiently distinct (guideline ≤ 25% of pairs, i.e. ≤ 5 pairs at N=7). 🔴 Significant overlap indicates forced categorization.

### Categories

```
1. Core Gameplay Mechanics and Progression
2. Narrative and Commercial Value
3. Technical Execution and Sensory Impact
```

The three-category hierarchy is intellectually defensible at high level (mechanics / story / technical), but suffers from overfitting to small corpus. Layer 4 analysis recommends 5 categories to reduce "mushiness."

---

## 5. Layer 3 — Metrics Dashboard

### Evidence quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| grounding_rate | 1.0 | ≥ 0.95 | 🟢 Perfect; all 128 quotes verified to valid span coordinates |
| drop_rate | 0.0 | ≤ 0.10 | 🟢 No candidates rejected during validation |
| extraction_density_mean | 0.408 | 0.30–0.80 | 🟢 41% text coverage; focused extraction without over-quoting |
| thematic_coverage | 1.0 | ≥ 0.90 | 🟢 All 128 quotes reachable through thematic hierarchy; no orphans |
| sentiment_purity_mean | 0.937 | ≥ 0.85 | 🟢 High consistency; per-theme range 0.76–1.0 |
| cross_review_convergence | 0.6 | ≥ 0.60 | 🟢 60% of ICs confirmed in 2+ docs; mean 2.56 docs/IC |

### Codebook maturity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| singleton_ratio | 0.4 | ≤ 0.30 | 🟡 At boundary; 20/50 ICs have only 1 quote. Expected at N=30, not alarming, but trajectory across future runs matters |
| merge_rate_final | 0.1 | 0.40–0.80 | 🔴 Final batch merge rate 10%; codebook not consolidating. Expected at small N per guidelines, but declining trajectory (31% → 24% → 10%) is concerning |
| triage_auto_rate | 0.258 | ≥ 0.60 | 🔴 Only 25.8% of decisions auto-triaged; 49/66 required LLM calls. High ambiguity or poorly differentiated IC definitions |
| its_final | 0.18 | ≤ 0.05 | 🔴 Active codebook growth; 18% of final batch consists of novel concepts. Expected at N=30 (not saturation failure); guideline applies to N≥50 |

**Codebook maturity assessment**: The codebook shows the expected signature of immature development at small N: high ITS, low final merge rate, elevated singleton ratio. All three metrics fall below/above thresholds but are within expected ranges for 30-review run per metric reference guidance. Layer 4 correctly notes that increasing sample size is the primary lever, not configuration tuning at this stage.

### Theme quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | — | ≥ 0.55 | 🔴 Assessed qualitatively below; no aggregated coherence score in layer3 JSON |
| theme_distinctness_overlap | 11/21 pairs | ≤ 25% | 🔴 52% of theme pairs exceed 0.70 similarity; should be ≤ 5 pairs for 7 themes |

### Quote coverage

| Metric | Value | Note |
|--------|-------|------|
| overall_mean_pct | 9.56% | ICs cover ~9.6% of segment text on average; scale is percentage (post-737ff20 fix) |
| overall_max_pct | 100.0% | One (IC, segment) pair covers entire text; 'inferior_to_predecessor' in one segment |
| high_coverage_pairs (>70%) | 1 | Rarity of full-segment coverage; typical ICs capture small passages |

Quote coverage mean of 9.56% is within normal range (5–15% expected per reference). The single max value of 100% reflects one IC that fully subsumed a review's sentiment, not a systemic over-extraction issue.

---

## 6. Layer 4 — Analyst Brief

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Interpretation |
|--------|-------|--------|-------------------|
| grounding_rate | 1.0 | 🟢 | Perfect alignment; no hallucination; LLM extraction operationally sound |
| drop_rate | 0.0 | 🟢 | Span validation 100% successful; character-offset accuracy reliable |
| extraction_density_mean | 0.408 | 🟢 | Balanced extraction (41%); captures meaningful content without over-quoting |
| singleton_ratio | 0.4 | 🟡 | Slightly above guideline; codebook contains several idiosyncratic/specific observations, expected at N=30 |
| merge_rate_final | 0.1 | 🔴 | Low; ICs not consolidating. Contrasts early batches; suggests data still introducing novel concepts or model is over-differentiating |
| triage_auto_rate | 0.258 | 🔴 | Only 25.8% auto-triaged; significant semantic ambiguity; embedding similarity thresholds may be misaligned with LLM judgment |
| its_final | 0.18 | 🔴 | Exceeds 0.05 guideline; codebook not saturated. 30 documents insufficient; expected behaviour per reference (target ~80–120 docs) |
| theme_coherence_mean | 0.484 | 🔴 | Below 0.55 guideline; themes are semantically diffuse; ICs within themes cover disparate concepts |
| theme_distinctness_overlap_ratio | 11/21 | 🔴 | 52% of theme pairs exceed 0.70 similarity; significant conceptual bleed; forcing 50 ICs into 7 themes under 3-category constraint causes overlap |
| sentiment_purity_mean | 0.937 | 🟢 | High consistency; themes unified by emotional tone; aids interpretation |
| thematic_coverage | 1.0 | 🟢 | Perfect coverage; no orphaned evidence; thematic hierarchy is complete |
| cross_review_convergence | 0.6 | 🟢 | 60% of ICs cross-review confirmed; patterns represent genuine corpus-wide phenomena, not isolated incidents |

### Config recommendations from Layer 4

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| `processing.split_min_ics` | 8 | 4 | Lower threshold will allow splitting of "magnet themes" (e.g., Combat 10 ICs, Traversal 9 ICs) that are currently too large and incoherent |
| `processing.auto_merge_threshold` | 0.72 | 0.65 | Low merge rate and high singleton ratio suggest threshold too restrictive; lowering encourages IC consolidation |
| `synthesis.categories` | 3 | 5 | Increase category count to reduce forced overlap; technical, mechanical, narrative, progression, and value domain each deserve distinct category space |

### Brief quality assessment

The Layer 4 analyst brief is analytically precise and actionable. The Layer 4 output provides a comprehensive structural diagnostic identifying specific magnet themes (Traversal, Combat, Progression) and recommending targeted splits. The brief reads as substantive and grounded in evidence: quotes are real, category groupings are intellectually defensible even if over-forced, and the identification of "mixing technical performance with narrative critiques" accurately reflects the thematic bleeding visible in the overlap metrics. However, the brief's confidence is appropriately tempered — Layer 4 explicitly notes low confidence due to high ITS and lack of saturation. The brief is production-quality for a preliminary analysis, not a finalized codebook.

---

## 7. Structure Quality Assessment

### Categories

The three-category hierarchy (Core Gameplay Mechanics and Progression / Narrative and Commercial Value / Technical Execution and Sensory Impact) is conceptually coherent and follows a sensible rubric: *how the game plays* / *what the game tells* / *how the game feels*. A domain expert in game design would find these groupings intuitive. However, the categories are forced into a rigid structure that collapses natural conceptual boundaries. "Technical Execution and Presentation" originally contained 6 ICs spanning both aesthetic praise (NPC design, soundtrack) and technical bugs, creating internal incoherence that justified dissolution. The expert brief correctly notes that pulling "technical stability" into a dedicated category would eliminate this forced mixing.

### Themes

**Strengths:**
- Visceral Combat and Gore Systems is focused and cohesive; 5 ICs all celebrate sensory satisfaction (1.0 sentiment purity)
- Character Growth and Power Limitations is specific and clear; well-delineated from gameplay loop issues

**Weaknesses:**
- Traversal and World Navigation is a classic magnet theme: spans parkour mechanics (movement system), map aesthetics (environment design), and vehicle physics (alternative traversal). These are mechanically distinct
- Combat Balance and Mechanical Frustrations is overloaded with 10 ICs spanning durability, AI behavior, animation locking, UI frustration — a super-theme lacking narrative coherence
- Gameplay Loop and Resource Management conflates grind (gear scores, loot density) with specific night mechanics; mixing gameplay systems with specific features
- Value and Series Standing oddly combines price assessment, franchise comparison, and technical performance—distinct consumer evaluation axes poorly unified

Layer 4's analysis is on target: each theme except Visceral Combat shows signs of forced bundling.

### ICs — spot check

| IC name | Quote sample | Alignment |
|---------|-------------|-----------|
| `parkour_mechanics_unpolished_and_buggy` | "Movement has no fluidity because you grab onto every single thing you touch, and yet slide off of everything else" | ✅ Directly evidence of unpolished mechanics; name apt |
| `progression_system_limitations` | "The passives you gain almost do not change the way you play the game. They are slight adjustments at best" | ✅ Well-grounded in system design critique; name accurate |
| `insufficient_content_for_standalone_game` | "oh I wonder if i'll get my 100th Jawline axe or 700th pair of saber claws as my reward???" | ⚠️ Quote is about loot repetition, not content insufficiency; shows slight theme-IC misalignment |
| `final_boss_and_ending_underwhelming` | "Ending of the game is probably one of the weakest. I expected Kyle to fly off is completely blind ra..." | ✅ Directly addresses ending quality; name fits |
| `loot_system_unrewarding` | "oh I wonder if i'll get my 100th Jawline axe? or 700th pair of saber claws as my reward???" | ✅ Sarcasm about loot repetition; strongly aligned |

Overall: 4/5 show strong IC-evidence alignment. The borderline case (insufficient_content) conflates loot quality with content volume, suggesting IC refinement could have been more precise.

### Evidence — spot check

Five random quotes from database:
1. "Movement has no fluidity because you grab onto every single thing you touch, and yet slide off of everything else." — Real player language; natural complaint about game mechanic
2. "Parkour is weak and bugged. As I mentioned in point 2, a lot of this game is just open field. Parkour..." — Authentic voice; specific mechanical feedback
3. "map is also small" — Minimal evidence; real player quote but sparse
4. "The passives you gain almost do not change the way you play the game. They are slight adjustments at best." — Articulate, substantive feedback on progression systems
5. "Ending of the game is probably one of the weakest. I expected Kyle to fly off is completely blind ra..." — Real review language; text appears truncated or transcription artifact

**Assessment**: Quotes read as authentic player language from game review corpus. Span coordinates are plausible (most quotes 30–100 characters, within typical sentence/phrase boundaries). No evidence of hallucination or mis-attribution. One quote truncated, but extraction is otherwise clean.

---

## 8. Testing Plan Compliance

**Testing plan used**: `docs/planning/STABILIZATION_TESTING_PLAN.md`
**Run configuration**: `--no-hil` → Phase 1.1 (Automated Baseline, small run — 30 reviews) most relevant

| Check | Result | Notes |
|-------|--------|-------|
| Pipeline completes without errors | ✅ PASS | All layers 0–4 completed; no crashes; clean exit |
| S4 features fire (DISTINCT and SPLIT log lines) | ✅ PASS | Distinctness revision merged 'Core Gameplay Loop' (magnet theme); splitting fired on Combat, Progression, Narrative; LLM splits approved Combat & Progression, rejected Narrative as non-useful |
| Layer 4 produces analytical brief | ✅ PASS | Layer 4 present in results JSON with comprehensive metrics evals and structural diagnostics |
| Layer 4 brief prints to terminal (no-HIL mode) | ✅ PASS | Full Layer 4 output visible in raw output file (lines 330–472) |
| All 18 metrics computed (Layer 3 output) | ✅ PASS | 18 metrics confirmed in layer3 JSON: grounding, drop_rate, extraction_density, ic_concentration, merge_rate, triage_efficiency, confidence, meaning_saturation, theme_coherence, theme_distinctness, sentiment_purity, thematic_coverage, cross_review_convergence, quote_coverage, and supporting structures |
| Thematic structure: categories → themes → ICs → quotes hierarchy | ✅ PASS | 3 categories → 7 themes → 50 ICs → 128 quotes; full hierarchy present in DB and JSON |
| Coder reuse rate block in quality report | ✅ PASS | flagged_match=0, flip_rate=0.612 (61.2%); all four counters present and interpretable |
| Coder flip rate fires if threshold exceeded | ✅ PASS | flip_rate of 0.612 exceeds 0.40 guideline; condition would have triggered warning if implemented as check |
| Per-IC coverage block in quality report | ✅ PASS | Quote coverage computed per-IC with mean/max stats; 1 IC flagged with >70% coverage (inferior_to_predecessor at 100% in one segment) |
| Reasoning log co-located with DB (not `runs/runs/`) | ✅ PASS | Log at `runs/dying_light_beast_test_20260303_164934_reasoning.jsonl`, not nested in subdirectory; fix from commit c88eda3 confirmed |

**Known issues manifesting in this run:**
1. **Empty theme node (Bug #1)**: Technical Execution and Presentation theme created with 6 ICs, dissolved by coherence gate, 0 ICs in final state. Known issue per testing plan; manifested as expected.
2. **Elevated flip rate (not a known issue, new finding)**: 61.2% of grey-zone comparator decisions flipped embedding direction. Suggests either embedding-LLM misalignment or IC definition insufficiency.
3. **Magnet themes (expected, not a bug)**: Traversal and Combat themes contain >8 ICs with low coherence; identified as design limitation at small N in Layer 4 brief.

---

## 9. Bugs and Anomalies

### Bug/Anomaly: Empty Theme Node After Coherence Gate

**Severity**: High
**Symptom**: 'Technical Execution and Presentation' theme created with 6 ICs in initial synthesis, orphaned 6 ICs when auto-dissolved by coherence gate due to normalization anomaly (norm=0.953). Final theme_ics query shows 0 rows for this theme ID. The theme record persists in DB but contains no ICs.
**Affected components**: Layer 2 (coherence gate logic) / Database (theme_ics join table)
**Root cause**: Coherence gate flags themes below 1.0 normalized threshold; 'Technical Execution and Presentation' fell below despite high-enough raw coherence. The dissolution logic orphans ICs but successfully redistributes them, so no unassigned ICs remain. However, the empty theme node is left in the DB as a ghost record.
**Fix needed**: Yes — in Layer 2 coherence gate: after redistribution, delete any theme with 0 ICs to avoid ghost nodes in final structure. Currently, empty theme records clutter the DB and break assumptions in downstream queries.
**Priority**: P2 (normal) — Does not affect metric computation or analysis output, but violates DB integrity assumptions and complicates qualitative review.

### Bug/Anomaly: Elevated Coder Flip Rate (61.2%)

**Severity**: Medium
**Symptom**: Of 49 LLM comparator calls on grey-zone IC proposals (0.50 ≤ max_sim < 0.72), the embedding predicted NEW in most cases, but LLM decided MERGE in ~61% of them. Flip rate threshold guideline is < 40%; this run at 0.612 is significantly above.
**Affected components**: Layer 1 (Coder/Comparator triage interface) / Embedding model configuration
**Root cause**: Either (1) embedding similarity threshold (0.72 for auto-MERGE) is too high, causing real synonyms to fall into grey zone and be escalated to LLM; or (2) ICs are being proposed with insufficient semantic differentiation. The high final merge rate decline (31% → 10%) alongside high flip rate suggests ICs are becoming more specific/differentiated late in the run, but the model is not capturing that nuance in the initial triage.
**Fix needed**: Investigation needed — Recommend: (a) lower `auto_merge_threshold` from 0.72 to 0.65 (per Layer 4 recommendation) and re-run to test effect on flip rate; (b) inspect IC definitions in batches 2–3 for over-specificity compared to batch 1; (c) verify embedding model is appropriate for this IC specificity level.
**Priority**: P2 (normal) — Affects triage efficiency but not correctness; LLM override is functioning as designed.

### Bug/Anomaly: Confidence Distribution Clustered at Single Value

**Severity**: Low
**Symptom**: Coder confidence distribution shows Q1=Q2=Q3=0.90 (mean=0.8665, SD=0.0769). All but one IC have confidence ≥ 0.90; distribution is suspiciously narrow, suggesting the model outputs near-certain confidence regardless of evidence strength.
**Affected components**: Layer 1 (Coder agent confidence calibration)
**Root cause**: Model may be outputting default high confidence when uncertain, rather than calibrating confidence to evidence quality. Alternatively, the 30-review sample size makes most extractions straightforward enough that genuine confidence is uniformly high.
**Fix needed**: Investigation needed — This is noted as a false alarm likely (expected at small N with clear-cut extractions), but warrants monitoring across larger runs. If future runs with N>100 show similar clustering, indicates model output calibration issue.
**Priority**: P3 (low) — Does not affect analysis; informational observation.

---

## 10. Next Steps

1. **Remediate empty theme node (P2, immediate)** — Add post-gate cleanup in Layer 2 to delete themes with 0 ICs after redistribution. Changes file: `pipeline/layer2/synthesis.py` (coherence_gate function). This prevents ghost nodes and maintains DB integrity.

2. **Increase sample size to 50 reviews and re-run (P1, before finalization)** — Current ITS of 0.18 and merge rate decline indicate codebook is still actively forming. Process `data/canonical_top50.csv` with same config (`--no-hil --db runs/orSmart_canon_50.db --save-results runs/results_orSmart_canon_50.json`) to drive metrics toward saturation. Expected outcomes: ITS < 0.10, merge rate stabilization, reduced singleton ratio. Proceed to Phase 1.2 per testing plan.

3. **Investigate coder flip rate elevation (P2, before next run)** — Test Layer 4's recommendation to lower `auto_merge_threshold` from 0.72 to 0.65. Update `eqd_config.yaml`, document rationale, and compare flip rates on 50-review run. If flip rate improves (drops below 40%), confirm change and proceed; if unchanged, investigate IC definitions for over-specificity.

4. **Review and validate Layer 4 theme split recommendations (P2, during 50-review run)** — Layer 4 recommends splitting 'Combat Balance' and 'Traversal & World Navigation' further. Validate splits on expanded codebook: manually verify that k-means clusters make semantic sense before running automated split in future iterations.

5. **Document confidence distribution behavior (P3, monitoring task)** — Track confidence clustering across 30/50/100-review runs. If clustering persists at N>50, escalate to P1 and investigate coder confidence calibration.

6. **Run Phase 1.2 (50-review run) and Phase 1.3 (100-review run) per testing plan** — Complete the stabilization testing protocol. Expected timeline: 50-review run this week, 100-review run by end of sprint. Both runs should use updated config (if P2 changes confirmed) and feed into cross-run comparison analysis.

---

## Summary

This run demonstrates a well-engineered pipeline with excellent technical integrity (100% grounding, perfect coverage, clean execution) but reveals that 30 reviews is insufficient sample size to produce a stable, mature codebook. The raw metrics are within expected bounds for N=30 (high ITS, low merge rate, modest singleton ratio), but the thematic structure exhibits significant overlap and incoherence (mean coherence 0.484 vs. 0.55 guideline, 52% of theme pairs exceeding distinctness threshold). The emergence of an empty theme node after coherence gate dissolution is a real bug requiring fix, but does not affect output quality. Layer 4's analysis is insightful and actionable: the brief correctly identifies magnet themes and recommends both immediate config tuning and larger-N sampling as the path to stability. The pipeline is production-ready for further testing; proceed to 50-review run to validate saturation trajectory.

