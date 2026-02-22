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
    name: str = Field(min_length=1, max_length=150)
    definition: str = Field(min_length=10, max_length=800)
    constituent_theme_names: List[str] = Field(min_length=1)


class CategorySynthesisOutput(BaseModel):
    """Full response from the category synthesis LLM call."""
    reasoning: str = Field(
        min_length=10,
        description="Chain-of-thought: how themes were grouped into categories and why",
    )
    categories: List[CategoryProposal] = Field(min_length=1)


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
    ic_name: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=5, max_length=600)
    quote_text: str = Field(min_length=1, description="Exact substring of canonical_text")
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
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
    SUBCODE = "SUBCODE"
    REJECT = "REJECT"


class ComparatorOutput(BaseModel):
    """
    Codebook Comparator LLM response.

    Used as response_model in the instructor call for comparison reasoning.
    """
    recommendation: ComparatorRecommendation
    merge_target_name: Optional[str] = Field(
        default=None,
        description="Name of existing IC to merge into (if MERGE/SUBCODE)",
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
    definition: str = Field(min_length=10, max_length=1000)
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
    themes: List[ThemeProposal] = Field(min_length=1)


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
    themes: List[ThemeProposal] = Field(min_length=1)
    changes_summary: str = Field(
        min_length=5,
        description="Summary of changes made in response to feedback",
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
