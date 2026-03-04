"""
Tests for src/reasoning_log.py.

Covers:
  - extract_reasoning(): multi-provider format handling
      * DeepSeek / compatible (reasoning_content field)
      * OpenAI direct (message.reasoning field)
      * OpenAI detail list (reasoning_details with summary / encrypted types)
      * Token count extraction from completion_tokens_details
      * Non-reasoning models (all fields absent)
      * None / empty completion guard
  - ReasoningLogger.log():
      * "full" mode writes all calls
      * "failures_only" mode skips calls with no reasoning
      * "failures_only" mode writes encrypted reasoning
      * Log entry contains expected fields
      * File-write failure is silently swallowed (never crashes pipeline)
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.reasoning_log import ReasoningLogger, extract_reasoning


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_completion(
    reasoning_content=None,
    reasoning=None,
    reasoning_details=None,
    reasoning_tokens=0,
    completion_tokens=100,
    total_tokens=200,
):
    """Build a minimal fake ChatCompletion object."""
    message = SimpleNamespace(
        reasoning_content=reasoning_content,
        reasoning=reasoning,
        reasoning_details=reasoning_details,
    )
    details = SimpleNamespace(reasoning_tokens=reasoning_tokens)
    usage = SimpleNamespace(
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        completion_tokens_details=details,
    )
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


# ── extract_reasoning: provider format handling ───────────────────────────────

class TestExtractReasoningFormats:

    def test_deepseek_reasoning_content(self):
        """DeepSeek-style: reasoning available via message.reasoning_content."""
        raw = _make_completion(reasoning_content="chain of thought here", reasoning_tokens=42)
        text, tokens, encrypted = extract_reasoning(raw)

        assert text == "chain of thought here"
        assert tokens == 42
        assert encrypted is False

    def test_openai_direct_reasoning_field(self):
        """OpenAI-style direct: reasoning available via message.reasoning."""
        raw = _make_completion(reasoning="direct reasoning text")
        text, tokens, encrypted = extract_reasoning(raw)

        assert text == "direct reasoning text"
        assert encrypted is False

    def test_openai_reasoning_details_summary(self):
        """OpenAI-style details list: type == reasoning.summary → text returned."""
        details = [{"type": "reasoning.summary", "summary": "summarised reasoning"}]
        raw = _make_completion(reasoning_details=details)
        text, tokens, encrypted = extract_reasoning(raw)

        assert text == "summarised reasoning"
        assert encrypted is False

    def test_openai_reasoning_details_encrypted(self):
        """OpenAI-style details list: type == reasoning.encrypted → encrypted flag set."""
        details = [{"type": "reasoning.encrypted"}]
        raw = _make_completion(reasoning_details=details)
        text, tokens, encrypted = extract_reasoning(raw)

        assert text is None
        assert encrypted is True

    def test_openai_reasoning_details_object_style(self):
        """reasoning_details entries can be objects (not dicts) depending on SDK version."""
        detail = SimpleNamespace(type="reasoning.summary", summary="object-style summary")
        raw = _make_completion(reasoning_details=[detail])
        text, tokens, encrypted = extract_reasoning(raw)

        assert text == "object-style summary"
        assert encrypted is False

    def test_reasoning_details_stops_at_first_summary(self):
        """Multiple detail entries: stops at first summary, doesn't clobber it."""
        details = [
            {"type": "reasoning.summary", "summary": "first summary"},
            {"type": "reasoning.summary", "summary": "second summary"},
        ]
        raw = _make_completion(reasoning_details=details)
        text, _, _ = extract_reasoning(raw)

        assert text == "first summary"

    def test_non_reasoning_model_returns_nones(self):
        """No reasoning fields present → (None, 0, False)."""
        raw = _make_completion()
        text, tokens, encrypted = extract_reasoning(raw)

        assert text is None
        assert tokens == 0
        assert encrypted is False

    def test_reasoning_tokens_extracted_from_usage(self):
        """Token count comes from usage.completion_tokens_details.reasoning_tokens."""
        raw = _make_completion(reasoning_content="thinking...", reasoning_tokens=77)
        _, tokens, _ = extract_reasoning(raw)

        assert tokens == 77

    def test_none_completion_returns_safe_defaults(self):
        """Guard: None completion → (None, 0, False) without raising."""
        text, tokens, encrypted = extract_reasoning(None)

        assert text is None
        assert tokens == 0
        assert encrypted is False

    def test_empty_choices_returns_safe_defaults(self):
        """Guard: empty choices list → safe defaults."""
        raw = SimpleNamespace(choices=[], usage=None)
        text, tokens, encrypted = extract_reasoning(raw)

        assert text is None
        assert tokens == 0
        assert encrypted is False

    def test_deepseek_takes_priority_over_openai(self):
        """If both reasoning_content and message.reasoning are present, DeepSeek wins."""
        raw = _make_completion(
            reasoning_content="deepseek content",
            reasoning="openai field",
        )
        text, _, _ = extract_reasoning(raw)

        assert text == "deepseek content"


# ── ReasoningLogger ───────────────────────────────────────────────────────────

class TestReasoningLogger:

    @pytest.fixture
    def log_dir(self, tmp_path):
        return tmp_path / "runs"

    def _read_log(self, log_dir: Path, run_id: str) -> list[dict]:
        path = log_dir / f"{run_id}_reasoning.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_full_mode_writes_non_reasoning_call(self, log_dir):
        """full mode: non-reasoning model call is still logged (reasoning fields = None/0)."""
        rl = ReasoningLogger(run_id="test-run", log_dir=log_dir, mode="full")
        raw = _make_completion()  # no reasoning fields

        rl.log("coder_agent", "model-x", raw)

        entries = self._read_log(log_dir, "test-run")
        assert len(entries) == 1
        assert entries[0]["agent"] == "coder_agent"
        assert entries[0]["reasoning_available"] is False
        assert entries[0]["reasoning_tokens"] == 0

    def test_full_mode_writes_reasoning_call(self, log_dir):
        """full mode: call with reasoning text is logged with content."""
        rl = ReasoningLogger(run_id="test-run", log_dir=log_dir, mode="full")
        raw = _make_completion(reasoning_content="my chain of thought", reasoning_tokens=55)

        rl.log("comparator", "deepseek-r1", raw)

        entries = self._read_log(log_dir, "test-run")
        assert len(entries) == 1
        assert entries[0]["reasoning_available"] is True
        assert entries[0]["reasoning_summary"] == "my chain of thought"
        assert entries[0]["reasoning_tokens"] == 55

    def test_failures_only_skips_non_reasoning(self, log_dir):
        """failures_only: call with no reasoning and not encrypted → not written."""
        rl = ReasoningLogger(run_id="test-run", log_dir=log_dir, mode="failures_only")
        raw = _make_completion()

        rl.log("coder_agent", "model-x", raw)

        entries = self._read_log(log_dir, "test-run")
        assert entries == []

    def test_failures_only_writes_encrypted(self, log_dir):
        """failures_only: encrypted reasoning (no text but something happened) is logged."""
        rl = ReasoningLogger(run_id="test-run", log_dir=log_dir, mode="failures_only")
        raw = _make_completion(reasoning_details=[{"type": "reasoning.encrypted"}])

        rl.log("coder_agent", "o1-mini", raw)

        entries = self._read_log(log_dir, "test-run")
        assert len(entries) == 1
        assert entries[0]["reasoning_encrypted"] is True

    def test_log_entry_contains_required_fields(self, log_dir):
        """Entry schema: all required fields are present."""
        rl = ReasoningLogger(run_id="run-001", log_dir=log_dir, mode="full")
        raw = _make_completion(reasoning_content="thinking", reasoning_tokens=10,
                               completion_tokens=80, total_tokens=100)

        rl.log("synthesizer_agent", "deepseek-r1", raw, context={"batch_id": 3})

        entry = self._read_log(log_dir, "run-001")[0]
        for field in ["timestamp", "run_id", "agent", "model_id",
                      "reasoning_available", "reasoning_encrypted",
                      "reasoning_tokens", "reasoning_summary",
                      "output_tokens", "total_tokens"]:
            assert field in entry, f"Missing field: {field}"
        assert entry["batch_id"] == 3  # context dict merged in
        assert entry["output_tokens"] == 70  # completion_tokens(80) - reasoning_tokens(10)

    def test_multiple_calls_appended_to_same_file(self, log_dir):
        """Multiple log() calls produce multiple JSONL lines in the same file."""
        rl = ReasoningLogger(run_id="multi-run", log_dir=log_dir, mode="full")
        raw = _make_completion()

        rl.log("agent_a", "model-x", raw)
        rl.log("agent_b", "model-y", raw)

        entries = self._read_log(log_dir, "multi-run")
        assert len(entries) == 2
        assert entries[0]["agent"] == "agent_a"
        assert entries[1]["agent"] == "agent_b"

    def test_file_write_failure_does_not_raise(self, log_dir):
        """Write failure is caught and logged as a warning — never crashes the pipeline."""
        rl = ReasoningLogger(run_id="test-run", log_dir=log_dir, mode="full")
        raw = _make_completion(reasoning_content="thinking")

        with patch("builtins.open", side_effect=OSError("disk full")):
            # Must not raise
            rl.log("coder_agent", "model-x", raw)

    def test_log_dir_created_if_missing(self, tmp_path):
        """Logger creates the log directory if it doesn't exist yet."""
        nested = tmp_path / "deep" / "nested" / "runs"
        assert not nested.exists()

        ReasoningLogger(run_id="x", log_dir=nested, mode="full")

        assert nested.exists()
