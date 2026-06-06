"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from src.core.models import (
    Document,
    InitialCode,
    ICStatus,
    Segment,
    VerbatimQuote,
    Theme,
    DecisionLog,
    DecisionType,
    QualityMetric,
    MetricType,
    new_id,
)


class TestNewId:
    def test_length(self):
        assert len(new_id()) == 12

    def test_unique(self):
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100


class TestDocument:
    def test_defaults(self):
        doc = Document(raw_text="Hello world")
        assert doc.id  # auto-generated
        assert doc.source_file is None
        assert doc.metadata == {}
        assert doc.created_at is not None

    def test_with_metadata(self):
        doc = Document(raw_text="Test", metadata={"rating": 5})
        assert doc.metadata["rating"] == 5


class TestSegment:
    def test_compute_hash(self):
        seg = Segment(
            document_id="doc1",
            canonical_text="Hello world",
            original_text="Hello world",
        )
        h = seg.compute_hash()
        assert len(h) == 64  # SHA-256 hex

    def test_verify_integrity_pass(self):
        seg = Segment(
            document_id="doc1",
            canonical_text="Hello world",
            original_text="Hello world",
        )
        seg.content_hash = seg.compute_hash()
        assert seg.verify_integrity() is True

    def test_verify_integrity_fail(self):
        seg = Segment(
            document_id="doc1",
            canonical_text="Hello world",
            original_text="Hello world",
            content_hash="wrong_hash",
        )
        assert seg.verify_integrity() is False


class TestVerbatimQuote:
    def test_valid_span(self):
        vq = VerbatimQuote(
            segment_id="seg1",
            quote_text="test",
            span_start=0,
            span_end=4,
        )
        assert vq.span_start == 0
        assert vq.span_end == 4

    def test_span_end_must_be_after_start(self):
        with pytest.raises(ValidationError):
            VerbatimQuote(
                segment_id="seg1",
                quote_text="test",
                span_start=5,
                span_end=3,
            )

    def test_span_end_equals_start_fails(self):
        with pytest.raises(ValidationError):
            VerbatimQuote(
                segment_id="seg1",
                quote_text="",
                span_start=5,
                span_end=5,
            )

    def test_verify_correct(self):
        canonical = "The product is great"
        vq = VerbatimQuote(
            segment_id="seg1",
            quote_text="product",
            span_start=4,
            span_end=11,
        )
        assert vq.verify(canonical) is True
        assert vq.is_verified is True

    def test_verify_wrong_span(self):
        canonical = "The product is great"
        vq = VerbatimQuote(
            segment_id="seg1",
            quote_text="product",
            span_start=0,
            span_end=7,
        )
        assert vq.verify(canonical) is False
        assert vq.is_verified is False

    def test_verify_hallucinated(self):
        canonical = "The product is great"
        vq = VerbatimQuote(
            segment_id="seg1",
            quote_text="terrible",
            span_start=4,
            span_end=12,
        )
        assert vq.verify(canonical) is False


class TestInitialCode:
    def test_embedding_input_text(self):
        ic = InitialCode(
            name="Delivery complaint",
            definition="Customer unhappy with delivery time",
        )
        assert ic.embedding_input_text() == "Delivery complaint | Customer unhappy with delivery time"

    def test_name_too_short(self):
        with pytest.raises(ValidationError):
            InitialCode(name="", definition="Some valid definition")

    def test_definition_too_short(self):
        with pytest.raises(ValidationError):
            InitialCode(name="Valid name", definition="Hi")


class TestTheme:
    def test_round_finalised_range(self):
        t = Theme(name="Test theme", definition="A test theme definition")
        assert t.round_finalised == 0

    def test_round_finalised_max(self):
        with pytest.raises(ValidationError):
            Theme(name="Test", definition="A test theme definition", round_finalised=4)


class TestDecisionLog:
    def test_similarity_range(self):
        with pytest.raises(ValidationError):
            DecisionLog(
                decision_type=DecisionType.CODEBOOK_UPDATE,
                similarity_score=1.5,
            )


class TestQualityMetric:
    def test_creation(self):
        qm = QualityMetric(
            metric_type=MetricType.GROUNDING,
            value=0.95,
        )
        assert qm.value == 0.95
        assert qm.entity_id is None
