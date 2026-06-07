"""
EQD-AI Reasoning Trace Support.

Provides:
  - extract_reasoning()    — pulls reasoning text/tokens/encryption flag from raw completion
  - ReasoningLogger        — writes per-call traces to a per-run JSONL file

Design notes:
  - Reasoning comes from the API response envelope, not the structured output.
    It is captured via instructor's create_with_completion() and processed here.
  - Agents never interact with this module directly — they hold an Optional[ReasoningLogger]
    injected by the pipeline, and call logger.log() after each LLM call.
  - Non-reasoning models: extract_reasoning() returns (None, 0, False) — no special handling
    needed. The logger records zeros so the JSONL is structurally consistent.

Log mode (controlled by pipeline):
  - "full"          → every call is logged (default during dev/test)
  - "failures_only" → only calls that raised an exception or got validation errors
    (appropriate for production — set via pipeline config before go-live)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Reasoning extraction ──────────────────────────────────────────────────────

def extract_reasoning(raw: Any) -> Tuple[Optional[str], int, bool]:
    """
    Extract reasoning text, token count, and encryption flag from a raw ChatCompletion.

    Handles three provider formats:
      - OpenAI / OpenRouter (openai style):
          message.reasoning           → direct text (rare, sometimes accessible)
          message.reasoning_details   → list of dicts with type "reasoning.summary"
                                        or "reasoning.encrypted"
          usage.completion_tokens_details.reasoning_tokens → token count
      - DeepSeek (and compatible models via OpenRouter):
          message.reasoning_content   → full chain-of-thought text (always accessible)
      - Non-reasoning models:
          None of the above fields present → returns (None, 0, False)

    Returns:
        (reasoning_text, reasoning_tokens, encrypted)
        reasoning_text:   str if accessible, None if absent or fully encrypted
        reasoning_tokens: int — tokens consumed by reasoning (0 if not a reasoning model)
        encrypted:        True if reasoning happened but content is not accessible
    """
    if not raw or not raw.choices:
        return None, 0, False

    message = raw.choices[0].message
    reasoning_text: Optional[str] = None
    encrypted = False

    # ── DeepSeek / compatible: reasoning_content field ───────────────────────
    rc = getattr(message, "reasoning_content", None)
    if rc:
        reasoning_text = rc

    # ── OpenAI: direct message.reasoning ─────────────────────────────────────
    if reasoning_text is None:
        r = getattr(message, "reasoning", None)
        if r:
            reasoning_text = r

    # ── OpenAI: reasoning_details list (o-series, gpt-5-nano) ────────────────
    if reasoning_text is None:
        details = getattr(message, "reasoning_details", None)
        if details:
            for detail in details:
                # detail can be a dict or an object depending on SDK version
                if isinstance(detail, dict):
                    dtype = detail.get("type", "")
                    if dtype == "reasoning.summary":
                        reasoning_text = detail.get("summary", "") or None
                        break
                    elif dtype == "reasoning.encrypted":
                        encrypted = True
                else:
                    dtype = getattr(detail, "type", "")
                    if dtype == "reasoning.summary":
                        reasoning_text = getattr(detail, "summary", None) or None
                        break
                    elif dtype == "reasoning.encrypted":
                        encrypted = True

    # ── Token count from usage ────────────────────────────────────────────────
    reasoning_tokens = 0
    if raw.usage:
        details_obj = getattr(raw.usage, "completion_tokens_details", None)
        if details_obj:
            reasoning_tokens = getattr(details_obj, "reasoning_tokens", 0) or 0

    return reasoning_text, reasoning_tokens, encrypted


# ── Reasoning logger ──────────────────────────────────────────────────────────

class ReasoningLogger:
    """
    Writes per-call reasoning traces to a JSONL file under runs/.

    File: runs/<run_id>_reasoning.jsonl
    Each line: JSON object with agent, model, reasoning text, tokens, timestamp.

    One instance per pipeline run. Injected into all agents by the pipeline.
    Agents call logger.log(...) after each successful LLM call.

    Log modes:
      "full"          — log every call (development / testing default)
      "failures_only" — log only calls where reasoning is present AND some
                        failure signal exists (future: hook into validation errors)
    """

    def __init__(
        self,
        run_id: str,
        log_dir: Path,
        mode: str = "full",
    ):
        self.run_id = run_id
        self.mode = mode
        self._path = log_dir / f"{run_id}_reasoning.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "full":
            logger.info(
                f"[REASONING] Logging all traces → {self._path}"
            )
        else:
            logger.info(
                f"[REASONING] Logging failures only → {self._path}"
            )

    def log(
        self,
        agent_name: str,
        model_id: str,
        raw: Any,
        context: Optional[dict] = None,
    ) -> None:
        """
        Extract reasoning from raw completion and write a JSONL entry.

        Args:
            agent_name: logical agent name ("coder_agent", "synthesizer_agent", etc.)
            model_id:   actual model string sent to the API
            raw:        raw ChatCompletion object from create_with_completion()
            context:    optional dict of extra fields (batch_id, sub_batch, etc.)
        """
        reasoning_text, reasoning_tokens, encrypted = extract_reasoning(raw)

        # In "full" mode: log all calls (even non-reasoning models — records zeros)
        # In "failures_only" mode: only log if there's something to inspect
        if self.mode == "failures_only" and not reasoning_text and not encrypted:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "agent": agent_name,
            "model_id": model_id,
            "reasoning_available": reasoning_text is not None,
            "reasoning_encrypted": encrypted,
            "reasoning_tokens": reasoning_tokens,
            "reasoning_summary": reasoning_text,
            "output_tokens": (
                getattr(raw.usage, "completion_tokens", 0) - reasoning_tokens
                if raw and raw.usage else 0
            ),
            "total_tokens": (
                getattr(raw.usage, "total_tokens", 0)
                if raw and raw.usage else 0
            ),
        }
        if context:
            entry.update(context)

        self._write(entry)

    def log_record(self, record: dict) -> None:
        """
        Write an arbitrary structured record to the trace file.

        Used for process-level traceability (per-candidate decisions, IC-definition
        refinement) that is not tied to a single raw LLM completion. The record is
        written verbatim with run_id + timestamp prepended. Always written
        regardless of log mode — these records are the audit trail (contract #2),
        not raw reasoning summaries.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            **record,
        }
        self._write(entry)

    def log_candidate(self, record: dict) -> None:
        """
        Write a per-candidate decision trace (Appendix B).

        Expected keys: pass, segment_id, quote_text, span_start, span_end,
        grounded, coder_existing_code_match, top_k, judge_verdict,
        judge_reasoning, final_action.
        """
        self.log_record({"type": "candidate", **record})

    def _write(self, entry: dict) -> None:
        """Append one JSON object as a line to the trace file (never raises)."""
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # Never let logging fail silently crash the pipeline
            logger.warning(f"[REASONING] Failed to write log entry: {e}")
