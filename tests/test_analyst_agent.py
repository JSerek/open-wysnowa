"""
Tests for Layer 4: Analyst Intelligence Agent.

Covers:
- Pydantic model validation
- Prompt building (all 6 functions)
- AnalystAgent with mocked LLM calls
- Config parsing (analyst_guidelines from YAML)
- Display function
"""

import pytest
from unittest.mock import MagicMock, patch

from src.models import (
    AnalyticalBrief,
    AnalystSynthesis,
    CategoryDiagnostic,
    ConfigRecommendation,
    MetricAssessment,
    MetricsInterpretation,
    StructuralDiagnostics,
    ThemeDiagnostic,
)
from src.config import AnalystGuidelinesConfig, MetricGuidelineConfig
from src.prompts import (
    build_analyst_synthesis_system_prompt,
    build_analyst_synthesis_user_prompt,
    build_metrics_interpretation_system_prompt,
    build_metrics_interpretation_user_prompt,
    build_structural_diagnostics_system_prompt,
    build_structural_diagnostics_user_prompt,
)
from src.analyst_agent import AnalystAgent
from src.quality_report import display_analytical_brief


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_guidelines():
    """Minimal analyst guidelines for testing."""
    return AnalystGuidelinesConfig(
        grounding_rate=MetricGuidelineConfig(
            description="Proportion of verified quotes",
            what_it_measures="Quote accuracy",
            healthy_min=0.95,
            low_means="Bad spans",
        ),
        drop_rate=MetricGuidelineConfig(
            description="Drop rate of candidates",
            what_it_measures="Span validation failures",
            healthy_max=0.15,
            high_means="Too many drops",
        ),
    )


@pytest.fixture
def sample_layer3():
    """Minimal layer3 results dict."""
    return {
        "grounding": {"total_quotes": 100, "verified": 96, "grounding_rate": 0.96},
        "extraction_density": {
            "distribution": {"mean": 0.52},
            "drop_rate": {"overall_rate": 0.08},
        },
        "ic_concentration": {"active_ics": 30, "singleton_count": 8, "singleton_ratio": 0.27},
        "merge_rate": {"per_batch": [0.3, 0.5, 0.6], "overall": 0.47},
        "triage_efficiency": {"auto_new": 10, "auto_merge": 15, "grey_zone": 5, "auto_rate": 0.83},
        "its_history": [
            {"batch_number": 1, "its_value": 0.5},
            {"batch_number": 2, "its_value": 0.2},
            {"batch_number": 3, "its_value": 0.03},
        ],
        "theme_coherence": {"per_theme": {"T1": 0.7, "T2": 0.5}, "mean": 0.6},
        "theme_distinctness": {"overlapping_pairs": [("T1", "T2", 0.75)], "overlap_ratio": 0.5},
        "sentiment_purity": {"per_theme": {"T1": 0.95, "T2": 0.80}, "mean": 0.875},
        "thematic_coverage": {"ratio": 0.92},
        "cross_review_convergence": {"confirmed_ratio": 0.65, "strong_ratio": 0.40},
        "ic_stability": {"mean_stability": 0.91, "substantially_rewritten": 2},
    }


@pytest.fixture
def sample_thematic_structure():
    """Minimal thematic structure."""
    return [
        {
            "name": "Category A",
            "definition": "Test category definition for category A",
            "themes": [
                {
                    "name": "Theme 1",
                    "definition": "First test theme definition for testing",
                    "initial_codes": [
                        {
                            "name": "ic_a",
                            "definition": "IC A definition text here",
                            "quote_count": 5,
                            "quotes": [{"quote_text": "Example quote text here"}],
                        },
                    ],
                },
            ],
        },
    ]


@pytest.fixture
def sample_metrics_interp():
    """MetricsInterpretation for testing Call 3."""
    return MetricsInterpretation(
        assessments=[
            MetricAssessment(
                metric_name="grounding_rate",
                observed_value="96.0%",
                status="healthy",
                interpretation="Grounding rate is well within guidelines, indicating reliable quote extraction with minimal hallucination.",
            ),
        ],
        data_quality_summary=(
            "Overall data quality is strong. The grounding rate indicates reliable "
            "quote extraction and the codebook is developing with appropriate evidence concentration."
        ),
        saturation_assessment=(
            "The codebook has not yet reached saturation. ITS values are still above "
            "the threshold, suggesting more data would yield new codes."
        ),
    )


@pytest.fixture
def sample_structural_diag():
    """StructuralDiagnostics for testing Call 3."""
    return StructuralDiagnostics(
        theme_diagnostics=[
            ThemeDiagnostic(
                theme_name="Theme 1",
                ic_count=5,
                coherence=0.7,
                issue_type="healthy",
                assessment="Theme 1 is well-defined with strong coherence and adequate evidence from multiple sources.",
            ),
        ],
        category_diagnostics=[
            CategoryDiagnostic(
                category_name="Category A",
                theme_count=3,
                assessment="Category A groups related themes effectively with clear conceptual boundaries.",
                potential_issue="healthy",
            ),
        ],
        strongest_themes=["Theme 1"],
        weakest_themes=["Theme 2"],
        structural_summary=(
            "The thematic structure shows reasonable coherence with some overlap "
            "between themes that could benefit from further refinement."
        ),
    )


@pytest.fixture
def mock_model_client():
    """Mock ModelClient with proper get_client return."""
    mc = MagicMock()
    mock_params = MagicMock(temperature=0.3, max_tokens=16000)
    mc.get_client.return_value = (MagicMock(), "claude-sonnet-4-5-20250929", mock_params)
    return mc


@pytest.fixture
def mock_config():
    """Mock EQDConfig."""
    config = MagicMock()
    config.analyst_guidelines = AnalystGuidelinesConfig()
    config.processing.batch_size = 10
    config.processing.segments_per_coder_call = 2
    config.processing.auto_merge_threshold = 0.72
    config.processing.auto_new_threshold = 0.5
    config.processing.coherence_threshold = 1.0
    config.processing.category_merge_threshold = 0.85
    config.theme_refinement.distinctness_threshold = 0.70
    config.theme_refinement.split_min_ics = 8
    config.theme_refinement.split_max_coherence = 0.50
    return config


# ── Model Validation Tests ────────────────────────────────────────────────


class TestLayer4Models:
    """Test Pydantic model validation for Layer 4."""

    def test_metric_assessment_valid(self):
        a = MetricAssessment(
            metric_name="grounding_rate",
            observed_value="96.2%",
            status="healthy",
            interpretation="This is a valid interpretation of the metric value in context of the run.",
        )
        assert a.status == "healthy"

    def test_metric_assessment_invalid_status(self):
        with pytest.raises(Exception):
            MetricAssessment(
                metric_name="x",
                observed_value="1",
                status="bad_status",
                interpretation="This is a valid interpretation of the metric value in context.",
            )

    def test_theme_diagnostic_valid(self):
        td = ThemeDiagnostic(
            theme_name="Combat Issues",
            ic_count=5,
            issue_type="magnet_theme",
            assessment="This theme has too many ICs and low coherence suggesting it needs splitting.",
        )
        assert td.issue_type == "magnet_theme"

    def test_theme_diagnostic_invalid_issue(self):
        with pytest.raises(Exception):
            ThemeDiagnostic(
                theme_name="X",
                ic_count=1,
                issue_type="nonexistent_issue",
                assessment="This is a valid assessment of the theme quality and structure.",
            )

    def test_category_diagnostic_valid(self):
        cd = CategoryDiagnostic(
            category_name="Core Mechanics",
            theme_count=3,
            assessment="This category groups related themes effectively with clear boundaries.",
            potential_issue="too_broad",
        )
        assert cd.potential_issue == "too_broad"

    def test_analytical_brief_container(
        self, sample_metrics_interp, sample_structural_diag,
    ):
        synthesis = AnalystSynthesis(
            overall_assessment=(
                "The analysis demonstrates strong data integrity with reliable quote extraction. "
                "The thematic structure shows reasonable coherence but some overlap between themes "
                "that could benefit from further refinement. The codebook is developing well but "
                "has not yet reached saturation."
            ),
            key_findings=["Finding 1 about the analysis quality"],
            config_recommendations=[],
            next_steps=["Process more data to reach saturation"],
            confidence_note="Small sample size (30 reviews) limits generalisability of findings.",
        )
        brief = AnalyticalBrief(
            metrics=sample_metrics_interp,
            structure=sample_structural_diag,
            synthesis=synthesis,
        )
        assert brief.metrics.assessments[0].metric_name == "grounding_rate"
        assert brief.synthesis.key_findings[0] == "Finding 1 about the analysis quality"

    def test_config_recommendation(self):
        rec = ConfigRecommendation(
            parameter="processing.category_merge_threshold",
            current_value="0.85",
            suggested_value="0.90",
            rationale="Categories are being merged too aggressively based on current threshold settings.",
        )
        assert rec.parameter == "processing.category_merge_threshold"


# ── Prompt Tests ──────────────────────────────────────────────────────────


class TestLayer4Prompts:
    """Test prompt building functions."""

    def test_metrics_system_prompt(self):
        prompt = build_metrics_interpretation_system_prompt()
        assert "qualitative data analysis" in prompt
        assert "healthy" in prompt
        assert "monitor" in prompt
        assert "investigate" in prompt

    def test_metrics_user_prompt(self, sample_layer3, sample_guidelines):
        prompt = build_metrics_interpretation_user_prompt(
            sample_layer3,
            sample_guidelines,
            {"n_documents": 30, "n_segments": 30, "n_ics": 30},
        )
        assert "30 documents" in prompt
        assert "grounding_rate" in prompt
        assert "METRIC DEFINITIONS" in prompt
        assert "OBSERVED VALUES" in prompt

    def test_structural_system_prompt(self):
        prompt = build_structural_diagnostics_system_prompt()
        assert "thematic structure" in prompt
        assert "magnet theme" in prompt

    def test_structural_user_prompt(self, sample_thematic_structure):
        prompt = build_structural_diagnostics_user_prompt(
            sample_thematic_structure,
            {"themes_proposed": 5, "themes_after_refinement": 4},
            # theme_coherence is a flat {name: float} dict in production
            {"theme_coherence": {"Theme 1": 0.7}, "sentiment_purity": {}},
        )
        assert "THEMATIC STRUCTURE" in prompt
        assert "Theme 1" in prompt
        assert "LAYER 2 SUMMARY" in prompt
        assert "0.700" in prompt  # coherence value should appear

    def test_synthesis_system_prompt(self):
        prompt = build_analyst_synthesis_system_prompt()
        assert "senior research methodologist" in prompt
        assert "config_recommendations" in prompt
        assert "DO NOT repeat" in prompt  # anti-redundancy instruction

    def test_synthesis_user_prompt(self):
        metrics_dump = {
            "assessments": [
                {
                    "metric_name": "grounding_rate",
                    "observed_value": "96%",
                    "status": "healthy",
                    "interpretation": "Good grounding rate",
                },
            ],
            "data_quality_summary": "Quality looks good",
            "saturation_assessment": "Not saturated",
        }
        structural_dump = {
            "theme_diagnostics": [
                {
                    "theme_name": "T1",
                    "ic_count": 5,
                    "issue_type": "healthy",
                    "assessment": "Fine",
                },
            ],
            "strongest_themes": ["T1"],
            "weakest_themes": ["T2"],
            "structural_summary": "Structure is OK",
        }
        prompt = build_analyst_synthesis_user_prompt(
            metrics_dump,
            structural_dump,
            {"batch_size": 10, "auto_merge_threshold": 0.72},
            {"documents": 30, "segments": 30, "active_ics": 30},
        )
        assert "METRICS INTERPRETATION" in prompt
        assert "STRUCTURAL DIAGNOSTICS" in prompt
        assert "CURRENT CONFIGURATION" in prompt
        assert "batch_size" in prompt


# ── Guidelines Config Tests ───────────────────────────────────────────────


class TestGuidelinesConfig:
    """Test AnalystGuidelinesConfig."""

    def test_default_config(self):
        cfg = AnalystGuidelinesConfig()
        # Default should have empty MetricGuidelineConfig objects
        assert cfg.grounding_rate.description == ""

    def test_to_prompt_block_with_data(self, sample_guidelines):
        block = sample_guidelines.to_prompt_block()
        assert "grounding_rate" in block
        assert "Proportion of verified quotes" in block
        assert "min 0.95" in block

    def test_to_prompt_block_empty(self):
        cfg = AnalystGuidelinesConfig()
        block = cfg.to_prompt_block()
        # Empty descriptions → no content
        assert block.strip() == ""

    def test_metric_guideline_config(self):
        g = MetricGuidelineConfig(
            description="Test metric",
            what_it_measures="Measures something",
            healthy_min=0.5,
            healthy_max=0.9,
            low_means="Too low",
            high_means="Too high",
        )
        assert g.healthy_min == 0.5
        assert g.healthy_max == 0.9


# ── Agent Tests (Mocked LLM) ─────────────────────────────────────────────


class TestAnalystAgent:
    """Test AnalystAgent with mocked LLM calls."""

    def _build_results(self, sample_layer3, sample_thematic_structure):
        """Build a full results dict for testing."""
        return {
            "layer0": {"documents": 30, "segments": 30},
            "layer1": {"new_ics_created": 30, "batches_processed": 3},
            "layer2": {
                "themes_proposed": 5,
                "themes_after_refinement": 4,
                "dissolved_theme_names": [],
                "ics_redistributed": 0,
                "ics_unassigned": 0,
            },
            "layer3": sample_layer3,
            "thematic_structure": sample_thematic_structure,
            "categories": {"categories_created": 2},
        }

    def test_analyze_success(
        self,
        mock_model_client,
        mock_config,
        sample_layer3,
        sample_thematic_structure,
        sample_metrics_interp,
        sample_structural_diag,
    ):
        """Test full analyze() flow with mocked LLM."""
        agent = AnalystAgent(mock_model_client, mock_config)
        results = self._build_results(sample_layer3, sample_thematic_structure)

        # Mock all 3 LLM calls
        client_mock = mock_model_client.get_client.return_value[0]

        synthesis = AnalystSynthesis(
            overall_assessment=(
                "The analysis demonstrates strong data integrity with reliable quote extraction. "
                "The thematic structure shows reasonable coherence but some overlap between themes "
                "that could benefit from further refinement. The codebook is developing well but "
                "has not yet reached saturation."
            ),
            key_findings=["Finding one about the overall analysis"],
            config_recommendations=[],
            next_steps=["Process more reviews to reach saturation"],
            confidence_note="Small sample size (30 reviews) limits generalisability of findings.",
        )

        client_mock.chat.completions.create.side_effect = [
            sample_metrics_interp,
            sample_structural_diag,
            synthesis,
        ]

        brief = agent.analyze(results)

        assert isinstance(brief, AnalyticalBrief)
        assert brief.metrics.assessments[0].metric_name == "grounding_rate"
        assert brief.structure.strongest_themes == ["Theme 1"]
        assert len(brief.synthesis.key_findings) >= 1
        assert client_mock.chat.completions.create.call_count == 3

    def test_analyze_call1_failure(
        self,
        mock_model_client,
        mock_config,
        sample_layer3,
        sample_thematic_structure,
    ):
        """Test that analyze raises when Call 1 fails."""
        agent = AnalystAgent(mock_model_client, mock_config)
        results = self._build_results(sample_layer3, sample_thematic_structure)

        client_mock = mock_model_client.get_client.return_value[0]
        client_mock.chat.completions.create.side_effect = Exception("LLM timeout")

        with pytest.raises(Exception, match="LLM timeout"):
            agent.analyze(results)

    def test_interpret_metrics_builds_run_summary(
        self,
        mock_model_client,
        mock_config,
        sample_layer3,
        sample_thematic_structure,
        sample_metrics_interp,
    ):
        """Test that _interpret_metrics passes correct run summary."""
        agent = AnalystAgent(mock_model_client, mock_config)
        results = self._build_results(sample_layer3, sample_thematic_structure)

        client_mock = mock_model_client.get_client.return_value[0]
        client_mock.chat.completions.create.return_value = sample_metrics_interp

        result = agent._interpret_metrics(results)
        assert isinstance(result, MetricsInterpretation)

        # Verify the LLM was called with system + user messages
        call_args = client_mock.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_diagnose_structure_passes_coherence(
        self,
        mock_model_client,
        mock_config,
        sample_layer3,
        sample_thematic_structure,
        sample_structural_diag,
    ):
        """Test that _diagnose_structure includes coherence data."""
        agent = AnalystAgent(mock_model_client, mock_config)
        results = self._build_results(sample_layer3, sample_thematic_structure)

        client_mock = mock_model_client.get_client.return_value[0]
        client_mock.chat.completions.create.return_value = sample_structural_diag

        result = agent._diagnose_structure(results)
        assert isinstance(result, StructuralDiagnostics)

    def test_synthesize_includes_config(
        self,
        mock_model_client,
        mock_config,
        sample_layer3,
        sample_thematic_structure,
        sample_metrics_interp,
        sample_structural_diag,
    ):
        """Test that _synthesize passes config summary."""
        agent = AnalystAgent(mock_model_client, mock_config)
        results = self._build_results(sample_layer3, sample_thematic_structure)

        synthesis = AnalystSynthesis(
            overall_assessment=(
                "The analysis demonstrates strong data integrity with reliable quote extraction. "
                "The thematic structure shows reasonable coherence but some overlap between themes."
            ),
            key_findings=["Finding about config parameters and their effects"],
            config_recommendations=[
                ConfigRecommendation(
                    parameter="processing.category_merge_threshold",
                    current_value="0.85",
                    suggested_value="0.90",
                    rationale="Categories are merged too aggressively with current threshold settings.",
                ),
            ],
            next_steps=["Run more reviews to reach saturation threshold"],
            confidence_note="Small sample size (30 reviews) limits generalisability of the findings.",
        )

        client_mock = mock_model_client.get_client.return_value[0]
        client_mock.chat.completions.create.return_value = synthesis

        result = agent._synthesize(sample_metrics_interp, sample_structural_diag, results)
        assert isinstance(result, AnalystSynthesis)
        assert len(result.config_recommendations) == 1
        assert result.config_recommendations[0].parameter == "processing.category_merge_threshold"


# ── Display Tests ─────────────────────────────────────────────────────────


class TestDisplayBrief:
    """Test display_analytical_brief output."""

    def test_display_runs_without_error(self, capsys):
        """Test that display_analytical_brief prints without crashing."""
        brief_dict = {
            "metrics": {
                "assessments": [
                    {
                        "metric_name": "grounding_rate",
                        "observed_value": "96.2%",
                        "status": "healthy",
                        "interpretation": "Grounding rate is well within guidelines for this run.",
                        "context_factors": None,
                    },
                ],
                "data_quality_summary": (
                    "Overall data quality is strong with reliable quote extraction "
                    "and appropriate codebook development."
                ),
                "saturation_assessment": (
                    "Codebook is approaching saturation but has not fully reached it. "
                    "More data would be beneficial."
                ),
            },
            "structure": {
                "theme_diagnostics": [
                    {
                        "theme_name": "Combat Issues",
                        "ic_count": 5,
                        "issue_type": "healthy",
                        "assessment": "Theme is well-defined with strong coherence and evidence.",
                        "suggested_action": None,
                    },
                ],
                "category_diagnostics": [],
                "strongest_themes": ["Combat Issues"],
                "weakest_themes": ["Story Pacing"],
                "structural_summary": "Structure is reasonable with room for improvement.",
            },
            "synthesis": {
                "overall_assessment": (
                    "The analysis demonstrates strong data integrity and a developing "
                    "thematic structure. The codebook is not yet saturated but the "
                    "foundation is solid for continued analysis with more data."
                ),
                "key_findings": [
                    "Strong grounding rate",
                    "Theme overlap needs attention",
                ],
                "config_recommendations": [
                    {
                        "parameter": "processing.category_merge_threshold",
                        "current_value": "0.85",
                        "suggested_value": "0.90",
                        "rationale": "Categories merged too aggressively at current threshold.",
                    },
                ],
                "next_steps": ["Process 20 more reviews"],
                "confidence_note": "Small sample size of 30 reviews limits findings.",
            },
        }

        display_analytical_brief(brief_dict)
        captured = capsys.readouterr()

        assert "LAYER 4" in captured.out
        assert "grounding_rate" in captured.out
        assert "Combat Issues" in captured.out
        assert "CONFIDENCE NOTE" in captured.out

    def test_display_empty_brief(self, capsys):
        """Test display handles empty/minimal brief."""
        display_analytical_brief({})
        captured = capsys.readouterr()
        assert "LAYER 4" in captured.out
