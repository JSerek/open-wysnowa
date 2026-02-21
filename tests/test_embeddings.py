"""Tests for embedding service.

Uses mock API calls — no real OpenAI requests in tests.
Cosine similarity is tested with known vectors.
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from src.db import InitialCodeRepo, VerbatimQuoteRepo
from src.embeddings import (
    cosine_similarity,
    EmbeddingService,
    SimilarityResult,
)
from src.models import InitialCode, ICStatus, VerbatimQuote


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(-1.0)

    def test_known_similarity(self):
        # cos(45°) = 1/√2 ≈ 0.7071
        v1 = [1.0, 0.0]
        v2 = [1.0, 1.0]
        expected = 1.0 / math.sqrt(2)
        assert cosine_similarity(v1, v2) == pytest.approx(expected, rel=1e-6)

    def test_zero_vector_returns_zero(self):
        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 2.0, 3.0]
        assert cosine_similarity(v1, v2) == 0.0

    def test_dimension_mismatch_raises(self):
        v1 = [1.0, 2.0]
        v2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="length mismatch"):
            cosine_similarity(v1, v2)


class TestFindSimilarICs:
    def test_finds_most_similar(self, db, sample_ics):
        """Using pre-set 3-dim embeddings from fixtures."""
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        # Create a mock model_client (won't be called for find_similar)
        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)

        # Query with vector similar to ic_001 (delivery complaint)
        query_vec = [0.75, 0.15, 0.35]
        results = service.find_similar_ics(query_vec, top_k=2)

        assert len(results) == 2
        # ic_001 and ic_003 should be most similar (both high on dim 0)
        top_ids = {r.ic_id for r in results}
        assert "ic_001" in top_ids

    def test_excludes_specified_ids(self, db, sample_ics):
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)

        results = service.find_similar_ics(
            [0.8, 0.1, 0.3], top_k=5, exclude_ids=["ic_001"]
        )
        result_ids = {r.ic_id for r in results}
        assert "ic_001" not in result_ids

    def test_empty_codebook(self, db):
        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)
        results = service.find_similar_ics([0.5, 0.5, 0.5])
        assert results == []


class TestThemeCoherence:
    def test_high_coherence(self, db, sample_ics):
        """ICs with similar embeddings should show high coherence."""
        ic_repo = InitialCodeRepo(db)
        # Two very similar ICs
        ic_a = InitialCode(
            id="ic_a", name="A", definition="Defn A",
            embedding_json=[0.9, 0.1, 0.0], status=ICStatus.ACTIVE,
        )
        ic_b = InitialCode(
            id="ic_b", name="B", definition="Defn B",
            embedding_json=[0.85, 0.15, 0.05], status=ICStatus.ACTIVE,
        )
        ic_repo.insert(ic_a)
        ic_repo.insert(ic_b)

        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)
        coherence = service.compute_theme_coherence(["ic_a", "ic_b"])
        assert coherence > 0.95

    def test_low_coherence(self, db):
        ic_repo = InitialCodeRepo(db)
        # Two orthogonal ICs
        ic_a = InitialCode(
            id="ic_x", name="X", definition="Defn X",
            embedding_json=[1.0, 0.0, 0.0], status=ICStatus.ACTIVE,
        )
        ic_b = InitialCode(
            id="ic_y", name="Y", definition="Defn Y",
            embedding_json=[0.0, 1.0, 0.0], status=ICStatus.ACTIVE,
        )
        ic_repo.insert(ic_a)
        ic_repo.insert(ic_b)

        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)
        coherence = service.compute_theme_coherence(["ic_x", "ic_y"])
        assert coherence == pytest.approx(0.0)

    def test_single_ic_returns_zero(self, db, sample_ics):
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])

        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)
        assert service.compute_theme_coherence(["ic_001"]) == 0.0


class TestMeaningSaturation:
    def test_first_quote_always_novel(self, db):
        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)
        result = service.compute_meaning_saturation("ic_nonexistent", [0.5, 0.5])
        assert result == 0.0  # No existing quotes → novel

    def test_redundant_quote_detected(self, db, sample_documents, sample_segment, sample_ics):
        from src.db import DocumentRepo, SegmentRepo
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        InitialCodeRepo(db).insert(sample_ics[0])

        vq_repo = VerbatimQuoteRepo(db)
        # Insert existing quote with embedding
        vq = VerbatimQuote(
            id="vq_existing", ic_id="ic_001", segment_id="seg_001",
            quote_text="test", span_start=0, span_end=4,
            quote_embedding_json=[0.9, 0.1, 0.0],
        )
        vq_repo.insert(vq)

        mock_mc = MagicMock()
        service = EmbeddingService(mock_mc, db)

        # Very similar new quote embedding
        max_sim = service.compute_meaning_saturation("ic_001", [0.88, 0.12, 0.02])
        assert max_sim > 0.95  # Redundant
