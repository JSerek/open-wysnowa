"""Tests for the Coder Agent with mocked LLM calls."""

import pytest
from unittest.mock import MagicMock, patch

from src.coder_agent import CoderAgent
from src.models import BatchCodingResult, ICCandidate, Segment, SegmentCodingResult


@pytest.fixture
def mock_model_client():
    """ModelClient mock that returns a mock instructor client."""
    mc = MagicMock()
    mock_client = MagicMock()
    mc.get_client.return_value = (mock_client, "test-model", MagicMock(temperature=0.2, max_tokens=4000))
    return mc, mock_client


@pytest.fixture
def test_segment():
    """Segment with known canonical text for span validation."""
    return Segment(
        id="seg_test",
        document_id="doc_test",
        canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
        original_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
        char_count=51,
        segment_index=0,
        content_hash="test_hash",
    )


class TestCoderAgentSpanValidation:
    """Test the _validate_span method — the critical quality gate."""

    def test_valid_span(self, mock_model_client, db, test_segment):
        mc, _ = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        canonical = test_segment.canonical_text
        quote_text = "dostawa trwała zbyt długo"
        start = canonical.index(quote_text)

        candidate = ICCandidate(
            ic_name="slow_delivery",
            definition="Customer reports slow delivery",
            quote_text=quote_text,
            span_start=start,
            span_end=start + len(quote_text),
            confidence=0.9,
        )
        assert agent._validate_span(candidate, test_segment) is True

    def test_wrong_offset_realigned(self, mock_model_client, db, test_segment):
        """Wrong offset but valid quote text → Tier 2 realigns, returns True."""
        mc, _ = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        candidate = ICCandidate(
            ic_name="slow_delivery",
            definition="Customer reports slow delivery",
            quote_text="dostawa trwała zbyt długo",
            span_start=0,  # Wrong offset
            span_end=25,
            confidence=0.9,
        )
        assert agent._validate_span(candidate, test_segment) is True
        # Verify spans were corrected in place
        assert candidate.span_start == 26
        assert candidate.span_end == 51

    def test_hallucinated_quote_dropped(self, mock_model_client, db, test_segment):
        """Quote text not in canonical at all → all tiers fail, returns False."""
        mc, _ = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        candidate = ICCandidate(
            ic_name="slow_delivery",
            definition="Customer reports slow delivery",
            quote_text="this text does not exist anywhere in the segment",
            span_start=0,
            span_end=48,
            confidence=0.9,
        )
        assert agent._validate_span(candidate, test_segment) is False

    def test_invalid_span_out_of_bounds(self, mock_model_client, db, test_segment):
        mc, _ = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        candidate = ICCandidate(
            ic_name="bad_code",
            definition="Some definition here",
            quote_text="text beyond the end",
            span_start=100,
            span_end=119,
            confidence=0.5,
        )
        assert agent._validate_span(candidate, test_segment) is False

    def test_hallucinated_text(self, mock_model_client, db, test_segment):
        mc, _ = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        candidate = ICCandidate(
            ic_name="hallucinated",
            definition="This text doesn't exist",
            quote_text="ten produkt jest okropny",
            span_start=0,
            span_end=24,
            confidence=0.8,
        )
        assert agent._validate_span(candidate, test_segment) is False


class TestCoderAgentProcessBatch:
    """Test process_batch with mocked LLM responses."""

    def test_returns_valid_candidates_only(self, mock_model_client, db, test_segment):
        mc, mock_client = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        canonical = test_segment.canonical_text
        good_text = "dostawa trwała zbyt długo"
        good_start = canonical.index(good_text)

        # Mock LLM to return one valid and one invalid candidate
        mock_result = SegmentCodingResult(
            segment_id=test_segment.id,
            candidates=[
                ICCandidate(
                    ic_name="valid_code",
                    definition="A valid code with correct spans",
                    quote_text=good_text,
                    span_start=good_start,
                    span_end=good_start + len(good_text),
                    confidence=0.9,
                ),
                ICCandidate(
                    ic_name="invalid_code",
                    definition="A code with wrong span offsets",
                    quote_text="wrong text here",
                    span_start=0,
                    span_end=15,
                    confidence=0.7,
                ),
            ],
        )
        mock_client.chat.completions.create.return_value = mock_result

        results = agent.process_batch([test_segment])

        assert test_segment.id in results
        assert len(results[test_segment.id]) == 1
        assert results[test_segment.id][0].ic_name == "valid_code"

    def test_empty_segment_returns_empty(self, mock_model_client, db):
        mc, mock_client = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        empty_segment = Segment(
            id="seg_empty",
            document_id="doc_test",
            canonical_text="ok",
            original_text="ok",
            char_count=2,
            content_hash="hash",
        )

        mock_result = SegmentCodingResult(
            segment_id="seg_empty",
            candidates=[],
        )
        mock_client.chat.completions.create.return_value = mock_result

        results = agent.process_batch([empty_segment])
        assert results["seg_empty"] == []

    def test_llm_failure_returns_empty(self, mock_model_client, db, test_segment):
        mc, mock_client = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        mock_client.chat.completions.create.side_effect = Exception("API error")

        results = agent.process_batch([test_segment])
        assert results[test_segment.id] == []


class TestCoderAgentBatchProcessing:
    """Tests for multi-segment micro-batch LLM calls."""

    @pytest.fixture
    def two_segments(self):
        return [
            Segment(
                id="seg_a",
                document_id="doc_test",
                canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
                original_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
                char_count=51,
                segment_index=0,
                content_hash="hash_a",
            ),
            Segment(
                id="seg_b",
                document_id="doc_test",
                canonical_text="Jakość materiału jest znakomita. Polecam każdemu!",
                original_text="Jakość materiału jest znakomita. Polecam każdemu!",
                char_count=49,
                segment_index=1,
                content_hash="hash_b",
            ),
        ]

    def test_multi_segment_batch_call(self, mock_model_client, db, two_segments):
        """When segments_per_coder_call > 1, multiple segments go in one LLM call."""
        mc, mock_client = mock_model_client
        config = MagicMock()
        config.processing.segments_per_coder_call = 5  # Both segments fit in one call

        seg_a, seg_b = two_segments
        good_text_a = "dostawa trwała zbyt długo"
        start_a = seg_a.canonical_text.index(good_text_a)
        good_text_b = "Jakość materiału jest znakomita"
        start_b = seg_b.canonical_text.index(good_text_b)

        # Mock LLM to return BatchCodingResult
        mock_client.chat.completions.create.return_value = BatchCodingResult(
            segment_results=[
                SegmentCodingResult(
                    segment_id="seg_a",
                    candidates=[
                        ICCandidate(
                            ic_name="slow_delivery",
                            definition="Slow delivery complaint",
                            quote_text=good_text_a,
                            span_start=start_a,
                            span_end=start_a + len(good_text_a),
                            confidence=0.9,
                        ),
                    ],
                ),
                SegmentCodingResult(
                    segment_id="seg_b",
                    candidates=[
                        ICCandidate(
                            ic_name="material_quality",
                            definition="High material quality",
                            quote_text=good_text_b,
                            span_start=start_b,
                            span_end=start_b + len(good_text_b),
                            confidence=0.85,
                        ),
                    ],
                ),
            ]
        )

        agent = CoderAgent(mc, db, config)
        results = agent.process_batch(two_segments)

        # Both segments should have results
        assert "seg_a" in results
        assert "seg_b" in results
        assert len(results["seg_a"]) == 1
        assert len(results["seg_b"]) == 1
        assert results["seg_a"][0].ic_name == "slow_delivery"
        assert results["seg_b"][0].ic_name == "material_quality"

        # Only 1 LLM call should be made (batch mode)
        assert mock_client.chat.completions.create.call_count == 1

    def test_batch_with_span_validation_per_segment(self, mock_model_client, db, two_segments):
        """Span validation uses each segment's own canonical_text."""
        mc, mock_client = mock_model_client
        config = MagicMock()
        config.processing.segments_per_coder_call = 5

        seg_a, seg_b = two_segments

        # Return a candidate for seg_b with text from seg_a (cross-contamination)
        mock_client.chat.completions.create.return_value = BatchCodingResult(
            segment_results=[
                SegmentCodingResult(segment_id="seg_a", candidates=[]),
                SegmentCodingResult(
                    segment_id="seg_b",
                    candidates=[
                        ICCandidate(
                            ic_name="cross_contaminated",
                            definition="Wrong segment text",
                            quote_text="dostawa trwała zbyt długo",  # From seg_a, not seg_b
                            span_start=0,
                            span_end=25,
                            confidence=0.8,
                        ),
                    ],
                ),
            ]
        )

        agent = CoderAgent(mc, db, config)
        results = agent.process_batch(two_segments)

        # Cross-contaminated candidate should be dropped
        assert len(results["seg_b"]) == 0

    def test_single_segment_uses_original_flow(self, mock_model_client, db, two_segments):
        """When segments_per_coder_call == 1, each segment gets its own LLM call."""
        mc, mock_client = mock_model_client
        config = MagicMock()
        config.processing.segments_per_coder_call = 1

        # Mock returns SegmentCodingResult (single mode), not BatchCodingResult
        mock_client.chat.completions.create.return_value = SegmentCodingResult(
            segment_id="seg_a",
            candidates=[],
        )

        agent = CoderAgent(mc, db, config)
        results = agent.process_batch(two_segments)

        # 2 separate LLM calls (one per segment)
        assert mock_client.chat.completions.create.call_count == 2
