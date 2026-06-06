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


class TestCodebookComparatorTriage:
    """Tests for the embedding-first triage paths (no LLM call)."""

    def _make_config(self):
        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.55   # production defaults (2026-03-04)
        config.processing.auto_merge_threshold = 0.65
        return config

    def test_auto_new_below_threshold_skips_llm(self, mock_services, db, test_candidate):
        """Similarity clearly below auto_new_threshold → NEW without LLM."""
        mc, mock_client, embedding_service = mock_services
        config = self._make_config()

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Unrelated code", similarity=0.40),
        ]

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.NEW
        assert meta["triage_path"] == "auto_new"
        assert meta["max_sim"] == pytest.approx(0.40)
        assert meta["llm_recommendation"] is None
        mock_client.chat.completions.create_with_completion.assert_not_called()

    def test_auto_new_reasoning_mentions_similarity(self, mock_services, db, test_candidate):
        """Auto-NEW reasoning string should surface the similarity value."""
        mc, _, embedding_service = mock_services
        config = self._make_config()

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Unrelated code", similarity=0.40),
        ]

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, _, _ = comparator.evaluate(test_candidate)

        assert "0.40" in output.reasoning or "0.400" in output.reasoning

    def test_auto_merge_above_threshold_skips_llm(self, mock_services, db, test_candidate):
        """Similarity clearly above auto_merge_threshold → MERGE without LLM."""
        mc, mock_client, embedding_service = mock_services
        config = self._make_config()

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.82),
            SimilarityResult(ic_id="ic_002", ic_name="Packaging damage", similarity=0.31),
        ]

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.MERGE
        assert output.merge_target_name == "Delivery speed complaint"  # top result
        assert meta["triage_path"] == "auto_merge"
        assert meta["max_sim"] == pytest.approx(0.82)
        assert meta["llm_recommendation"] is None
        mock_client.chat.completions.create_with_completion.assert_not_called()

    def test_auto_merge_targets_top_result(self, mock_services, db, test_candidate):
        """Auto-merge always targets the top-1 result, not any other neighbour."""
        mc, _, embedding_service = mock_services
        config = self._make_config()

        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Top match", similarity=0.90),
            SimilarityResult(ic_id="ic_002", ic_name="Second match", similarity=0.88),
        ]

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, _, _ = comparator.evaluate(test_candidate)

        assert output.merge_target_name == "Top match"

    def test_grey_zone_boundary_calls_llm(self, mock_services, db, test_candidate, sample_ics):
        """Similarity in grey zone (0.55–0.65) → LLM is called."""
        mc, mock_client, embedding_service = mock_services
        config = self._make_config()

        from src.core.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        # 0.60 is in the grey zone for thresholds 0.55/0.65
        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.60),
        ]

        mock_client.chat.completions.create_with_completion.return_value = (
            ComparatorOutput(
                recommendation=ComparatorRecommendation.MERGE,
                merge_target_name="Delivery speed complaint",
                reasoning="Semantically equivalent — both describe slow delivery.",
            ),
            MagicMock(),
        )

        comparator = CodebookComparator(mc, embedding_service, db, config)
        output, top_k, meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.MERGE
        assert meta["triage_path"] == "grey_zone"
        assert meta["llm_recommendation"] == "MERGE"
        mock_client.chat.completions.create_with_completion.assert_called_once()

    def test_llm_failure_in_grey_zone_defaults_to_new(self, mock_services, db, test_candidate, sample_ics):
        """LLM failure in grey zone → safe fallback to NEW."""
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
        assert meta["triage_path"] == "grey_zone"
        assert "failed" in output.reasoning.lower()
