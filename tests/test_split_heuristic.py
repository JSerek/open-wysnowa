"""Tests for Theme Splitting Heuristic — k-means + LLM (S4 Feature 2)."""

import pytest
from unittest.mock import MagicMock, patch

from src.models import (
    InitialCode,
    ICStatus,
    SplitProposal,
    SplitValidationOutput,
    ThemeProposal,
)
from src.pipeline import EQDPipeline
from src.prompts import (
    build_split_validation_system_prompt,
    build_split_validation_user_prompt,
)
from src.synthesizer_agent import SynthesizerAgent


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def magnet_ics():
    """10 ICs forming two clear clusters in 3D embedding space.

    Cluster A (combat): ic_01..ic_05 near [0.9, 0.1, 0.1]
    Cluster B (balance): ic_06..ic_10 near [0.1, 0.9, 0.1]
    """
    ics = []
    for i in range(1, 6):
        ics.append(InitialCode(
            id=f"ic_{i:02d}", name=f"combat_issue_{i}",
            definition=f"Combat problem {i}",
            embedding_json=[0.9 + i * 0.01, 0.1 - i * 0.01, 0.1],
            status=ICStatus.ACTIVE,
        ))
    for i in range(6, 11):
        ics.append(InitialCode(
            id=f"ic_{i:02d}", name=f"balance_issue_{i}",
            definition=f"Balance problem {i}",
            embedding_json=[0.1, 0.9 + (i - 5) * 0.01, 0.1],
            status=ICStatus.ACTIVE,
        ))
    return ics


@pytest.fixture
def magnet_theme(magnet_ics):
    """A magnet theme with all 10 ICs."""
    return ThemeProposal(
        name="Combat System Deficiencies",
        definition="Everything wrong with combat",
        rationale="Broad combat theme",
        constituent_ic_names=[ic.name for ic in magnet_ics],
    )


def _make_pipeline(db, ics=None):
    """Create a minimal pipeline instance with mocked services."""
    from src.db import InitialCodeRepo
    from src.config import ThemeRefinementConfig

    if ics:
        ic_repo = InitialCodeRepo(db)
        for ic in ics:
            ic_repo.insert(ic)

    pipeline = EQDPipeline.__new__(EQDPipeline)
    pipeline.db = db
    pipeline.embedding_service = MagicMock()
    pipeline.synthesizer = MagicMock(spec=SynthesizerAgent)

    config = MagicMock()
    config.theme_refinement = ThemeRefinementConfig()
    pipeline.config = config

    return pipeline


# ── Prompt Tests ─────────────────────────────────────────────────────────────


class TestSplitValidationPrompts:
    """Test prompt building functions for split validation."""

    def test_system_prompt_contains_split_guidance(self):
        prompt = build_split_validation_system_prompt()
        assert "SPLIT" in prompt
        assert "DO NOT SPLIT" in prompt or "not splitting" in prompt.lower()

    def test_user_prompt_contains_theme_and_clusters(self, magnet_theme, magnet_ics):
        ic_defs = {ic.name: ic.definition for ic in magnet_ics}
        cluster_a = [ic.name for ic in magnet_ics[:5]]
        cluster_b = [ic.name for ic in magnet_ics[5:]]

        prompt = build_split_validation_user_prompt(
            magnet_theme, cluster_a, cluster_b, ic_defs,
        )

        assert "Combat System Deficiencies" in prompt
        assert "combat_issue_1" in prompt
        assert "balance_issue_6" in prompt
        assert "CLUSTER A" in prompt
        assert "CLUSTER B" in prompt


# ── k-means Tests ────────────────────────────────────────────────────────────


class TestKMeansSplit:
    """Test the pure Python k-means implementation."""

    def test_two_clear_clusters(self, db, magnet_ics):
        """Two well-separated clusters should be correctly identified."""
        pipeline = _make_pipeline(db, magnet_ics)

        ic_names = [ic.name for ic in magnet_ics]
        ic_embeddings = {ic.name: ic.embedding_json for ic in magnet_ics}

        cluster_a, cluster_b = pipeline._kmeans_split(ic_names, ic_embeddings)

        # Both clusters should be non-empty
        assert len(cluster_a) > 0
        assert len(cluster_b) > 0
        assert len(cluster_a) + len(cluster_b) == 10

        # One cluster should contain combat ICs, other should contain balance ICs
        combat_names = {f"combat_issue_{i}" for i in range(1, 6)}
        balance_names = {f"balance_issue_{i}" for i in range(6, 11)}

        set_a = set(cluster_a)
        set_b = set(cluster_b)

        # Either cluster_a is combat and cluster_b is balance, or vice versa
        correct_split = (
            (set_a == combat_names and set_b == balance_names) or
            (set_a == balance_names and set_b == combat_names)
        )
        assert correct_split, f"k-means didn't separate clusters: A={set_a}, B={set_b}"

    def test_both_clusters_non_empty(self, db, magnet_ics):
        """Even with poor separation, both clusters must have at least 1 IC."""
        pipeline = _make_pipeline(db, magnet_ics)

        # All embeddings identical → degenerate case
        ic_names = ["a", "b", "c", "d"]
        ic_embeddings = {
            "a": [1.0, 0.0, 0.0],
            "b": [1.0, 0.0, 0.0],
            "c": [1.0, 0.0, 0.0],
            "d": [1.0, 0.0, 0.0],
        }

        cluster_a, cluster_b = pipeline._kmeans_split(ic_names, ic_embeddings)
        assert len(cluster_a) > 0
        assert len(cluster_b) > 0
        assert len(cluster_a) + len(cluster_b) == 4

    def test_minimal_input_two_ics(self, db, magnet_ics):
        """With exactly 2 ICs, each goes to its own cluster."""
        pipeline = _make_pipeline(db, magnet_ics)

        ic_names = ["ic_x", "ic_y"]
        ic_embeddings = {
            "ic_x": [1.0, 0.0, 0.0],
            "ic_y": [0.0, 1.0, 0.0],
        }

        cluster_a, cluster_b = pipeline._kmeans_split(ic_names, ic_embeddings)
        assert len(cluster_a) == 1
        assert len(cluster_b) == 1


# ── Synthesizer Split Validation Tests ───────────────────────────────────────


class TestSynthesizerSplitValidation:
    """Test SynthesizerAgent.validate_split()."""

    def test_llm_approves_split(self):
        mc = MagicMock()
        mock_params = MagicMock(temperature=0.3, max_tokens=8000)
        mc.get_client.return_value = (MagicMock(), "model-id", mock_params)
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        theme = ThemeProposal(
            name="Broad Theme", definition="Too broad and unfocused",
            rationale="Reason", constituent_ic_names=["a", "b", "c", "d"],
        )

        validation = SplitValidationOutput(
            should_split=True,
            reasoning="Clusters represent genuinely different phenomena",
            sub_themes=[
                SplitProposal(name="Sub A", definition="About cluster A", constituent_ic_names=["a", "b"]),
                SplitProposal(name="Sub B", definition="About cluster B", constituent_ic_names=["c", "d"]),
            ],
        )
        agent._call_split_validation_llm = MagicMock(return_value=validation)

        result = agent.validate_split(
            theme, ["a", "b"], ["c", "d"], {"a": "def_a", "b": "def_b", "c": "def_c", "d": "def_d"},
        )

        assert result is not None
        assert result.should_split is True
        assert len(result.sub_themes) == 2

    def test_llm_rejects_split(self):
        mc = MagicMock()
        mock_params = MagicMock(temperature=0.3, max_tokens=8000)
        mc.get_client.return_value = (MagicMock(), "model-id", mock_params)
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        theme = ThemeProposal(
            name="Coherent Theme", definition="This is fine",
            rationale="Reason", constituent_ic_names=["a", "b"],
        )

        validation = SplitValidationOutput(
            should_split=False,
            reasoning="Clusters are just different facets of the same phenomenon",
            sub_themes=None,
        )
        agent._call_split_validation_llm = MagicMock(return_value=validation)

        result = agent.validate_split(
            theme, ["a"], ["b"], {"a": "def_a", "b": "def_b"},
        )

        assert result is not None
        assert result.should_split is False

    def test_llm_failure_returns_none(self):
        mc = MagicMock()
        mock_params = MagicMock(temperature=0.3, max_tokens=8000)
        mc.get_client.return_value = (MagicMock(), "model-id", mock_params)
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        theme = ThemeProposal(
            name="Theme", definition="About things",
            rationale="Reason", constituent_ic_names=["a"],
        )

        agent._call_split_validation_llm = MagicMock(side_effect=Exception("LLM down"))
        result = agent.validate_split(
            theme, ["a"], ["b"], {"a": "def_a", "b": "def_b"},
        )
        assert result is None


# ── Pipeline Split Heuristic Tests ───────────────────────────────────────────


class TestPipelineSplitHeuristic:
    """Test _run_split_heuristic in the pipeline."""

    def test_no_magnet_themes_returns_original(self, db, magnet_ics):
        """Small themes with good coherence pass through unchanged."""
        pipeline = _make_pipeline(db, magnet_ics)

        # Small theme (3 ICs < split_min_ics=8) → not flagged
        themes = [
            ThemeProposal(
                name="Small Theme", definition="Compact and coherent",
                rationale="Reason", constituent_ic_names=["combat_issue_1", "combat_issue_2", "combat_issue_3"],
            ),
        ]

        result = pipeline._run_split_heuristic(themes)
        assert len(result) == 1
        assert result[0].name == "Small Theme"
        pipeline.synthesizer.validate_split.assert_not_called()

    def test_magnet_theme_triggers_split(self, db, magnet_ics, magnet_theme):
        """Theme meeting all criteria should be evaluated for splitting."""
        pipeline = _make_pipeline(db, magnet_ics)

        # We need the coherence computation to return a low value
        # and distinctness to return many overlaps
        # Monkey-patch to simulate the conditions
        original_coherence = pipeline._compute_live_coherence
        original_distinctness = pipeline._compute_live_distinctness

        def mock_coherence(themes):
            return {t.name: 0.30 for t in themes}  # Low coherence

        def mock_distinctness(themes):
            # Return many overlaps involving our theme
            pairs = []
            for i in range(5):
                pairs.append((magnet_theme.name, f"other_theme_{i}", 0.75))
            return pairs

        pipeline._compute_live_coherence = mock_coherence
        pipeline._compute_live_distinctness = mock_distinctness

        # LLM approves split
        pipeline.synthesizer.validate_split.return_value = SplitValidationOutput(
            should_split=True,
            reasoning="Clear split between combat mechanics and balance issues",
            sub_themes=[
                SplitProposal(
                    name="Combat Mechanics Issues",
                    definition="Problems with core combat gameplay",
                    constituent_ic_names=[f"combat_issue_{i}" for i in range(1, 6)],
                ),
                SplitProposal(
                    name="Combat Balance Issues",
                    definition="Problems with combat fairness and tuning",
                    constituent_ic_names=[f"balance_issue_{i}" for i in range(6, 11)],
                ),
            ],
        )

        result = pipeline._run_split_heuristic([magnet_theme])

        # Original replaced by 2 sub-themes
        assert len(result) == 2
        names = {t.name for t in result}
        assert "Combat Mechanics Issues" in names
        assert "Combat Balance Issues" in names
        assert "Combat System Deficiencies" not in names

    def test_llm_rejects_split_keeps_original(self, db, magnet_ics, magnet_theme):
        """When LLM says no, the original theme is preserved."""
        pipeline = _make_pipeline(db, magnet_ics)

        pipeline._compute_live_coherence = lambda t: {x.name: 0.30 for x in t}
        pipeline._compute_live_distinctness = lambda t: [
            (magnet_theme.name, f"other_{i}", 0.75) for i in range(5)
        ]

        pipeline.synthesizer.validate_split.return_value = SplitValidationOutput(
            should_split=False,
            reasoning="The theme should remain unified — split is artificial",
            sub_themes=None,
        )

        result = pipeline._run_split_heuristic([magnet_theme])
        assert len(result) == 1
        assert result[0].name == "Combat System Deficiencies"

    def test_llm_failure_keeps_original(self, db, magnet_ics, magnet_theme):
        """When LLM call fails, original theme is preserved."""
        pipeline = _make_pipeline(db, magnet_ics)

        pipeline._compute_live_coherence = lambda t: {x.name: 0.30 for x in t}
        pipeline._compute_live_distinctness = lambda t: [
            (magnet_theme.name, f"other_{i}", 0.75) for i in range(5)
        ]

        pipeline.synthesizer.validate_split.return_value = None

        result = pipeline._run_split_heuristic([magnet_theme])
        assert len(result) == 1
        assert result[0].name == "Combat System Deficiencies"

    def test_too_few_ics_with_embeddings_skips(self, db, magnet_theme):
        """Theme with < 4 ICs having embeddings should be skipped."""
        from src.db import InitialCodeRepo

        # Only insert 3 ICs with embeddings (rest have None)
        ic_repo = InitialCodeRepo(db)
        for i in range(1, 4):
            ic_repo.insert(InitialCode(
                id=f"ic_{i:02d}", name=f"combat_issue_{i}",
                definition=f"Combat problem {i}",
                embedding_json=[0.9, 0.1, 0.1],
                status=ICStatus.ACTIVE,
            ))
        # Rest exist but with no embeddings
        for i in range(4, 11):
            name = f"combat_issue_{i}" if i < 6 else f"balance_issue_{i}"
            ic_repo.insert(InitialCode(
                id=f"ic_{i:02d}", name=name,
                definition=f"Problem {i}",
                embedding_json=None,
                status=ICStatus.ACTIVE,
            ))

        pipeline = _make_pipeline(db)

        pipeline._compute_live_coherence = lambda t: {x.name: 0.30 for x in t}
        pipeline._compute_live_distinctness = lambda t: [
            (magnet_theme.name, f"other_{i}", 0.75) for i in range(5)
        ]

        result = pipeline._run_split_heuristic([magnet_theme])
        assert len(result) == 1  # Unchanged — too few embeddings
        pipeline.synthesizer.validate_split.assert_not_called()


# ── Model Tests ──────────────────────────────────────────────────────────────


class TestSplitModels:
    """Test Pydantic models for split validation."""

    def test_split_validation_output_approve(self):
        output = SplitValidationOutput(
            should_split=True,
            reasoning="Clear semantic distinction between clusters",
            sub_themes=[
                SplitProposal(name="Sub A", definition="First half of the theme",
                              constituent_ic_names=["ic_1", "ic_2"]),
                SplitProposal(name="Sub B", definition="Second half of the theme",
                              constituent_ic_names=["ic_3", "ic_4"]),
            ],
        )
        assert output.should_split is True
        assert len(output.sub_themes) == 2

    def test_split_validation_output_reject(self):
        output = SplitValidationOutput(
            should_split=False,
            reasoning="Just different facets of the same thing",
            sub_themes=None,
        )
        assert output.should_split is False
        assert output.sub_themes is None

    def test_split_proposal_validation(self):
        with pytest.raises(Exception):
            SplitProposal(name="", definition="Valid def", constituent_ic_names=["ic_1"])

    def test_distinctness_revision_output(self):
        from src.models import DistinctnessRevisionOutput
        output = DistinctnessRevisionOutput(
            reasoning="Sharpened definitions to be more distinct from each other",
            themes=[
                ThemeProposal(
                    name="Theme X", definition="Specifically about X",
                    rationale="Reason", constituent_ic_names=["ic_1"],
                ),
            ],
        )
        assert len(output.themes) == 1
