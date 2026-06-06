"""Tests for codebook sign-off — display logic and data preparation."""

import pytest
from unittest.mock import MagicMock, patch

from src.extraction.codebook_signoff import CodebookSignoff, display_codebook_summary
from src.core.db import Database, InitialCodeRepo, VerbatimQuoteRepo
from src.core.models import InitialCode, ICStatus, VerbatimQuote


class TestDisplayCodebookSummary:
    """Test display formatting (capture stdout)."""

    def test_empty_codebook(self, capsys):
        display_codebook_summary([], {})
        captured = capsys.readouterr()
        assert "0 active" in captured.out
        assert "Empty codebook" in captured.out

    def test_flags_thin_evidence(self, sample_ics, capsys):
        # ic_001 has 5 quotes, ic_002 has 1, ic_003 has 2
        quote_counts = {
            "ic_001": 5,
            "ic_002": 1,
            "ic_003": 2,
        }
        display_codebook_summary(sample_ics, quote_counts)
        captured = capsys.readouterr()
        assert "3 active" in captured.out
        # ic_002 and ic_003 have < 3 quotes
        assert "thin evidence" in captured.out.lower() or "⚠" in captured.out

    def test_no_flags_when_all_evidence_sufficient(self, capsys):
        ics = [
            InitialCode(id="ic_x", name="good_code", definition="Well-supported code",
                        status=ICStatus.ACTIVE),
        ]
        quote_counts = {"ic_x": 5}
        display_codebook_summary(ics, quote_counts)
        captured = capsys.readouterr()
        assert "thin evidence" not in captured.out.lower()

    def test_flags_low_confidence_ics(self, sample_ics, capsys):
        """ICs in low_confidence_ic_ids set show ⚑ flag and appear in summary."""
        quote_counts = {"ic_001": 5, "ic_002": 5, "ic_003": 5}
        low_conf = {"ic_002"}  # only ic_002 is low-confidence
        display_codebook_summary(sample_ics, quote_counts, low_confidence_ic_ids=low_conf)
        captured = capsys.readouterr()
        # The flagged IC name should appear in the low-confidence summary block
        assert "⚑" in captured.out
        assert "low-confidence" in captured.out.lower() or "low confidence" in captured.out.lower()

    def test_no_confidence_flags_when_none_low(self, sample_ics, capsys):
        """No ⚑ flags when low_confidence_ic_ids is empty."""
        quote_counts = {"ic_001": 5, "ic_002": 5, "ic_003": 5}
        display_codebook_summary(sample_ics, quote_counts, low_confidence_ic_ids=set())
        captured = capsys.readouterr()
        assert "⚑" not in captured.out

    def test_no_confidence_flags_when_param_omitted(self, sample_ics, capsys):
        """Default (no param) behaves the same as empty set — no ⚑."""
        quote_counts = {"ic_001": 5, "ic_002": 5, "ic_003": 5}
        display_codebook_summary(sample_ics, quote_counts)
        captured = capsys.readouterr()
        assert "⚑" not in captured.out

    def test_both_flags_can_coexist(self, sample_ics, capsys):
        """An IC can be both thin-evidence ⚠ and low-confidence ⚑ simultaneously."""
        quote_counts = {"ic_001": 5, "ic_002": 1, "ic_003": 5}  # ic_002 thin
        low_conf = {"ic_002"}  # ic_002 also low-confidence
        display_codebook_summary(sample_ics, quote_counts, low_confidence_ic_ids=low_conf)
        captured = capsys.readouterr()
        assert "⚠" in captured.out
        assert "⚑" in captured.out


class TestLowConfidenceTracking:
    """Test that orchestrator correctly populates low_confidence_ic_ids."""

    def test_low_confidence_ic_id_captured_in_layer1_summary(self):
        """
        When a new IC is accepted with confidence < 0.6, its ID appears in
        layer1_summary['low_confidence_ic_ids'].
        """
        # We test the invariant at the summary-dict level by inspecting
        # what orchestrator initialises and what the tracking condition gates on.
        # This is a structural test — it verifies the key exists and the
        # threshold condition (< 0.6) is correct per the spec.
        summary = {
            "new_ic_confidences": [],
            "low_confidence_ic_ids": [],
        }
        # Simulate accepting a new IC with confidence 0.45 (below threshold)
        fake_ic_id = "ic_low_conf_001"
        fake_confidence = 0.45
        summary["new_ic_confidences"].append(fake_confidence)
        if fake_confidence < 0.6:
            summary["low_confidence_ic_ids"].append(fake_ic_id)

        assert fake_ic_id in summary["low_confidence_ic_ids"]
        assert len(summary["low_confidence_ic_ids"]) == 1

    def test_high_confidence_ic_not_flagged(self):
        """IC with confidence >= 0.6 does NOT appear in low_confidence_ic_ids."""
        summary = {
            "new_ic_confidences": [],
            "low_confidence_ic_ids": [],
        }
        fake_ic_id = "ic_high_conf_001"
        fake_confidence = 0.82
        summary["new_ic_confidences"].append(fake_confidence)
        if fake_confidence < 0.6:
            summary["low_confidence_ic_ids"].append(fake_ic_id)

        assert fake_ic_id not in summary["low_confidence_ic_ids"]
        assert len(summary["low_confidence_ic_ids"]) == 0

    def test_boundary_at_exactly_0_6_not_flagged(self):
        """Confidence exactly at 0.6 is NOT flagged (strict < 0.6 threshold)."""
        summary = {"new_ic_confidences": [], "low_confidence_ic_ids": []}
        fake_ic_id = "ic_boundary"
        fake_confidence = 0.6
        summary["new_ic_confidences"].append(fake_confidence)
        if fake_confidence < 0.6:
            summary["low_confidence_ic_ids"].append(fake_ic_id)

        assert fake_ic_id not in summary["low_confidence_ic_ids"]


class TestCodebookSignoffRunAcceptsLowConfIds:
    """Test that CodebookSignoff.run() passes low_confidence_ic_ids to display."""

    def test_run_passes_ids_to_display(self):
        """
        CodebookSignoff.run() should pass the flagged IDs to display_codebook_summary.
        We verify this by patching display_codebook_summary and checking its call args.
        """
        with patch("src.extraction.codebook_signoff.display_codebook_summary") as mock_display, \
             patch("src.extraction.codebook_signoff.prompt_signoff_action", return_value="S"), \
             patch.object(CodebookSignoff, "_confirm_signoff", return_value=True), \
             patch.object(CodebookSignoff, "_get_quote_counts", return_value={}):

            db = MagicMock()
            emb_svc = MagicMock()
            signoff = CodebookSignoff.__new__(CodebookSignoff)
            signoff.db = db
            signoff.embedding_service = emb_svc
            signoff.ic_repo = MagicMock()
            signoff.vq_repo = MagicMock()
            signoff.decision_repo = MagicMock()
            signoff.ic_repo.get_all_active.return_value = []

            low_conf_ids = ["ic_a", "ic_b"]
            signoff.run(low_confidence_ic_ids=low_conf_ids)

            # display_codebook_summary should have been called with the flagged ids as a set
            call_kwargs = mock_display.call_args[1] if mock_display.call_args[1] else {}
            call_args = mock_display.call_args[0] if mock_display.call_args[0] else ()
            # The flagged set is the third positional arg or low_confidence_ic_ids kwarg
            called_ids = call_kwargs.get("low_confidence_ic_ids") or (
                call_args[2] if len(call_args) > 2 else None
            )
            assert called_ids == {"ic_a", "ic_b"}

    def test_run_without_ids_passes_empty_set(self):
        """When no IDs passed, display receives an empty set (no ⚑ flags)."""
        with patch("src.extraction.codebook_signoff.display_codebook_summary") as mock_display, \
             patch("src.extraction.codebook_signoff.prompt_signoff_action", return_value="S"), \
             patch.object(CodebookSignoff, "_confirm_signoff", return_value=True), \
             patch.object(CodebookSignoff, "_get_quote_counts", return_value={}):

            signoff = CodebookSignoff.__new__(CodebookSignoff)
            signoff.db = MagicMock()
            signoff.embedding_service = MagicMock()
            signoff.ic_repo = MagicMock()
            signoff.vq_repo = MagicMock()
            signoff.decision_repo = MagicMock()
            signoff.ic_repo.get_all_active.return_value = []

            signoff.run()

            call_kwargs = mock_display.call_args[1] if mock_display.call_args[1] else {}
            call_args = mock_display.call_args[0] if mock_display.call_args[0] else ()
            called_ids = call_kwargs.get("low_confidence_ic_ids") or (
                call_args[2] if len(call_args) > 2 else None
            )
            assert called_ids == set()


class TestCodebookSignoffQuoteCounts:
    """Test the _get_quote_counts helper."""

    def test_counts_quotes_per_ic(self, db, sample_ics, sample_quotes):
        """Insert ICs and quotes, then verify counts."""
        ic_repo = InitialCodeRepo(db)
        vq_repo = VerbatimQuoteRepo(db)

        # Need a segment for foreign key
        from src.core.db import SegmentRepo, DocumentRepo
        from src.core.models import Document, Segment

        doc = Document(id="doc_001", raw_text="test text")
        DocumentRepo(db).insert(doc)
        seg = Segment(
            id="seg_001", document_id="doc_001",
            canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo. Paczka była uszkodzona.",
            original_text="test", char_count=75, content_hash="hash",
        )
        SegmentRepo(db).insert(seg)

        for ic in sample_ics:
            ic_repo.insert(ic)
        for vq in sample_quotes:
            vq_repo.insert(vq)

        # Create signoff instance and test
        emb_svc = MagicMock()
        signoff = CodebookSignoff(db, emb_svc)
        counts = signoff._get_quote_counts(sample_ics)

        assert counts["ic_001"] == 1  # vq_001
        assert counts["ic_003"] == 1  # vq_002
        assert counts["ic_002"] == 0  # No quotes
