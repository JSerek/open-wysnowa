# EQD-AI Metric Reference

This file is the authoritative reference for interpreting pipeline metrics.
Thresholds and interpretation notes reflect current design intent and are
updated as the pipeline evolves. Always consult this file — do not rely on
training-time memory.

---

## How to use this file

For each metric, this file gives:
- **What it measures** (the question it answers)
- **Thresholds** (🟢 healthy / 🟡 watch / 🔴 flag)
- **Interpretation notes** (context that changes the reading)
- **Common failure patterns**

The thresholds assume a standard Discovery run on a moderate-size corpus
(30–100 reviews). Small N (< 30) will produce lower maturity metrics by
design — that is expected behaviour, not a failure.

---

## Layer 1 Metrics

### Singleton Ratio

**What it measures:** The fraction of ICs that have exactly one quote assigned.
A high singleton ratio means the codebook is fragmented — most ICs are
one-offs with no cross-review evidence.

| Value | Status | Interpretation |
|-------|--------|----------------|
| ≤ 0.30 | 🟢 | Codebook well-grounded, most ICs have multi-review evidence |
| 0.31–0.50 | 🟡 | Moderate fragmentation — watch trajectory across batches |
| > 0.50 | 🔴 | High fragmentation — likely codebook not mature enough, or model too literal |

**Notes:**
- At N=30, a ratio of 0.35–0.45 is common and not alarming; the trajectory
  matters more than the absolute value.
- If singleton ratio is high AND ITS is high, the codebook is actively growing
  — more data will help.
- If singleton ratio is high but ITS is low, the model may be minting overly
  specific ICs rather than abstracting to reusable codes. Check IC names for
  over-specificity.
- Previous runs using weaker models (e.g. gemini_flash_lite) showed 82.5%
  singletons; orSmart (gemini-3-flash-preview) achieved 40% — model quality
  matters significantly for this metric.

---

### IC Refinement Rate

**What it measures:** The proportion of ICs that were substantively refined
after initial extraction. Refinement improves IC names and definitions.

| Value | Status | Interpretation |
|-------|--------|----------------|
| 100% | 🟢 | All ICs refined as designed |
| < 100% | 🔴 | Silent failure in refinement — check for NameError or timeout |

**Notes:**
- IC refinement is an all-or-nothing feature — it should either run for all ICs
  or have failed entirely. A partial rate suggests a crash that was swallowed.
- Fixed in commit c88eda3. If you see < 100%, check for regression.

---

### Per-Batch Merge Rate

**What it measures:** The proportion of new Coder proposals that were merged
into existing ICs in each batch. Tracks codebook solidification over time.

| Batch 1 | Later batches | Status | Interpretation |
|---------|---------------|--------|----------------|
| > 30% | Declining | 🟢 | Codebook forming, then stabilising |
| > 30% | Flat / rising | 🟡 | Codebook may be over-merging or LLM drifting |
| < 20% in all batches | — | 🔴 | Very little reuse — fragmented extraction |

**Notes:**
- A declining merge rate across batches is the expected healthy pattern. It
  reflects the codebook maturing: early batches form new codes, later batches
  mostly match existing ones.
- The final batch merge rate is the most diagnostic value. If it's still > 30%
  in the last batch, the codebook hasn't stabilised.
- merge_rate_final in Layer 4 is computed differently — it is the aggregate
  merge rate, not the final-batch rate. Both are useful.

---

### ITS — Incremental Thematic Saturation

**What it measures:** The proportion of ICs in each batch that introduced a
genuinely new concept (no match in the existing codebook). Tracks how novel
the incoming data is relative to what's been seen.

| Final ITS | Status | Interpretation |
|-----------|--------|----------------|
| ≤ 0.05 | 🟢 | Saturated — codebook covers the conceptual space |
| 0.06–0.15 | 🟡 | Near-saturation — more data would help |
| > 0.15 | 🔴 | Active growth — codebook not yet mature |

**Critical interpretation note:**
High ITS is expected at small N. At 30 reviews, ITS=0.18 is completely normal.
It means "18% of new concepts appear in the last batch" — not that the
pipeline has failed. The question is whether ITS is declining across batches
(healthy trajectory) vs. flat or rising (possible data quality issue).

The saturation guideline (ITS ≤ 0.05) is a target for when you have enough
data. For a typical dense qualitative corpus, this requires approximately
80–120 reviews. Do not flag high ITS as a critical issue at N < 50.

---

### Flip Rate (Coder Reuse)

**What it measures:** The proportion of Comparator decisions where the coder
first proposed NEW but the Comparator overrode to MERGE (or vice versa). High
flip rates mean the Coder and Comparator frequently disagree.

| Value | Status | Interpretation |
|-------|--------|----------------|
| < 40% | 🟢 | Coder and Comparator broadly agree |
| 40–60% | 🟡 | Significant disagreement — check IC specificity |
| > 60% | 🔴 | Coder and Comparator pulling in opposite directions |

---

### Confidence Distribution

**What it measures:** The distribution of coder confidence scores across all
ICs. Should reflect genuine discrimination between strong and weak evidence.

| Pattern | Status | Interpretation |
|---------|--------|----------------|
| Mean 0.7–0.9, SD > 0.10, spread across Q1–Q3 | 🟢 | Calibrated |
| Heavily clustered at single value (SD < 0.08) | 🟡 | Possibly uniform output from model, not genuine confidence |
| All scores at 0.95–1.0 | 🔴 | Model outputting near-certain confidence regardless of evidence |

**Note:** A narrow distribution (e.g. Q1=Q2=Q3=0.9) is suspicious and worth
flagging, even if the mean looks healthy. It suggests the model is not
actually discriminating between stronger and weaker extractions.

---

## Layer 2 Metrics

### Theme Coherence (per-theme and mean)

**What it measures:** How semantically unified the ICs within a theme are.
Computed as the average pairwise cosine similarity between IC embeddings
within a theme. High coherence = tight, focused theme.

| Value | Status | Interpretation |
|-------|--------|----------------|
| ≥ 0.60 per theme | 🟢 | Tight, focused theme |
| 0.55–0.59 per theme | 🟡 | Adequate, marginal |
| < 0.55 per theme | 🔴 | Diffuse — ICs may span multiple distinct concepts |
| Mean ≥ 0.60 | 🟢 | |
| Mean 0.55–0.59 | 🟡 | |
| Mean < 0.55 | 🔴 | |

**Notes:**
- Coherence at small N is often lower because ICs are broad (fewer reviews =
  less opportunity to refine conceptual boundaries). Below-threshold coherence
  at N=30 is noted but not alarming.
- If a theme has < 4 ICs AND low coherence, it may be a stray/catch-all theme
  rather than a real conceptual cluster. Worth flagging for qualitative review.
- Coherence gate dissolves themes below `coherence_threshold` (default: 0.45
  normalised). This is lower than the evaluation threshold above — the gate is
  a safety floor, not a quality target.

---

### Theme Distinctness (overlap ratio)

**What it measures:** The proportion of theme pairs whose centroid similarity
exceeds 0.70. High overlap means themes are not clearly differentiated.

| Value | Status | Interpretation |
|-------|--------|----------------|
| ≤ 25% of pairs overlapping | 🟢 | Themes well-separated |
| 26–40% of pairs | 🟡 | Some overlap — watch for redundant themes |
| > 40% of pairs | 🔴 | Significant overlap — themes may need merging or splitting |

**Notes:**
- S4's distinctness gate merges or removes themes exceeding overlap thresholds.
  If the gate fired, the final distinctness should be better than the initial.
- Report both pre-gate and post-gate overlap counts if both are visible in the
  raw output.

---

### Empty Theme Detection

**What it measures:** Whether any theme record in the DB has 0 assigned ICs.
This is always a bug, not an expected state.

| Condition | Status |
|-----------|--------|
| All themes have ≥ 1 IC | 🟢 |
| Any theme has 0 ICs | 🔴 Bug (see Bug #1 in known issues) |

**Detection query:**
```sql
SELECT t.name, COUNT(ti.ic_id) AS ic_count
FROM themes t
LEFT JOIN theme_ics ti ON ti.theme_id = t.id
GROUP BY t.id
ORDER BY ic_count ASC;
```

Any row with `ic_count = 0` is a ghost node. Check `meaning_saturation_per_theme`
for `last_ic_segment = -1` as the downstream symptom.

---

## Layer 3 Metrics

### Grounding Rate

**What it measures:** The fraction of verbatim quotes that have valid,
non-empty span_start/span_end coordinates pointing to actual text in the
source segment.

| Value | Status |
|-------|--------|
| ≥ 0.95 | 🟢 |
| 0.85–0.94 | 🟡 |
| < 0.85 | 🔴 |

A grounding rate of 1.0 is achievable and expected in clean runs. Any rate
below 0.95 warrants investigation of the grounding validation logic.

---

### Drop Rate

**What it measures:** The fraction of extracted quotes that were dropped during
validation (failed grounding, span out of bounds, empty text, etc.).

| Value | Status |
|-------|--------|
| ≤ 0.10 | 🟢 |
| 0.11–0.20 | 🟡 |
| > 0.20 | 🔴 |

High drop rate alongside low grounding rate suggests the coder is hallucinating
spans rather than extracting real text.

---

### Extraction Density (mean)

**What it measures:** The average proportion of a segment's characters that
are covered by at least one verbatim quote. Reflects how thoroughly the coder
extracts evidence from each review.

| Value | Status | Interpretation |
|-------|--------|----------------|
| 0.30–0.80 | 🟢 | Good coverage without being exhaustive |
| < 0.30 | 🟡 | Under-extraction — coder may be too selective |
| > 0.80 | 🟡 | Over-extraction — coder may be quoting too broadly |

---

### Triage Auto-Rate

**What it measures:** The proportion of Comparator decisions that were made
with high confidence (no HIL intervention needed). In `--no-hil` runs, this
is the proportion of MERGE/NEW decisions made without ambiguity flags.

| Value | Status | Interpretation |
|-------|--------|----------------|
| ≥ 0.60 | 🟢 | Comparator is decisive |
| 0.40–0.59 | 🟡 | Many grey-zone decisions |
| < 0.40 | 🔴 | Comparator struggling — check similarity thresholds |

---

### Thematic Coverage

**What it measures:** The proportion of segments that have at least one IC
assigned from each theme. Checks for evidence gaps.

| Value | Status |
|-------|--------|
| ≥ 0.90 | 🟢 |
| 0.80–0.89 | 🟡 |
| < 0.80 | 🔴 |

---

### Sentiment Purity (mean)

**What it measures:** How consistently the sentiment of verbatim quotes matches
the intended direction of their IC. A purity of 1.0 means all quotes matched
their IC's sentiment polarity.

| Value | Status |
|-------|--------|
| ≥ 0.85 | 🟢 |
| 0.75–0.84 | 🟡 |
| < 0.75 | 🔴 |

---

### Cross-Review Convergence

**What it measures:** The proportion of ICs that have evidence from 2 or more
distinct reviews ("confirmed" convergence). Indicates how well the codebook
generalises beyond individual reviewers.

| Value | Status | Interpretation |
|-------|--------|----------------|
| ≥ 0.60 | 🟢 | Most ICs grounded in multiple reviewers |
| 0.45–0.59 | 🟡 | Moderate — some ICs remain reviewer-specific |
| < 0.45 | 🔴 | Many reviewer-specific ICs — codebook may not generalise |

---

### Quote Coverage (`overall_mean_pct` / `overall_max_pct`)

**What it measures:** For each (IC, segment) pair, what fraction of the
segment's characters are covered by quotes attributed to that IC. Summary
stats reflect the distribution across all pairs.

**Important:** Values are stored as **percentages** (0–100) since pipeline
version post-737ff20. If you see values < 2.0 for `overall_mean`, the run
predates this fix and values are 0–1 fractions — multiply by 100 mentally.

| Mean coverage | Interpretation |
|---------------|----------------|
| > 15% | ICs are capturing substantial text passages |
| 5–15% | Normal — ICs typically cover a few sentences |
| < 5% | Possibly very short quotes or sparse extraction |

---

## Layer 4 Evaluation

Layer 4 runs its own metric evaluation and produces 🟢/🟡/🔴 flags. These
use thresholds derived from the same values above. The Layer 4 output is
authoritative for the overall run health summary.

Layer 4 also produces **config recommendations** — parameter adjustments it
suggests based on the run's metric profile. Record these verbatim; they are
actionable inputs for the next run's config tuning.

### Key Layer 4 metrics (summary)

| Metric | Layer 4 key | Healthy range |
|--------|-------------|---------------|
| Grounding | `grounding_rate` | ≥ 0.95 |
| Drop rate | `drop_rate` | ≤ 0.10 |
| Extraction density | `extraction_density_mean` | 0.30–0.80 |
| Singletons | `singleton_ratio` | ≤ 0.30 |
| Merge rate | `merge_rate_final` | 0.40–0.80 (low OK at small N) |
| Triage auto | `triage_auto_rate` | ≥ 0.60 |
| ITS final | `its_final` | ≤ 0.05 (low OK at small N) |
| Theme coherence | `theme_coherence_mean` | ≥ 0.55 |
| Distinctness pairs | `theme_distinctness_overlap_ratio` | ≤ 25% |
| Sentiment purity | `sentiment_purity_mean` | ≥ 0.85 |
| Thematic coverage | `thematic_coverage` | ≥ 0.90 |
| Convergence | `cross_review_convergence` | ≥ 0.60 |

---

## Interpretation Patterns

### "Immature codebook" signature
ITS > 0.15 + singleton_ratio > 0.40 + merge_rate_final < 0.20 all together
= codebook is still growing actively. This is expected at N < 50. Recommend
running more data before drawing conclusions from theme structure.

### "Over-merging" signature
merge_rate_final > 0.80 + theme_coherence_mean < 0.50 = the comparator is
merging too aggressively, collapsing distinct concepts into broad ICs.
Likely fix: lower `auto_merge_threshold`.

### "Fragmented extraction" signature
singleton_ratio > 0.60 + ITS high + IC names are very specific/event-like =
the coder is minting one IC per incident rather than abstracting to reusable
codes. Model quality is the primary lever; also check IC refinement is running.

### "Ghost theme" signature
Any theme with `last_ic_segment = -1` in meaning saturation, or DB query
showing 0 ICs for a theme that appears in the Layer 2 narrative = Bug #1
(empty theme node after coherence gate dissolution). Not a metric issue —
a DB integrity bug.
