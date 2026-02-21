"""Tests for Layer 2 prompt construction — synthesizer and revision prompts."""

import pytest
from src.models import ThemeFeedback, ThemeFeedbackOption, ThemeProposal
from src.prompts import (
    build_synthesizer_system_prompt,
    build_synthesizer_user_prompt,
    build_revision_system_prompt,
    build_revision_user_prompt,
    build_ic_refinement_prompt,
)


class TestSynthesizerSystemPrompt:
    def test_contains_methodology_principles(self):
        prompt = build_synthesizer_system_prompt()
        assert "PATTERNS OF MEANING" in prompt.upper()
        assert "M:N RELATIONSHIP" in prompt
        assert "QUOTE INHERITANCE" in prompt
        assert "GROUNDED" in prompt.upper()

    def test_contains_output_instructions(self):
        prompt = build_synthesizer_system_prompt()
        assert "SynthesisOutput" in prompt
        assert "ThemeProposal" in prompt

    def test_forbids_re_extraction(self):
        prompt = build_synthesizer_system_prompt()
        assert "NOT extract" in prompt or "not re-coding" in prompt.lower()

    def test_contains_fewer_is_better_principle(self):
        prompt = build_synthesizer_system_prompt()
        assert "FEWER IS BETTER" in prompt

    def test_contains_chain_of_thought_steps(self):
        prompt = build_synthesizer_system_prompt()
        assert "CLUSTER" in prompt
        assert "LABEL" in prompt
        assert "REDUNDANCY CHECK" in prompt
        assert "COVERAGE CHECK" in prompt
        assert "FINALISE" in prompt

    def test_contains_few_shot_example(self):
        prompt = build_synthesizer_system_prompt()
        assert "FEW-SHOT EXAMPLE" in prompt
        assert "combat_sluggish" in prompt

    def test_naming_conventions(self):
        prompt = build_synthesizer_system_prompt()
        assert "3 to 6 words" in prompt
        assert "descriptive" in prompt.lower()
        assert "NOT evaluative" in prompt or "not evaluative" in prompt.lower()

    def test_instructs_reasoning_field(self):
        prompt = build_synthesizer_system_prompt()
        assert "reasoning" in prompt.lower()
        assert "chain-of-thought" in prompt.lower()


class TestSynthesizerUserPrompt:
    def test_formats_codebook(self):
        codebook = [
            {
                "name": "slow_delivery",
                "definition": "Delivery took too long",
                "quote_count": 5,
                "example_quotes": ["dostawa trwała za długo"],
            },
            {
                "name": "product_quality",
                "definition": "Product exceeded expectations",
                "quote_count": 3,
                "example_quotes": [],
            },
        ]
        prompt = build_synthesizer_user_prompt(codebook)
        assert "2 active Initial Codes" in prompt
        assert "slow_delivery" in prompt
        assert "product_quality" in prompt
        assert "5 verbatim quote" in prompt

    def test_includes_example_quotes(self):
        codebook = [
            {
                "name": "buggy_game",
                "definition": "Game has many bugs",
                "quote_count": 2,
                "example_quotes": ["crashed on startup", "textures not loading"],
            },
        ]
        prompt = build_synthesizer_user_prompt(codebook)
        assert "crashed on startup" in prompt
        assert "textures not loading" in prompt

    def test_truncates_long_quotes(self):
        long_quote = "x" * 200
        codebook = [
            {
                "name": "long_review",
                "definition": "Very long review",
                "quote_count": 1,
                "example_quotes": [long_quote],
            },
        ]
        prompt = build_synthesizer_user_prompt(codebook)
        assert "..." in prompt  # Truncated
        assert long_quote not in prompt  # Full quote NOT present

    def test_max_3_example_quotes(self):
        codebook = [
            {
                "name": "test_code",
                "definition": "Test code with many quotes",
                "quote_count": 10,
                "example_quotes": ["q1", "q2", "q3", "q4", "q5"],
            },
        ]
        prompt = build_synthesizer_user_prompt(codebook)
        assert "q1" in prompt
        assert "q3" in prompt
        assert "q4" not in prompt  # Only first 3

    def test_empty_codebook(self):
        prompt = build_synthesizer_user_prompt([])
        assert "empty" in prompt.lower()

    def test_codebook_with_zero_quotes(self):
        codebook = [
            {
                "name": "orphan_code",
                "definition": "Code with no quotes",
                "quote_count": 0,
                "example_quotes": [],
            },
        ]
        prompt = build_synthesizer_user_prompt(codebook)
        assert "0 verbatim" in prompt


class TestRevisionSystemPrompt:
    def test_mentions_all_seven_feedback_types(self):
        prompt = build_revision_system_prompt()
        assert "SPLIT" in prompt
        assert "MERGE" in prompt
        assert "IC_MISASSIGNED" in prompt
        assert "RENAME" in prompt
        assert "REDEFINE" in prompt
        assert "OVERLAP_CONFLICT" in prompt
        assert "FREETEXT" in prompt

    def test_output_model(self):
        prompt = build_revision_system_prompt()
        assert "RevisionOutput" in prompt

    def test_instructs_apply_all_feedback(self):
        prompt = build_revision_system_prompt()
        assert "Apply ALL feedback" in prompt or "Apply all feedback" in prompt


class TestRevisionUserPrompt:
    @pytest.fixture
    def sample_themes(self):
        return [
            ThemeProposal(
                name="Service quality concerns",
                definition="Customers express dissatisfaction with service delivery and responsiveness",
                rationale="Groups delivery and response time ICs",
                constituent_ic_names=["slow_delivery", "poor_response", "no_updates"],
            ),
            ThemeProposal(
                name="Product satisfaction",
                definition="Positive evaluations of product quality and features",
                rationale="Groups product praise ICs",
                constituent_ic_names=["great_quality", "good_features"],
            ),
        ]

    @pytest.fixture
    def sample_feedback(self):
        return [
            ThemeFeedback(
                theme_name="Service quality concerns",
                option=ThemeFeedbackOption.RENAME,
                details="Service delivery failures",
            ),
            ThemeFeedback(
                theme_name="Product satisfaction",
                option=ThemeFeedbackOption.SPLIT,
                details="Quality praise, Feature praise",
            ),
        ]

    def test_includes_theme_names(self, sample_themes, sample_feedback):
        prompt = build_revision_user_prompt(sample_themes, sample_feedback)
        assert "Service quality concerns" in prompt
        assert "Product satisfaction" in prompt

    def test_includes_ic_lists(self, sample_themes, sample_feedback):
        prompt = build_revision_user_prompt(sample_themes, sample_feedback)
        assert "slow_delivery" in prompt
        assert "poor_response" in prompt
        assert "no_updates" in prompt

    def test_includes_feedback_details(self, sample_themes, sample_feedback):
        prompt = build_revision_user_prompt(sample_themes, sample_feedback)
        assert "RENAME" in prompt
        assert "Service delivery failures" in prompt
        assert "SPLIT" in prompt
        assert "Quality praise, Feature praise" in prompt

    def test_feedback_count(self, sample_themes, sample_feedback):
        prompt = build_revision_user_prompt(sample_themes, sample_feedback)
        assert "2 item(s)" in prompt

    def test_theme_count(self, sample_themes, sample_feedback):
        prompt = build_revision_user_prompt(sample_themes, sample_feedback)
        assert "2 themes" in prompt


class TestICRefinementPrompt:
    def test_includes_ic_name_and_definition(self):
        prompt = build_ic_refinement_prompt(
            ic_name="combat_sluggish",
            original_definition="Combat feels slow and unresponsive",
            merge_count=3,
            quote_texts=["combat is sluggish", "fighting feels slow", "attacks are delayed", "melee is clunky"],
        )
        assert "combat_sluggish" in prompt
        assert "Combat feels slow and unresponsive" in prompt

    def test_includes_all_quotes(self):
        quotes = ["quote one", "quote two", "quote three"]
        prompt = build_ic_refinement_prompt(
            ic_name="test_ic",
            original_definition="Test definition",
            merge_count=2,
            quote_texts=quotes,
        )
        for q in quotes:
            assert q in prompt

    def test_truncates_long_quotes(self):
        long_quote = "x" * 300
        prompt = build_ic_refinement_prompt(
            ic_name="test_ic",
            original_definition="Test definition",
            merge_count=1,
            quote_texts=[long_quote],
        )
        assert "..." in prompt
        assert long_quote not in prompt

    def test_includes_merge_count(self):
        prompt = build_ic_refinement_prompt(
            ic_name="test_ic",
            original_definition="Test definition",
            merge_count=5,
            quote_texts=["q1", "q2"],
        )
        assert "5 additional" in prompt

    def test_mentions_response_model(self):
        prompt = build_ic_refinement_prompt(
            ic_name="test_ic",
            original_definition="Test definition",
            merge_count=1,
            quote_texts=["q1"],
        )
        assert "RefinedICOutput" in prompt
