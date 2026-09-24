"""Tests for the Coder Agent with mocked LLM calls."""

import pytest
from unittest.mock import MagicMock, patch

from src.extraction.coder_agent import CoderAgent, GroundingDrop, ground_candidate
from src.core.models import ICCandidate, RawICCandidate, Segment, SegmentCodingResult
from src.preprocessing import DropClass


@pytest.fixture
def mock_model_client():
    """ModelClient mock that returns a mock instructor client."""
    mc = MagicMock()
    mock_client = MagicMock()
    mc.get_client.return_value = (mock_client, "test-model", MagicMock(temperature=0.2, max_tokens=4000))
    return mc, mock_client


@pytest.fixture
def test_segment():
    """Segment with known canonical text for grounding."""
    return Segment(
        id="seg_test",
        document_id="doc_test",
        canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
        original_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
        char_count=51,
        segment_index=0,
        content_hash="test_hash",
    )


class TestCoderAgentGrounding:
    """Test ground_candidate — the verbatim grounding gate (offsets are computed)."""

    def test_verbatim_quote_grounded_with_computed_span(self, test_segment):
        """A verbatim quote is grounded and its span is computed by the system."""
        raw = RawICCandidate(
            ic_name="slow_delivery",
            definition="Customer reports slow delivery",
            quote_text="dostawa trwała zbyt długo",
            confidence=0.9,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert isinstance(cand, ICCandidate)
        canonical = test_segment.canonical_text
        assert cand.span_start == canonical.index("dostawa trwała zbyt długo")
        assert canonical[cand.span_start:cand.span_end] == cand.quote_text
        assert cand.n_occurrences == 1
        assert cand.occurrence_resolution == "unique"
        assert match.drop_class is None

    def test_hallucinated_quote_dropped(self, test_segment):
        """Quote text not present verbatim → None + UNMATCHED."""
        raw = RawICCandidate(
            ic_name="hallucinated",
            definition="This text does not exist",
            quote_text="ten produkt jest okropny",
            confidence=0.8,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None
        assert match.drop_class == DropClass.UNMATCHED

    def test_partially_altered_quote_dropped(self, test_segment):
        """A near-miss with altered words is not verbatim → dropped."""
        raw = RawICCandidate(
            ic_name="altered",
            definition="Quote with a changed word",
            quote_text="dostawa trwała bardzo długo",  # 'zbyt' → 'bardzo'
            confidence=0.7,
        )
        cand, _ = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None

    def test_case_near_miss_dropped_with_class(self, test_segment):
        raw = RawICCandidate(
            ic_name="case_miss",
            definition="Quote differing only in letter case",
            quote_text="DOSTAWA trwała zbyt długo",
            confidence=0.7,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None
        assert match.drop_class == DropClass.CASE


class TestCoderAgentProcessBatch:
    """Test process_batch with mocked LLM responses."""

    def test_returns_grounded_candidates_only(self, mock_model_client, db, test_segment):
        mc, mock_client = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        good_text = "dostawa trwała zbyt długo"

        # LLM returns one verbatim and one hallucinated candidate (no offsets)
        mock_result = SegmentCodingResult(
            segment_id=test_segment.id,
            candidates=[
                RawICCandidate(
                    ic_name="valid_code",
                    definition="A valid code with a verbatim quote",
                    quote_text=good_text,
                    confidence=0.9,
                ),
                RawICCandidate(
                    ic_name="invalid_code",
                    definition="A code with a hallucinated quote",
                    quote_text="wrong text not in the segment",
                    confidence=0.7,
                ),
            ],
        )
        mock_client.chat.completions.create_with_completion.return_value = (mock_result, MagicMock())

        results = agent.process_batch([test_segment])

        assert test_segment.id in results
        assert len(results[test_segment.id]) == 1
        cand = results[test_segment.id][0]
        assert cand.ic_name == "valid_code"
        # Span computed by the agent
        assert test_segment.canonical_text[cand.span_start:cand.span_end] == good_text
        # The hallucinated candidate is counted as a drop
        assert agent.last_drop_counts[test_segment.id] == 1

        # Full drop record (not just a count) is exposed for the reasoning log
        drops = agent.last_drops[test_segment.id]
        assert drops == [
            GroundingDrop(
                ic_name="invalid_code",
                quote_text="wrong text not in the segment",
                drop_class=DropClass.UNMATCHED,
            )
        ]

    def test_repeated_phrase_gets_distinct_spans(self, mock_model_client, db):
        """Two candidates quoting a phrase that occurs twice get different occurrences."""
        mc, mock_client = mock_model_client
        agent = CoderAgent(mc, db, MagicMock())
        text = "The combat is bad. The story was fine. The combat is bad."
        seg = Segment(
            id="seg_dup", document_id="doc_test", canonical_text=text,
            original_text=text, char_count=len(text), content_hash="h",
        )
        mock_client.chat.completions.create_with_completion.return_value = (
            SegmentCodingResult(segment_id="seg_dup", candidates=[
                RawICCandidate(ic_name="combat_bad_a", definition="Combat criticised",
                               quote_text="The combat is bad", confidence=0.9),
                RawICCandidate(ic_name="combat_bad_b", definition="Combat criticised again",
                               quote_text="The combat is bad", confidence=0.9),
            ]),
            MagicMock(),
        )
        cands = agent.process_batch([seg])["seg_dup"]
        assert [c.span_start for c in cands] == [0, text.index("The combat is bad", 1)]
        assert all(c.occurrence_resolution == "first_free" for c in cands)
        assert all(c.n_occurrences == 2 for c in cands)
        assert agent.last_drops["seg_dup"] == []

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

        mock_result = SegmentCodingResult(segment_id="seg_empty", candidates=[])
        mock_client.chat.completions.create_with_completion.return_value = (mock_result, MagicMock())

        results = agent.process_batch([empty_segment])
        assert results["seg_empty"] == []

    def test_llm_failure_returns_empty(self, mock_model_client, db, test_segment):
        mc, mock_client = mock_model_client
        config = MagicMock()
        agent = CoderAgent(mc, db, config)

        mock_client.chat.completions.create_with_completion.side_effect = Exception("API error")

        results = agent.process_batch([test_segment])
        assert results[test_segment.id] == []
