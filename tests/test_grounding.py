"""Tests for ground truth verification and coverage computation."""

import pytest

from src.core.db import DocumentRepo, SegmentRepo, InitialCodeRepo, VerbatimQuoteRepo
from src.preprocessing import (
    verify_quote,
    attempt_realign,
    verify_ic_quotes,
    compute_coverage,
    corpus_coverage_summary,
    GroundingReport,
)
from src.core.models import (
    Document,
    InitialCode,
    ICStatus,
    Segment,
    VerbatimQuote,
)


class TestVerifyQuote:
    def test_correct_span_passes(self, sample_segment, sample_quotes):
        canonical = sample_segment.canonical_text
        quote = sample_quotes[0]
        assert verify_quote(quote, canonical) is True
        assert quote.is_verified is True

    def test_wrong_span_fails(self, sample_segment):
        canonical = sample_segment.canonical_text
        quote = VerbatimQuote(
            id="vq_bad",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="dostawa trwała zbyt długo",
            span_start=0,  # Wrong start
            span_end=25,
        )
        assert verify_quote(quote, canonical) is False

    def test_hallucinated_text_fails(self, sample_segment):
        canonical = sample_segment.canonical_text
        quote = VerbatimQuote(
            id="vq_hallucinated",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="ten produkt jest okropny",  # Not in text
            span_start=0,
            span_end=24,
        )
        assert verify_quote(quote, canonical) is False


class TestAttemptRealign:
    def test_finds_correct_span(self, sample_segment):
        canonical = sample_segment.canonical_text
        quote = VerbatimQuote(
            id="vq_misaligned",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="dostawa trwała zbyt długo",
            span_start=0,  # Wrong
            span_end=25,  # Wrong
        )
        new_span = attempt_realign(quote, canonical)
        assert new_span is not None
        start, end = new_span
        assert canonical[start:end] == "dostawa trwała zbyt długo"

    def test_returns_none_for_hallucinated(self, sample_segment):
        canonical = sample_segment.canonical_text
        quote = VerbatimQuote(
            id="vq_fake",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="this text does not exist anywhere",
            span_start=0,
            span_end=33,
        )
        assert attempt_realign(quote, canonical) is None


class TestVerifyICQuotes:
    def _setup_db(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        """Helper to set up all FK parents and insert test data."""
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        ic_repo.insert(sample_ics[2])
        vq_repo = VerbatimQuoteRepo(db)
        for q in sample_quotes:
            vq_repo.insert(q)

    def test_all_quotes_verified(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        self._setup_db(db, sample_documents, sample_segment, sample_ics, sample_quotes)
        report = verify_ic_quotes(sample_ics[0], db)
        assert report.total_quotes == 1
        assert report.verified_count == 1
        assert report.grounding_rate == 1.0
        assert report.is_acceptable is True

    def test_realignment_works(self, db, sample_documents, sample_segment, sample_ics):
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])

        # Insert quote with wrong span but correct text
        vq_repo = VerbatimQuoteRepo(db)
        quote = VerbatimQuote(
            id="vq_misaligned",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="dostawa trwała zbyt długo",
            span_start=0,  # Wrong
            span_end=25,  # Wrong
        )
        vq_repo.insert(quote)

        report = verify_ic_quotes(sample_ics[0], db, auto_realign=True)
        assert report.realigned_count == 1
        assert report.grounding_rate == 1.0

    def test_hallucinated_quote_caught(self, db, sample_documents, sample_segment, sample_ics):
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])

        vq_repo = VerbatimQuoteRepo(db)
        quote = VerbatimQuote(
            id="vq_hallucinated",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text="ten produkt jest beznadziejny",
            span_start=0,
            span_end=29,
        )
        vq_repo.insert(quote)

        report = verify_ic_quotes(sample_ics[0], db)
        assert report.failed_count == 1
        assert report.not_found_count == 0  # Segment exists, but text doesn't match
        assert report.grounding_rate == 0.0
        assert report.is_acceptable is False


class TestCoverage:
    def _setup_verified_quotes(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        """Insert data and verify quotes."""
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        ic_repo.insert(sample_ics[2])
        vq_repo = VerbatimQuoteRepo(db)
        canonical = sample_segment.canonical_text
        for q in sample_quotes:
            q.verify(canonical)  # Mark as verified
            vq_repo.insert(q)

    def test_coverage_with_verified_quotes(
        self, db, sample_documents, sample_segment, sample_ics, sample_quotes
    ):
        self._setup_verified_quotes(db, sample_documents, sample_segment, sample_ics, sample_quotes)
        cov = compute_coverage("seg_001", db)
        # Two non-overlapping quotes covering some fraction of 75 chars
        assert 0.0 < cov < 1.0

    def test_coverage_empty_segment(self, db, sample_documents):
        DocumentRepo(db).insert(sample_documents[0])
        seg = Segment(
            id="seg_empty", document_id="doc_001",
            canonical_text="", original_text="",
            char_count=0, content_hash="empty",
        )
        SegmentRepo(db).insert(seg)
        assert compute_coverage("seg_empty", db) == 0.0

    def test_coverage_no_quotes(self, db, sample_documents, sample_segment):
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        assert compute_coverage("seg_001", db) == 0.0

    def test_corpus_coverage_summary(
        self, db, sample_documents, sample_segment, sample_ics, sample_quotes
    ):
        self._setup_verified_quotes(db, sample_documents, sample_segment, sample_ics, sample_quotes)
        mean_cov, covered_count, total = corpus_coverage_summary(db)
        assert total == 1  # Only one segment in DB
        assert covered_count == 1
        assert 0.0 < mean_cov < 1.0


class TestGroundingReport:
    def test_empty_report(self):
        report = GroundingReport()
        assert report.grounding_rate == 1.0  # No quotes = trivially grounded
        assert report.is_acceptable is True

    def test_partial_grounding(self):
        report = GroundingReport(
            total_quotes=10,
            verified_count=8,
            failed_count=2,
        )
        assert report.grounding_rate == 0.8
        assert report.is_acceptable is False  # Below 95%

    def test_acceptable_with_realignment(self):
        report = GroundingReport(
            total_quotes=20,
            verified_count=18,
            realigned_count=2,
            failed_count=0,
        )
        assert report.grounding_rate == 1.0
        assert report.is_acceptable is True
