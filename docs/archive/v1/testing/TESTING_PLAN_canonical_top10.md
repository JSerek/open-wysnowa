# Testing Plan — canonical_top10

Dataset: `data/canonical_top10.csv`  
Reviews: 10 most-upvoted negative reviews for *Dying Light: The Beast* (votes_up range: 943–119).  
Model block: **orSmart** (`google/gemini-3-flash-preview` via OpenRouter).

---

## Run 1 — No-HIL (automated baseline)

Purpose: establish baseline codebook and metrics without human intervention.

```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv \
  --db runs/orSmart_canon10_nohil.db \
  --no-hil
```

What to record in a summary doc:
- Total ICs extracted
- Codebook size (final unique codes)
- Triage breakdown: auto-NEW / auto-MERGE / grey-zone LLM calls
- L3 metrics: ITS_final, coherence_mean, distinctness_mean
- Number of themes and categories produced
- Wall-clock runtime

---

## Run 2 — With HIL (human-in-the-loop)

Purpose: exercise all HIL decision types on a small, manageable dataset.

```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv \
  --db runs/orSmart_canon10_hil.db
```

### HIL checklist

During the L1 codebook sign-off checkpoint, exercise each decision type at least once:

| Key | Decision type | Done |
|-----|--------------|------|
| N   | Accept IC as new code | [ ] |
| M   | Manually merge IC into existing code | [ ] |
| S   | Select from multiple candidate matches | [ ] |
| R   | Reject IC candidate | [ ] |
| E   | Edit IC label before accepting | [ ] |
| Q   | Quit mid-batch (verify graceful state save) | [ ] |

After Q, re-run the same command to confirm the pipeline resumes cleanly from the saved state (or restarts from the checkpoint without data loss).

---

## Pass criteria

| Criterion | No-HIL | HIL |
|-----------|--------|-----|
| Pipeline completes without exception | ✅ required | ✅ required |
| L3 metrics written to DB | ✅ required | ✅ required |
| ITS_final computed | record value | record value |
| All 6 HIL decision types exercised | N/A | ✅ required |
| Resume after Q works | N/A | ✅ required |

---

## After both runs

Compare results:

```bash
.venv/bin/python scripts/compare_runs.py \
  runs/orSmart_canon10_nohil.db \
  runs/orSmart_canon10_hil.db
```

Record findings in `docs/testing/TEST_RUN_SUMMARY_orSmart_canon10_<date>.md`.
