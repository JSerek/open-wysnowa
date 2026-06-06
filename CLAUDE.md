# EQD-AI — Project Context for Claude Code

## What this project is

EQD-AI is a qualitative research pipeline that turns raw text reviews (currently: Steam game reviews) into a structured thematic codebook with analytical interpretation. It implements a grounded theory–style workflow: extract initial codes (ICs) → build a codebook via comparator triage → synthesize themes → compute quality metrics → generate an analyst brief.

The pipeline has 5 layers:
- **L0** — preprocessing (segmentation)
- **L1** — IC extraction + codebook building (coder agent + comparator triage)
- **L2** — theme synthesis (synthesizer + S4 gates: distinctness revision, split heuristic, coherence gate, orphan pass, category synthesis)
- **L3** — quality metrics (18 metrics: grounding, ITS, coherence, distinctness, convergence, etc.)
- **L4** — analytical interpretation (3-call analyst brief)

HIL (human-in-the-loop) checkpoints exist after L1 codebook sign-off and after L2 category sign-off. `--no-hil` skips both.

---

## Active model config

Block: **orSmart** (in `eqd_config.yaml` under `agents:`)

| Agent | Model | Provider |
|-------|-------|----------|
| coder_agent | `google/gemini-3-flash-preview` | OpenRouter |
| codebook_comparator | `google/gemini-3-flash-preview` | OpenRouter |
| synthesizer_agent | `google/gemini-3-flash-preview` | OpenRouter |
| analyst_agent | `google/gemini-3-flash-preview` | OpenRouter |
| embedding | `text-embedding-3-small` | OpenAI |

Requires `OPENROUTER_API_KEY` in `.env`. Run with `.venv/bin/python`.

---

## Key thresholds (as of 2026-03-04)

```yaml
processing:
  auto_new_threshold: 0.55       # was 0.50 before 2026-03-04
  auto_merge_threshold: 0.65     # was 0.72 before 2026-03-04
  distinctness_threshold: 0.80   # was 0.70 before 2026-03-04
  coherence_threshold: 0.5       # multiplier on observed baseline
  cat_merge_sim_threshold: 0.90  # ⚠️ needs raising to 0.95 — see open issues
```

Triage logic: sim < 0.55 → auto-NEW, sim > 0.65 → auto-MERGE, 0.55–0.65 → grey zone → LLM comparator call.

---

## Canonical test datasets

All stabilization runs use the same nested subsets from `dying_light_beast_negative_full.csv`, sorted by `votes_up` descending. 30 ⊂ 50 ⊂ 100.

```
data/canonical_top30.csv    # top 30 most-upvoted negative reviews
data/canonical_top50.csv    # top 50
data/canonical_top100.csv   # top 100 (votes range: 943–9)
```

---

## Testing status

**Phase 1 (automated baseline, no-HIL): COMPLETE as of 2026-03-04**

| Run | Dataset | DB | ITS_final | Status |
|-----|---------|-----|-----------|--------|
| orSmart_canon_30 | canonical_top30 | runs/orSmart_canon_30.db | — | ✅ |
| orSmart_canon_50_test2 | canonical_top50 | runs/orSmart_canon_50.db | 0.154 🔴 | ✅ |
| orSmart_canon_100_test2 | canonical_top100 | runs/orSmart_canon_100_test2.db | 0.029 🟢 | ✅ SATURATED |

Test summaries: `docs/testing/TEST_RUN_SUMMARY_*.md`

**Phase 2 (HIL testing): NOT STARTED**

Next command to run:
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top30.csv --db runs/canon_hil.db
```

HIL checklist (per `docs/planning/STABILIZATION_TESTING_PLAN.md` §2.1) — must exercise each decision type:
- [ ] N — accept new IC
- [ ] M — manual merge
- [ ] S — select from multiple matches
- [ ] R — reject candidate
- [ ] E — edit before accepting
- [ ] Q — quit mid-batch (graceful handling)

---

## Open issues (before Phase 2)

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | `cat_merge_sim_threshold = 0.90` too permissive → N=100 produced 2 categories instead of 3 | P2 | Raise to `0.95` in `eqd_config.yaml` |
| 2 | Coherence gate inactive at small N — floor = 0.5 × baseline (~0.20) never fires | P3 | Investigate absolute floor vs relative multiplier in `pipeline.py` |
| 3 | L4 config recommendations conflict with 2026-03-04 threshold changes | P3 | Head-to-head comparison test before acting |
| 4 | Comparator LLM-embedding agreement declining with scale (N=30: 79% → N=50: 62% → N=100: 56%) | P3 | Monitor; no action until < 50% |
| 5 | merge_rate_final_batch 🔴 flag misleading when n_candidates < 5 | P4 | Add guard in L4 prompt |

---

## Key source files

```
src/
  pipeline.py            # orchestrator, all layer calls
  codebook_comparator.py # embedding triage + LLM grey zone
  reasoning_log.py       # extract_reasoning() + ReasoningLogger
  quality_metrics.py     # L3 — all 18 metrics
  hil.py                 # terminal HIL UI (untested in Phase 1)
scripts/
  run_pipeline.py        # CLI entrypoint
  compare_runs.py        # cross-run comparison (Phase 1.4, not yet run)
tests/
  test_codebook_comparator.py   # triage path tests (production thresholds 0.55/0.65)
  test_reasoning_log.py         # 16 tests, full provider format coverage
  test_config.py                # active model: google/gemini-3-flash-preview
  test_prompts.py               # threshold assertions: 0.65/0.55
docs/
  planning/STABILIZATION_TESTING_PLAN.md  # the test plan
  testing/                                # run summaries
  IDEAS.md                               # backlog (token tracking = [ready])
```

---

## Running tests

```bash
.venv/bin/python -m pytest tests/ -v
```

All tests green as of commit `a18889d` (2026-03-04).

---

## Notes on the domain

The test dataset is negative Steam reviews for *Dying Light: The Beast*. The thematic complaints cluster around: combat mechanics, parkour/traversal, character progression, narrative quality, content value/price, technical bugs, and a positive "redeeming elements" counter-theme. This is useful context when evaluating theme names and coherence scores.
