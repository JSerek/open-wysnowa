# Test Run Summary: orSmart · Canon-30 · 2026-03-03

**Status**: PASS with caveats — three bugs found, no crashes, Layer 4 complete

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | 2026-03-03 |
| **Dataset** | `data/canonical_top30.csv` — 30 most-upvoted negative reviews, Dying Light Beast |
| **Flags** | `--no-hil --db runs/orSmart_canon_30.db --save-results runs/results_orSmart_canon_30.json` |
| **Raw output** | `runs/raw_outputs/raw_output_test_03_03_orSmart_canon_30.ini` |
| **DB** | `runs/orSmart_canon_30.db` |
| **Results JSON** | `runs/results_orSmart_canon_30.json` |

### Models (all agents → `or_smart`)

| Agent | Model | Provider | Reasoning |
|-------|-------|----------|-----------|
| `coder_agent` | `google/gemini-3-flash-preview` | OpenRouter | `reasoning_effort: low` |
| `codebook_comparator` | `google/gemini-3-flash-preview` | OpenRouter | `reasoning_effort: low` |
| `synthesizer_agent` | `google/gemini-3-flash-preview` | OpenRouter | model default |
| `category_agent` | `google/gemini-3-flash-preview` | OpenRouter | model default |
| `analyst_agent` | `google/gemini-3-flash-preview` | OpenRouter | model default |
| `embedding` | `text-embedding-3-small` | OpenAI | — |

Config alias: `or_smart` → `openrouter` provider, `reasoning: true`, `reasoning_style: openai`.

---

## 2. Pipeline Execution Summary

All four layers completed without crashes or fatal errors.

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ PASS | 30 segments loaded |
| L1 Extraction | ✅ PASS | 3 batches × 10 segments; IC refinement active |
| L2 Synthesis | ⚠️ PASS w/ bug | Empty theme node persists after coherence gate |
| L3 Metrics | ⚠️ PASS w/ bug | Quote coverage stored as fraction, not % |
| L4 Analysis | ✅ PASS | 3/3 analyst calls completed; brief produced |

---

## 3. Layer 1 — Extraction & Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | 50 | |
| Singletons (1 quote only) | 20 (40%) | ↓ from 82.5% in prior run — major improvement |
| Merges | 17 | |
| Drops | 0 | |
| ICs refined | 30/30 | IC refinement confirmed WORKING (was silently failing) |

### Merge rate across batches

| Batch | Merge rate | Interpretation |
|-------|-----------|----------------|
| 1 | 31% | Codebook forming |
| 2 | 17% | Growth slowing |
| 3 | 10% | Still well above saturation floor |

Overall merge rate: **25.4%**. Declining trajectory is expected, but final batch rate of 10% is low — codebook not mature at 30 reviews.

### ITS (Incremental Thematic Saturation)

| Batch | ITS | Threshold |
|-------|-----|-----------|
| 1 | 1.00 | — |
| 2 | 0.244 | — |
| 3 | 0.180 | < 0.05 (target) |

**Not saturated.** ITS=0.18 means 18% of ICs in the final batch were new concepts. This is expected for 30 reviews — the dataset is too small to saturate this corpus. Need ~80–100 reviews minimum, estimated.

### Coder reuse / stability

| Metric | Value | Flag |
|--------|-------|------|
| flagged_match | 61 | Coder is actively reusing existing ICs |
| flip_rate | 25.4% | ✅ Below 40% warning threshold |

Reuse tracking is working. Flip rate is acceptable.

### Confidence distribution

| Metric | Value | Note |
|--------|-------|------|
| mean | 0.872 | |
| SD | 0.08 | Very narrow |
| Q1–Q3 | 0.85–0.90 | Heavily clustered at 0.9 |

Distribution is suspiciously narrow — almost all ICs land at 0.85–0.90. This may reflect the model's tendency to output near-uniform high-confidence scores rather than genuine discriminative calibration. Flag for future investigation.

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

```
Synthesizer proposes 7 themes
  ↓
[S4 Distinctness] "Core Gameplay Loop Experience" merged/removed (overlap > 0.70)
  ↓
[S4 Splits] 2 themes split → 9 themes total
  ↓
[Coherence gate] "Technical Execution and Presentation" dissolved → 8 themes
  ↓
[BUG] Empty theme node not deleted → 7 functional themes + 1 empty ghost = 8 in DB
```

### Final theme structure (7 functional)

| # | Theme | IC count | Coherence |
|---|-------|----------|-----------|
| 1 | Progression and Reward System Failures | 8 | 0.50 |
| 2 | Gameplay Identity and Design Direction | 7 | 0.48 |
| 3 | Combat System Deficiencies | 6 | 0.49 |
| 4 | Narrative and World Design Shortcomings | 7 | 0.51 |
| 5 | Enemy Design and AI Behavior | 5 | 0.46 |
| 6 | Content Value and Player Experience | 8 | 0.52 |
| 7 | Parkour and Movement System | 4 | — |
| ~~8~~ | ~~Technical Execution and Presentation~~ | ~~0~~ | ~~(ghost)~~ |

Average coherence: **0.484** — below the 0.55 guideline. All themes are below threshold. Themes exist but are semantically diffuse.

### Distinctness

11 of 21 theme pairs exceed 0.70 centroid similarity. S4's distinctness revision reduced some pairs (merged "Core Gameplay Loop Experience"), but substantial overlap persists. Config tuning recommended.

### Categories

```
Core Gameplay Mechanics and Progression
Narrative and Commercial Value
Technical Execution and Sensory Impact
```

3 categories for 7 functional themes — Layer 4 flagged this as too few; recommends 5. Category "Technical Execution and Sensory Impact" references the dissolved ghost theme, which is semantically misleading.

---

## 5. Layer 3 — Metric Dashboard

### Evidence quality

| Metric | Value | Guideline | Status |
|--------|-------|-----------|--------|
| grounding_rate | 1.00 | ≥ 0.95 | ✅ |
| drop_rate | 0.00 | ≤ 0.15 | ✅ |
| extraction_density_mean | 0.408 | 0.30–0.80 | ✅ |
| thematic_coverage | 1.00 | ≥ 0.90 | ✅ |
| sentiment_purity_mean | 0.937 | ≥ 0.80 | ✅ |
| cross_review_convergence | 0.60 | ≥ 0.50 | ✅ |

Evidence grounding, coverage, and cross-document convergence are all healthy. The coder is extracting real quotes, not hallucinating spans.

### Codebook maturity

| Metric | Value | Guideline | Status |
|--------|-------|-----------|--------|
| singleton_ratio | 0.40 | ≤ 0.30 | 🟡 |
| merge_rate_final | 0.10 | 0.40–0.80 | 🔴 |
| triage_auto_rate | 0.258 | ≥ 0.60 | 🔴 |
| its_final | 0.18 | ≤ 0.05 | 🔴 |

Codebook is not mature. Expected at 30 reviews — data volume too low. Triage auto-rate is low, indicating many grey-zone decisions that fell to the LLM comparator.

### Theme quality

| Metric | Value | Guideline | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | 0.484 | ≥ 0.55 | 🟡 |
| theme_distinctness_overlap_ratio | 11/21 pairs | ≤ 0.25 | 🔴 |

Theme coherence is below guideline. Distinctness is significantly out of spec. S4's refinement pass helped (removed one highly-overlapping theme, split two) but the underlying issue is that 30 reviews produce semantically broad ICs that cluster loosely.

### Quote coverage

| Metric | Value (stored) | Actual % |
|--------|---------------|----------|
| overall_mean | 0.096 | 9.6% |
| overall_max | 1.000 | 100% |

**Note**: Values stored as 0-1 fractions in JSON but displayed as % in terminal. Raw output shows 9.6% / 100% correctly — JSON summary has a scale inconsistency (see Bug #2).

---

## 6. Layer 4 — Analyst Brief

3 of 3 analytical calls completed. Brief produced with theme-level findings.

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Flag |
|--------|-------|--------|----------|
| grounding_rate | 1.0 | 🟢 Healthy | — |
| drop_rate | 0.0 | 🟢 Healthy | — |
| extraction_density_mean | 0.408 | 🟢 Healthy | — |
| singleton_ratio | 0.40 | 🟡 Above ceiling | High — IC evidence thin |
| merge_rate_final | 0.10 | 🔴 Below floor | Codebook still growing |
| triage_auto_rate | 0.258 | 🔴 Below floor | Many grey-zone decisions |
| its_final | 0.18 | 🔴 High | Not saturated |
| theme_coherence_mean | 0.484 | 🟡 Below floor | Themes diffuse |
| theme_distinctness_overlap_ratio | 11 pairs | 🔴 High | Excessive overlap |
| sentiment_purity_mean | 0.937 | 🟢 Healthy | — |
| thematic_coverage | 1.0 | 🟢 Healthy | — |
| cross_review_convergence | 0.60 | 🟢 Healthy | — |

### Config recommendations from Layer 4 analyst

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| `split_min_ics` | 8 | 4 | 7 themes have 4–8 ICs; threshold too high |
| `auto_merge_threshold` | 0.72 | 0.65 | Reduce grey-zone comparator load |
| `synthesis.categories` | 3 | 5 | 3 categories too coarse for 7 themes |

---

## 7. Design Validation Findings

### What is working ✅

| Feature | Result |
|---------|--------|
| IC refinement | ✅ 30/30 ICs refined with substantive improvements (was silently failing — now confirmed FIXED) |
| S4 distinctness revision | ✅ Merged "Core Gameplay Loop Experience"; flagged overlapping pairs |
| S4 split heuristic | ✅ 2 themes split; LLM validation approved both |
| Coherence gate | ✅ Dissolved below-threshold theme |
| Reasoning log | ✅ Co-located with DB (`runs/` directory), not in `runs/runs/` (fix confirmed) |
| Grounding validation | ✅ 128/128 quotes grounded — zero hallucinated spans |
| Coder reuse tracking | ✅ All 4 counters present and non-zero |
| Layer 4 completion | ✅ All 3 analyst calls returned; brief coherent |
| --no-hil flag | ✅ No HIL prompts fired |

### What needs attention ⚠️

| Area | Observation |
|------|-------------|
| Coherence | All 7 themes below 0.55 — expected at N=30 but worth tracking |
| Confidence distribution | Near-uniform clustering at 0.85–0.90 — not calibrated |
| ITS | 0.18 final — not saturated; correct for small sample but needs ~3× data |
| Category count | 3 categories too coarse per Layer 4; `synthesis.n_categories` tuning needed |

---

## 8. Bugs Found

### Bug #1 — Empty theme node persists after coherence gate dissolution (CRITICAL)

**Symptom**: `meaning_saturation last_seg = -1` for "Technical Execution and Presentation". Theme appears in DB with 0 ICs, 0 quotes, and is displayed in Layer 3 output.

**Root cause**: `_apply_dissolution()` or the persistence layer redistributes a dissolved theme's ICs but does not delete the empty theme node from the DB.

**Downstream effects**:
- Ghost theme in DB skews theme count (8 vs 7 functional)
- `meaning_saturation` crashes / returns -1 for empty theme
- Category references dissolved theme misleadingly
- Layer 4 may analyze an empty theme

**Fix needed in**: `src/synthesizer_agent.py` → theme persistence / dissolution cleanup. After redistribution, delete theme rows with 0 ICs.

**Priority**: High

---

### Bug #2 — Quote coverage stored as fraction, displayed as percent (MINOR)

**Symptom**: `results_orSmart_canon_30.json` → `quote_coverage.overall_mean = 0.096`, `overall_max = 1.0`. Terminal output correctly shows "9.6% / 100%".

**Root cause**: Metric computation stores raw ratio (0.0–1.0) in JSON summary, while display layer multiplies by 100. Inconsistency between storage and display representation.

**Fix needed in**: Layer 3 metric serialization — either store as percentage (multiply × 100 before writing to JSON) or document explicitly that values are 0–1 fractions.

**Priority**: Low (cosmetic, correct in display)

---

### Bug #3 — ~~`meaning_saturation.last_segment_index` not serialized to JSON~~ FALSE ALARM

**Original diagnosis**: `last_segment_index` key not found in `results.json`.

**Correction**: The field IS serialized — it is stored as `last_ic_segment` (not `last_segment_index`). The previous analysis queried the wrong key. `meaning_saturation_per_theme[theme_name]["last_ic_segment"]` is present and correct for all themes.

The `-1` value observed for "Technical Execution and Presentation" is a downstream symptom of Bug #1 (empty theme has no ICs, so `max(seg_indices)` is called on an empty list and falls back to `-1`). Deleting the ghost theme node (Bug #1 fix) eliminates this entirely.

**No code change needed.**

---

## 9. Comparison to Prior Run

| Metric | Prior run (gemini_flash_lite, direct) | This run (gemini-3-flash-preview, OpenRouter) | Change |
|--------|---------------------------------------|-----------------------------------------------|--------|
| Active ICs | ~40 | 50 | +25% |
| Singleton ratio | 82.5% | 40% | ↓ 42pp — major improvement |
| IC refinement | BROKEN (silent fail) | WORKING (30/30) | Fixed |
| Crashes | IC refinement NameError | None | Fixed |
| Grounding | N/A | 100% | |
| Thematic coverage | N/A | 100% | |

Model quality has a substantial impact on IC diversity. The switch from `gemini_flash_lite` to `gemini-3-flash-preview` (via OpenRouter) improved singleton ratio from 82.5% → 40%, suggesting the stronger model creates more differentiated ICs that attract evidence from multiple reviews.

---

## 10. Testing Plan Checklist (Phase 1.1 relevant items)

| Check | Result |
|-------|--------|
| All layers complete without crash | ✅ |
| IC count reasonable (>15) | ✅ 50 |
| Singleton ratio < 80% | ✅ 40% |
| Merge rate > 0 | ✅ 25.4% |
| Grounding > 0.95 | ✅ 1.0 |
| Drop rate < 0.15 | ✅ 0.0 |
| Layer 4 completes | ✅ 3/3 |
| IC refinement active | ✅ 30/30 |
| Coder reuse counters present & non-zero | ✅ |
| Flip rate < 40% | ✅ 25.4% |
| Reasoning log co-located with DB | ✅ |
| No HIL prompts in --no-hil run | ✅ |
| Empty theme cleanup after coherence gate | ❌ Bug #1 (fixed) |
| Quote coverage JSON scale correct | ❌ Bug #2 (fixed) |
| last_ic_segment in JSON | ✅ present (Bug #3 was false alarm — wrong key searched) |

---

## 11. Next Steps

1. **Fix Bug #1** (empty theme node): highest priority — affects DB integrity and downstream metrics
2. **Re-run at larger scale** (80–100 reviews): ITS=0.18 indicates the codebook is not mature; need more data to reach the 0.05 saturation floor
3. **Tune config per Layer 4 recommendations**: `split_min_ics: 4`, `auto_merge_threshold: 0.65`, `n_categories: 5`
4. **Fix Bug #2 and #3** (minor): quote coverage scale, last_seg serialization
5. **Investigate confidence distribution**: why are nearly all ICs at 0.85–0.90?
