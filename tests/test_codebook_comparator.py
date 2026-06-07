"""Tests for the Codebook Comparator with mocked LLM and embeddings."""

import pytest
from unittest.mock import MagicMock, patch

from src.extraction.codebook_comparator import CodebookComparator
from src.core.embeddings import SimilarityResult
from src.core.models import (
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


class TestCodebookComparatorSingleTrack:
    """v2: no thresholds — every candidate against a non-empty codebook hits the judge."""

    def _make_config(self):
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        return config

    def _seed_and_eval(self, mc, mock_client, embedding_service, db, test_candidate,
                       sample_ics, similarity, verdict):
        from src.core.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint",
                             similarity=similarity),
        ]
        mock_client.chat.completions.create_with_completion.return_value = (
            ComparatorOutput(
                recommendation=verdict,
                merge_target_name="Delivery speed complaint" if verdict == ComparatorRecommendation.MERGE else None,
                reasoning="Judge decision based on definitions.",
            ),
            MagicMock(),
        )
        comparator = CodebookComparator(mc, embedding_service, db, self._make_config())
        return comparator.evaluate(test_candidate)

    def test_low_similarity_still_calls_llm(self, mock_services, db, test_candidate, sample_ics):
        """Low top-1 similarity no longer auto-NEWs — the judge still decides."""
        mc, mock_client, embedding_service = mock_services
        output, top_k, meta = self._seed_and_eval(
            mc, mock_client, embedding_service, db, test_candidate, sample_ics,
            similarity=0.40, verdict=ComparatorRecommendation.NEW,
        )
        assert output.recommendation == ComparatorRecommendation.NEW
        assert meta["decision_path"] == "llm"
        assert meta["max_sim"] == pytest.approx(0.40)
        assert meta["llm_recommendation"] == "NEW"
        mock_client.chat.completions.create_with_completion.assert_called_once()

    def test_high_similarity_still_calls_llm(self, mock_services, db, test_candidate, sample_ics):
        """High top-1 similarity no longer auto-MERGEs — the judge still decides."""
        mc, mock_client, embedding_service = mock_services
        output, top_k, meta = self._seed_and_eval(
            mc, mock_client, embedding_service, db, test_candidate, sample_ics,
            similarity=0.82, verdict=ComparatorRecommendation.MERGE,
        )
        assert output.recommendation == ComparatorRecommendation.MERGE
        assert meta["decision_path"] == "llm"
        assert meta["max_sim"] == pytest.approx(0.82)
        assert meta["llm_recommendation"] == "MERGE"
        mock_client.chat.completions.create_with_completion.assert_called_once()

    def test_llm_failure_defaults_to_new(self, mock_services, db, test_candidate, sample_ics):
        """Judge failure → safe fallback to NEW."""
        mc, mock_client, embedding_service = mock_services
        config = self._make_config()

        from src.core.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.60),
        ]
        mock_client.chat.completions.create_with_completion.side_effect = Exception("API timeout")

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, _, meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.NEW
        assert meta["decision_path"] == "llm"
        assert "failed" in output.reasoning.lower()
