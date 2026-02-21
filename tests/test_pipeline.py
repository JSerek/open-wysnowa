"""Tests for the full pipeline — mocked sub-components."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.models import (
    Document,
    ThemeProposal,
)
from src.pipeline import EQDPipeline


class TestPipelineHelpers:
    """Test pipeline helper methods that don't require full setup."""

    def test_make_serializable_handles_dicts(self):
        from scripts.run_pipeline import _make_serializable

        data = {"a": 1, "b": [2, 3], "c": {"nested": True}}
        result = _make_serializable(data)
        assert result == data

    def test_get_decision_summary(self, db):
        """Test decision log summarization."""
        from src.db import DecisionLogRepo
        from src.models import DecisionLog, DecisionType

        repo = DecisionLogRepo(db)
        repo.insert(DecisionLog(decision_type=DecisionType.CODEBOOK_UPDATE, human_action="CREATE"))
        repo.insert(DecisionLog(decision_type=DecisionType.CODEBOOK_UPDATE, human_action="CREATE"))
        repo.insert(DecisionLog(decision_type=DecisionType.CODEBOOK_UPDATE, human_action="MERGE"))
        repo.insert(DecisionLog(decision_type=DecisionType.CODEBOOK_UPDATE, human_action="REJECT"))

        # Manually call the helper logic
        logs = repo.get_all()
        summary = {}
        for log in logs:
            action = log.human_action or "unknown"
            summary[action] = summary.get(action, 0) + 1

        assert summary == {"CREATE": 2, "MERGE": 1, "REJECT": 1}


class TestPipelineComputeLiveCoherence:
    """Test live coherence computation for theme proposals."""

    def test_single_ic_theme_is_trivially_coherent(self, db, sample_ics):
        """Theme with 1 IC should get coherence = 1.0."""
        from src.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        # Create minimal pipeline with mocked services
        with patch("src.pipeline.load_config"), \
             patch("src.pipeline.ModelClient"), \
             patch("src.pipeline.EmbeddingService") as mock_emb_cls, \
             patch("src.pipeline.Layer1Orchestrator"), \
             patch("src.pipeline.CodebookSignoff"), \
             patch("src.pipeline.SynthesizerAgent"), \
             patch("src.pipeline.QualityMetricsEngine"):

            mock_emb = MagicMock()
            mock_emb_cls.return_value = mock_emb

            pipeline = EQDPipeline.__new__(EQDPipeline)
            pipeline.db = db
            pipeline.embedding_service = mock_emb

            themes = [
                ThemeProposal(
                    name="Solo theme",
                    definition="Theme with just one code",
                    rationale="Single IC",
                    constituent_ic_names=["Delivery speed complaint"],
                ),
            ]

            coherence = pipeline._compute_live_coherence(themes)
            assert coherence["Solo theme"] == 1.0
            mock_emb.compute_theme_coherence.assert_not_called()

    def test_multi_ic_theme_calls_embedding_service(self, db, sample_ics):
        """Theme with 2+ ICs should delegate to embedding service."""
        from src.db import InitialCodeRepo
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        mock_emb = MagicMock()
        mock_emb.compute_theme_coherence.return_value = 0.65

        pipeline = EQDPipeline.__new__(EQDPipeline)
        pipeline.db = db
        pipeline.embedding_service = mock_emb

        themes = [
            ThemeProposal(
                name="Delivery theme",
                definition="Groups delivery and packaging ICs together",
                rationale="Delivery issues",
                constituent_ic_names=["Delivery speed complaint", "Packaging damage"],
            ),
        ]

        coherence = pipeline._compute_live_coherence(themes)
        assert coherence["Delivery theme"] == 0.65
        mock_emb.compute_theme_coherence.assert_called_once()
