# EQD-AI Improvement Plan: 4 Fixes

## Fix 1: Theme Deduplication (filter export to latest round)

**Problem**: `export_thematic_structure()` and quality metrics query ALL themes from ALL synthesis rounds. With 3 rounds, you get 72 themes instead of 22.

**Root cause**: SQL queries use `SELECT * FROM themes` with no `WHERE round_finalised = ...` filter.

**Changes**:
- `src/db.py` — Add `ThemeRepo.get_latest_round()` method: returns `(themes, round_number)` filtered to `WHERE round_finalised = (SELECT MAX(round_finalised) FROM themes)`
- `src/pipeline.py` — Update `export_thematic_structure()` to use `get_latest_round()` instead of raw `SELECT *`
- `src/quality_metrics.py` — Update `compute_theme_coherence()` and `compute_theme_distinctness()` to use `get_latest_round()` (both currently query all themes at lines 277 and 313)

**Tests**: Add multi-round scenario test verifying only latest round themes appear in export and metrics.

---

## Fix 2: Cumulative Saturation Curve

**Problem**: Current ITS tracks `new_ics / ics_before` per batch. User wants a cumulative discovery curve: for each segment processed (x-axis), what fraction of the final codebook has been discovered (y-axis). Plottable as a CDF-like curve from 0 → 1.

**Approach**: Track which segment introduced each NEW IC during Layer 1 processing. After Layer 1 completes, compute the cumulative curve.

**Changes**:
- `src/models.py` — Add `SaturationPoint(BaseModel)`: `segment_index: int`, `cumulative_ics: int`, `total_ics: int`, `fraction: float`
- `src/orchestrator.py` — Extend `ITSTracker`:
  - Add `ic_first_seen: Dict[str, int]` mapping IC id → segment processing order index
  - Add `segment_count: int` counter incremented as segments are processed
  - New method `record_new_ic(ic_id, segment_index)` called from `_apply_new` path
  - New method `build_saturation_curve() -> List[SaturationPoint]` — after all processing, for each segment index compute cumulative discovered / final total
- `src/orchestrator.py` — In the batch loop, after `_apply_decision` returns "new", call `its_tracker.record_new_ic(ic.id, current_segment_index)`
  - Need to track a running segment index across batches
- `src/quality_metrics.py` — Add `compute_saturation_curve()` that receives the curve data and persists it
- `src/pipeline.py` — Extract curve from orchestrator after Layer 1, include in results
- `scripts/run_pipeline.py` — Display saturation summary: "95% codebook discovered by segment X of Y"

**Tests**: Test ITSTracker.build_saturation_curve() with known IC introduction sequence.

---

## Fix 3: Per-Theme Meaning Saturation

**Problem**: Meaning saturation reported as global average (`avg diversity=0.55 across 82 ICs`). User needs per-theme values.

**Approach**: After computing per-IC diversity (existing logic), aggregate to theme level by averaging IC diversities within each theme.

**Changes**:
- `src/quality_metrics.py` — Refactor `compute_meaning_saturation()`:
  - Extract `_compute_ic_diversity(quotes, embeddings) -> float` helper (reusable)
  - Keep existing per-IC computation
  - Add new `compute_meaning_saturation_per_theme() -> Dict[str, Dict]` that:
    1. Gets latest-round themes (uses Fix 1's `get_latest_round()`)
    2. For each theme, gets its ICs, looks up their per-IC diversity scores
    3. Returns `{theme_name: {avg_diversity, ic_count, ic_diversities: [{ic_name, diversity}]}}`
  - Persist per-theme metric with `entity_type="theme"`
- `scripts/run_pipeline.py` — Display per-theme meaning saturation instead of global average

**Tests**: Theme with 2 ICs of known diversity → verify average computed correctly.

---

## Fix 4: Category Layer (Categories → Themes → ICs → Quotes)

**Problem**: No hierarchical grouping above themes. 22 themes need higher-order categories like "Parkour", "Combat", "Story", "UX".

**Approach**: Post-synthesis LLM pass that groups final themes into 4-8 categories. Uses theme centroids (already computable from IC embeddings) for context, but delegates grouping to LLM for meaningful naming.

**Changes**:
- `src/models.py` — Add:
  - `Category(BaseModel)`: id, name, definition, created_at
  - `CategoryTheme(BaseModel)`: category_id, theme_id, assigned_at
  - `CategoryProposal(BaseModel)`: name, definition, constituent_theme_names (LLM response model)
  - `CategorySynthesisOutput(BaseModel)`: categories: List[CategoryProposal]
- `src/db.py` — Add:
  - Schema: `categories` table + `category_themes` junction table
  - `CategoryRepo`: insert, get_all, assign_theme, get_themes_for_category
- `src/prompts.py` — Add `build_category_system_prompt()` and `build_category_user_prompt(themes_data)`
- `src/category_agent.py` (NEW) — `CategoryAgent`:
  - `synthesize(themes) -> List[CategoryProposal]`: single LLM call with all theme names + definitions + IC counts
  - `persist(proposals, themes) -> List[Category]`: save to DB with junction records
  - Uses haiku model (simple grouping task, doesn't need sonnet)
- `src/pipeline.py` — After Layer 2 synthesis, run CategoryAgent on final themes
- `src/pipeline.py` — Update `export_thematic_structure()` to return `{categories: [{name, definition, themes: [{...existing structure}]}]}`
- `eqd_config.yaml` — Add `category_agent` model config
- `scripts/run_pipeline.py` — Display category hierarchy in console output

**Tests**: Test CategoryAgent with mocked LLM, test export hierarchy structure.

---

## Implementation Order

1. **Fix 1** (theme dedup) — prerequisite for Fixes 3 and 4
2. **Fix 3** (per-theme meaning saturation) — depends on Fix 1's `get_latest_round()`
3. **Fix 2** (cumulative saturation curve) — independent, modifies orchestrator
4. **Fix 4** (category layer) — largest change, new agent + DB tables

## Files Modified

| File | Fix 1 | Fix 2 | Fix 3 | Fix 4 |
|------|-------|-------|-------|-------|
| src/models.py | | ✓ | | ✓ |
| src/db.py | ✓ | | | ✓ |
| src/orchestrator.py | | ✓ | | |
| src/quality_metrics.py | ✓ | ✓ | ✓ | |
| src/pipeline.py | ✓ | ✓ | ✓ | ✓ |
| src/prompts.py | | | | ✓ |
| src/category_agent.py | | | | ✓ (NEW) |
| eqd_config.yaml | | | | ✓ |
| scripts/run_pipeline.py | | ✓ | ✓ | ✓ |
| tests/ | ✓ | ✓ | ✓ | ✓ |
