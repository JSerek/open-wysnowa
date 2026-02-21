"""Tests for the Codebook Comparator with mocked LLM and embeddings."""

import pytest
from unittest.mock import MagicMock, patch

from src.codebook_comparator import CodebookComparator
from src.embeddings import SimilarityResult
from src.models import (
    ComparatorOutput,
    ComparatorRecommendation,
    ICCandidate,
    InitialCode,
    ICStatus,
)


@pytest.fixture
def mock_services():
    """Mock ModelClient and EmbeddingService."""
    mc = MagicMock()
    mock_client = MagicMock()
    mc.get_client.return_value = (
        mock_client, "test-model",
        MagicMock(temperature=0.1, max_tokens=2000),
    )

    embedding_service = MagicMock()
    embedding_service.embed_text.return_value = [0.5, 0.5, 0.5]

    return mc, mock_client, embedding_service


@pytest.fixture
def test_candidate():
    return ICCandidate(
        ic_name="slow_delivery",
        definition="Customer complains about delivery speed",
        quote_text="dostawa trwała zbyt długo",
        span_start=26,
        span_end=51,
        confidence=0.9,
    )


class TestCodebookComparatorEmptyCodebook:
    def test_empty_codebook_returns_new(self, mock_services, db, test_candidate):
        mc, _, embedding_service = mock_services
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5

        embedding_service.find_similar_ics.return_value = []  # Empty codebook

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, _meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.NEW
        assert "empty" in output.reasoning.lower() or "first" in output.reasoning.lower()
        assert top_k == []
        # LLM should NOT be called
        mc.get_client.assert_not_called()


class TestCodebookComparatorPrecomputedEmbedding:
    def test_precomputed_embedding_skips_embed_call(self, mock_services, db, test_candidate):
        mc, _, embedding_service = mock_services
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5

        embedding_service.find_similar_ics.return_value = []  # Empty codebook

        comparator = CodebookComparator(mc, embedding_service, db, config)
        precomputed = [0.1, 0.2, 0.3]
        output, top_k, _meta = comparator.evaluate(test_candidate, precomputed_embedding=precomputed)

        assert output.recommendation == ComparatorRecommendation.NEW
        # embed_text should NOT be called when precomputed is provided
        embedding_service.embed_text.assert_not_called()
        # But find_similar_ics should be called with the precomputed embedding
        embedding_service.find_similar_ics.assert_called_once_with(
            embedding=precomputed, top_k=5,
        )


class TestCodebookComparatorWithCodes:
    def test_returns_recommendation(self, mock_services, db, test_candidate, sample_ics):
        mc, mock_client, embedding_service = mock_services
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        # Insert ICs so they can be looked up
        from src.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        # Mock top-K results (0.87 is in the grey zone → LLM will be called)
        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.87),
            SimilarityResult(ic_id="ic_003", ic_name="Packaging damage", similarity=0.45),
        ]

        # Mock LLM response
        mock_client.chat.completions.create.return_value = ComparatorOutput(
            recommendation=ComparatorRecommendation.MERGE,
            merge_target_name="Delivery speed complaint",
            reasoning="Semantically equivalent — both describe slow delivery.",
        )

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, _meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.MERGE
        assert output.merge_target_name == "Delivery speed complaint"
        assert len(top_k) == 2

    def test_llm_failure_defaults_to_new(self, mock_services, db, test_candidate, sample_ics):
        mc, mock_client, embedding_service = mock_services
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        from src.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        # 0.87 is in the grey zone → will attempt LLM call, which fails
        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.87),
        ]

        # LLM fails
        mock_client.chat.completions.create.side_effect = Exception("API timeout")

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, _meta = comparator.evaluate(test_candidate)

        # Should fallback to NEW
        assert output.recommendation == ComparatorRecommendation.NEW
        assert "failed" in output.reasoning.lower()
