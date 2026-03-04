"""Tests for prompt construction."""

import pytest
from src.models import InitialCode, ICStatus
from src.prompts import (
    build_codebook_context,
    build_coder_system_prompt,
    build_coder_user_prompt,
    build_comparator_system_prompt,
    build_comparator_user_prompt,
)


class TestBuildCodebookContext:
    def test_empty_codebook(self):
        result = build_codebook_context([])
        assert "Empty codebook" in result
        assert "no existing codes" in result

    def test_with_codes(self, sample_ics):
        result = build_codebook_context(sample_ics)
        assert "3 active codes" in result
        assert "Delivery speed complaint" in result
        assert "Product quality praise" in result
        assert "Packaging damage" in result

    def test_includes_definitions(self, sample_ics):
        result = build_codebook_context(sample_ics)
        assert "dissatisfaction with the time" in result


class TestBuildCoderPrompts:
    def test_system_prompt_contains_principles(self):
        prompt = build_coder_system_prompt("(Empty codebook)")
        assert "STAY CLOSE TO DATA" in prompt
        assert "EXACT VERBATIM QUOTES" in prompt
        assert "CORRECT SPAN OFFSETS" in prompt
        assert "DON'T FORCE CODES" in prompt
        assert "span_start" in prompt
        assert "span_end" in prompt

    def test_system_prompt_includes_codebook(self, sample_ics):
        context = build_codebook_context(sample_ics)
        prompt = build_coder_system_prompt(context)
        assert "Delivery speed complaint" in prompt

    def test_user_prompt_includes_segment(self):
        prompt = build_coder_user_prompt("seg_123", "This is the text to code.")
        assert "seg_123" in prompt
        assert "This is the text to code." in prompt
        assert "canonical" in prompt.lower()


class TestBuildComparatorPrompts:
    def test_system_prompt_contains_recommendations(self):
        prompt = build_comparator_system_prompt()
        assert "NEW" in prompt
        assert "MERGE" in prompt
        assert "REJECT" in prompt
        assert "SUBCODE" not in prompt  # SUBCODE removed in favour of MERGE
        # Threshold guidance uses actual triage thresholds (0.55/0.65), not old stale values (0.85/0.70)
        assert "0.65" in prompt or "0.55" in prompt  # updated 2026-03-04: calibrated to real grey zone

    def test_user_prompt_with_top_k(self):
        top_k = [
            ("ic_001", "delivery_speed", "Time taken for delivery", 0.87),
            ("ic_002", "shipping_delay", "Package delayed in transit", 0.72),
        ]
        prompt = build_comparator_user_prompt(
            candidate_name="slow_delivery",
            candidate_definition="Customer reports slow delivery",
            candidate_quote="dostawa trwała zbyt długo",
            top_k=top_k,
        )
        assert "slow_delivery" in prompt
        assert "delivery_speed" in prompt
        assert "0.870" in prompt
        assert "shipping_delay" in prompt
        assert "0.720" in prompt

    def test_user_prompt_empty_codebook(self):
        prompt = build_comparator_user_prompt(
            candidate_name="first_code",
            candidate_definition="The first code ever",
            candidate_quote="some quote",
            top_k=[],
        )
        assert "codebook is empty" in prompt.lower()
