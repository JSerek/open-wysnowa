# Test Run Summary: orSmart · canon50test2 · 2026-03-04

**Overall status**: PASS with caveats — all layers completed cleanly, but codebook shows rising ITS in final batches (active discovery phase, not saturation), and theme coherence + distinctness are both below guideline at N=50.

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | 2026-03-04 |
| **Dataset** | `data/canonical_top50.csv` — 50 most-upvoted negative reviews from dying_light_beast_negative_full (votes range: 943–~200) |
| **Flags** | `.venv/bin/python scripts/run_pipeline.py data/canonical_top50.csv --no-hil --db runs/orSmart_canon_50.db --save-results runs/results_orSmart_canon_50.json` |
| **Raw output** | `runs/raw_outputs/raw_output_test_04_03_orSmart_canon_50_test2.txt` |
| **DB** | `runs/orSmart_canon_50.db` |
| **Results JSON** | `runs/results_orSmart_canon_50.json` |
| **Reasoning log** | `runs/dying_light_beast_test_20260304_160945_reasoning.jsonl` |

### Models

| Agent | Model string | Provider | Reasoning |
|-------|-------------|----------|-----------|
| `coder_agent` | `google/gemini-3-flash-preview` | OpenRouter | `reasoning_effort: low` |
| `codebook_comparator` | `google/gemini-3-flash-preview` | OpenRouter | `reasoning_effort: low` |
| `synthesizer_agent` | `google/gemini-3-flash-preview` | OpenRouter | — (model default) |
| `category_agent` | `google/gemini-3-flash-preview` | OpenRouter | — (model default) |
| `analyst_agent` | `google/gemini-3-flash-preview` | OpenRouter | — (model default) |
| `embedding` | `text-embedding-3-small` | OpenAI | — |

---

## 2. Pipeline Execution Summary

All five layers completed without error or crash. No integrity failures, no DB corruption, no missing outputs. L3 computed all 18 metrics; L4 produced a 3-call analytical brief. The run is the correct Phase 1.2 run using `canonical_top50.csv` (50 reviews), in contrast to the previous misfired run (`raw_output_test_04_03_orSmart_canon_50`) which used `canonical_top30.csv`.

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ | 50 documents → 50 segments |
| L1 Extraction | ✅ | 52 ICs, 5 batches, 0 drops, 35/35 IC refinements |
| L2 Synthesis | ✅ | 8 themes → 9 after S4 split; S4 distinctness gate fired on 1 pair |
| L3 Metrics | ✅ | All 18 metrics computed |
| L4 Analysis | ✅ | 3-call brief completed; config recommendations present |

---

## 3. Layer 1 — Extraction and Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | 52 | |
| Singletons | 17 (32.7%) | 🟡 vs ≤ 30% target — marginally over at N=50, expected |
| Merges | 33 | Out of 85 new candidates total |
| Drops | 0 | 🟢 Perfect span validation |
| ICs refined | 35/35 | 🟢 100% of ICs with 2+ quotes received refinement |

### Per-batch merge rates and ITS

| Batch | Segments | Candidates | Merges | Merge rate | ITS | Interpretation |
|-------|----------|-----------|--------|-----------|-----|----------------|
| 1 | 10 | 43 | 15 | 34.9% | 1.000 | Trivially 1.0 — empty codebook; acceptable |
| 2 | 10 | 14 | 7 | 50.0% | 0.200 | Rapid codebook consolidation — healthy |
| 3 | 10 | 6 | 2 | 33.3% | 0.103 | Approaching saturation; only 6 candidates — low-n instability |
| 4 | 10 | 9 | 4 | 44.4% | 0.114 | ⚠️ ITS uptick — new phenomena emerging |
| 5 | 10 | 13 | 5 | 38.5% | 0.154 | ⚠️ ITS rising further — active discovery in final batch |

**ITS trajectory**: Declining (B1→B3) then **rising** (B3→B5: 0.103→0.114→0.154) — codebook is in active growth at N=50, not approaching saturation. Both ITS and candidate count increase in B5 (13 candidates), indicating the data still contains novel phenomena. Saturation has NOT been reached.

**Merge rate trajectory**: Non-monotonic across all batches (34.9%→50.0%→33.3%→44.4%→38.5%). B3 had only 6 total candidates, making its rate statistically noisy. No clear stabilization trend visible.

### Coder reuse and stability

| Metric | Value | Status |
|--------|-------|--------|
| flagged_match (coder reuses existing IC) | 123 | |
| coder_new_comp_new | 52 | Coder and comparator agree: NEW |
| coder_new_comp_merge | 33 | Coder said NEW, comparator overrode to MERGE (flip) |
| coder_new_comp_reject | 0 | No hard rejections |
| flip_rate | 38.8% (33/85) | 🟢 Below 40% threshold — comparator overrides are acceptable |

### Confidence distribution

| Metric | Value |
|--------|-------|
| mean | 0.883 |
| SD | 0.047 |
| Q1 | 0.900 |
| Q2 (median) | 0.900 |
| Q3 | 0.900 |

The distribution is heavily compressed into the 0.8–0.9 range — IQR is effectively zero, with Q1=Q2=Q3=0.90. This suggests the model is applying a near-uniform confidence level rather than discriminating meaningfully between higher- and lower-quality extractions. This overconfidence pattern appeared in the N=30 run as well and is likely a model characteristic (Gemini Flash via OpenRouter) rather than a data issue.

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

The synthesizer proposed 8 themes in round 1. The S4 distinctness gate then detected 1 overlapping pair above the 0.80 threshold — "Traversal & World Design" ↔ "Character Progression Systems" (sim=0.809). The LLM chose to SHARPEN both rather than merge, rewriting definitions to emphasize what makes each distinct (movement/world-space mechanics vs. player-character development systems). Theme count remained at 8.

The S4 split heuristic flagged "Technical Stability & Interface" as a magnet theme (8 ICs, coherence=0.400, 5 overlapping pairs). k-means produced cluster_a=3 ICs and cluster_b=5 ICs. The LLM validated the split, yielding "UI and Control Design Friction" (3 ICs — clunky controls, animation friction, immersion-breaking parameters) and "Technical Stability and Performance" (5 ICs — bugs, glitches, performance, account prompts, multiplayer). Theme count increased to 9.

The coherence gate computed baseline=0.411; with `coherence_threshold=0.5`, the gate fires below 0.411 × 0.5 = 0.206. No theme fell below this level, so 0 themes were dissolved. The orphan reassessment pass found 0 orphaned ICs. Category synthesis targeted 3 categories.

```
Synthesizer → 8 themes
  ↓ [S4 distinctness] → 1 pair flagged, SHARPENED → 8 themes (unchanged count)
  ↓ [S4 split] → 1 theme split → 9 themes
  ↓ [Coherence gate] → 0 themes dissolved (baseline=0.411, gate floor=0.206) → 9 themes
  ↓ [Orphan pass] → 0 orphans → 9 themes final
```

### Final themes

| # | Theme | IC count | Coherence | Status |
|---|-------|----------|-----------|--------|
| 1 | Combat Mechanics & Balance | 8 | 0.514 | 🟡 below 0.55 |
| 2 | Traversal & World Design | 7 | 0.454 | 🔴 |
| 3 | Character Progression Systems | 7 | 0.526 | 🟡 below 0.55 |
| 4 | Narrative & Quest Execution | 7 | 0.516 | 🟡 below 0.55 |
| 5 | Content Value & Length | 6 | 0.514 | 🟡 below 0.55 |
| 6 | Audiovisual & Sensory Praise | 6 | 0.490 | 🔴 |
| 7 | Gameplay Flow Interruptions | 3 | 0.466 | 🔴 |
| 8 | UI and Control Design Friction | 3 | 0.390 | 🔴 weakest |
| 9 | Technical Stability and Performance | 5 | 0.471 | 🔴 |

**Mean coherence**: 0.482 (🔴 vs ≥ 0.55 guideline — no theme meets the guideline at N=50)

**Distinctness**: 14 of 36 pairs exceed 0.70 similarity (38.9%) (🔴 vs ≤ 25% guideline). Combat Mechanics & Balance is the most promiscuous theme — it overlaps with 6 other themes, reflecting its position as a cross-cutting concept in this game domain.

### Categories

```
Core Gameplay & Mechanical Systems
  → Combat Mechanics & Balance, Traversal & World Design,
    Gameplay Flow Interruptions, UI and Control Design Friction

Narrative, Progression, & Product Value
  → Character Progression Systems, Narrative & Quest Execution,
    Content Value & Length

Technical Performance & Sensory Quality
  → Audiovisual & Sensory Praise, Technical Stability and Performance
```

Intellectually defensible groupings. The three-way split between mechanics, narrative/value, and technical/sensory maps cleanly to a standard product experience framework. The decision to group Audiovisual Praise alongside Technical Stability is analytically interesting — the brief describes this as "the game looks and sounds good, but runs poorly," which is a genuine analytical observation worth surfacing to stakeholders.

---

## 5. Layer 3 — Metrics Dashboard

### Evidence quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| grounding_rate | 1.000 | ≥ 0.95 | 🟢 |
| drop_rate | 0.000 | ≤ 0.10 | 🟢 |
| extraction_density_mean | 0.475 | 0.30–0.80 | 🟢 |
| thematic_coverage | 1.000 | ≥ 0.90 | 🟢 |
| sentiment_purity_mean | 0.949 | ≥ 0.85 | 🟢 |
| cross_review_convergence | 0.673 | ≥ 0.60 | 🟢 |

### Codebook maturity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| singleton_ratio | 0.327 | ≤ 0.30 | 🟡 marginally over; expected at N=50 |
| merge_rate_final | 0.385 | 0.40–0.80 | 🟡 just below floor; non-saturated codebook |
| triage_auto_rate | 0.560 | ≥ 0.60 | 🟡 slightly under; grey-zone rate elevated |
| its_final | 0.154 | ≤ 0.05 | 🔴 |

### Theme quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | 0.482 | ≥ 0.55 | 🔴 |
| theme_distinctness_overlap | 14/36 pairs (38.9%) | ≤ 25% | 🔴 |

### Quote coverage

| Metric | Value | Note |
|--------|-------|------|
| overall_mean_pct | 11.7% | Per-IC coverage across all segments |
| overall_max_pct | 100.0% | 3 ICs with 100% coverage in their source segment |
| high_coverage_pairs (>70%) | 3 | Dense-coded ICs, not indicative of over-extraction |

Low mean coverage (11.7%) reflects a 52-IC codebook covering 50 segments — each IC only partially applies to each document, which is expected and healthy at this codebook size.

---

## 6. Layer 4 — Analyst Brief

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Interpretation |
|--------|-------|--------|-------------------|
| grounding_rate | 1.000 | 🟢 | Coder not hallucinating quote boundaries |
| drop_rate | 0.000 | 🟢 | No span position errors |
| extraction_density_mean | 0.475 | 🟢 | Healthy capture depth |
| singleton_ratio | 0.327 | 🟡 | Idiosyncratic codes likely to consolidate with more data |
| merge_rate_final | 0.385 | 🟡 | Codebook still expanding; final batch saw 13 candidates |
| triage_auto_rate | 0.560 | 🟡 | Subtle IC differences causing embedding ambiguity |
| its_final | 0.154 | 🔴 | 15% of codebook still new in final batch; upward trend |
| theme_coherence_mean | 0.482 | 🔴 | ICs within themes are semantically diverse; themes too broad |
| theme_distinctness_overlap_ratio | 14 pairs | 🔴 | Significant conceptual bleeding across themes |
| sentiment_purity_mean | 0.949 | 🟢 | Themes are tonally consistent |
| thematic_coverage | 1.000 | 🟢 | All evidence integrated into structure |
| cross_review_convergence | 0.673 | 🟢 | Most ICs confirmed across multiple documents |

### Config recommendations from Layer 4

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| auto_merge_threshold | 0.65 | 0.72 | More conservative merging to reduce overlapping themes |
| auto_new_threshold | 0.55 | 0.50 | Encourage consolidation to reduce singleton ratio |
| split_min_ics | 8 | 5 | Lower limit enables split of 5–7 IC magnet themes sooner |
| batch_size | 10 | 15 | More context per iteration to stabilise ITS and merge rates |

**Note — recommendations conflict with 2026-03-04 config changes (Anomaly A-003).** The 2026-03-04 changes moved in the *opposite* direction on auto_merge (0.72→0.65) and auto_new (0.50→0.55), motivated by earlier runs showing incorrect over-merging at high thresholds. This conflict requires a dedicated calibration test before acting on L4's suggestions. Do not apply L4's auto_merge/auto_new changes without running a head-to-head comparison.

### Brief quality assessment

The L4 brief correctly identifies the core tension: technically the data is clean (perfect grounding, full coverage), but thematically the structure is immature. The "magnet theme" framing for UI and Control Design Friction (0.390 coherence) is accurate and actionable. The brief's recommended dissolution of "Gameplay Flow Interruptions" is well-reasoned — this 3-IC theme is a catch-all that doesn't hold together conceptually. The analogy of the game "looking and sounds good but running poorly" is an effective interpretive frame for stakeholder communication.

One area where the brief overstates: it labels the overlap as "conceptual bleeding" implying a structural design problem, but at N=50 with a 52-IC codebook, high inter-theme cosine similarity is partly a scale artifact (themes share vocabulary because they all describe the same game). The overlap should be re-evaluated at N=100 before concluding the thematic structure is fundamentally flawed.

---

## 7. Structure Quality Assessment

### Categories

The three categories are mutually exclusive and collectively exhaustive within the data. A product researcher would find the split intuitive: mechanical/interaction issues, narrative/value issues, and technical/sensory quality. The grouping of "Audiovisual Praise" under Technical Performance (rather than under Content/Value) is debatable but defensible — it creates the interpretive contrast between high artistic quality and low stability performance within a single category.

### Themes

Theme names are mostly specific and clear, but three themes warrant attention. "Gameplay Flow Interruptions" is too vague — it functions as a residual bucket for ICs that didn't fit elsewhere (night mechanics, enemy scaling, immersion). "Traversal & World Design" conflates physical movement with map-level design critique, which are related but analytically separable. "Combat Mechanics & Balance" has 8 ICs spanning weapon balance, hitbox issues, stamina, enemy behavior, and animation lock — it is the codebook's thematic centre of gravity, overlapping with 6 of the other 8 themes, suggesting it needs to be split or that some of its ICs belong elsewhere.

No exact duplicates exist between themes. The "Gameplay Flow Interruptions" / "Combat Mechanics & Balance" overlap (sim=0.743) is the closest pair in the Core Gameplay category.

### ICs — spot check

| IC name | Quote sample | Alignment |
|---------|-------------|-----------|
| `parkour_mechanics_unpolished` | merged with `parkour_mechanics_improvement` AND `parkour_mechanics_praise` | ⚠️ IC absorbed opposing-sentiment evidence; definition is now dual-valence |
| `combat_mechanics_improved_difficulty` | `(max_sim=0.567)` → NEW; positive IC in a predominantly negative theme | ⚠️ Sentiment interloper in "Combat Mechanics & Balance" |
| `technical_bugs_and_glitches` | merged `coop_technical_bugs` (sim=0.695) and `technical_bugs_and_broken_systems` (sim=0.773) | ✅ Logical merges; well-scoped |
| `beast_mode_mechanic_repetitive` | merged `beast_mode_mechanic_underwhelming` (sim=0.810) | ✅ Near-synonym merge; name accurately reflects consolidated evidence |
| `unfinished_game_perception` | absorbed `game_perceived_as_dlc_with_filler` and `price_not_justified_for_content` | ✅ Correct consolidation of three overlapping value-disappointment concepts |

### Evidence — spot check

The following segment text fragments appear in the density analysis output:

- `"They make you travel five minutes to talk to someone for two"` — 100% extraction density; genuine player complaint about travel/padding structure. Plausible span.
- `"Game series has great movement and parkour mechanics. Set it"` — 99% density; positive parkour framing, absorbed into `parkour_mechanics_unpolished` — explains the dual-valence IC.
- `"The success of Dying Light came down to three components: zo"` — 11% density; analytical review structure; only specific criticisms coded rather than the full analytical frame. Expected.
- `"I hate to give this game a negative review because it DOES h"` — 12% density; nuanced hedged review; limited codeable content. Expected.

All quote fragments read as real player language. Span coverage rates are consistent with the review types (analytical/reflective reviews naturally have lower extraction density than direct-complaint reviews).

---

## 8. Testing Plan Compliance

**Testing plan used**: `docs/planning/STABILIZATION_TESTING_PLAN.md`
**Run configuration**: `--no-hil` → Phase 1.2 (50-review automated run)

| Check | Result | Notes |
|-------|--------|-------|
| Pipeline completes without errors | ✅ | All 5 layers clean |
| More ICs discovered than 30-review run | ✅ | 52 ICs vs 28 after batch 1 of this run; codebook still growing |
| Saturation curve shows progression (ITS decreasing) | ⚠️ | Partially — B1→B3 declining, then B4–B5 rising (0.103→0.114→0.154) |
| Merge rate increases across batches (codebook stabilizing) | ❌ | Non-monotonic: 34.9%→50.0%→33.3%→44.4%→38.5% — no stabilization trend |
| Layer 4 brief identifies patterns | ✅ | 4 key findings, 3 config recommendations, structural diagnostics |
| No theme has more than 15 ICs (magnet theme check) | ✅ | Max is 8 ICs (Combat Mechanics & Balance) |
| Category merge threshold: no wrong merges (sim < 0.90) | ✅ | 3 category groups, no spurious merges visible |
| S4 features fire (`[DISTINCT]`, `[SPLIT]` log lines) | ✅ | Distinctness gate: 1 pair sharpened; split gate: 1 theme split |
| Coherence gate fires on low-coherence themes | ⚠️ | Gate computed baseline=0.411; floor=0.206. No themes below floor despite 4 themes below 0.55 guideline. Gate effectively inactive at this N. |
| Reasoning log co-located with DB | ✅ | `runs/dying_light_beast_test_20260304_160945_reasoning.jsonl` (correct path) |

**Known issues manifesting in this run:**

- **Coherence gate effectively inactive at small N** — baseline coherence is low (0.411) because all themes are low-coherence at N=50; the 0.5× multiplier creates a floor too low to fire. Appeared in N=30 run too. Status: known, configuration tradeoff (gate is a safety net for genuinely weak themes, not a quality-improvement mechanism at this scale).
- **L4 config recommendations conflict with 2026-03-04 changes** — same issue as in the N=30 run. Status: unresolved, deferred to head-to-head comparison at N=100.

---

## 9. Bugs and Anomalies

### Anomaly A-001: Rising ITS in final batches (non-saturation)

**Severity**: Medium (expected at N=50, but important to document for Phase 1.3 interpretation)
**Symptom**: ITS rises from B3 (0.103) to B4 (0.114) to B5 (0.154), opposite of the saturation trajectory. B5 introduced 8 new ICs — the highest single-batch creation since B1.
**Affected components**: L1 triage, saturation assessment
**Root cause**: N=50 is simply not enough reviews to saturate this codebook. The data still contains novel phenomena (new ICs introduced as late as segment 49 of 50). This is not a pipeline bug — it is an expected finding at this scale for a game with diverse complaint categories.
**Fix needed**: No — increase sample size to N=100 (Phase 1.3). Expected that ITS will continue declining at N=100 given the nested-subset design.
**Priority**: P3 (informational)

### Anomaly A-002: Coherence gate inactive at small N

**Severity**: Low
**Symptom**: 0 themes dissolved by coherence gate despite 9/9 themes falling below the 0.55 guideline. Gate threshold is effectively 0.5 × 0.411 = 0.206.
**Affected components**: `pipeline.py` coherence gate logic, `eqd_config.yaml` `coherence_threshold`
**Root cause**: The gate multiplies `coherence_threshold` (0.5) by the observed baseline. At N=50, baseline is 0.411 (all themes are low-coherence), making the floor 0.206 — too low to ever fire. This is the same issue as the N=30 run. Setting `coherence_threshold=1.0` would restore original behaviour (gate fires below baseline), but that would dissolve most themes at this scale.
**Fix needed**: Investigation — consider whether the gate should compare to a fixed absolute floor rather than a multiplier of observed baseline, or whether the gate should be disabled below a minimum N.
**Priority**: P3

### Anomaly A-003: L4 config recommendations contradict 2026-03-04 changes

**Severity**: Low (process/documentation issue)
**Symptom**: L4 recommends `auto_merge_threshold` → 0.72 and `auto_new_threshold` → 0.50. These are the values from *before* the 2026-03-04 changes (which moved to 0.65 and 0.55 respectively, motivated by over-merging observed at the old thresholds).
**Affected components**: L4 analyst agent, `eqd_config.yaml`
**Root cause**: The analyst agent reasons from first-principles metrics (singleton ratio, merge rate) without awareness of the change history. Its recommendations are mechanically valid given the observed metrics but contradict the empirical reasoning that drove the 2026-03-04 changes.
**Fix needed**: No immediate code change — defer to Phase 1.3 head-to-head comparison. Document this conflict in STABILIZATION_TESTING_PLAN.md known issues.
**Priority**: P3

### Anomaly A-004: Dual-valence IC (`parkour_mechanics_unpolished`)

**Severity**: Low
**Symptom**: The IC `parkour_mechanics_unpolished` absorbed `parkour_mechanics_improvement` (positive) and `parkour_mechanics_praise` (positive) through auto-merge (sim 0.774 and 0.743 respectively). The resulting IC now contains both positive and negative evidence about parkour, despite the name suggesting only criticism.
**Affected components**: L1 codebook comparator, IC naming
**Root cause**: High embedding similarity between positive and negative statements about the same mechanic — the embedding space doesn't separate valence for domain-specific terms. The auto-merge threshold (0.65) is correctly set but cosine similarity doesn't capture sentiment direction.
**Fix needed**: No pipeline change needed. This is an inherent limitation of embedding-based triage for semantically related but sentiment-opposed concepts. The IC should be manually renamed during HIL review to reflect its dual-valence nature (e.g., `parkour_mechanics_mixed_reception`). Note: L3 sentiment_purity flag did NOT catch this because the flag operates at theme level, not IC level.
**Priority**: P3

---

## 10. Next Steps

1. **Run Phase 1.3 (100 reviews)** — `python scripts/run_pipeline.py data/canonical_top100.csv --no-hil --db runs/canon_100.db --save-results runs/results_canon_100.json`. Primary question: does ITS resume its decline at N=100, or does it plateau? Expected: B6–B10 should show ITS < 0.10 if the codebook is approaching maturity.

2. **Resolve L4 config recommendation conflict (Anomaly A-003)** — After Phase 1.3, run a side-by-side on N=30 using the pre-2026-03-04 thresholds (auto_merge=0.72, auto_new=0.50) vs current thresholds. Compare singleton_ratio, ITS, and theme coherence. Whichever configuration produces lower singletons AND better coherence wins.

3. **Investigate coherence gate activation at small N (Anomaly A-002)** — In `pipeline.py`, review the coherence gate threshold logic. Consider adding an absolute floor (e.g., never dissolve themes with coherence > 0.35) alongside the relative multiplier, or add a minimum-N guard (`if total_segments < 60: skip gate`). File is `src/pipeline.py`, function `_run_coherence_gate()`.

4. **Implement IC-level sentiment tracking** — The `parkour_mechanics_unpolished` dual-valence issue (Anomaly A-004) highlights a gap: sentiment_purity is only measured at theme level, not IC level. A post-refinement pass that flags ICs where >20% of their quotes are opposite-valence to the majority would catch this class of issue. Implement in `src/quality_metrics.py`.

5. **Dissolve "Gameplay Flow Interruptions" in the next HIL session** — The 3-IC theme (night mechanics, enemy scaling, immersion-breaking parameters) is conceptually incoherent and contributes to the high overlap count. Its ICs should be redistributed: `night_mechanics_interrupt_gameplay_flow` and `enemy_level_scaling_negative` → Combat Mechanics & Balance; `immersion_breaking_player_specific_parameters` → Narrative & Quest Execution.
