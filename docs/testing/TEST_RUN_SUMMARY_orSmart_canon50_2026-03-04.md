# Test Run Summary: orSmart · canon50 · 2026-03-04

**Overall status**: PASS with caveats — Pipeline completed cleanly with zero errors; all layers produced valid output and the new config changes (comparator prompt fix, tightened triage thresholds, raised distinctness gate) behaved as designed. **Critical caveat: the run used `canonical_top30.csv` (30 reviews), not `canonical_top50.csv` as required for Phase 1.2. This is effectively a Phase 1.1 regression run, not Phase 1.2.**

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | 2026-03-04 |
| **Dataset** | `data/canonical_top30.csv` — ⚠️ 30 reviews (canonical top-30). Expected `canonical_top50.csv` for Phase 1.2. |
| **Flags** | `python scripts/run_pipeline.py data/canonical_top30.csv --no-hil --db runs/test_orSmart_canon_50.db --save-results runs/test_orSmart_results_canon_50.json` (reconstructed) |
| **Raw output** | `runs/raw_outputs/raw_output_test_04_03_orSmart_canon_50.ini` |
| **DB** | `runs/test_orSmart_canon_50.db` |
| **Results JSON** | `runs/test_orSmart_results_canon_50.json` |
| **Reasoning log** | `runs/dying_light_beast_test_20260304_152635_reasoning.jsonl` — full mode |

### Models

| Agent | Model string | Provider | Reasoning |
|-------|-------------|----------|-----------|
| `coder_agent` | `google/gemini-3-flash-preview` | openrouter | `reasoning_effort: low` |
| `codebook_comparator` | `google/gemini-3-flash-preview` | openrouter | `reasoning_effort: low` |
| `synthesizer_agent` | `google/gemini-3-flash-preview` | openrouter | model default |
| `category_agent` | `google/gemini-3-flash-preview` | openrouter | model default |
| `analyst_agent` | `google/gemini-3-flash-preview` | openrouter | model default |
| `embedding` | `text-embedding-3-small` | openai | — |

**Active config block**: `or_smart` (all agents). Config changes applied vs. prior runs (2026-03-04):
- `auto_merge_threshold`: 0.72 → 0.65
- `auto_new_threshold`: 0.50 → 0.55
- `distinctness_threshold`: 0.70 → 0.80
- `coherence_threshold`: 1.0 → 0.5
- Comparator system prompt: fixed to use actual triage thresholds (0.55/0.65) instead of stale hardcoded values (0.70/0.85)

---

## 2. Pipeline Execution Summary

All five layers completed without error. No tracebacks, no `[ERROR]` or `[CRITICAL]` lines. IC refinement ran for 29/29 eligible ICs. Layer 4 completed all 3 LLM calls. Reasoning log was created at the correct path (no double-path bug). Codebook sign-off was auto-approved (HIL disabled).

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ | 30 docs → 30 segments |
| L1 Extraction | ✅ | 3 batches, 44 ICs, 29/29 refined |
| L2 Synthesis | ✅ | 7 → 8 themes; split fired, distinctness gate skipped, coherence gate 0 fires |
| L3 Metrics | ✅ | 18 metrics computed |
| L4 Analysis | ✅ | 3/3 LLM calls complete |

---

## 3. Layer 1 — Extraction and Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | 44 | |
| Singletons | 15 (34.1%) | 🟡 above 30% target; expected at N=30 |
| Merges | 25 | |
| Drops | 0 | |
| ICs refined | 29/29 (100%) | 🟢 all eligible ICs refined |

Note: refinement runs only on ICs with 2+ quotes; 15 singletons are not eligible. 29/29 of the multi-quote ICs were refined.

### Per-batch merge rates and ITS

| Batch | Segments | Merge rate | ITS | Interpretation |
|-------|----------|-----------|-----|----------------|
| 1 | 10 | 34.1% (15/44) | 1.000 | First batch — all ICs are new by definition |
| 2 | 10 | 42.9% (6/14) | 0.216 | Codebook growing; ITS sharply declining |
| 3 | 10 | 36.4% (4/11) | 0.159 | Slight merge-rate dip; ITS still declining |

**ITS trajectory**: declining (1.0 → 0.22 → 0.16) — healthy direction. Final ITS of 15.9% is high but expected at N=30. Merge rate pattern is non-monotonic (B2 rose, B3 fell back), reflecting codebook instability at small N rather than a pipeline issue.

### Coder reuse and stability

| Metric | Value | Status |
|--------|-------|--------|
| flagged_match | 55 | Coder reused existing ICs on 55 occasions |
| new_comp_new | 44 | Coder said NEW → Comparator confirmed NEW |
| new_comp_merge | 25 | Coder said NEW → Comparator overrode to MERGE |
| flip_rate | 36.2% (25/69) | 🟢 below 40% threshold |
| Comparator LLM-embedding agreement | 79.3% (23/29 grey-zone calls) | Comparator and embedding broadly aligned |

**Triage breakdown**: 57.4% auto-decided (21 auto-NEW + 18 auto-MERGE), 29 grey-zone LLM calls, 1 empty codebook. The first run with the corrected comparator prompt (0.55/0.65 triage guidance) and tighter thresholds.

### Confidence distribution

| Metric | Value |
|--------|-------|
| mean | 0.886 |
| SD | 0.046 |
| Q1 | 0.90 |
| Q2 | 0.90 |
| Q3 | 0.90 |

⚠️ Overconfidence signature persists: IQR=0.0, Q1=Q2=Q3=0.90. Identical to prior runs. See reliability warning in `metric_reference.md` — confidence scores remain unreliable pending multi-model comparison.

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

Synthesizer proposed 7 themes in 1 round, assigning all 44 ICs. S4 distinctness revision checked pairs above the new threshold (0.80) and found none — correctly skipped. S4 split heuristic fired on "Combat Mechanics & Balance" (9 ICs, coherence=0.487, 4 overlapping pairs) and split it into two clusters. LLM approved the split. Coherence gate ran with baseline=0.409 and threshold=0.5, yielding a dissolution floor of ~0.205; no theme fell below this, so 0 themes dissolved. Orphan pass found 0 orphaned ICs. Category synthesis produced 3 categories.

```
Synthesizer → 7 themes
  ↓ [S4 distinctness] → skipped (no pairs above 0.80 threshold)
  ↓ [S4 split] → 8 themes (Combat split into Feel + Systems)
  ↓ [Coherence gate] → 0 dissolutions (floor=0.205, all above)
  ↓ [Orphan reassessment] → 0 orphans
  ↓ [Category synthesis] → 3 categories
```

### Final themes

| # | Theme | IC count | Coherence | Status |
|---|-------|----------|-----------|--------|
| 1 | Parkour & Traversal Friction | 5 | 0.490 | 🔴 below 0.55 |
| 2 | World Design & Exploration | 5 | 0.453 | 🔴 |
| 3 | Narrative & Quest Quality | 6 | 0.465 | 🔴 |
| 4 | Value & Content Scope | 6 | 0.444 | 🔴 |
| 5 | Progression & Reward Systems | 7 | 0.525 | 🟡 near threshold |
| 6 | Technical & Audiovisual Presentation | 6 | 0.399 | 🔴 weakest |
| 7 | Combat Feel and Encounter Quality | 3 | 0.529 | 🟡 |
| 8 | Combat Systems and Resource Balance | 6 | 0.504 | 🟡 |

**Mean coherence**: 0.476 (🔴 below 0.55 guideline). All themes below the 0.55 target. L4 correctly identifies this as a small-N problem — themes are broad by necessity at 30 reviews.

**Distinctness**: 13 of 28 pairs exceed 0.70 similarity (46.4%) 🔴. Highest: World Design & Exploration ↔ Progression & Reward Systems (0.791). Note: the distinctness gate threshold (0.80) was correctly not triggered — no pair exceeds 0.80 — but the thematic blurring at 0.70 level remains significant. L4 identified this as the primary structural problem.

**Ghost theme check**: ✅ all 8 themes have ≥1 IC. No ghost nodes.

### Categories

```
World Architecture & Traversal
  → Parkour & Traversal Friction, World Design & Exploration
Combat Mechanics & Engagement
  → Combat Feel and Encounter Quality, Combat Systems and Resource Balance
Narrative, Value & Technical Execution
  → Narrative & Quest Quality, Value & Content Scope, Progression & Reward Systems,
    Technical & Audiovisual Presentation
```

The first two categories are clean groupings. "Narrative, Value & Technical Execution" is a catch-all housing 4 diverse themes — L4 correctly flags this as a structural issue. The LLM placed Technical & Audiovisual here because it "supports the value proposition", but the logic is strained given the sentiment mixing in that theme.

---

## 5. Layer 3 — Metrics Dashboard

### Evidence quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| grounding_rate | 1.000 (124/124) | ≥ 0.95 | 🟢 |
| drop_rate | 0.008 (1/125) | ≤ 0.10 | 🟢 |
| extraction_density_mean | 0.413 (41.3%) | 0.30–0.80 | 🟢 |
| thematic_coverage | 1.000 (124/124) | ≥ 0.90 | 🟢 |
| sentiment_purity_mean | 0.891 | ≥ 0.85 | 🟢 |
| cross_review_convergence | 63.6% confirmed (2+ docs) | ≥ 0.60 | 🟢 |

Evidence layer is clean across all metrics. 3 high-density segments (≥0.80) and 3 low-density (<0.20) — these are structural features of the corpus (very short vs. very long reviews), not extraction failures.

### Codebook maturity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| singleton_ratio | 0.341 (34.1%) | ≤ 0.30 | 🟡 expected at N=30 |
| merge_rate_final (batch 3) | 36.4% | 0.40–0.80 | 🟡 below healthy min; codebook still growing |
| triage_auto_rate | 57.4% | ≥ 0.60 | 🟡 just below threshold |
| its_final (batch 3) | 15.9% | ≤ 0.05 | 🔴 high, but expected at N=30 |

All four maturity metrics are below target, consistent with the "immature codebook" pattern (ITS > 0.15 + singleton > 0.30 + merge < 0.40 at N=30). This is expected, not alarming.

### Theme quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | 0.476 | ≥ 0.55 | 🔴 all 8 themes below guideline |
| theme_distinctness_overlap | 13/28 pairs (46.4%) | ≤ 25% | 🔴 significant overlap |

### Quote coverage

| Metric | Value | Note |
|--------|-------|------|
| overall_mean_pct | 10.07% | Normal range (5–15%); scale confirmed correct (percentage, not fraction) |
| overall_max_pct | 100.0% | 2 ICs covering an entire segment — both are single-sentence segments |
| high_coverage_pairs (>70%) | 2 | `story_content_padded_with_filler`, `inferior_to_predecessor` — both have a 100% coverage segment; the segments are very short (76 and 229 chars) |

---

## 6. Layer 4 — Analyst Brief

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Interpretation |
|--------|-------|--------|-------------------|
| grounding_rate | 100% | 🟢 | Perfect fidelity, no span hallucination |
| drop_rate | 0.81% | 🟢 | Exceptionally low; extraction logic reliable |
| extraction_density_mean | 41.3% | 🟢 | Balanced extraction within healthy range |
| singleton_ratio | 34.1% | 🟡 | Slightly above guideline; expected at N=30 |
| merge_rate_final | 36.4% | 🟡 | Below 40% min; unstable growth pattern |
| triage_auto_rate | 57.4% | 🟡 | Just below threshold; many grey-zone decisions |
| its_final | 15.9% | 🔴 | High; codebook not yet saturated |
| theme_coherence_mean | 0.476 | 🔴 | Loose themes; possible premature synthesis |
| theme_distinctness_overlap_ratio | 13/28 (46.4%) | 🔴 | Poor differentiation; themes bleeding together |
| sentiment_purity_mean | 89.1% | 🟢 | Consistent sentiment; 1 theme flagged (Technical) |
| thematic_coverage | 100% | 🟢 | All evidence integrated |
| cross_review_convergence | 63.6% | 🟢 | Strong for N=30 |

### Config recommendations from Layer 4

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| `auto_merge_threshold` | 0.65 | 0.75 | Prevent premature merging; reduce magnet theme effect |
| `split_min_ics` | 8 | 4 | Current limit too high for 30-doc sample; allow earlier splits |
| `distinctness_threshold` | 0.80 | 0.85 | Force better theme differentiation; address 13 overlapping pairs |
| `auto_new_threshold` | 0.55 | 0.45 | Lower to encourage more specific ICs; reduce singleton ratio |

⚠️ Note: The `auto_merge_threshold` recommendation (0.65 → 0.75) conflicts with the direction taken in our 2026-03-04 config update (which lowered it from 0.72 to 0.65 on L4 recommendation from the canon-100 run). The two runs give opposing guidance — this reflects the different trade-off at N=30 vs N=100. Defer this change until Phase 1.2 (true 50-review run) provides more evidence.

⚠️ Note: The `auto_new_threshold` recommendation (0.55 → 0.45) also conflicts with the 2026-03-04 update (which raised it from 0.50 to 0.55). Same caution applies.

### Brief quality assessment

L4's diagnosis is accurate and specific. It correctly identifies Technical & Audiovisual as the weakest theme (magnet + sentiment mixing), names 5 specific action recommendations per theme, and provides a coherent overall narrative ("high technical fidelity, conceptual blurring"). The saturation assessment is honest about the insufficient sample size. The brief is actionable and would be trustworthy to a researcher who understood the N=30 limitation.

---

## 7. Structure Quality Assessment

### Categories

The first two categories (World Architecture & Traversal; Combat Mechanics & Engagement) are mutually exclusive and thematically tight. The third (Narrative, Value & Technical Execution) is a structural catch-all that bundles value perception, narrative quality, progression mechanics, and technical performance. A domain expert would likely reject this grouping. The LLM's rationale for including Technical here (it "supports the value proposition") is weak. This is a known limitation of 3-category synthesis on a 8-theme structure — one bucket will always be over-broad.

### Themes

Most themes have clear, specific names grounded in the corpus. "Progression & Reward Systems" is the strongest (coherence 0.525, 7 ICs, well-differentiated). "Technical & Audiovisual Presentation" is the weakest — it conflates negative performance feedback (`technical_performance_and_stability_issues`, `coop_technical_glitches`) with positive praise (`visual_and_technical_performance_praise`, `audio_quality_praise`, `gore_and_physics_high_quality`) and UI frustration (`ui_and_control_scheme_frustration`). This is confirmed by its 0.399 coherence and 0.583 sentiment purity. L4 recommended splitting it into Performance (negative) and Art/Sound (positive) — correct diagnosis.

### ICs — spot check

| IC name | Quote sample | Alignment |
|---------|-------------|-----------|
| `progression_and_combat_sluggishness` | "its very repetitive, combat start to get monotonous" | ✅ aligned |
| `price_not_justified_for_content_volume` | "overhyped, would refund if I could. max spend £15-£20 if youre interested" | ✅ aligned |
| `perceived_dlc_origins` | "It feels like an unfinished DLC." | ✅ aligned |
| `night_mechanics_disrupt_gameplay_flow` | "Night is a mere shadow of its old self" | ✅ — evocative, correctly coded |
| `enemy_level_scaling_immersion_breaking` | "The fact that there are area levels alone should tell you how i feel about this" | ✅ aligned; span plausible (463–594) |

All spot-checked ICs show appropriate name-to-quote alignment. Language is authentic player voice.

### Evidence — spot check

8 quotes sampled from DB. All read as real player language; no truncation artifacts; spans plausible for segment lengths. `loot_and_reward_system_dissatisfaction` sample (span 390–545, 155 chars) is a long but coherent quote about the reward system — span size is proportionate. `gore_and_physics_high_quality` (span 2238–2291, 53 chars) is a short, clean quote. No anomalies detected.

---

## 8. Testing Plan Compliance

**Testing plan used**: `docs/planning/STABILIZATION_TESTING_PLAN.md`
**Run configuration**: `--no-hil` → Phase 1 most relevant
**Critical finding**: This run used `canonical_top30.csv` instead of the required `canonical_top50.csv`. It constitutes a Phase 1.1 regression check with the new config, not Phase 1.2.

### Phase 1.1 regression checks

| Check | Result | Notes |
|-------|--------|-------|
| Pipeline completes without errors | ✅ | All layers complete, no tracebacks |
| S4 features fire (`[DISTINCT]` and `[SPLIT]` log lines) | ✅ | Distinctness skipped (no pairs above 0.80); Split fired on Combat theme |
| Layer 4 produces analytical brief | ✅ | 3/3 calls complete |
| Layer 4 brief prints to terminal | ✅ | Full brief visible in raw output |
| All 18 metrics computed | ✅ | Confirmed in raw output |
| Thematic structure has categories → themes → ICs → quotes hierarchy | ✅ | 3 categories, 8 themes, 44 ICs, 124 quotes |
| Coder reuse rate block present (all four counters) | ✅ | flagged_match=55, new_comp_new=44, new_comp_merge=25, new_comp_reject=0 |
| Coder flip rate < 40% | ✅ | 36.2% |
| Per-IC coverage block present | ✅ | overall_mean_pct=10.07%, high_coverage flagged |
| Reasoning log co-located with DB (not in `runs/runs/`) | ✅ | Path: `runs/dying_light_beast_test_20260304_152635_reasoning.jsonl` |
| No ghost themes | ✅ | All 8 themes have ≥ 1 IC |

### Phase 1.2 checks (not applicable — wrong dataset)

| Check | Result | Notes |
|-------|--------|-------|
| More ICs discovered than 30-review run | ⚪ N/A | Run is 30 reviews; comparison meaningless |
| Saturation curve shows ITS decreasing | ⚪ N/A | Same dataset as 30-review canon |
| Merge rate increases across batches | ❌ | Non-monotonic: 34.1% → 42.9% → 36.4% |
| No theme has more than 15 ICs | ✅ | Max is 7 (Progression & Reward Systems) |
| Category merge threshold: no wrong merges | ✅ | No category merges apparent |

### Known issues status

| Issue # | Status in this run |
|---------|-------------------|
| #1 (Layer 2 too passive) | Partially addressed — split fired; coherence gate still not triggering dissolutions (0 fires) |
| #2 (Low convergence confidence) | 63.6% confirmed 🟢 — improved vs. earlier runs |
| #4 (17% unassigned ICs) | 0% unassigned — thematic coverage 100% ✅ |
| #6 (Gemini Flash Lite too weak) | N/A — using or_smart (gemini-3-flash-preview) |
| #8 (Float ordinal ID leakage) | Not observed in this run |
| #9 (IC names with spaces) | Not observed in this run |
| #10 (82.5% singleton ratio) | 34.1% — significant improvement with or_smart |
| #11 (IC refinement NameError) | Not observed — fix confirmed working |
| #12 (Double runs/ path) | Not observed — fix confirmed working |

---

## 9. Bugs and Anomalies

### Anomaly A-001: Wrong dataset — run named "canon_50" used canonical_top30

**Severity**: High (for Phase 1.2 completion purposes)
**Symptom**: Raw output header reads `Dataset: data/canonical_top30.csv` and `Loaded 30 reviews`. DB and results files are named `test_orSmart_canon_50.*`, implying 50 reviews were intended. The testing plan Phase 1.2 requires `data/canonical_top50.csv`.
**Affected components**: Run configuration (CLI invocation)
**Root cause**: User ran the pipeline with the wrong dataset file. The `_50` naming in DB/results is misleading.
**Fix needed**: Re-run Phase 1.2 with `data/canonical_top50.csv` and a correctly named DB/results file.
**Priority**: P1 — Phase 1.2 is not complete until the correct dataset is used.

### Anomaly A-002: Coherence gate still not dissolving themes at N=30

**Severity**: Low
**Symptom**: `coherence_threshold: 0.5` was set to make the gate more sensitive than the old 1.0 value. With baseline=0.409, the computed dissolution floor is 0.5 × 0.409 = 0.205. The weakest theme (Technical & Audiovisual, raw=0.399) is well above this floor, so 0 themes were dissolved. The gate did not fire in this run, nor in any previous run.
**Affected components**: `src/pipeline.py` (coherence gate logic), `eqd_config.yaml` (`coherence_threshold`)
**Root cause**: The gate threshold is a multiplier on the baseline. At N=30, the baseline coherence is low (0.409), so the floor is very low (0.205). Only themes with near-zero coherence would trigger it. The gate is calibrated for larger N where baseline coherence is higher.
**Fix needed**: No immediate fix — this is expected behavior at N=30. Re-evaluate after Phase 1.3 (100 reviews) where baseline coherence should be higher. Consider documenting the expected trigger range in `metric_reference.md`.
**Priority**: P3 — informational; not blocking.

### Anomaly A-003: L4 config recommendations contradict 2026-03-04 config changes

**Severity**: Low / informational
**Symptom**: L4 recommends raising `auto_merge_threshold` to 0.75 (we just lowered it from 0.72 to 0.65) and lowering `auto_new_threshold` to 0.45 (we just raised it from 0.50 to 0.55). Opposing directional guidance from two different run scales.
**Affected components**: `eqd_config.yaml`, `docs/planning/IDEAS.md`
**Root cause**: L4 guidance is sample-size-dependent. At N=30, the codebook is immature and needs more distinct ICs (hence: higher merge threshold, lower new threshold). At N=100, the codebook was over-fragmenting (hence: lower merge threshold, higher new threshold). Both recommendations are locally correct.
**Fix needed**: No immediate action. Defer config decision until Phase 1.2 (genuine 50-review run) and Phase 1.3 provide a clearer trajectory. Document the conflict in IDEAS.md as a calibration question.
**Priority**: P3 — informational.

---

## 10. Next Steps

1. **Re-run Phase 1.2 with correct dataset** — Run `data/canonical_top50.csv` with `--db runs/orSmart_canon_50.db`. This is the only unblocked action before proceeding to Phase 1.3.

2. **Validate config changes worked as intended** — The comparator prompt fix, tightened auto_merge/auto_new thresholds, and raised distinctness_threshold all behaved correctly in this run. The 30-review result (44 ICs vs 78 in canon-100) is consistent with tighter merging. Confirm these hold at 50 reviews.

3. **Defer conflicting L4 config recommendations** — Do not act on the `auto_merge_threshold` (→0.75) and `auto_new_threshold` (→0.45) suggestions until Phase 1.2 and 1.3 data is available. Log the conflict in `docs/planning/IDEAS.md`.

4. **Investigate coherence gate calibration post-Phase 1.3** — At 100 reviews, baseline coherence should be higher and the gate may start firing. Revisit the threshold value and document expected trigger range in `metric_reference.md`.

5. **Fix Technical & Audiovisual magnet theme in HIL Phase 2** — This theme conflates technical failure (negative) with audiovisual praise (positive). At the current 30-review scale this is unavoidable automatically; the correct resolution is HIL theme editing in Phase 2 testing, or waiting for larger N where split heuristics can fire on it.

6. **Update testing plan** — Mark Phase 1.2 as attempted but not completed (wrong dataset). Note that the 2026-03-04 config changes have been validated at N=30.
