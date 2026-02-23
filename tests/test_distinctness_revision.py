"""Tests for Distinctness-Aware Revision Pass (S4 Feature 1)."""

import pytest
from unittest.mock import MagicMock, patch

from src.models import (
    DistinctnessRevisionOutput,
    InitialCode,
    ICStatus,
    ThemeProposal,
)
from src.pipeline import EQDPipeline
from src.prompts import (
    build_distinctness_revision_system_prompt,
    build_distinctness_revision_user_prompt,
)
from src.synthesizer_agent import SynthesizerAgent


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def ics_with_embeddings():
    """ICs with 3-dim embeddings — two clusters: delivery-related vs quality-related."""
    return [
        InitialCode(id="ic_a1", name="Slow delivery", definition="Delivery took too long",
                     embedding_json=[0.9, 0.1, 0.1], status=ICStatus.ACTIVE),
        InitialCode(id="ic_a2", name="Late shipping", definition="Shipping was delayed",
                     embedding_json=[0.85, 0.15, 0.1], status=ICStatus.ACTIVE),
        InitialCode(id="ic_b1", name="Great quality", definition="Product quality is excellent",
                     embedding_json=[0.1, 0.9, 0.1], status=ICStatus.ACTIVE),
        InitialCode(id="ic_b2", name="Durable materials", definition="Materials are strong",
                     embedding_json=[0.15, 0.85, 0.15], status=ICStatus.ACTIVE),
        InitialCode(id="ic_c1", name="Poor support", definition="Customer support is unhelpful",
                     embedding_json=[0.1, 0.1, 0.9], status=ICStatus.ACTIVE),
    ]


@pytest.fixture
def overlapping_themes():
    """Two themes that overlap significantly + one distinct."""
    return [
        ThemeProposal(
            name="Delivery Problems",
            definition="Issues related to shipping speed",
            rationale="Groups delivery ICs",
            constituent_ic_names=["Slow delivery", "Late shipping"],
        ),
        ThemeProposal(
            name="Shipping Delays",
            definition="Delays in receiving orders",
            rationale="Groups shipping ICs",
            constituent_ic_names=["Slow delivery", "Late shipping"],
        ),
        ThemeProposal(
            name="Product Quality",
            definition="Positive views on product build quality",
            rationale="Groups quality ICs",
            constituent_ic_names=["Great quality", "Durable materials"],
        ),
    ]


def _make_pipeline(db, ics=None):
    """Create a minimal pipeline instance with mocked services."""
    from src.db import InitialCodeRepo

    if ics:
        ic_repo = InitialCodeRepo(db)
        for ic in ics:
            ic_repo.insert(ic)

    pipeline = EQDPipeline.__new__(EQDPipeline)
    pipeline.db = db
    pipeline.embedding_service = MagicMock()
    pipeline.synthesizer = MagicMock(spec=SynthesizerAgent)

    # Config with theme_refinement
    from src.config import ThemeRefinementConfig
    config = MagicMock()
    config.theme_refinement = ThemeRefinementConfig()
    pipeline.config = config

    return pipeline


# ── Prompt Tests ─────────────────────────────────────────────────────────────


class TestDistinctnessPrompts:
    """Test prompt building functions for distinctness revision."""

    def test_system_prompt_contains_merge_sharpen(self):
        prompt = build_distinctness_revision_system_prompt()
        assert "MERGE" in prompt
        assert "SHARPEN" in prompt

    def test_user_prompt_contains_all_themes(self, overlapping_themes):
        pairs = [("Delivery Problems", "Shipping Delays", 0.95)]
        prompt = build_distinctness_revision_user_prompt(overlapping_themes, pairs)

        assert "Delivery Problems" in prompt
        assert "Shipping Delays" in prompt
        assert "Product Quality" in prompt
        assert "0.950" in prompt

    def test_user_prompt_contains_all_pairs(self, overlapping_themes):
        pairs = [
            ("Delivery Problems", "Shipping Delays", 0.95),
            ("Delivery Problems", "Product Quality", 0.72),
        ]
        prompt = build_distinctness_revision_user_prompt(overlapping_themes, pairs)
        assert "0.950" in prompt
        assert "0.720" in prompt

    def test_user_prompt_with_empty_pairs(self, overlapping_themes):
        prompt = build_distinctness_revision_user_prompt(overlapping_themes, [])
        # Should still include themes even with no pairs
        assert "Delivery Problems" in prompt


# ── Synthesizer Agent Tests ──────────────────────────────────────────────────


class TestSynthesizerDistinctnessRevision:
    """Test SynthesizerAgent.revise_for_distinctness()."""

    def test_no_overlapping_pairs_returns_themes(self):
        mc = MagicMock()
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        themes = [
            ThemeProposal(
                name="Theme A", definition="About A things",
                rationale="Reason A", constituent_ic_names=["ic_1"],
            ),
        ]
        result = agent.revise_for_distinctness(themes, overlapping_pairs=[])
        assert result == themes  # Unchanged

    def test_calls_llm_with_overlapping_pairs(self):
        mc = MagicMock()
        mock_params = MagicMock(temperature=0.3, max_tokens=8000)
        mc.get_client.return_value = (MagicMock(), "model-id", mock_params)
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        themes = [
            ThemeProposal(name="Theme A", definition="About A things",
                          rationale="Reason", constituent_ic_names=["ic_1"]),
            ThemeProposal(name="Theme B", definition="About B things",
                          rationale="Reason", constituent_ic_names=["ic_2"]),
        ]
        pairs = [("Theme A", "Theme B", 0.85)]

        # Mock the LLM call
        revised = DistinctnessRevisionOutput(
            reasoning="Sharpened both themes to be more distinct",
            themes=[
                ThemeProposal(name="Theme A (refined)", definition="Specifically about A",
                              rationale="Reason", constituent_ic_names=["ic_1"]),
                ThemeProposal(name="Theme B (refined)", definition="Specifically about B",
                              rationale="Reason", constituent_ic_names=["ic_2"]),
            ],
        )
        agent._call_distinctness_llm = MagicMock(return_value=revised)

        result = agent.revise_for_distinctness(themes, pairs)
        assert len(result) == 2
        assert result[0].name == "Theme A (refined)"
        agent._call_distinctness_llm.assert_called_once()

    def test_llm_failure_returns_none(self):
        mc = MagicMock()
        mock_params = MagicMock(temperature=0.3, max_tokens=8000)
        mc.get_client.return_value = (MagicMock(), "model-id", mock_params)
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        themes = [
            ThemeProposal(name="Theme A", definition="About A things",
                          rationale="Reason", constituent_ic_names=["ic_1"]),
        ]
        pairs = [("Theme A", "Theme B", 0.85)]

        agent._call_distinctness_llm = MagicMock(side_effect=Exception("LLM error"))
        result = agent.revise_for_distinctness(themes, pairs)
        assert result is None


# ── Pipeline Integration Tests ───────────────────────────────────────────────


class TestPipelineDistinctnessRevision:
    """Test _run_distinctness_revision in the pipeline."""

    def test_no_overlaps_returns_original(self, db, ics_with_embeddings):
        """When no pairs exceed threshold, themes pass through unchanged."""
        pipeline = _make_pipeline(db, ics_with_embeddings)

        # Theme with distinct ICs
        themes = [
            ThemeProposal(
                name="Quality", definition="About product quality",
                rationale="Reason", constituent_ic_names=["Great quality", "Durable materials"],
            ),
            ThemeProposal(
                name="Support", definition="About customer support",
                rationale="Reason", constituent_ic_names=["Poor support"],
            ),
        ]

        result = pipeline._run_distinctness_revision(themes)
        # These themes use very different embeddings, no overlaps expected
        assert len(result) == 2
        pipeline.synthesizer.revise_for_distinctness.assert_not_called()

    def test_overlapping_themes_trigger_llm(self, db, ics_with_embeddings):
        """When pairs exceed threshold, synthesizer is called."""
        pipeline = _make_pipeline(db, ics_with_embeddings)

        # Two themes sharing the same ICs → high similarity
        themes = [
            ThemeProposal(
                name="Delivery Problems", definition="Delivery issues",
                rationale="Reason", constituent_ic_names=["Slow delivery", "Late shipping"],
            ),
            ThemeProposal(
                name="Shipping Delays", definition="Shipping issues",
                rationale="Reason", constituent_ic_names=["Slow delivery", "Late shipping"],
            ),
        ]

        # Mock revision to merge
        merged = [
            ThemeProposal(
                name="Delivery & Shipping Issues", definition="All delivery problems",
                rationale="Merged", constituent_ic_names=["Slow delivery", "Late shipping"],
            ),
        ]
        pipeline.synthesizer.revise_for_distinctness.return_value = merged

        result = pipeline._run_distinctness_revision(themes)
        assert len(result) == 1
        assert result[0].name == "Delivery & Shipping Issues"
        pipeline.synthesizer.revise_for_distinctness.assert_called_once()

    def test_llm_failure_keeps_originals(self, db, ics_with_embeddings):
        """Graceful fallback: if LLM fails, original themes are kept."""
        pipeline = _make_pipeline(db, ics_with_embeddings)

        themes = [
            ThemeProposal(
                name="Theme A", definition="About A things in detail",
                rationale="Reason", constituent_ic_names=["Slow delivery", "Late shipping"],
            ),
            ThemeProposal(
                name="Theme B", definition="About B things in detail",
                rationale="Reason", constituent_ic_names=["Slow delivery", "Late shipping"],
            ),
        ]

        pipeline.synthesizer.revise_for_distinctness.return_value = None

        result = pipeline._run_distinctness_revision(themes)
        assert len(result) == 2  # Original themes preserved
        assert result[0].name == "Theme A"


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestThemeRefinementConfig:
    """Test ThemeRefinementConfig defaults and parsing."""

    def test_defaults(self):
        from src.config import ThemeRefinementConfig
        cfg = ThemeRefinementConfig()
        assert cfg.distinctness_threshold == 0.70
        assert cfg.max_overlap_pairs == 10
        assert cfg.split_min_ics == 8
        assert cfg.split_max_coherence == 0.50
        assert cfg.split_min_overlaps == 3

    def test_custom_values(self):
        from src.config import ThemeRefinementConfig
        cfg = ThemeRefinementConfig(
            distinctness_threshold=0.80,
            max_overlap_pairs=5,
            split_min_ics=6,
        )
        assert cfg.distinctness_threshold == 0.80
        assert cfg.max_overlap_pairs == 5
        assert cfg.split_min_ics == 6
