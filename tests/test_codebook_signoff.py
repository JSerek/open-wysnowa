"""Tests for codebook sign-off — display logic and data preparation."""

import pytest
from unittest.mock import MagicMock, patch

from src.codebook_signoff import CodebookSignoff, display_codebook_summary
from src.db import Database, InitialCodeRepo, VerbatimQuoteRepo
from src.models import InitialCode, ICStatus, VerbatimQuote


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


class TestCodebookSignoffQuoteCounts:
    """Test the _get_quote_counts helper."""

    def test_counts_quotes_per_ic(self, db, sample_ics, sample_quotes):
        """Insert ICs and quotes, then verify counts."""
        ic_repo = InitialCodeRepo(db)
        vq_repo = VerbatimQuoteRepo(db)

        # Need a segment for foreign key
        from src.db import SegmentRepo, DocumentRepo
        from src.models import Document, Segment

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
