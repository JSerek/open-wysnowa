# Layer 4: Analyst Intelligence — Full Design Document

> Implementation-ready spec for Layer 4. Three-call LLM architecture with YAML-configurable
> metric guidelines. Reads from the existing `results` dict — no pipeline flow changes.

---

## 1. Architecture Overview

Layer 4 sits after Layer 3 (quality metrics). It consumes the full `results` dict and produces
a structured analytical interpretation. Three focused LLM calls, each with a specific job:

```
results dict (from pipeline.run())
    │
    ├─→ Call 1: Metrics Interpretation
    │     Input: results["layer3"] (all 17 quality metrics)
    │     Output: MetricsInterpretation
    │
    ├─→ Call 2: Structural Diagnostics
    │     Input: results["thematic_structure"] + results["layer2"] + results["categories"]
    │     Output: StructuralDiagnostics
    │
    └─→ Call 3: Synthesis & Recommendations
          Input: outputs of Call 1 + Call 2 + pipeline config summary
          Output: AnalystSynthesis
          │
          └─→ Combined into: AnalyticalBrief (returned as results["layer4"])
```

All three calls use Sonnet 4.5 (`claude-sonnet-4-5-20250929`).

---

## 2. Pydantic Models

### 2.1 Call 1 Output: MetricsInterpretation

```python
class MetricAssessment(BaseModel):
    """Assessment of a single quality metric."""
    metric_name: str = Field(description="Metric identifier, e.g. 'grounding_rate'")
    observed_value: str = Field(description="Formatted value, e.g. '96.2%', '28/120 pairs'")
    status: Literal["healthy", "monitor", "investigate"] = Field(
        description="healthy=within guidelines, monitor=borderline, investigate=outside guidelines"
    )
    interpretation: str = Field(
        min_length=20, max_length=500,
        description="What this value means in context of this specific run"
    )
    context_factors: Optional[str] = Field(
        default=None, max_length=300,
        description="Factors that might explain the value (sample size, data characteristics, etc.)"
    )


class MetricsInterpretation(BaseModel):
    """Output of Call 1: metrics interpretation."""
    assessments: List[MetricAssessment] = Field(min_length=1)
    data_quality_summary: str = Field(
        min_length=50, max_length=800,
        description="Overall assessment of data integrity and codebook health"
    )
    saturation_assessment: str = Field(
        min_length=50, max_length=500,
        description="Is the codebook saturated? Should we process more data?"
    )
```

### 2.2 Call 2 Output: StructuralDiagnostics

```python
class ThemeDiagnostic(BaseModel):
    """Diagnostic for a single theme."""
    theme_name: str
    ic_count: int
    coherence: Optional[float] = None
    issue_type: Optional[Literal[
        "magnet_theme", "weak_coherence", "low_evidence",
        "naming_unclear", "sentiment_mixed", "healthy"
    ]] = Field(default="healthy")
    assessment: str = Field(min_length=20, max_length=500)
    suggested_action: Optional[str] = Field(
        default=None, max_length=200,
        description="Specific action if issue detected, e.g. 'consider splitting' or 'review IC assignments'"
    )


class CategoryDiagnostic(BaseModel):
    """Diagnostic for a category grouping."""
    category_name: str
    theme_count: int
    assessment: str = Field(min_length=20, max_length=300)
    potential_issue: Optional[Literal[
        "too_broad", "single_theme", "misaligned_themes", "healthy"
    ]] = Field(default="healthy")


class StructuralDiagnostics(BaseModel):
    """Output of Call 2: structural analysis."""
    theme_diagnostics: List[ThemeDiagnostic] = Field(min_length=1)
    category_diagnostics: List[CategoryDiagnostic]
    strongest_themes: List[str] = Field(
        max_length=5,
        description="Top themes by evidence quality + coherence"
    )
    weakest_themes: List[str] = Field(
        max_length=5,
        description="Themes needing attention"
    )
    structural_summary: str = Field(
        min_length=50, max_length=1000,
        description="Overall assessment of the thematic structure"
    )
```

### 2.3 Call 3 Output: AnalystSynthesis

```python
class ConfigRecommendation(BaseModel):
    """A specific configuration change suggestion."""
    parameter: str = Field(description="YAML config key, e.g. 'processing.category_merge_threshold'")
    current_value: str
    suggested_value: str
    rationale: str = Field(min_length=20, max_length=300)


class AnalystSynthesis(BaseModel):
    """Output of Call 3: synthesis and recommendations."""
    overall_assessment: str = Field(
        min_length=100, max_length=2000,
        description="Integrative assessment of the full analysis — what did we learn?"
    )
    key_findings: List[str] = Field(
        min_length=1, max_length=7,
        description="Most important takeaways, ordered by significance"
    )
    config_recommendations: List[ConfigRecommendation]
    next_steps: List[str] = Field(
        min_length=1, max_length=5,
        description="Prioritized actions: what should the analyst do next?"
    )
    confidence_note: str = Field(
        min_length=20, max_length=500,
        description="Caveats: sample size, saturation status, known limitations of this run"
    )
```

### 2.4 Combined Container

```python
class AnalyticalBrief(BaseModel):
    """Full Layer 4 output — container for all three call results."""
    metrics: MetricsInterpretation
    structure: StructuralDiagnostics
    synthesis: AnalystSynthesis
```

---

## 3. YAML Configuration

### 3.1 Agent Config (add to `agents` section)

```yaml
agents:
  # ... existing agents ...

  analyst_agent:
    model: claude_sonnet
    temperature: 0.3       # slightly higher for interpretive flexibility
    max_tokens: 16000
```

### 3.2 Metric Guidelines (new top-level section)

These are GUIDELINES, not hard thresholds. The LLM uses them as reference ranges,
not pass/fail criteria. The analyst can adjust them as they learn what's normal for their data.

```yaml
# ── ANALYST GUIDELINES ──────────────────────────────────────────
# Reference ranges for Layer 4 metric interpretation.
# These are guidelines, not gates. The LLM uses them to contextualize
# metric values, not to make pass/fail decisions.
analyst_guidelines:
  # DATA INTEGRITY
  grounding_rate:
    healthy_min: 0.95
    description: "Proportion of verbatim quotes whose spans exactly match the source text"
    what_it_measures: "Whether the coder agent is hallucinating quote boundaries"
    low_means: "The coder is generating quotes that don't match the source text — check span validation"

  drop_rate:
    healthy_max: 0.15
    description: "Proportion of LLM-proposed IC candidates dropped due to span validation failure"
    what_it_measures: "How often the coder proposes quotes with incorrect character offsets"
    high_means: "The coder is frequently hallucinating span positions — may indicate prompt issues or difficult text"

  extraction_density_mean:
    healthy_min: 0.30
    healthy_max: 0.80
    description: "Mean fraction of segment text covered by IC quotes (character-level)"
    what_it_measures: "How much of each segment's content is being captured by IC extraction"
    low_means: "Large portions of text are being ignored — possible missed phenomena"
    high_means: "Nearly all text is being coded — check for over-extraction or trivial ICs"

  # CODEBOOK HEALTH
  singleton_ratio:
    healthy_max: 0.30
    description: "Proportion of active ICs with only 1 supporting quote"
    what_it_measures: "Evidence concentration — are ICs well-supported or one-off observations?"
    high_means: "Many ICs have minimal evidence — possible over-splitting or premature IC creation"

  merge_rate_final:
    healthy_min: 0.40
    healthy_max: 0.80
    description: "Proportion of new candidates merged into existing ICs (final batches)"
    what_it_measures: "Codebook maturity — higher merge rate suggests the codebook is stabilizing"
    low_means: "Codebook is still growing rapidly — may need more data before thematic synthesis"
    high_means: "Very few new concepts emerging — codebook may be saturated"

  triage_auto_rate:
    healthy_min: 0.60
    description: "Proportion of triage decisions made automatically (high-confidence)"
    what_it_measures: "How often the embedding similarity gives a clear signal"
    low_means: "Many grey-zone cases — thresholds may need tuning or ICs are poorly differentiated"

  # SATURATION
  its_final:
    healthy_max: 0.05
    description: "Incremental Type Saturation — fraction of new ICs in the last batch"
    what_it_measures: "Whether new concepts are still emerging from the data"
    high_means: "New concepts still emerging — more data needed before the codebook is stable"

  # THEME QUALITY
  theme_coherence_mean:
    healthy_min: 0.55
    description: "Mean intra-theme IC embedding similarity"
    what_it_measures: "How semantically similar the ICs within each theme are"
    low_means: "Themes may be grouping unrelated concepts — consider splitting or reorganizing"

  theme_distinctness_overlap_ratio:
    healthy_max: 0.25
    description: "Proportion of theme pairs with centroid similarity > 0.70"
    what_it_measures: "How much themes overlap with each other"
    high_means: "Many overlapping themes — consider merging similar themes or sharpening definitions"

  sentiment_purity_mean:
    healthy_min: 0.80
    description: "Mean dominant-sentiment ratio per theme"
    what_it_measures: "Whether themes mix positive and negative evidence"
    low_means: "Themes contain mixed sentiment — may be analytically confusing"

  thematic_coverage:
    healthy_min: 0.90
    description: "Proportion of quotes belonging to ICs that are assigned to themes"
    what_it_measures: "How much evidence is captured in the thematic structure"
    low_means: "Significant evidence is outside the thematic structure — orphaned ICs need attention"

  cross_review_convergence:
    healthy_min: 0.50
    description: "Proportion of ICs with evidence from 2+ different documents"
    what_it_measures: "Whether ICs represent cross-document patterns vs single-document artifacts"
    low_means: "Many ICs supported by only one document — may be idiosyncratic, not thematic"
```

---

## 4. Prompt Design

### 4.1 Call 1: Metrics Interpretation

**System prompt:**
```
You are a qualitative data analysis methodologist interpreting quality metrics
from an automated thematic analysis pipeline (Braun & Clarke approach, LLM-assisted).

Your task: interpret each metric value in context. For each metric, you receive:
- The metric definition (what it measures and how)
- A guideline range (NOT a pass/fail threshold — a reference for what's typical)
- The observed value from this specific run

Your interpretation should:
1. State whether the value is within, near, or outside the guideline range
2. Explain what this means for the quality of this specific analysis
3. Consider contextual factors (sample size, data characteristics) that could explain the value
4. Avoid binary good/bad judgments — frame as "healthy", "worth monitoring", or "worth investigating"

Use the status field:
- "healthy" = within guideline range, no concerns
- "monitor" = borderline or slightly outside range, not alarming but worth noting
- "investigate" = clearly outside range, may indicate a real issue

IMPORTANT: These guidelines are calibration references, not rules. A value outside the
guideline range is not automatically a problem — it may reflect the specific characteristics
of this dataset. Your job is to interpret, not to judge.
```

**User prompt:**
```
Here are the quality metrics from this pipeline run.
Dataset: {n_documents} documents, {n_segments} segments, {n_ics} active ICs.

── METRIC DEFINITIONS AND GUIDELINES ──
{for each metric in analyst_guidelines config:
  {metric_name}:
    Definition: {description}
    What it measures: {what_it_measures}
    Guideline range: {healthy_min/max formatted}
    When low/high: {low_means / high_means}
}

── OBSERVED VALUES ──
{formatted results from results["layer3"]:
  grounding_rate: {value}
  drop_rate: {value}
  extraction_density_mean: {value}
  ...etc for all 17 metrics
}

── ADDITIONAL CONTEXT ──
Batch merge rate progression: {batch_merge_rates formatted}
ITS history: {last 3 ITS values}
Saturation status: {reached/not reached}

Interpret each metric and provide an overall data quality assessment.
```

### 4.2 Call 2: Structural Diagnostics

**System prompt:**
```
You are a qualitative data analyst evaluating the thematic structure produced
by an automated Braun & Clarke thematic analysis pipeline.

You receive the full Category → Theme → IC hierarchy with evidence counts.
Your task: assess the quality and coherence of this structure.

For each theme, evaluate:
1. Is the theme well-defined? Does the name accurately capture its ICs?
2. Is there sufficient evidence (quote count)?
3. Are the ICs cohesive (do they belong together)?
4. Is there a sentiment mixing issue?
5. Is this a "magnet theme" (too many ICs, low coherence)?

For each category, evaluate:
1. Do the themes within it form a coherent grouping?
2. Is the category too broad (catch-all) or too narrow (single theme)?

Identify the strongest themes (well-evidenced, coherent, clearly defined)
and weakest themes (sparse evidence, low coherence, unclear boundaries).

Be specific in your assessments — reference theme names, IC counts, and
concrete observations. Avoid generic statements.
```

**User prompt:**
```
── THEMATIC STRUCTURE ──
{for each category:
  CATEGORY: {name} ({definition})
    {for each theme in category:
      THEME: {name} ({definition})
        Coherence: {score if available}
        Sentiment purity: {score if available}
        ICs ({count}):
          {for each IC (max 2 example quotes per IC to limit size):
            - {ic_name}: {definition} [{quote_count} quotes]
              Example: "{first_quote_text[:100]}"
          }
    }
}

── LAYER 2 SUMMARY ──
Themes proposed: {n}
Themes after refinement: {n}
Themes dissolved (coherence gate): {names}
ICs redistributed: {n}
ICs unassigned: {n}

── COHERENCE DETAILS ──
{per-theme coherence scores}
{distinctness warnings (overlapping pairs)}

Assess the thematic structure. Be specific about each theme.
```

### 4.3 Call 3: Synthesis & Recommendations

**System prompt:**
```
You are a senior research methodologist providing final recommendations
for a qualitative data analysis pipeline run.

You receive:
1. A metrics interpretation (from a colleague who analyzed the quality metrics)
2. A structural diagnostics report (from a colleague who analyzed the thematic structure)
3. The pipeline configuration used for this run

Your task: synthesize these into actionable guidance.

1. Overall assessment: what is the quality and trustworthiness of this analysis?
2. Key findings: what are the 3-7 most important observations?
3. Config recommendations: what specific parameter changes would improve results?
4. Next steps: what should the analyst do next? (prioritized)
5. Confidence note: what caveats should the analyst keep in mind?

Be concrete and actionable. Reference specific metrics, themes, and config
parameters. Avoid vague recommendations like "improve data quality."
```

**User prompt:**
```
── METRICS INTERPRETATION ──
{MetricsInterpretation serialized as formatted text}

── STRUCTURAL DIAGNOSTICS ──
{StructuralDiagnostics serialized as formatted text}

── CURRENT CONFIGURATION ──
{relevant config values:
  batch_size: {v}
  segments_per_coder_call: {v}
  auto_merge_threshold: {v}
  auto_new_threshold: {v}
  coherence_threshold: {v}
  category_merge_threshold: {v}
  distinctness_threshold: {v}
  split_min_ics: {v}
  ...
}

── RUN SUMMARY ──
Documents: {n}, Segments: {n}, Active ICs: {n}
Themes: {n} (after refinement), Categories: {n}
Mode: Discovery
Model: {agent models used}

Synthesize the analysis and provide concrete recommendations.
```

---

## 5. Implementation Plan

### 5.1 File: `src/config.py`

Add `AnalystGuidelinesConfig` with all metric guideline fields.
Add `analyst_guidelines: AnalystGuidelinesConfig` to `EQDConfig`.
Parse from YAML in `load_config()`.

### 5.2 File: `src/models.py`

Add all Pydantic models from Section 2:
- `MetricAssessment`
- `MetricsInterpretation`
- `ThemeDiagnostic`
- `CategoryDiagnostic`
- `StructuralDiagnostics`
- `ConfigRecommendation`
- `AnalystSynthesis`
- `AnalyticalBrief`

### 5.3 File: `src/prompts.py`

Add 6 new prompt functions:
- `build_metrics_interpretation_system_prompt()` → static system prompt
- `build_metrics_interpretation_user_prompt(results, guidelines, run_summary)` → dynamic
- `build_structural_diagnostics_system_prompt()` → static system prompt
- `build_structural_diagnostics_user_prompt(thematic_structure, layer2_results, coherence_data)` → dynamic
- `build_analyst_synthesis_system_prompt()` → static system prompt
- `build_analyst_synthesis_user_prompt(metrics_interp, structural_diag, config, run_summary)` → dynamic

### 5.4 File: `src/analyst_agent.py` (NEW)

```python
class AnalystAgent:
    """Layer 4: LLM-powered analytical interpretation."""

    def __init__(self, model_client, config):
        self.model_client = model_client
        self.config = config

    def analyze(self, results: Dict[str, Any]) -> AnalyticalBrief:
        """Run all 3 analysis calls and return combined brief."""
        metrics_interp = self._interpret_metrics(results)
        structural_diag = self._diagnose_structure(results)
        synthesis = self._synthesize(metrics_interp, structural_diag, results)
        return AnalyticalBrief(
            metrics=metrics_interp,
            structure=structural_diag,
            synthesis=synthesis,
        )

    def _interpret_metrics(self, results) -> MetricsInterpretation:
        """Call 1: metrics interpretation."""
        ...

    def _diagnose_structure(self, results) -> StructuralDiagnostics:
        """Call 2: structural diagnostics."""
        ...

    def _synthesize(self, metrics, structure, results) -> AnalystSynthesis:
        """Call 3: synthesis and recommendations."""
        ...

    # @retry-decorated LLM call methods (same pattern as SynthesizerAgent):
    def _call_metrics_llm(...) -> MetricsInterpretation: ...
    def _call_structural_llm(...) -> StructuralDiagnostics: ...
    def _call_synthesis_llm(...) -> AnalystSynthesis: ...
```

### 5.5 File: `src/pipeline.py`

Add to `__init__`:
```python
self.analyst = AnalystAgent(self.model_client, self.config)
```

Add to `run()`, after Layer 3 and before final display:
```python
# ── Layer 4: Analyst Intelligence ──────────────────────────────
logger.info("[PIPELINE] Layer 4: Analytical interpretation")
try:
    analytical_brief = self.analyst.analyze(results)
    results["layer4"] = analytical_brief.model_dump()
    logger.info("[PIPELINE] Layer 4 complete")
except Exception as e:
    logger.error(f"[PIPELINE] Layer 4 failed (non-fatal): {e}")
    results["layer4"] = None
```

Layer 4 failure is NON-FATAL — the pipeline still completes and returns all other results.

### 5.6 File: `src/quality_report.py`

Add `display_analytical_brief(brief: Dict)` function that renders the Layer 4 output
in the terminal. Format: section headers + text blocks, no complex tables.

```
═══════════════════════════════════════════════════
  LAYER 4: ANALYTICAL INTERPRETATION
═══════════════════════════════════════════════════

── METRICS ASSESSMENT ──────────────────────────────
  grounding_rate: 96.2% [HEALTHY]
    All quotes verified against source text...

  drop_rate: 9.2% [HEALTHY]
    Span validation is working effectively...

  ...

── DATA QUALITY SUMMARY ────────────────────────────
  {data_quality_summary}

── SATURATION ──────────────────────────────────────
  {saturation_assessment}

── THEMATIC STRUCTURE ──────────────────────────────
  Strongest: {list}
  Weakest: {list}

  {per-theme diagnostics}

── OVERALL ASSESSMENT ──────────────────────────────
  {overall_assessment}

── KEY FINDINGS ────────────────────────────────────
  1. {finding}
  2. {finding}
  ...

── RECOMMENDATIONS ─────────────────────────────────
  Config changes:
    {parameter}: {current} → {suggested} ({rationale})
    ...

  Next steps:
    1. {step}
    2. {step}
    ...

── CONFIDENCE NOTE ─────────────────────────────────
  {confidence_note}
═══════════════════════════════════════════════════
```

### 5.7 File: `eqd_config.yaml`

Add `analyst_agent` to agents section.
Add full `analyst_guidelines` section (from Section 3.2 above).

### 5.8 Tests

**`tests/test_analyst_agent.py`:**
- Test prompt building (all 6 functions)
- Test with mocked LLM responses (3 calls)
- Test graceful failure (LLM error → None, pipeline continues)
- Test config parsing (guidelines from YAML)
- Test model validation (all Pydantic models)

---

## 6. Input Data Reference

What each call receives from the existing `results` dict:

### Call 1 reads from `results["layer3"]`:
```python
{
    "grounding": {"total_quotes": int, "verified": int, "grounding_rate": float, ...},
    "extraction_density": {"distribution": {"mean": float, ...}, "drop_rate": {"overall_rate": float, ...}},
    "ic_concentration": {"active_ics": int, "singleton_count": int, "singleton_ratio": float, ...},
    "merge_rate": {"per_batch": [...], "overall": float},
    "triage_efficiency": {"auto_new": int, "auto_merge": int, "grey_zone": int, "auto_rate": float},
    "comparator_agreement": {"total_grey": int, "agreed": int, "agreement_rate": float},
    "its_history": [BatchITS(...)],
    "meaning_saturation_per_theme": {...},
    "theme_coherence": {"per_theme": {...}, "mean": float},
    "theme_distinctness": {"overlapping_pairs": [...], "overlap_ratio": float},
    "coherence_normalized": {...},
    "cross_theme_ic_sharing": {...},
    "ic_stability": {"mean_stability": float, "substantially_rewritten": int},
    "orphaned_ics": {"count": int, "ic_ids": [...]},
    "thematic_coverage": {"ratio": float},
    "cross_review_convergence": {"confirmed_ratio": float, "strong_ratio": float},
    "sentiment_purity": {"per_theme": {...}, "mean": float},
}
```

### Call 2 reads from `results["thematic_structure"]`:
```python
[
    {
        "id": str, "name": str, "definition": str,
        "theme_count": int,
        "themes": [
            {
                "id": str, "name": str, "definition": str, "rationale": str,
                "ic_count": int,
                "initial_codes": [
                    {"id": str, "name": str, "definition": str, "quote_count": int,
                     "quotes": [{"quote_text": str, ...}]},
                ],
            },
        ],
    },
]
```

### Call 3 reads from outputs of Call 1 + Call 2, plus:
- `results["layer0"]`: document/segment counts
- `results["layer1"]`: IC creation stats
- `results["layer2"]`: theme synthesis stats
- Pipeline config (from `self.config`)

---

## 7. Key Design Decisions

1. **Three calls, not one.** Focused context per call → better reasoning. Total cost ~3 Sonnet calls.
2. **Guidelines, not thresholds.** YAML-configurable reference ranges. The LLM contextualizes, doesn't judge.
3. **Metric definitions in prompt.** Each metric gets its full definition + what high/low means, so the LLM understands what it's interpreting.
4. **Limited quotes in Call 2.** Max 2 example quotes per IC to keep prompt size manageable. IC definitions provide the semantic content.
5. **Non-fatal.** Layer 4 failure doesn't break the pipeline. Results are still complete without it.
6. **No DB persistence (v1).** The brief lives in `results["layer4"]` and gets serialized to the results JSON file. DB persistence can come later if needed for cross-run comparison.

---

## 8. Implementation Order

1. `src/models.py` — add all 8 Pydantic models
2. `eqd_config.yaml` — add `analyst_agent` + `analyst_guidelines` sections
3. `src/config.py` — add `AnalystGuidelinesConfig`, parse from YAML
4. `src/prompts.py` — add 6 prompt functions
5. `src/analyst_agent.py` — new file, 3 public + 3 private methods
6. `src/pipeline.py` — wire Layer 4 into `run()`, add to `__init__`
7. `src/quality_report.py` — add `display_analytical_brief()`
8. `tests/test_analyst_agent.py` — full test coverage
9. Run all tests

---

*Document version: 1.0 — 2026-02-23*
*Based on: pipeline output analysis, quality metrics engine (17 metrics),
existing Sonnet 4.5 agent patterns (synthesizer, category agents)*
