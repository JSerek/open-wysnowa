"""Tests for Layer 1 Orchestrator — ITS tracking and pipeline logic."""

import pytest
from unittest.mock import MagicMock, patch

from src.core.models import (
    BatchITS,
    ComparatorOutput,
    ComparatorRecommendation,
    ICCandidate,
    Segment,
    SegmentCodingResult,
)
from src.extraction.orchestrator import ITSTracker, Layer1Orchestrator


# ── ITS Tracker Tests ────────────────────────────────────────────────────────

class TestITSTracker:
    """Deterministic tests for ITS computation — no mocking needed."""

    def test_first_batch_all_new(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)
        result = tracker.record_batch(batch_number=1, ics_before=0, new_ics_created=5)
        assert result.its_value == 1.0  # First batch with codes
        assert result.consecutive_low == 0
        assert result.is_checkpoint is False

    def test_normal_batch(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)
        result = tracker.record_batch(batch_number=1, ics_before=10, new_ics_created=3)
        assert result.its_value == 0.3
        assert result.consecutive_low == 0

    def test_low_its_tracking(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)

        # Batch 1: high ITS
        r1 = tracker.record_batch(1, ics_before=10, new_ics_created=2)
        assert r1.consecutive_low == 0

        # Batch 2: low ITS
        r2 = tracker.record_batch(2, ics_before=12, new_ics_created=0)
        assert r2.its_value == 0.0
        assert r2.consecutive_low == 1

        # Batch 3: still low
        r3 = tracker.record_batch(3, ics_before=12, new_ics_created=0)
        assert r3.consecutive_low == 2
        assert r3.is_checkpoint is False  # Need 3

        # Batch 4: third consecutive low → checkpoint
        r4 = tracker.record_batch(4, ics_before=12, new_ics_created=0)
        assert r4.consecutive_low == 3
        assert r4.is_checkpoint is True

    def test_consecutive_resets_on_high_its(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)

        tracker.record_batch(1, ics_before=10, new_ics_created=0)
        tracker.record_batch(2, ics_before=10, new_ics_created=0)

        # Batch with new codes breaks the streak
        r3 = tracker.record_batch(3, ics_before=10, new_ics_created=3)
        assert r3.its_value == 0.3
        assert r3.consecutive_low == 0

    def test_boundary_threshold(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)

        # Exactly at threshold — still below
        r = tracker.record_batch(1, ics_before=100, new_ics_created=1)
        assert r.its_value == 0.01  # Below 0.02
        assert r.consecutive_low == 1

    def test_history_accumulates(self):
        tracker = ITSTracker(threshold=0.02, consecutive_needed=3)
        tracker.record_batch(1, 0, 5)
        tracker.record_batch(2, 5, 2)
        tracker.record_batch(3, 7, 0)
        assert len(tracker.history) == 3


# ── Orchestrator Integration Tests ───────────────────────────────────────────

class TestLayer1Orchestrator:
    """Test orchestrator with fully mocked sub-components."""

    @pytest.fixture
    def test_segment(self):
        return Segment(
            id="seg_test",
            document_id="doc_test",
            canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
            original_text="Produkt jest świetny, ale dostawa trwała zbyt długo.",
            char_count=51,
            segment_index=0,
            content_hash="test_hash",
        )

    @pytest.fixture
    def mock_orchestrator(self, db, test_segment):
        """Create orchestrator with all sub-components mocked.

        Seeds the DB with the test document and segment so FK constraints
        are satisfied when the orchestrator persists ICs and quotes.
        """
        from src.core.db import DocumentRepo, SegmentRepo
        from src.core.models import Document

        # Seed DB with FK parents
        DocumentRepo(db).insert(Document(id="doc_test", raw_text="test"))
        SegmentRepo(db).insert(test_segment)

        mc = MagicMock()
        config = MagicMock()
        config.processing.batch_size = 15
        config.processing.its_saturation_threshold = 0.02
        config.processing.its_consecutive_batches = 3
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.8

        orch = Layer1Orchestrator(mc, db, config)

        # Replace sub-components with mocks
        orch.coder_agent = MagicMock()
        orch.comparator = MagicMock()
        orch.embedding_service = MagicMock()

        return orch

    def test_empty_segments(self, mock_orchestrator):
        result = mock_orchestrator.run([], enable_hil=False)
        assert result["total_segments"] == 0
        assert result["batches_processed"] == 0

    def test_all_existing_matches_skip_comparator(self, mock_orchestrator, test_segment):
        canonical = test_segment.canonical_text
        quote_text = "dostawa trwała zbyt długo"
        start = canonical.index(quote_text)

        # Coder Agent returns candidate with existing match
        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [
                ICCandidate(
                    ic_name="delivery_complaint",
                    definition="Slow delivery complaint",
                    quote_text=quote_text,
                    span_start=start,
                    span_end=start + len(quote_text),
                    confidence=0.9,
                    existing_code_match="delivery_speed_complaint",
                ),
            ]
        }

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["existing_matches"] == 1
        assert result["total_candidates"] == 1
        # Comparator should NOT be called for existing matches
        mock_orchestrator.comparator.evaluate.assert_not_called()

    def test_new_candidate_auto_accept(self, mock_orchestrator, test_segment):
        canonical = test_segment.canonical_text
        quote_text = "dostawa trwała zbyt długo"
        start = canonical.index(quote_text)

        candidate = ICCandidate(
            ic_name="new_code",
            definition="A brand new code about delivery",
            quote_text=quote_text,
            span_start=start,
            span_end=start + len(quote_text),
            confidence=0.85,
            existing_code_match=None,
        )

        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [candidate],
        }

        # Comparator recommends NEW
        mock_orchestrator.comparator.evaluate.return_value = (
            ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning="No similar codes in codebook.",
            ),
            [],  # empty top-K
            {"triage_path": "empty_codebook", "max_sim": None, "llm_recommendation": None},
        )

        # Mock embedding: embed_ic/embed_quote must return real objects (not MagicMock)
        # because the repos call json.dumps on embedding_json fields.
        def fake_embed_ic(ic):
            ic.embedding_json = [0.1, 0.2, 0.3]
            return ic
        def fake_embed_quote(quote):
            quote.quote_embedding_json = [0.1, 0.2, 0.3]
            return quote
        mock_orchestrator.embedding_service.embed_ic.side_effect = fake_embed_ic
        mock_orchestrator.embedding_service.embed_quote.side_effect = fake_embed_quote
        mock_orchestrator.segment_repo = MagicMock()
        mock_orchestrator.segment_repo.get_by_id.return_value = test_segment

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["new_ics_created"] == 1
        assert result["total_candidates"] == 1

    def test_reject_recommendation_auto_accept(self, mock_orchestrator, test_segment):
        canonical = test_segment.canonical_text
        quote_text = "Produkt jest świetny"
        start = canonical.index(quote_text)

        candidate = ICCandidate(
            ic_name="vague_code",
            definition="Something vague about the product",
            quote_text=quote_text,
            span_start=start,
            span_end=start + len(quote_text),
            confidence=0.4,
            existing_code_match=None,
        )

        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [candidate],
        }

        mock_orchestrator.comparator.evaluate.return_value = (
            ComparatorOutput(
                recommendation=ComparatorRecommendation.REJECT,
                reasoning="Too vague, not analytically useful.",
            ),
            [],
            {"triage_path": "grey_zone", "max_sim": 0.6, "llm_recommendation": "REJECT"},
        )

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["rejected"] == 1
        assert result["new_ics_created"] == 0
