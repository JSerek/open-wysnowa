"""Tests for Layer 0 preprocessing pipeline."""

import pytest

from src.db import DocumentRepo, SegmentRepo
from src.models import Document
from src.preprocessing import (
    normalize,
    canonicalize,
    segment_corpus,
    batch_segments,
    preprocess_documents,
)


class TestNormalize:
    def test_basic_text_unchanged(self):
        text = "Hello world"
        result, rules = normalize(text)
        assert result == "Hello world"
        assert rules == []

    def test_preserves_case(self):
        """Critical: no lowercasing for verbatim quote matching."""
        text = "UPPERCASE and MixedCase"
        result, rules = normalize(text)
        assert result == "UPPERCASE and MixedCase"

    def test_strips_whitespace(self):
        text = "  hello  "
        result, rules = normalize(text)
        assert result == "hello"
        assert "strip_whitespace" in rules

    def test_collapses_whitespace(self):
        text = "hello   world\t\ttab\n\nnewline"
        result, rules = normalize(text)
        assert result == "hello world tab newline"
        assert "collapse_whitespace" in rules

    def test_nfkc_normalization(self):
        # ﬁ (U+FB01, fi ligature) → "fi" under NFKC
        text = "ﬁnance"
        result, rules = normalize(text)
        assert result == "finance"
        assert "nfkc_unicode" in rules

    def test_zero_width_removal(self):
        text = "hello\u200bworld"  # zero-width space
        result, rules = normalize(text)
        assert result == "helloworld"
        assert "remove_zero_width" in rules

    def test_polish_characters_preserved(self):
        text = "Jakość produktu jest świetna, żółty, źrebak"
        result, rules = normalize(text)
        assert "ść" in result
        assert "żółty" in result
        assert "źrebak" in result

    def test_empty_string(self):
        result, rules = normalize("")
        assert result == ""
        assert rules == []

    def test_combined_rules(self):
        text = "  hello   \u200b world  "
        result, rules = normalize(text)
        assert result == "hello world"
        assert "strip_whitespace" in rules
        assert "collapse_whitespace" in rules
        assert "remove_zero_width" in rules


class TestCanonicalize:
    def test_creates_segment(self):
        doc = Document(id="d1", raw_text="Hello   world")
        seg = canonicalize(doc)
        assert seg.document_id == "d1"
        assert seg.canonical_text == "Hello world"
        assert seg.original_text == "Hello   world"
        assert seg.char_count == 11
        assert "collapse_whitespace" in seg.normalization_rules

    def test_hash_integrity(self):
        doc = Document(id="d1", raw_text="Test text")
        seg = canonicalize(doc)
        assert seg.content_hash != ""
        assert seg.verify_integrity() is True

    def test_different_texts_different_hashes(self):
        doc1 = Document(id="d1", raw_text="Text one")
        doc2 = Document(id="d2", raw_text="Text two")
        seg1 = canonicalize(doc1)
        seg2 = canonicalize(doc2)
        assert seg1.content_hash != seg2.content_hash

    def test_same_text_same_hash(self):
        doc1 = Document(id="d1", raw_text="Same text")
        doc2 = Document(id="d2", raw_text="Same text")
        seg1 = canonicalize(doc1)
        seg2 = canonicalize(doc2)
        assert seg1.content_hash == seg2.content_hash


class TestSegmentCorpus:
    def test_segment_all_documents(self, sample_documents):
        segments = segment_corpus(sample_documents)
        assert len(segments) == 3

    def test_segments_linked_to_documents(self, sample_documents):
        segments = segment_corpus(sample_documents)
        doc_ids = {s.document_id for s in segments}
        expected_ids = {d.id for d in sample_documents}
        assert doc_ids == expected_ids


class TestBatchSegments:
    def test_batch_size(self, sample_documents):
        segments = segment_corpus(sample_documents)
        batches = list(batch_segments(segments, batch_size=2))
        assert len(batches) == 2  # 3 segments / batch_size 2 = 2 batches
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_batch_size_larger_than_corpus(self, sample_documents):
        segments = segment_corpus(sample_documents)
        batches = list(batch_segments(segments, batch_size=100))
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_empty_corpus(self):
        batches = list(batch_segments([], batch_size=15))
        assert batches == []


class TestPreprocessDocuments:
    def test_full_pipeline(self, db, sample_documents):
        segments = preprocess_documents(sample_documents, db)
        assert len(segments) == 3

        # Verify documents persisted
        doc_repo = DocumentRepo(db)
        assert len(doc_repo.get_all()) == 3

        # Verify segments persisted
        seg_repo = SegmentRepo(db)
        for seg in segments:
            retrieved = seg_repo.get_by_id(seg.id)
            assert retrieved is not None
            assert retrieved.verify_integrity()
