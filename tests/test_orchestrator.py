"""Tests for Layer 1 Orchestrator — ITS tracking and pipeline logic."""

import pytest
from unittest.mock import MagicMock, patch

from src.core.models import (
    BatchITS,
    ComparatorOutput,
    ComparatorRecommendation,
    ICCandidate,
    Segment,
    SecondPassResult,
    SegmentCodingResult,
)
from src.extraction.orchestrator import ITSTracker, Layer1Orchestrator
from src.extraction.coder_agent import GroundingDrop
from src.preprocessing import DropClass


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
        orch.coder_agent.last_drop_counts = {}
        orch.coder_agent.last_drops = {}
        orch.comparator = MagicMock()
        orch.embedding_service = MagicMock()
        # Pass-2 audit mocked to a no-op (these tests exercise the pass-1 track).
        orch.second_pass_agent = MagicMock()
        orch.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id="seg_test", fragments=[],
        )
        # Candidate texts are batch-embedded per pass; return one vector per text.
        orch.embedding_service.embed_texts_batch.side_effect = (
            lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
        )

        return orch

    def test_empty_segments(self, mock_orchestrator):
        result = mock_orchestrator.run([], enable_hil=False)
        assert result["total_segments"] == 0
        assert result["batches_processed"] == 0

    def test_existing_match_still_goes_through_judge(self, mock_orchestrator, test_segment):
        """v2: existing_code_match is a logged signal only — candidate still hits the judge."""
        canonical = test_segment.canonical_text
        quote_text = "dostawa trwała zbyt długo"
        start = canonical.index(quote_text)

        # Coder Agent returns candidate with existing match flagged
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
        # Judge is consulted for every candidate now
        mock_orchestrator.comparator.evaluate.return_value = (
            ComparatorOutput(
                recommendation=ComparatorRecommendation.MERGE,
                merge_target_name="delivery_speed_complaint",
                reasoning="Same phenomenon as existing code.",
            ),
            [],  # no top_k needed for the assertion
            {"decision_path": "llm", "max_sim": 0.7, "llm_recommendation": "MERGE"},
        )

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["total_candidates"] == 1
        # existing_code_match recorded as a signal
        assert result["coder_flagged_match"] == 1
        # Comparator IS called — no shortcut path anymore
        mock_orchestrator.comparator.evaluate.assert_called_once()

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
            {"decision_path": "empty_codebook", "max_sim": None, "llm_recommendation": None},
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
            {"decision_path": "llm", "max_sim": 0.6, "llm_recommendation": "REJECT"},
        )

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["rejected"] == 1
        assert result["new_ics_created"] == 0

    def test_pass1_drops_logged_and_classified(self, mock_orchestrator, test_segment):
        """Every pass-1 grounding drop becomes a full reasoning-log record + class count."""
        mock_orchestrator.coder_agent.process_batch.return_value = {test_segment.id: []}
        mock_orchestrator.coder_agent.last_drop_counts = {test_segment.id: 2}
        mock_orchestrator.coder_agent.last_drops = {test_segment.id: [
            GroundingDrop("a", "Produkt jest świetny... zbyt długo", DropClass.ELLIPSIS_STITCH),
            GroundingDrop("b", "zupełnie inny tekst", DropClass.UNMATCHED),
        ]}
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["grounding_drop_classes"] == {"ellipsis_stitch": 1, "unmatched": 1}
        assert result["total_dropped"] == 2
        records = [c.args[0] for c in mock_orchestrator.reasoning_logger.log_record.call_args_list]
        drops = [r for r in records if r.get("type") == "grounding_drop"]
        assert len(drops) == 2
        assert drops[0] == {
            "type": "grounding_drop", "pass": 1, "segment_id": test_segment.id,
            "ic_name": "a", "quote_text": "Produkt jest świetny... zbyt długo",
            "drop_class": "ellipsis_stitch", "grounded": False,
            "final_action": "grounding_drop",
        }

    def test_candidate_record_carries_occurrence_fields(self, mock_orchestrator, test_segment):
        canonical = test_segment.canonical_text
        quote_text = "Produkt jest świetny"
        start = canonical.index(quote_text)
        mock_orchestrator.coder_agent.process_batch.return_value = {test_segment.id: [
            ICCandidate(
                ic_name="product_praise", definition="Praise for the product",
                quote_text=quote_text, span_start=start,
                span_end=start + len(quote_text), confidence=0.8,
                n_occurrences=1, occurrence_resolution="unique",
            )
        ]}
        mock_orchestrator.comparator.evaluate.return_value = (
            ComparatorOutput(recommendation=ComparatorRecommendation.REJECT,
                             reasoning="Too vague."),
            [],
            {"decision_path": "llm", "max_sim": 0.6, "llm_recommendation": "REJECT"},
        )
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        rec = mock_orchestrator.reasoning_logger.log_candidate.call_args.args[0]
        assert rec["n_occurrences"] == 1
        assert rec["occurrence_resolution"] == "unique"
        assert result["accepted_quotes_total"] == 1
        assert result["ambiguous_occurrences"] == {"first_free": 0, "first_fallback": 0}
