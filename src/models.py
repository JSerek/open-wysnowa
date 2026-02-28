"""
EQD-AI Pydantic Data Models.

All entities from Architecture Document Section 10.
Single file — split when it exceeds ~300 lines.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Helpers ───────────────────────────────────────────────────────────────────

def new_id() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:12]


# ── Enums ─────────────────────────────────────────────────────────────────────

class ICStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MERGED = "merged"


class DecisionType(str, Enum):
    CODEBOOK_UPDATE = "codebook_update"
    SIGNOFF_EDIT = "signoff_edit"
    THEME_FEEDBACK = "theme_feedback"


class MetricType(str, Enum):
    GROUNDING = "grounding"
    COVERAGE = "coverage"
    ITS = "its"
    MEANING_SATURATION = "meaning_saturation"
    THEME_COHERENCE = "theme_coherence"
    THEME_DISTINCTNESS = "theme_distinctness"
    IC_CONCENTRATION = "ic_concentration"
    MERGE_RATE = "merge_rate"
    TRIAGE_EFFICIENCY = "triage_efficiency"
    COMPARATOR_AGREEMENT = "comparator_agreement"
    CROSS_THEME_IC_SHARING = "cross_theme_ic_sharing"
    COHERENCE_NORMALIZED = "coherence_normalized"
    CANDIDATE_DROP_RATE = "candidate_drop_rate"
    THEMATIC_COVERAGE = "thematic_coverage"
    CROSS_REVIEW_CONVERGENCE = "cross_review_convergence"
    IC_STABILITY = "ic_stability"
    SENTIMENT_PURITY = "sentiment_purity"


# ── Document & Segment ────────────────────────────────────────────────────────

class Document(BaseModel):
    """Raw input record. One per comment/review/response."""
    id: str = Field(default_factory=new_id)
    source_file: Optional[str] = None
    raw_text: str = Field(description="Original unmodified text")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Segment(BaseModel):
    """
    Preprocessed unit of analysis.

    canonical_text is IMMUTABLE after creation. All spans reference it.
    """
    id: str = Field(default_factory=new_id)
    document_id: str
    canonical_text: str = Field(description="Normalised text — ground truth for spans")
    original_text: str = Field(description="Raw text before normalisation")
    char_count: int = Field(default=0)
    segment_index: int = Field(default=0, description="Position within document")
    normalization_rules: List[str] = Field(default_factory=list)
    content_hash: str = Field(default="", description="SHA-256 of canonical_text")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_hash(self) -> str:
        return hashlib.sha256(self.canonical_text.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        return self.content_hash == self.compute_hash()


# ── Initial Code & Verbatim Quote ─────────────────────────────────────────────

class VerbatimQuote(BaseModel):
    """
    Exact substring of canonical_text with character-level span.

    Ground truth verification: canonical_text[span_start:span_end] == quote_text
    """
    id: str = Field(default_factory=new_id)
    ic_id: str = Field(default="")
    segment_id: str
    quote_text: str
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    is_verified: bool = Field(default=False)
    sentiment: Optional[str] = Field(
        default=None,
        description="Sentiment of the quote: positive, negative, neutral, or mixed",
    )
    quote_embedding_json: Optional[List[float]] = None

    @field_validator("span_end")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("span_start", 0)
        if v <= start:
            raise ValueError(f"span_end ({v}) must be greater than span_start ({start})")
        return v

    def verify(self, canonical_text: str) -> bool:
        """Deterministic ground truth check — no LLM involved."""
        expected = canonical_text[self.span_start : self.span_end]
        self.is_verified = expected == self.quote_text
        return self.is_verified


class InitialCode(BaseModel):
    """
    Lowest-level analytical unit, grounded in verbatim evidence.

    Codebook entry. Embedding computed on write (embed-on-write pattern).
    """
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=5, max_length=600)
    embedding_json: Optional[List[float]] = None
    status: ICStatus = Field(default=ICStatus.ACTIVE)
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Coder agent's self-assessed confidence (0–1) at the time this IC "
            "was first created. Reflects how certain the model was that the "
            "extracted concept was grounded in the verbatim text. None for ICs "
            "created before this field was introduced."
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def embedding_input_text(self) -> str:
        """Text to embed: name | definition. Used by EmbeddingService."""
        return f"{self.name} | {self.definition}"


# ── Theme ─────────────────────────────────────────────────────────────────────

class Theme(BaseModel):
    """Higher-order analytical pattern synthesised from ICs."""
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=10, max_length=1000)
    rationale: str = Field(default="", description="Why these ICs form a coherent theme")
    round_finalised: int = Field(default=0, ge=0, le=3)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ThemeIC(BaseModel):
    """M:N junction between Theme and InitialCode."""
    theme_id: str
    ic_id: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


# ── Category (higher-order grouping above themes) ────────────────────────────

class Category(BaseModel):
    """Higher-order cluster of themes (e.g. 'Parkour', 'Combat', 'Story')."""
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=150)
    definition: str = Field(min_length=10, max_length=800)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryTheme(BaseModel):
    """M:N junction between Category and Theme."""
    category_id: str
    theme_id: str
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class CategoryProposal(BaseModel):
    """LLM response model: one proposed category."""
    name: str = Field(
        min_length=1,
        max_length=150,
        description=(
            "Short category label (2-5 words) representing the highest level of abstraction. "
            "Use a noun phrase, not a sentence."
        ),
    )
    definition: str = Field(
        min_length=10,
        max_length=800,
        description=(
            "1-2 sentence definition of what conceptually unifies these themes "
            "at a higher level of abstraction than any individual theme."
        ),
    )
    constituent_theme_names: List[str] = Field(
        min_length=1,
        description=(
            "Exact names of themes from the provided input list. "
            "Copy theme names verbatim — spelling and capitalisation must match exactly."
        ),
    )


class CategorySynthesisOutput(BaseModel):
    """Full response from the category synthesis LLM call."""
    reasoning: str = Field(
        min_length=10,
        description="Chain-of-thought: how themes were grouped into categories and why",
    )
    categories: List[CategoryProposal] = Field(
        min_length=1,
        description=(
            "All proposed categories. Every theme from the input list must appear "
            "in exactly one category's constituent_theme_names."
        ),
    )


# ── Audit & Quality ──────────────────────────────────────────────────────────

class DecisionLog(BaseModel):
    """Full audit trail entry for every analytical decision."""
    id: str = Field(default_factory=new_id)
    decision_type: DecisionType
    ic_id: Optional[str] = None
    llm_recommendation: Optional[str] = None
    human_action: Optional[str] = None
    similarity_score: Optional[float] = Field(default=None, ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class QualityMetric(BaseModel):
    """Computed quality signal — not a gate, a signal for the analyst."""
    id: str = Field(default_factory=new_id)
    metric_type: MetricType
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    value: float
    computed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Layer 1: LLM Response Models ────────────────────────────────────────────

class Sentiment(str, Enum):
    """Sentiment of a verbatim quote as assessed by the Coder Agent."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ICCandidate(BaseModel):
    """
    Single IC candidate extracted by the Coder Agent from a segment.

    The LLM outputs a list of these per segment. Each must include
    an exact verbatim quote with character-level span offsets.
    """
    ic_name: str = Field(
        min_length=1,
        max_length=120,
        description=(
            "Short noun-phrase label for the concept (3-8 words). "
            "Describe what the code represents, not the quote itself. "
            "Do not use verbs as labels."
        ),
    )
    definition: str = Field(
        min_length=5,
        max_length=600,
        description=(
            "One-sentence definition of what this code captures. "
            "Must be directly grounded in the verbatim text — "
            "do not infer beyond what is explicitly stated."
        ),
    )
    quote_text: str = Field(
        min_length=1,
        description="Exact substring of canonical_text — copy verbatim, no paraphrasing",
    )
    span_start: int = Field(
        ge=0,
        description="Character offset of the start of quote_text in canonical_text (0-indexed, inclusive)",
    )
    span_end: int = Field(
        ge=1,
        description=(
            "Character offset of the end of quote_text in canonical_text (exclusive). "
            "Must satisfy: canonical_text[span_start:span_end] == quote_text exactly."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0-1")
    sentiment: Optional[Sentiment] = Field(
        default=None,
        description="Sentiment of the verbatim quote: positive, negative, neutral, or mixed",
    )
    existing_code_match: Optional[str] = Field(
        default=None,
        description="Name of matching existing IC, or null if proposing new code",
    )

    @field_validator("span_end")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("span_start", 0)
        if v <= start:
            raise ValueError(f"span_end ({v}) must be > span_start ({start})")
        return v


class SegmentCodingResult(BaseModel):
    """
    Instructor response wrapper: Coder Agent output for one segment.

    Used as response_model in the instructor call (single-segment mode).
    """
    segment_id: str
    candidates: List[ICCandidate] = Field(default_factory=list)


class BatchCodingResult(BaseModel):
    """
    Multi-segment coding result: Coder Agent output for N segments.

    Used as response_model when segments_per_coder_call > 1.
    Each SegmentCodingResult carries its segment_id so we can map
    candidates back to their source segment for span validation.
    """
    segment_results: List[SegmentCodingResult] = Field(default_factory=list)


class ComparatorRecommendation(str, Enum):
    """Codebook Comparator's recommendation for a new IC candidate."""
    NEW = "NEW"
    MERGE = "MERGE"
    REJECT = "REJECT"


class ComparatorOutput(BaseModel):
    """
    Codebook Comparator LLM response.

    Used as response_model in the instructor call for comparison reasoning.
    """
    recommendation: ComparatorRecommendation = Field(
        description=(
            "Your decision: NEW (add to codebook as a distinct concept), "
            "MERGE (semantically equivalent to an existing code — same meaning or a "
            "meaningful specialisation that doesn't warrant its own code), "
            "or REJECT (not a valid analytical concept — meta-commentary, noise, or too vague)."
        ),
    )
    merge_target_name: Optional[str] = Field(
        default=None,
        description="Name of existing IC to merge into (if MERGE)",
    )
    reasoning: str = Field(
        min_length=5,
        description="Brief explanation of the recommendation",
    )


class BatchITS(BaseModel):
    """
    Incremental Type Saturation tracking for one batch.

    ITS = new_ics_created / ics_before (rate of new code emergence).
    Saturation checkpoint triggers when ITS < threshold for N consecutive batches.
    """
    batch_number: int = Field(ge=1)
    ics_before: int = Field(ge=0)
    new_ics_created: int = Field(ge=0)
    its_value: float = Field(ge=0.0)
    consecutive_low: int = Field(default=0, ge=0)
    is_checkpoint: bool = Field(default=False)


class SaturationPoint(BaseModel):
    """One point on the cumulative IC discovery curve.

    Plotted: x = segment_index (0-based), y = fraction (0.0 → 1.0).
    """
    segment_index: int = Field(ge=0)
    cumulative_ics: int = Field(ge=0)
    total_ics: int = Field(ge=0)
    fraction: float = Field(ge=0.0, le=1.0)
    new_ics_in_segment: int = Field(default=0, ge=0)


# ── Layer 2: Theme Synthesis Models ──────────────────────────────────────────

class ThemeProposal(BaseModel):
    """
    Single theme proposed by the Synthesizer Agent.

    Themes group related ICs into higher-order patterns of meaning.
    M:N relationship: one IC can belong to multiple themes.
    Quotes are inherited transitively (IC → VerbatimQuote), not re-extracted.
    """
    name: str = Field(min_length=1, max_length=80, description="Short descriptive label, 3-6 words")
    definition: str = Field(
        min_length=10,
        max_length=1000,
        description=(
            "1-3 sentence definition of what conceptually unifies these ICs "
            "at a higher level of abstraction. Describe the pattern, not just list the codes."
        ),
    )
    rationale: str = Field(
        min_length=5,
        description="Why these ICs form a coherent theme",
    )
    constituent_ic_names: List[str] = Field(
        min_length=1,
        description="Names of ICs assigned to this theme",
    )


class SynthesisOutput(BaseModel):
    """
    Full Synthesizer Agent response (response_model for instructor).

    Contains all proposed themes for the codebook.
    reasoning captures the CoT steps the LLM followed (cluster → label → merge → check → finalise).
    """
    reasoning: str = Field(
        min_length=10,
        description="Chain-of-thought: clustering, labelling, redundancy check, coverage check",
    )
    themes: List[ThemeProposal] = Field(
        min_length=1,
        description=(
            "All proposed themes. Every active IC in the provided codebook "
            "must appear in at least one theme's constituent_ic_names list."
        ),
    )


class ThemeFeedbackOption(str, Enum):
    """Structured feedback options for theme iteration (HIL Level 3)."""
    SPLIT = "1"            # Too broad — split into two sub-themes
    MERGE = "2"            # Too narrow — merge with another theme
    IC_MISASSIGNED = "3"   # Move specific IC to a different theme
    RENAME = "4"           # Apply new name
    REDEFINE = "5"         # Apply revised definition
    OVERLAP_CONFLICT = "6" # Flag two themes as too similar
    FREETEXT = "7"         # Any other feedback


class ThemeFeedback(BaseModel):
    """
    Human feedback on a single theme during HIL iteration.

    details carries option-specific data:
    - SPLIT: provisional names for sub-themes
    - MERGE: target theme name to merge with
    - IC_MISASSIGNED: "ic_name -> target_theme_name"
    - RENAME: new name
    - REDEFINE: new definition
    - OVERLAP_CONFLICT: other theme name
    - FREETEXT: free-text instruction
    """
    theme_name: str
    option: ThemeFeedbackOption
    details: Optional[str] = None


class RevisionOutput(BaseModel):
    """
    Synthesizer Agent's revision response after receiving human feedback.

    Used as response_model for rounds 2-3.
    """
    themes: List[ThemeProposal] = Field(
        min_length=1,
        description=(
            "Complete revised theme list. Include all themes — "
            "both the ones you changed and the ones you left unchanged."
        ),
    )
    changes_summary: str = Field(
        min_length=5,
        description="Summary of changes made in response to feedback",
    )


# ── Layer 2: Post-Synthesis Refinement Models ─────────────────────────────


class DistinctnessRevisionOutput(BaseModel):
    """
    LLM response for distinctness-aware revision pass.

    The LLM receives overlapping theme pairs and decides to MERGE or SHARPEN each.
    Returns the full revised theme list (revised + unchanged).
    """
    reasoning: str = Field(
        min_length=10,
        description="Brief explanation of merge/sharpen decisions for each flagged pair",
    )
    themes: List[ThemeProposal] = Field(
        min_length=1,
        description=(
            "Complete revised theme list. Include all themes — "
            "both the merged/sharpened ones and the unchanged ones."
        ),
    )


class SplitProposal(BaseModel):
    """One half of a proposed theme split."""
    name: str = Field(min_length=1, max_length=80)
    definition: str = Field(min_length=10, max_length=1000)
    constituent_ic_names: List[str] = Field(min_length=1)


class SplitValidationOutput(BaseModel):
    """
    LLM response for theme split validation.

    The LLM evaluates whether a k-means split of a magnet theme is
    semantically meaningful or just a statistical artifact.
    """
    should_split: bool = Field(
        description="True if the split is meaningful, False if the theme should stay unified",
    )
    reasoning: str = Field(
        min_length=10,
        description="Why the split is or isn't meaningful",
    )
    sub_themes: Optional[List[SplitProposal]] = Field(
        default=None,
        description="Two sub-themes if should_split=True. Null if should_split=False.",
    )


class OrphanDisposition(BaseModel):
    """
    LLM disposition for a single orphaned IC.

    Three possible actions:
      - assign_existing: IC fits a surviving theme — target_theme required
      - new_theme: IC should be grouped with other orphans into a new thin theme
      - isolated: IC is a genuine one-off, no meaningful thematic home
    """
    ic_name: str = Field(description="Name of the orphaned IC")
    action: str = Field(
        description="One of: assign_existing, new_theme, isolated",
    )
    target_theme: Optional[str] = Field(
        default=None,
        description="Name of existing surviving theme (required if action=assign_existing)",
    )
    reasoning: str = Field(
        min_length=5,
        max_length=300,
        description="Brief justification for this disposition",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"assign_existing", "new_theme", "isolated"}
        alias_map = {
            "assign": "assign_existing",
            "existing": "assign_existing",
            "new": "new_theme",
            "thin_theme": "new_theme",
            "flag": "isolated",
            "standalone": "isolated",
            "unassigned": "isolated",
        }
        if v in alias_map:
            return alias_map[v]
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}, got '{v}'")
        return v


class OrphanReassessmentOutput(BaseModel):
    """
    Full LLM response for the orphan IC reassessment pass.

    Contains a disposition for every orphaned IC plus any new thin themes
    to create from grouped orphans.
    """
    reasoning: str = Field(
        min_length=10,
        max_length=1000,
        description="Overall reasoning across all dispositions",
    )
    dispositions: List["OrphanDisposition"] = Field(
        min_length=1,
        description="One disposition per orphaned IC — every orphan must be accounted for",
    )
    new_themes: List[ThemeProposal] = Field(
        default_factory=list,
        description=(
            "New thin themes formed from grouped orphans. "
            "Only include if action=new_theme was assigned to 2+ ICs with common ground."
        ),
    )


class RefinedICOutput(BaseModel):
    """
    LLM response for IC definition refinement.

    After all segments are processed, ICs that received 3+ merges may have
    definitions that no longer reflect the full breadth of their evidence.
    This model captures the refined definition.
    """
    refined_definition: str = Field(
        min_length=5,
        max_length=600,
        description="Updated definition that reflects all merged evidence",
    )
    change_summary: str = Field(
        min_length=3,
        description="Brief note on what changed and why",
    )


# ── Layer 4: Analyst Intelligence Models ─────────────────────────────────


class MetricAssessment(BaseModel):
    """Assessment of a single quality metric."""
    metric_name: str = Field(description="Metric identifier, e.g. 'grounding_rate'")
    observed_value: str = Field(description="Formatted value, e.g. '96.2%', '28/120 pairs'")
    status: str = Field(
        description="healthy=within guidelines, monitor=borderline, investigate=outside guidelines",
    )
    interpretation: str = Field(
        min_length=20, max_length=500,
        description="What this value means in context of this specific run",
    )
    context_factors: Optional[str] = Field(
        default=None, max_length=300,
        description="Factors that might explain the value (sample size, data characteristics, etc.)",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"healthy", "monitor", "investigate"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


class MetricsInterpretation(BaseModel):
    """Output of Call 1: metrics interpretation."""
    assessments: List[MetricAssessment] = Field(
        min_length=1,
        description=(
            "One MetricAssessment per metric provided in the input. "
            "Include every metric — do not skip any."
        ),
    )
    data_quality_summary: str = Field(
        min_length=50, max_length=800,
        description="Overall assessment of data integrity and codebook health",
    )
    saturation_assessment: str = Field(
        min_length=50, max_length=500,
        description="Is the codebook saturated? Should we process more data?",
    )


class ThemeDiagnostic(BaseModel):
    """Diagnostic for a single theme."""
    theme_name: str
    ic_count: int
    coherence: Optional[float] = None
    issue_type: Optional[str] = Field(default="healthy")
    assessment: str = Field(min_length=20, max_length=800)
    suggested_action: Optional[str] = Field(
        default=None, max_length=400,
        description="Specific action if issue detected",
    )

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, v: Optional[str]) -> Optional[str]:
        allowed = {
            "magnet_theme", "weak_coherence", "low_evidence",
            "naming_unclear", "sentiment_mixed", "healthy",
            # aliases the LLM commonly uses — map to canonical values below
            "low_coherence", "dissolved", "sentiment_mixing",
            "boundary_overlap", "catch_all",
            None,
        }
        # normalise aliases to canonical
        alias_map = {
            "low_coherence": "weak_coherence",
            "sentiment_mixing": "sentiment_mixed",
            "dissolved": "healthy",       # dissolved themes have no remaining issues
            "boundary_overlap": "weak_coherence",
            "catch_all": "magnet_theme",
        }
        if v in alias_map:
            return alias_map[v]
        if v not in allowed:
            raise ValueError(f"issue_type must be one of {allowed}, got '{v}'")
        return v


class CategoryDiagnostic(BaseModel):
    """Diagnostic for a category grouping."""
    category_name: str
    theme_count: int
    assessment: str = Field(min_length=20, max_length=500)
    potential_issue: Optional[str] = Field(default="healthy")

    @field_validator("potential_issue")
    @classmethod
    def validate_potential_issue(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"too_broad", "single_theme", "misaligned_themes", "healthy", None}
        # normalise aliases
        alias_map = {
            "catch_all": "too_broad",
            "boundary_overlap": "misaligned_themes",
        }
        if v in alias_map:
            return alias_map[v]
        if v not in allowed:
            raise ValueError(f"potential_issue must be one of {allowed}, got '{v}'")
        return v


class StructuralDiagnostics(BaseModel):
    """Output of Call 2: structural analysis."""
    theme_diagnostics: List[ThemeDiagnostic] = Field(
        min_length=1,
        description=(
            "One ThemeDiagnostic per theme. Assess every theme in the input list — "
            "do not omit any, even if the theme appears healthy."
        ),
    )
    category_diagnostics: List[CategoryDiagnostic] = Field(
        default_factory=list,
        description=(
            "One CategoryDiagnostic per category. Include all categories if provided. "
            "Empty list if no categories exist."
        ),
    )
    strongest_themes: List[str] = Field(
        description="Top themes by evidence quality + coherence",
    )
    weakest_themes: List[str] = Field(
        description="Themes needing attention",
    )
    structural_summary: str = Field(
        min_length=50, max_length=1500,
        description="Overall assessment of the thematic structure",
    )


class ConfigRecommendation(BaseModel):
    """A specific configuration change suggestion."""
    parameter: str = Field(description="YAML config key, e.g. 'processing.category_merge_threshold'")
    current_value: str = Field(
        description="The parameter's current value, as a string (read from the config provided).",
    )
    suggested_value: str = Field(
        description="The recommended new value, as a string.",
    )
    rationale: str = Field(min_length=20, max_length=300)


class AnalystSynthesis(BaseModel):
    """Output of Call 3: synthesis and recommendations."""
    overall_assessment: str = Field(
        min_length=100, max_length=2000,
        description="Integrative assessment of the full analysis — what did we learn?",
    )
    key_findings: List[str] = Field(
        min_length=1,
        description="Most important takeaways, ordered by significance",
    )
    config_recommendations: List[ConfigRecommendation] = Field(default_factory=list)
    next_steps: List[str] = Field(
        min_length=1,
        description="Prioritised actions: what should the analyst do next?",
    )
    confidence_note: str = Field(
        min_length=20, max_length=500,
        description="Caveats: sample size, saturation status, known limitations of this run",
    )


class AnalyticalBrief(BaseModel):
    """Full Layer 4 output — container for all three call results."""
    metrics: MetricsInterpretation
    structure: StructuralDiagnostics
    synthesis: AnalystSynthesis
