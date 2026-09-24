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


# ── locate_quote (P0: hard gate + drop diagnostics + occurrence selection) ────

from src.preprocessing import DropClass, QuoteMatch, locate_quote

REVIEW = "The combat is sluggish and clunky. The story was fine. Loading times are far too long."
DUP = "The combat is bad. The story was fine. The combat is bad. The combat is bad."


class TestLocateQuoteAcceptance:
    def test_unique_exact_match(self):
        m = locate_quote("The story was fine", REVIEW)
        s = REVIEW.index("The story was fine")
        assert m.span == (s, s + len("The story was fine"))
        assert m.n_occurrences == 1
        assert m.resolution == "unique"
        assert m.drop_class is None

    def test_span_invariant_holds(self):
        m = locate_quote("Loading times are far too long", REVIEW)
        s, e = m.span
        assert REVIEW[s:e] == "Loading times are far too long"

    def test_duplicate_first_free_skips_claimed(self):
        first = DUP.index("The combat is bad")
        second = DUP.index("The combat is bad", first + 1)
        m = locate_quote("The combat is bad", DUP, claimed_spans=[(first, first + 17)])
        assert m.span == (second, second + 17)
        assert m.n_occurrences == 3
        assert m.resolution == "first_free"

    def test_duplicate_unclaimed_takes_first_as_first_free(self):
        m = locate_quote("The combat is bad", DUP)
        assert m.span == (0, 17)
        assert m.resolution == "first_free"

    def test_three_occurrences_two_claimed_picks_third(self):
        idx = [0]
        while True:
            nxt = DUP.find("The combat is bad", idx[-1] + 1)
            if nxt < 0:
                break
            idx.append(nxt)
        assert len(idx) == 3
        claimed = [(idx[0], idx[0] + 17), (idx[1], idx[1] + 17)]
        m = locate_quote("The combat is bad", DUP, claimed_spans=claimed)
        assert m.span == (idx[2], idx[2] + 17)
        assert m.resolution == "first_free"

    def test_all_claimed_falls_back_to_first(self):
        claimed = [(0, len(DUP))]
        m = locate_quote("The combat is bad", DUP, claimed_spans=claimed)
        assert m.span == (0, 17)
        assert m.resolution == "first_fallback"

    def test_claimed_spans_irrelevant_for_unique(self):
        m = locate_quote("The story was fine", REVIEW, claimed_spans=[(0, len(REVIEW))])
        assert m.resolution == "unique"


class TestLocateQuoteDropClasses:
    def test_whitespace_difference_is_normalized_ws(self):
        m = locate_quote("The  combat is\nsluggish", REVIEW)
        assert m.span is None
        assert m.resolution is None
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_typographic_apostrophe_is_normalized_ws(self):
        canonical = "I don't like the ending at all."
        m = locate_quote("I don’t like the ending", canonical)
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_decomposed_diacritics_is_normalized_ws(self):
        canonical = "Produkt jest świetny, ale dostawa trwała zbyt długo."
        decomposed = "świetny"  # 's' + combining acute; NFKC → 'ś'
        m = locate_quote(f"Produkt jest {decomposed}", canonical)
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_case_difference_is_case(self):
        m = locate_quote("the combat is sluggish", REVIEW)
        assert m.drop_class == DropClass.CASE

    def test_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish... Loading times are far too long", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_unicode_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish… The story was fine", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_trailing_ellipsis_truncation_is_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish...", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_case_wins_over_ellipsis(self):
        canonical = "Wait... what? This ending is absurd."
        m = locate_quote("wait... What?", canonical)
        assert m.drop_class == DropClass.CASE

    def test_ellipsis_with_missing_fragment_is_unmatched(self):
        m = locate_quote("The combat is sluggish... the graphics are ugly", REVIEW)
        assert m.drop_class == DropClass.UNMATCHED

    def test_paraphrase_is_unmatched(self):
        m = locate_quote("loading is way too slow", REVIEW)
        assert m.drop_class == DropClass.UNMATCHED

    def test_empty_quote_is_unmatched(self):
        for q in ("", "   ", "\n"):
            m = locate_quote(q, REVIEW)
            assert m.span is None
            assert m.n_occurrences == 0
            assert m.drop_class == DropClass.UNMATCHED

    def test_quote_match_is_frozen(self):
        m = locate_quote("The story was fine", REVIEW)
        assert isinstance(m, QuoteMatch)
        with pytest.raises(Exception):
            m.span = None  # type: ignore[misc]
