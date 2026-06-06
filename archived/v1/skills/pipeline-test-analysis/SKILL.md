---
name: pipeline-test-analysis
description: >
  Use this skill whenever the user wants to analyze, document, or review the
  results of an EQD-AI pipeline test run. Triggers include any mention of
  analyzing a pipeline run, reviewing test output, checking if a test passed,
  writing a test result summary, or any request that involves a raw output file
  (.ini, .txt, .log) from the EQD-AI pipeline together with a .db or .json
  results file. Also trigger when the user says things like "I just ran the
  pipeline", "let's document this run", "check the test results", or "analyze
  the output against our testing plan". This skill enforces a standardized,
  reproducible analysis process — always use it rather than improvising.
---

# EQD-AI Pipeline Test Analysis

## Purpose

This skill standardises how every pipeline test run is analysed and documented.
It produces a consistent, traceable test result summary that:
- confirms what ran, how, and on what data
- interprets layer-by-layer metrics against defined thresholds
- checks design intent against the active testing plan
- logs any bugs or anomalies in a structured format
- delivers a permanent, comparable record in `docs/testing/`

A single run analysis is self-contained. Never compare against other runs in
the same document — cross-run comparisons belong in a separate comparative
analysis.

---

## Step 0 — Gather Inputs

Before touching any files, ask the user for these three things. Use
`AskUserQuestion` so the answers are collected cleanly before work begins.

**Required:**
1. **Raw output file path** — the `.ini` / `.txt` / `.log` file saved during
   the run. Naming may vary (e.g. `raw_output_test_03_03_orSmart_canon_30.ini`).
2. **Testing plan file path** — the Markdown file whose checklist this run
   should be evaluated against (e.g.
   `docs/planning/STABILIZATION_TESTING_PLAN.md`). Do not assume a default;
   there may be multiple plans.

**Optional (confirm or override):**
3. **Config file path** — defaults to `eqd_config.yaml` at the project root.
   Ask only if the user mentions an alternate config.

**Derived paths (confirm before using):**
Once you have the raw output filename, derive the sibling artifacts by
convention:
- `.db` → `runs/<stem>.db`  (e.g. `runs/orSmart_canon_30.db`)
- `.json` → `runs/results_<stem>.json`  (e.g. `runs/results_orSmart_canon_30.json`)

Confirm with the user before proceeding if the actual paths differ from these
conventions.

---

## Step 1 — Pre-flight: Verify Artifacts

Check that every required file exists and is non-empty **before** starting any
analysis. A partial run produces misleading metrics — catching it here saves
time.

| Artifact | Required | Check |
|----------|----------|-------|
| Raw output file | ✅ | Exists, > 0 bytes, > 50 lines |
| Config YAML | ✅ | Exists, readable |
| Testing plan | ✅ | Exists, readable |
| Results JSON | ✅ | Exists, valid JSON (python -c "import json; json.load(open(...))")  |
| Database file | ✅ | Exists, SQLite (file --brief should say "SQLite 3.x") |

If any required artifact is missing or corrupt, **stop and tell the user**
before proceeding. Do not attempt analysis on incomplete data.

---

## Step 2 — Config Extraction

Read the config YAML and the header section of the raw output (first ~50 lines
typically contain the startup banner). Extract and record:

| Item | Source | What to capture |
|------|--------|-----------------|
| Model alias per agent | `eqd_config.yaml` | Alias → provider → model string |
| Actual model strings | Config `models:` block | e.g. `google/gemini-3-flash-preview` |
| Provider | Config | e.g. `openrouter`, `openai`, `anthropic` |
| Dataset file | Raw output or CLI args | Filename + brief description if known |
| Number of segments | Raw output | e.g. "30 segments loaded" |
| Run flags | Raw output CLI banner | All flags used, reconstruct the full command |
| HIL mode | Flags | `--no-hil` / `--hil` / default |
| DB path | Flags | Exact path |
| Results JSON path | Flags | Exact path |
| Reasoning log | Raw output | Path and mode (`full` / `failures_only` / off) |

Reconstruct the **exact CLI command** as it would need to be typed to reproduce
the run. This is the reproducibility anchor.

---

## Step 3 — Pipeline Integrity Check

Read the raw output top-to-bottom. Before interpreting any metrics, confirm the
run completed fully.

**Check for:**
- All four layers present in the output (Layer 0 / 1 / 2 / 3 / Layer 4)
- No Python tracebacks or unhandled exceptions
- No agent calls that returned 0 outputs when > 0 were expected
- No `[ERROR]` or `[CRITICAL]` log lines
- Layer 4 called the expected number of times (should match number of categories)
- IC refinement ran (look for "refined" count in Layer 1 summary)
- Reasoning log created at expected path (not in `runs/runs/`)

If any integrity check fails, flag it prominently at the top of the summary
document as a **run integrity issue** before proceeding with metric analysis.
Metrics from a partially-completed run are unreliable.

---

## Step 4 — Layer-by-Layer Analysis

**Reading order:** Raw output first (narrative context), then JSON (metric
verification), then DB only for structural anomalies or counts the JSON doesn't
expose.

Before reading metrics, load the metric reference:
📄 `skills/pipeline-test-analysis/references/metric_reference.md`

This file contains threshold tables, interpretation guidance, and the "why"
behind each metric. Consult it throughout the analysis — do not rely on
training-time memory for thresholds, as they evolve.

### Layer 1 — Extraction and Codebook

From raw output, capture:
- Total ICs extracted, merges, drops
- Singleton count and ratio
- Per-batch merge rates (Batch 1 / 2 / 3 …)
- ITS per batch (final ITS is most important)
- IC refinement count (n refined / n total)
- Coder reuse counters (flagged_match, flip_rate)
- Confidence distribution (mean, SD, Q1/Q3)

Interpret each metric against the thresholds in `metric_reference.md`. Use the
🟢 / 🟡 / 🔴 convention consistently. Note the trajectory (e.g. "merge rate
declining across batches as expected") not just the value.

**Key design intent checks:**
- Is IC refinement firing for all ICs? (Silent failure is a known risk)
- Is the codebook growing at a healthy rate or stalling?
- Is the ITS trajectory heading toward saturation?

### Layer 2 — Theme Synthesis

From raw output, capture the full theme evolution:
- Initial theme count from synthesizer
- S4 distinctness gate: how many themes merged/removed
- S4 split heuristic: how many themes split
- Coherence gate: how many themes dissolved, which ones
- Orphan reassessment: ICs redistributed vs. unassigned
- Final functional theme count (excluding empty ghost nodes)

**Critical design intent checks:**
- Did the coherence gate leave any empty theme nodes in the DB?
  Query: `SELECT t.name, COUNT(ti.ic_id) AS n FROM themes t LEFT JOIN theme_ics ti ON ti.theme_id=t.id GROUP BY t.id`
  Any row with `n=0` is a ghost — this is Bug #1 territory.
- Did any theme produce `last_ic_segment = -1` in meaning saturation?
  This is a downstream symptom of an empty ghost theme.

For each final theme: record name, IC count, coherence score, and note whether
any show semantic overlap with others.

### Layer 3 — Metrics

Extract from results JSON (`layer3` key — note: top-level `quality_metrics` is
often empty). For each metric, record value, threshold, and RAG status.

The metrics fall into three groups:

**Evidence quality** (grounding, drop rate, extraction density, thematic
coverage, sentiment purity, convergence) — these tell you whether the coder
extracted real, well-distributed evidence.

**Codebook maturity** (singleton ratio, merge rate, triage auto-rate, ITS) —
these tell you whether the codebook is developed enough to be trusted. Low
values here at small N are expected, not failures.

**Theme quality** (coherence mean, distinctness overlap ratio) — these tell you
whether the synthesis stage produced defensible, separable concepts.

Also check quote coverage: `quote_coverage.overall_mean_pct` should be a
percentage value (0–100), not a fraction. If it's < 1.0, the scale is wrong
(Bug #2 pattern).

### Layer 4 — Analytical Brief

Layer 4 produces both **quantitative flags** and a **qualitative brief**.
Review both.

**Quantitative:** Layer 4 reports 🟢/🟡/🔴 on each metric. Summarise these
in a table. Note any config recommendations the analyst made (e.g. suggested
threshold changes).

**Qualitative:** Read the actual brief content. Ask:
- Do the category names make intellectual sense for the corpus?
- Are the themes grounded in recognisable player experience concepts?
- Does the brief narrative cohere, or does it contradict the metric picture?
- Are there any categories that reference a dissolved/ghost theme?

A clean metric picture with an incoherent brief is still a failure. The brief
is the deliverable that a real researcher would read.

---

## Step 5 — Structure Quality Assessment

This is a substantive, non-metric review. Read the actual ICs, themes, and
categories — not just their counts and scores.

**Categories (2–5 expected):**
- Are they mutually exclusive at a conceptual level?
- Do they collectively cover the full scope of the corpus?
- Would a domain expert find these groupings intuitive?

**Themes (target 5–10):**
- Does each theme have a clear, specific name (not a generic label)?
- Is the definition distinguishable from adjacent themes?
- Are there any themes that seem to be a catch-all or wastebasket?

**Initial Codes (ICs):**
- Are the names descriptive and specific (not just rephrasing the theme)?
- Spot-check 3–5 ICs with high singleton ratios — do they represent genuinely
  rare phenomena or just noisy extraction?
- Spot-check 3–5 ICs with the most quotes — do the quotes actually support the
  IC name?

**Evidence (verbatim quotes):**
- Pull a sample of 5–10 quotes from the DB. Do they read as real player
  language, or do they look truncated / mis-attributed?
- Are span_start / span_end values plausible for the segment length?

---

## Step 6 — Testing Plan Compliance

Read the testing plan file the user specified. For each checklist item that is
relevant to this run's configuration:

- Mark ✅ PASS, ❌ FAIL, or ⚪ N/A (not applicable for this run config)
- For FAILs, note the observed behaviour briefly
- For N/A, note why (e.g. "HIL features not applicable — run used --no-hil")

Focus on the Phase most relevant to the run. A `--no-hil` run primarily tests
Phase 1 (automated baseline); HIL features (Phase 2) are N/A.

**After the checklist:** Note any known issues from the testing plan that
manifested in this run, and any new anomalies that do not correspond to any
existing known issue.

---

## Step 7 — Bug and Anomaly Log

For every unexpected behaviour found anywhere in the analysis, create a
structured entry. Use this format:

```
### Bug/Anomaly: <short title>

**Severity**: Critical / High / Medium / Low
**Symptom**: What was observed (specific values, log lines, query results)
**Affected components**: Which files/modules/layers
**Root cause**: Best explanation, or "Unknown — needs investigation"
**Fix needed**: Yes (with location hint) / No (false alarm) / Investigation needed
**Priority**: P0 blocker / P1 high / P2 normal / P3 low
```

If after investigation an anomaly turns out to be a false alarm (wrong key
name, expected behaviour under unusual conditions, etc.), document it as such
with the explanation — do not silently drop it.

---

## Step 8 — Write the Summary Document

Save the completed analysis to:
```
docs/testing/TEST_RUN_SUMMARY_{model_alias}_{dataset_short}_{YYYY-MM-DD}.md
```

Example: `docs/testing/TEST_RUN_SUMMARY_orSmart_canon30_2026-03-03.md`

Use the template in:
📄 `skills/pipeline-test-analysis/references/output_template.md`

The template defines required sections and their contents. Fill every section —
do not omit sections because the data was uninteresting. An empty or N/A
section is more informative than a missing one.

After saving, present the file to the user with `mcp__cowork__present_files`.

---

## What this skill must NOT do

- **Do not compare to other test runs** in the summary document. Cross-run
  comparison is a separate task requiring two or more completed summaries.
- **Do not fix bugs** found during analysis. Describe them precisely in Step 7
  so they can be fixed as a separate committed change.
- **Do not modify the testing plan** file. Note items that need updating, but
  leave the actual edit for the user to initiate.
- **Do not run the pipeline.** This skill analyses a completed run only.
- **Do not skip layers** because the output looks clean. The value of a
  standardised process is consistency — every run gets the same depth.
- **Do not summarise the summary.** The output document should contain the full
  analysis. Do not produce a short chat response and call it done.

---

## Quick Checklist (use as a final gate before saving)

Before writing the document, confirm:

- [ ] All artifacts verified (Step 1)
- [ ] Full CLI command reconstructed (Step 2)
- [ ] Run integrity confirmed — no crashes, all layers present (Step 3)
- [ ] All four layers analysed with metric reference consulted (Step 4)
- [ ] At least one IC, theme, and quote spot-checked qualitatively (Step 5)
- [ ] Testing plan checklist completed (Step 6)
- [ ] All anomalies have structured entries (Step 7)
- [ ] Output document uses the standard template (Step 8)
- [ ] No cross-run comparisons in the document
