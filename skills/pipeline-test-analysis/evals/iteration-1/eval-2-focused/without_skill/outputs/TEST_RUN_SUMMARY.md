# orSmart Canon 30 Test Run Analysis
**Date:** 2026-03-03
**Config:** OpenRouter with `or_smart` model (reasoning enabled)
**Dataset:** canonical_top30.csv (30 Dying Light: The Beast reviews)
**Database:** runs/orSmart_canon_30.db
**Results:** runs/results_orSmart_canon_30.json

---

## Executive Summary

The orSmart canon 30 run completed successfully end-to-end without errors. The pipeline demonstrates **excellent technical execution** (100% grounding, 0% drop rate) but reveals **fundamental stability issues** at the conceptual level. The test surfaces critical problems with codebook maturation, theme synthesis, and the appropriateness of the 3-category hierarchy for a small, complex dataset.

**Status against Stabilization Plan Phase 1.1:**
- ✅ Pipeline completes without errors (first successful run after 2026-03-01 fixes)
- ✅ S4 features fire (distinctness revision and splitting observed)
- ✅ Layer 4 produces analytical brief with detailed diagnostics
- ✅ All 18 quality metrics computed
- ✅ Thematic structure with categories → themes → ICs hierarchy
- ⚠️ **Critical findings: High ITS (0.18), low merge rate (0.1 final), 40% singleton ratio — dataset struggling with saturation**

---

## Layer 1: IC Extraction & Codebook Quality

### Overview
- **Documents:** 30 reviews
- **Segments:** 30
- **Total candidates:** 128
- **New ICs created:** 50
- **Merged candidates:** 17
- **Rejected:** 0
- **Drop rate:** 0.0% (0/128)

### ITS (Incremental Type Saturation) Analysis

**Batch progression:**
1. **Batch 1** (segments 0-9): 31 new ICs from 45 candidates → 34/50 codebook (68%)
2. **Batch 2** (segments 10-19): 10 new ICs from 12 candidates → 44/50 codebook (88%)
3. **Batch 3** (segments 20-29): 9 new ICs from 10 candidates → 50/50 codebook (100%)

**Saturation curve analysis:**
- **50% codebook reached at:** segment 8 (26.7% of data)
- **80% codebook reached at:** segment 18 (60% of data)
- **95% codebook reached at:** segment 29 (96.7% of data)
- **100% codebook reached at:** segment 30
- **Final ITS:** 0.18 (batch 3: 2 new ICs out of 11 total)

**Assessment:** ITS of 0.18 **significantly exceeds** the 0.05 guideline, indicating the codebook has **not reached saturation**. The low merge rate in batch 3 (0.10, down from 0.31 in batch 1) combined with persistent new IC creation suggests:
1. The 30-segment dataset is **insufficient for convergence** on this complex domain
2. The coder/comparator agents are **highly prone to IC splitting** rather than recognizing equivalences
3. New concepts are emerging at the tail of the dataset (segments 25-29 had consistent new ICs)

**Stabilization Plan expectation:** Plan checks for ITS < 0.02 for 3 consecutive batches at the 100-review scale. At 30 reviews, saturation is not expected, but the high ITS suggests the embedding space is under-constrained or the similarity thresholds are mistuned.

---

### Singleton Ratio Analysis

**Result:** 40% (20 out of 50 ICs have only 1 supporting quote)

**Guideline:** Healthy max = 0.30 (30%)
**Status:** 🔴 **Investigate** — 33% higher than guideline

**Distribution:**
- Singletons: 20
- 2-quote ICs: ~13
- 3+ quote ICs: ~17 (including 1 with 8 quotes)
- Mean quotes per IC: 2.56

**Individual low-confidence IC:** Only 1 IC flagged with confidence < 0.70:
- `a92437a33aa2` (confidence 0.4) — created in segment 14, likely a borderline NEW decision that the comparator assigned low confidence

**Assessment:** The singleton ratio is **problematic** for a 30-segment run on the stabilization baseline. In the **gemini_flash_lite** canon_30 run (2026-03-01), the plan notes indicated 82.5% singleton ratio. This run's 40% is a **significant improvement**, suggesting:
1. **Comparator agent is more effective with or_smart** than with gemini_flash_lite
2. **LLM-embedding agreement on merges improved** (61.2% agreement on grey-zone calls)
3. **Auto-merge threshold of 0.72 is performing better** with the or_smart model

However, 40% singletons still indicates:
- **Over-splitting of related concepts** across documents (e.g., variant phrasings of "zombies are tanky" created separate ICs)
- **Possible semantic drift** in the embedding space or coder prompt — ICs that should cluster are not being recognized as equivalent

**Comparison to testing plan:** The plan assumes canonical datasets should show **stabilizing merge rates** (>40% in final batches). This run shows **declining merge rates** (batch 1: 31%, batch 3: 10%), which is the **inverse of expected behavior**. This suggests the codebook is still fragmenting, not consolidating.

---

### Triage Efficiency

**Auto-decided candidates:** 17 out of 66 grey-zone calls (25.8%)
**LLM calls required:** 49 out of 67 new candidates

**Breakdown:**
- `auto_new`: 6 (high-confidence NEW from similarity)
- `auto_merge`: 11 (high-confidence MERGE from similarity)
- `grey_zone`: 49 (sent to LLM for decision)
- `empty_codebook`: 1 (first segment, always new)

**Guideline:** Healthy triage auto rate ≥ 0.60 (60%)
**Status:** 🔴 **Investigate** — 25.8% vs 60% guideline is 57% **below target**

**Interpretation:** Only 1 in 4 decisions were made automatically by the embedding similarity layer. This indicates:
1. **IC definitions are poorly differentiated** — embeddings struggle to clearly separate similar-but-distinct concepts
2. **Similarity thresholds (0.50 for auto_new, 0.72 for auto_merge) are too tight** — too much ambiguity for the embedding model
3. **Codebook complexity** — even with only 50 ICs, the embedding space has significant overlap

**LLM-embedding agreement (61.2%):** On the 49 grey-zone calls, the LLM recommendation **agreed with the embedding direction** (NEW vs MERGE) 61.2% of the time. This suggests:
- **Moderate model-embedding misalignment** (below ideal >80%)
- **Embedding model has weak signal** on these borderline cases
- **LLM is making different semantic judgments** (e.g., treating subtle nuances as distinct vs equivalent)

---

## Layer 2: Theme Synthesis & Structure Quality

### Theme Overview
**Themes created:** 8 (after 1 coherence-based dissolution)
**Final theme count in output:** 7 (1 empty theme: "Technical Execution and Presentation")

**Theme sizes:**
1. **Combat Balance and Mechanical Frustrations** — 10 ICs
2. **Traversal and World Navigation** — 9 ICs
3. **Narrative Depth and Pacing** — 8 ICs
4. **Gameplay Loop and Resource Management** — 7 ICs
5. **Value and Series Standing** — 6 ICs
6. **Character Growth and Power Limitations** — 5 ICs
7. **Visceral Combat and Gore Systems** — 5 ICs
8. **Technical Execution and Presentation** — 0 ICs (dissolved)

### Coherence Analysis

**Mean theme coherence:** 0.484
**Guideline:** Healthy min = 0.55
**Status:** 🔴 **Critical** — All 7 themes **fall below 0.55 threshold**

**Per-theme coherence:**
```
Combat Balance and Mechanical Frustrations:  0.501  (weakest coherent theme)
Character Growth and Power Limitations:      0.497
Narrative Depth and Pacing:                  0.487
Gameplay Loop and Resource Management:       0.484
Traversal and World Navigation:              0.478
Visceral Combat and Gore Systems:            0.484
Value and Series Standing:                   0.457  (weakest overall)
```

**Layer 4 diagnostics identified 6 themes with issues:**

1. **"Character Growth and Power Limitations"** [WEAK_COHERENCE]
   - Mixes "UI/skill tree complaints" with "combat stamina limitations" with "beast mode mechanics"
   - Breadth spans from structural progression to minute-to-minute resource constraints
   - Suggested split: "Progression System Design" + "Combat Resource Constraints"

2. **"Traversal and World Navigation"** [MAGNET_THEME]
   - Houses map aesthetics, "soulless" environments, vehicle physics, and parkour bugs
   - "World design" and "movement mechanics" are orthogonal; forced together here
   - Suggested split: Extract "Parkour and Movement Mechanics" as standalone

3. **"Gameplay Loop and Resource Management"** [SENTIMENT_MIXED]
   - Contains 1 positive IC ("high_player_engagement_and_enjoyment") amid 6 negative ICs
   - Night mechanics + resource farming forced into one theme (distinct subsystems)
   - Suggested action: Remove positive IC; refocus on "Economy and Grind"

4. **"Combat Balance and Mechanical Frustrations"** [WEAK_COHERENCE / OVERLOADED]
   - 10 ICs spanning: UI/controls, AI behavior, weapon durability, animation locking
   - Highest coherence (0.501) but still below threshold — protected by `split_min_ics: 8`
   - Suggested split: "Technical Combat Issues" + "Combat Balancing"

5. **"Narrative Depth and Pacing"** [WEAK_COHERENCE]
   - Conflates "writing quality" with "content quantity" (filler junk)
   - Quest design and ending disappointment are structurally different from pacing
   - Contains 1 positive IC that dilutes the critique
   - Suggested split: "Content Volume and Pacing" vs "Narrative Quality and Logic"

6. **"Value and Series Standing"** [WEAKEST THEME]
   - Balances technical performance (crashes), soundtrack praise, and price-to-content
   - Completely orthogonal domains (stability ≠ music ≠ pricing)
   - Suggested action: Move performance ICs to dedicated "Stability" theme

### Theme Distinctness (Overlap Analysis)

**Mean pairwise theme similarity:** 0.720
**Guideline:** Healthy overlap ratio = 0.25 (25% of pairs > 0.70)
**Status:** 🔴 **Critical** — 11 out of 21 pairs **exceed 0.70 similarity (52%)**

**High-overlap pairs:**
```
Narrative Depth and Pacing ↔ Gameplay Loop and Resource Management:     0.837
Traversal and World Navigation ↔ Gameplay Loop and Resource Management: 0.811
Combat Balance and Mechanical Frustrations ↔ Character Growth and Power: 0.814
Narrative Depth and Pacing ↔ Character Growth and Power:                0.767
Narrative Depth and Pacing ↔ Traversal and World Navigation:            0.770
```

**Layer 4 assessment:** The synthesis into 3 categories **forced distinct themes into overlapping conceptual spaces**. Each theme contains sub-clusters that should be separate:
- "Combat" and "Character Growth" share frustration about progression scaling
- "Narrative" and "Gameplay Loop" both address content volume and grinding
- "Traversal" and "Gameplay Loop" both reference engagement/tedium

**Config issue identified:** The `coherence_threshold: 1.0` is functionally ignored because `split_min_ics: 8` **prevents splitting of themes with <8 ICs**. Since Combat (10 ICs) is the only theme exceeding this, others cannot be split despite low coherence. This is a **major bottleneck**.

### Theme Synthesis Output Quality

**Category synthesis rationale:** The synthesizer correctly identified 3 domains:
1. **"Core Gameplay Mechanics and Progression"** — Themes 1, 5, 7, 8 (moment-to-moment verbs + systems)
2. **"Narrative and Commercial Value"** — Themes 2, 3 (story quality + positioning)
3. **"Technical Execution and Sensory Impact"** — Themes 4, 6 (veneer, performance, feel)

**Layer 4 critique:** While the synthesizer's logic is sound, the **3-category target is too coarse** for 7 distinct themes. The forced clustering is causing:
- **Technical stability** to be lumped with soundtrack praise (Value theme)
- **Movement mechanics** to be bundled with environmental design (Traversal theme)
- **Positive praise** scattered across negative themes (muddying sentiment purity despite 0.94 average)

---

## Layer 3: Quality Metrics Assessment

### Technical Integrity (Strong)

**Grounding rate:** 1.0 (100% of 128 quotes validated)
**Status:** 🟢 **Healthy**
**Interpretation:** The coder agent is producing character-accurate spans with zero hallucinations. Perfect alignment indicates:
- The extraction logic is sound
- The LLM is not inventing quote boundaries
- Span validation passes all checks

**Drop rate:** 0.0% (0 of 128 candidates rejected)
**Status:** 🟢 **Healthy**
**Interpretation:** No quote spans failed offset validation. This suggests:
- The coder's character-position math is accurate
- No off-by-one or character-encoding errors
- Segment preprocessing is clean

**Extraction density mean:** 0.408 (41% of text coded)
**Status:** 🟢 **Healthy** (guideline: 0.30–0.80)
**Distribution:** median=0.348, p25=0.21, p75=0.60
**Interpretation:** Balanced extraction — neither over-verbose nor under-extracted. Three low-density segments:
- segment `21212d3a53dd`: 0.097 (only 171 of 1754 chars coded)
- segment `50df360d6225`: 0.127 (690 of 5434 chars)
- segment `f6b60bab5d2d`: 0.138 (775 of 5629 chars)

These are long reviews with short, general criticisms — the coder correctly ignored filler.

### Codebook Maturation (Problematic)

**Merge rate overall:** 25.4% (17 merges out of 67 new candidates)
**Guideline:** Healthy final batch ≥ 0.40
**Status:** 🔴 **Investigate**

**Batch-by-batch merge rate:**
```
Batch 1: 31.1% (14 merges / 45 new candidates)
Batch 2: 16.7% (2 merges / 12 new candidates)
Batch 3: 10.0% (1 merge / 10 new candidates)  ← DECLINING
```

**Interpretation:** Rather than converging (merge rate increasing), the codebook is **diverging** (merge rate decreasing). This is the **inverse of expected maturation**:
- Early batches: codebook sparse → higher novelty → more new ICs → higher merge rate of candidates
- Late batches: codebook dense → more candidates should match → merge rate should increase

Instead:
- Batch 3 merge rate (10%) is **1/3 of batch 1** (31%)
- Only **1 out of 10 final candidates** was merged
- This suggests **novel concepts are still emerging** or **similarity thresholds are too high**

**Layer 4 assessment:** "The progression (0.31 to 0.1) shows a decline in merging, which is counter-intuitive for a maturing codebook; suggests the data is still introducing novel concepts."

---

### Thematic Synthesis Quality (Moderate)

**Thematic coverage:** 1.0 (100% of 128 quotes assigned to themes)
**Status:** 🟢 **Healthy**
**Interpretation:** Zero orphaned ICs — all 50 ICs successfully integrated into thematic structure.

**Sentiment purity mean:** 0.937
**Status:** 🟢 **Healthy** (guideline ≥ 0.80)
**Theme breakdown:**
- Combat Balance: 1.00 (pure negative)
- Traversal: 1.00 (pure negative)
- Visceral: 1.00 (pure positive)
- Character Growth: 0.93 (93% negative)
- Narrative Depth: 0.95 (95% negative)
- Value: 0.76 (76% negative) — **contaminated by 3 positive and 2 neutral ICs**

**Cross-review convergence:** 60.0% (30 out of 50 ICs cited in 2+ documents)
**Status:** 🟢 **Healthy** (guideline ≥ 0.50)
**Distribution:** 38% strong convergence (3+ docs), 22% moderate (2 docs)
**Interpretation:** Most ICs represent cross-document patterns, not idiosyncratic single-review phenomena.

---

### Convergence & Stability (Warning Signals)

**IC stability (refinement change metric):** Mean = 0.8665 (very high, >0.85 is good)
**Substantially rewritten ICs:** 7 out of 30 refinement passes
**Low-stability outliers:**
```
0.7445  narrative_and_character_inconsistency       (41% change)
0.7951  technical_performance_stability_issues      (38% change)
0.8277  inferior_to_predecessor                     (35% change)
0.8278  frustrating_animation_lock_mechanics        (35% change)
0.8304  gameplay_pacing_issues                      (34% change)
```

**Interpretation:** IC refinement successfully **tightened definitions** on 5-7 concepts that were initially too broad. This is healthy — the pipeline is self-correcting over-broad extractions.

---

## Layer 4: Analytical Interpretation & Recommendations

### Key Findings (from Layer 4 Brief)

1. **Inverse relationship of merge rate and ITS:** "The declining merge rate and high ITS indicate the pipeline is encountering novel concepts faster than it can categorize them, suggesting the current 30-segment sample is insufficient for the complexity of the domain."

2. **Embedding model limitations:** "Low triage confidence (25.8%) combined with high theme overlap (11 pairs) suggests the embedding model cannot distinguish between 'Technical Performance' and 'Gameplay Mechanics' under the current threshold settings."

3. **Config bottleneck:** "The 1.0 coherence threshold is functionally ignored by the system because the 'split_min_ics' of 8 prevents the necessary partitioning of overloaded themes like 'Combat Balance' (10 ICs)."

4. **Sentiment-driven over semantic grouping:** "High sentiment purity (0.937) despite low coherence indicates that themes are being grouped by 'how the player feels' rather than 'what the player is talking about', leading to analytically thin categories."

### Configuration Recommendations (from Layer 4)

```
processing.split_min_ics:        8 → 4
  Rationale: Allow magnet themes (Combat, Traversal) to split despite high IC count

processing.auto_merge_threshold: 0.72 → 0.65
  Rationale: Low merge rate and high singleton ratio suggest threshold too restrictive

synthesis.categories:            3 → 5
  Rationale: Reduce overlap and distinctness issues by allowing tech/mech/narrative separation
```

### Immediate Next Steps (from Layer 4)

1. **Scale up:** Process additional 20–30 segments (move to canon_50 run) to stabilize codebook and drive down ITS
2. **Manual theme split:** Separate "Traversal and World Navigation" into "Movement Mechanics" + "Environmental Design"
3. **Re-tune thresholds:** Apply split_min_ics=4 and auto_merge_threshold=0.65; re-run Layer 2
4. **Purge empty nodes:** Delete "Technical Execution and Presentation"; redistribute technical ICs to new "Stability" theme

---

## Comparison to Stabilization Testing Plan

### Phase 1.1 Checklist (Canon 30)

| Check | Status | Notes |
|-------|--------|-------|
| Pipeline completes without errors | ✅ | First success after 2026-03-01 fixes (Layer 3 crash, IC refinement NameError fixed) |
| S4 features fire (DISTINCT, SPLIT) | ✅ | Distinctness fired (revised overlapping themes); splitting fired (1 coherence-based dissolution) |
| Layer 4 produces brief | ✅ | Comprehensive 3-call brief with metrics, structure, synthesis, config recommendations |
| All 18 metrics computed | ✅ | Grounding, drop rate, extraction density, IC concentration, merge rate, triage, ITS, coherence, distinctness, sentiment, coverage, convergence, stability |
| Thematic hierarchy complete | ✅ | Categories → Themes (7) → ICs (50) → Quotes (128) |
| Coder reuse rate diagnostic | ✅ | coder_flagged_match=61, coder_new_comp_new=50, coder_new_comp_merge=17, coder_new_comp_reject=0 |
| Coder flip rate note fires | ❓ | No log entry visible; threshold = 40% merge/total_new = 17/50 = 34% (below threshold, so warning suppressed) |
| Per-IC coverage stats | ✅ | Max coverage 100% (1 IC), mean 9.6%, high-coverage flag at >70% |
| Reasoning log co-located | ✅ | Found at `runs/dying_light_beast_test_20260303_[timestamp]_reasoning.jsonl` (correct location, not double-path) |

### Known Issues Check

| # | Issue | Expected Outcome | Actual Result |
|---|-------|------------------|----------------|
| 6 | Gemini Flash Lite weak for batch coder | Should switch to gemini_flash or Haiku | ✅ orSmart model used instead; structured output much cleaner |
| 7 | compute_coder_confidence() crash | Should be fixed in 00dbe2c | ✅ Run completed Layer 3 successfully |
| 8 | Float ordinal ID leakage | Should test with different model | ✅ No float ordinals observed; clean integer IDs |
| 9 | IC names with spaces | Should test with different model | ✅ No spaces in IC names; all properly slugified |
| 10 | 82.5% singleton ratio | Should improve with better model | 🔴 Actually 40% (improved!), but still above 0.30 guideline |
| 11 | IC refinement NameError | Should be fixed in c88eda3 | ✅ 30 ICs refined successfully; 7 substantially rewritten |
| 12 | Double runs/ path bug | Should be fixed in c88eda3 | ✅ Reasoning log in correct location |

---

## Data Quality & Recommendations

### Summary Assessment

**Technical Layer:** ✅ **Excellent**
- Perfect grounding, zero drop rate, reliable span extraction
- Coder agent working flawlessly with or_smart model
- No hallucinations or off-by-one errors

**Codebook Layer:** 🔴 **Problematic**
- 40% singleton ratio (goal <30%)
- Declining merge rate (31% → 10%) indicates divergence, not convergence
- Low triage auto-rate (25.8% vs 60% goal) suggests IC definitions are poorly differentiated
- High ITS (0.18 vs 0.05 goal) indicates saturation NOT reached

**Thematic Layer:** 🔴 **Unstable**
- All 7 themes below 0.55 coherence threshold (mean 0.484)
- 52% of theme pairs overlap significantly (11/21 > 0.70 similarity)
- Multiple "magnet themes" grouping orthogonal concepts
- Empty theme after redistribution (technical execution)

**Structural Synthesis:** ⚠️ **Premature**
- 3-category target forces distinct themes together
- Layer 4 recommends increasing to 5 categories
- Config bottleneck: split_min_ics=8 prevents necessary theme splits

### Root Causes

1. **Dataset complexity vs sample size:** 30 reviews of a complex game (combat, progression, narrative, technical) → too many orthogonal dimensions for 50 ICs to represent coherently

2. **Embedding space underspecification:** 25.8% auto-triage rate suggests the embedding model cannot distinguish subtle IC differences (e.g., "animation_lock" vs "hitbox_issues")

3. **Merge threshold too high:** 0.72 auto_merge_threshold prevents consolidation of legitimately similar ICs; comparator override needed 49/67 times

4. **Config mismatch:** split_min_ics=8 protects large themes (Combat=10) from splitting, but smaller themes (Character Growth=5) cannot split despite low coherence (0.497)

5. **Category count too low:** Forcing 7 themes into 3 categories creates overlap; 5 categories would allow "Technical," "Mechanical," and "Narrative" to separate cleanly

### Recommendations for Next Phase (Phase 1.2: Canon 50)

**Before running canon_50:**

1. **Lower split_min_ics to 4** — Allow fractured themes like Character Growth and Value to split
2. **Reduce auto_merge_threshold to 0.65** — Encourage codebook consolidation; rely more on comparator LLM
3. **Increase synthesis categories to 5** — Separate technical, mechanical, narrative, progression, and content/value
4. **Monitor IC stability during refinement** — Watch for over-aggressive definition changes

**Run canon_50:**

1. Expect ITS to drop (more data → more saturation)
2. Expect merge rate to stabilize or increase (50 reviews > 30)
3. Monitor singleton ratio — should drop toward 0.30 with better consolidation
4. Check if triage auto-rate improves (larger codebook → stronger signals)

**If canon_50 results are similar:**

1. Consider lowering auto_merge_threshold further (0.60)
2. Investigate whether or_smart's "reasoning: true" is causing over-differentiation
3. Test with haiku + sonnet (different models per config block) for comparison
4. Review coder prompt for emphasis on "differentiation vs consolidation"

---

## Conclusion

The **orSmart canon 30 run is technically sound but conceptually immature**. The pipeline's extraction layer works excellently, but the codebook is failing to stabilize and the thematic synthesis is forcing disparate concepts together.

**This run validates the Stabilization Plan's core insight:** 30 reviews are **insufficient for convergence** on a complex domain. The high ITS (0.18) and declining merge rate are red flags that the dataset needs to expand to 50–100 reviews before finalizing structure.

**The good news:** All critical bugs from 2026-03-01 are fixed. The pipeline runs end-to-end without errors. The or_smart model produces much cleaner structured output than gemini_flash_lite.

**The challenge ahead:** Tuning thresholds and category counts to match the dataset's actual dimensionality, and confirming that the issues observed at canon_30 resolve at canon_50 and canon_100 scales.

---

## Files Generated
- Raw output: `/sessions/relaxed-loving-bell/mnt/eqa_ai/runs/raw_outputs/raw_output_test_03_03_orSmart_canon_30.ini` (667 lines)
- Results JSON: `/sessions/relaxed-loving-bell/mnt/eqa_ai/runs/results_orSmart_canon_30.json`
- Database: `/sessions/relaxed-loving-bell/mnt/eqa_ai/runs/orSmart_canon_30.db`
- Reasoning log: `/sessions/relaxed-loving-bell/mnt/eqa_ai/runs/dying_light_beast_test_20260303_164934_reasoning.jsonl`
- Thematic structure: `/sessions/relaxed-loving-bell/mnt/eqa_ai/runs/orSmart_canon_30_thematic_structure.json`

---

*Analysis completed 2026-03-03*
