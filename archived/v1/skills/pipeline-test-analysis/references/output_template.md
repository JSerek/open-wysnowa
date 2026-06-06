# Test Summary Document — Standard Template

## Naming convention

```
docs/testing/TEST_RUN_SUMMARY_{model_alias}_{dataset_short}_{YYYY-MM-DD}.md
```

Examples:
- `TEST_RUN_SUMMARY_orSmart_canon30_2026-03-03.md`
- `TEST_RUN_SUMMARY_claude3h_full100_2026-04-15.md`
- `TEST_RUN_SUMMARY_o4mini_hil_pilot_2026-05-01.md`

**Rules:**
- `model_alias` = the config alias (e.g. `orSmart`, `claude3h`), not the model
  string — keeps filenames readable
- `dataset_short` = abbreviated dataset name, no spaces, no underscores except
  as word separators
- Date = run date, not write date
- Always save to `docs/testing/` — never to `runs/` or the project root

---

## Document template

Replace every `{…}` placeholder. Do not omit any section — write "N/A — \<reason\>"
if a section genuinely does not apply to this run.

---

```markdown
# Test Run Summary: {model_alias} · {dataset_short} · {YYYY-MM-DD}

**Overall status**: {PASS / PASS with caveats / FAIL} — {one-sentence reason}

---

## 1. Run Configuration

| Parameter | Value |
|-----------|-------|
| **Date** | {YYYY-MM-DD} |
| **Dataset** | `{filepath}` — {description of corpus} |
| **Flags** | `{full reconstructed CLI command}` |
| **Raw output** | `{path}` |
| **DB** | `{path}` |
| **Results JSON** | `{path}` |
| **Reasoning log** | `{path or "not enabled"}` |

### Models

| Agent | Model string | Provider | Reasoning |
|-------|-------------|----------|-----------|
| `coder_agent` | `{model}` | {provider} | {setting or "—"} |
| `codebook_comparator` | `{model}` | {provider} | {setting or "—"} |
| `synthesizer_agent` | `{model}` | {provider} | {setting or "—"} |
| `category_agent` | `{model}` | {provider} | {setting or "—"} |
| `analyst_agent` | `{model}` | {provider} | {setting or "—"} |
| `embedding` | `{model}` | {provider} | — |

---

## 2. Pipeline Execution Summary

{One paragraph: did all layers complete without error? Any crashes or
integrity issues? If all clean, say so explicitly.}

| Layer | Status | Notes |
|-------|--------|-------|
| L0 Ingestion | ✅ / ⚠️ / ❌ | {notes} |
| L1 Extraction | ✅ / ⚠️ / ❌ | {notes} |
| L2 Synthesis | ✅ / ⚠️ / ❌ | {notes} |
| L3 Metrics | ✅ / ⚠️ / ❌ | {notes} |
| L4 Analysis | ✅ / ⚠️ / ❌ | {notes} |

---

## 3. Layer 1 — Extraction and Codebook

### IC statistics

| Metric | Value | Note |
|--------|-------|------|
| Active ICs | {n} | |
| Singletons | {n} ({pct}%) | 🟢/🟡/🔴 vs ≤ 30% target |
| Merges | {n} | |
| Drops | {n} | |
| ICs refined | {n}/{total} | 🟢 if 100% |

### Per-batch merge rates and ITS

| Batch | Segments | Merge rate | ITS | Interpretation |
|-------|----------|-----------|-----|----------------|
| 1 | {n} | {pct}% | {val} | {notes} |
| 2 | {n} | {pct}% | {val} | {notes} |
| 3 | {n} | {pct}% | {val} | {notes} |

**ITS trajectory**: {declining / flat / rising} — {interpretation sentence}

### Coder reuse and stability

| Metric | Value | Status |
|--------|-------|--------|
| flagged_match | {n} | |
| flip_rate | {pct}% | 🟢 if < 40% |

### Confidence distribution

| Metric | Value |
|--------|-------|
| mean | {val} |
| SD | {val} |
| Q1 | {val} |
| Q3 | {val} |

{One sentence interpreting the distribution — is it well-spread or suspiciously
clustered?}

---

## 4. Layer 2 — Theme Synthesis

### Theme evolution

{Describe the full evolution in prose: initial count → S4 gates → final count.
Include which gates fired and what they changed.}

```
{Include a simple text diagram if helpful:
  Synthesizer → N themes
    ↓ [S4 distinctness] → N-k themes
    ↓ [S4 splits] → N+j themes
    ↓ [Coherence gate] → N themes final
    ↓ [Orphan reassessment] → M ICs redistributed}
```

### Final themes

| # | Theme | IC count | Coherence | Status |
|---|-------|----------|-----------|--------|
| 1 | {name} | {n} | {score} | 🟢/🟡/🔴 |
| … | … | … | … | … |

**Mean coherence**: {val} ({🟢/🟡/🔴} vs ≥ 0.55 guideline)
**Distinctness**: {n} of {total} pairs exceeding 0.70 similarity ({🟢/🟡/🔴})

### Categories

```
{Category 1 name}
{Category 2 name}
…
```

{One sentence: are these intellectually defensible groupings?}

---

## 5. Layer 3 — Metrics Dashboard

### Evidence quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| grounding_rate | {val} | ≥ 0.95 | 🟢/🟡/🔴 |
| drop_rate | {val} | ≤ 0.10 | 🟢/🟡/🔴 |
| extraction_density_mean | {val} | 0.30–0.80 | 🟢/🟡/🔴 |
| thematic_coverage | {val} | ≥ 0.90 | 🟢/🟡/🔴 |
| sentiment_purity_mean | {val} | ≥ 0.85 | 🟢/🟡/🔴 |
| cross_review_convergence | {val} | ≥ 0.60 | 🟢/🟡/🔴 |

### Codebook maturity

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| singleton_ratio | {val} | ≤ 0.30 | 🟢/🟡/🔴 |
| merge_rate_final | {val} | 0.40–0.80 | 🟢/🟡/🔴 |
| triage_auto_rate | {val} | ≥ 0.60 | 🟢/🟡/🔴 |
| its_final | {val} | ≤ 0.05 | 🟢/🟡/🔴 |

### Theme quality

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| theme_coherence_mean | {val} | ≥ 0.55 | 🟢/🟡/🔴 |
| theme_distinctness_overlap | {n}/{total} pairs | ≤ 25% | 🟢/🟡/🔴 |

### Quote coverage

| Metric | Value | Note |
|--------|-------|------|
| overall_mean_pct | {val}% | {scale note if applicable} |
| overall_max_pct | {val}% | |
| high_coverage_pairs (>70%) | {n} | |

---

## 6. Layer 4 — Analyst Brief

### Layer 4 metric evaluation

| Metric | Value | Rating | LLM Interpretation |
|--------|-------|--------|-------------------|
| grounding_rate | {val} | 🟢/🟡/🔴 | {note} |
| drop_rate | {val} | 🟢/🟡/🔴 | {note} |
| extraction_density_mean | {val} | 🟢/🟡/🔴 | {note} |
| singleton_ratio | {val} | 🟢/🟡/🔴 | {note} |
| merge_rate_final | {val} | 🟢/🟡/🔴 | {note} |
| triage_auto_rate | {val} | 🟢/🟡/🔴 | {note} |
| its_final | {val} | 🟢/🟡/🔴 | {note} |
| theme_coherence_mean | {val} | 🟢/🟡/🔴 | {note} |
| theme_distinctness_overlap_ratio | {val} | 🟢/🟡/🔴 | {note} |
| sentiment_purity_mean | {val} | 🟢/🟡/🔴 | {note} |
| thematic_coverage | {val} | 🟢/🟡/🔴 | {note} |
| cross_review_convergence | {val} | 🟢/🟡/🔴 | {note} |

### Config recommendations from Layer 4

| Parameter | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| {param} | {val} | {val} | {reason} |

### Brief quality assessment

{2–3 sentences assessing the qualitative brief content. Are the categories
intellectually coherent? Does the narrative match the metric picture? Any
themes or categories that are misleading given known anomalies?}

---

## 7. Structure Quality Assessment

### Categories

{Assess 2–3 sentences: are they mutually exclusive? Collectively exhaustive?
Would a domain expert find these groupings intuitive?}

### Themes

{Assess 2–3 sentences: are names specific and clear? Any catch-all or
wastebasket themes? Any themes that seem like duplicates?}

### ICs — spot check

{Select 3–5 ICs for qualitative review. For each, note the IC name, quote it,
and assess whether the name and evidence are aligned.}

| IC name | Quote sample | Alignment |
|---------|-------------|-----------|
| {name} | "{quote fragment}" | ✅ / ⚠️ misnamed / ❌ |

### Evidence — spot check

{Select 5–10 raw quotes from DB. Do they read as real player language? Are
spans plausible?}

---

## 8. Testing Plan Compliance

**Testing plan used**: `{filepath}`
**Run configuration**: `{--no-hil / --hil / etc.}` → Phase {n} most relevant

| Check | Result | Notes |
|-------|--------|-------|
| {Item from testing plan} | ✅ / ❌ / ⚪ N/A | {brief note} |
| … | … | … |

**Known issues manifesting in this run:**
{List known issue IDs and brief status — appeared as expected / not seen / new variant}

---

## 9. Bugs and Anomalies

{If none found, write "No bugs or anomalies identified in this run."}

### Bug/Anomaly: {title}

**Severity**: {Critical / High / Medium / Low}
**Symptom**: {What was observed}
**Affected components**: {Files/modules/layers}
**Root cause**: {Best explanation or "Unknown — needs investigation"}
**Fix needed**: {Yes — in {location} / No — false alarm / Investigation needed}
**Priority**: {P0 / P1 / P2 / P3}

---

## 10. Next Steps

{Numbered list of specific, actionable items. Include priority. Do not include
vague items like "improve quality" — be specific about what to do and why.}

1. {Action} — {why, what to expect}
2. …
```

---

## Writing guidance

**Overall status line:**
- `PASS` — all integrity checks clean, no bugs, metrics within guidelines or
  expected given sample size
- `PASS with caveats` — run completed, bugs found or metrics outside guidelines
  but with understood reasons; document the caveats
- `FAIL` — run did not complete, a crash occurred, or a P0 bug was found

**On metric status at small N:**
Do not mark immature-codebook metrics (ITS, merge_rate_final, singleton_ratio)
as 🔴 just because they're outside guideline values at N < 50. Note the
expected-vs-actual reading, but reserve 🔴 for genuinely unexpected values or
values outside range even accounting for small N.

**On the Next Steps section:**
The most useful next steps reference specific config changes, specific files to
fix, or a specific larger dataset to run. "Run more data" is only useful if you
specify how much and why that amount. "Fix Bug #1" is only useful if you
specify the file and function.
