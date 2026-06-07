"""
EQD-AI Layer 1: Coder Agent (v2 — single-pass, raw measurement).

Processes one segment per LLM call. The model returns only verbatim quote text
(plus name/definition/confidence/sentiment) — it never produces character offsets.
LLMs cannot count offsets reliably (empirically ~93% wrong, drift growing with
length), so the system computes the span deterministically by locating the quote
in the canonical text.

Grounding gate (v2 contract #4 — hard gate, no repair):
    the quote must be an EXACT verbatim substring of canonical_text.
    span_start = canonical_text.find(quote_text); if not found → the quote contains
    hallucinated characters/words → candidate DROPPED (counted in
    `last_drop_counts` → quote_hallucination_rate). No realignment, no fuzzy match.

Pattern: instructor + Pydantic + tenacity retry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import EQDConfig, ModelClient
from src.core.reasoning_log import ReasoningLogger
from src.core.db import Database, InitialCodeRepo
from src.core.models import ICCandidate, RawICCandidate, Segment, SegmentCodingResult
from src.extraction.prompts import (
    build_codebook_context,
    build_coder_system_prompt,
    build_coder_user_prompt,
)

logger = logging.getLogger(__name__)


class CoderAgent:
    """
    Analyses text segments and extracts Initial Code candidates.

    Input: batch of Segments + current codebook (from DB)
    Output: {segment_id: [ICCandidate, ...]}

    The codebook is fetched once per batch (not per segment) to keep it
    consistent within a batch. New ICs created during a batch appear in
    the next batch's codebook.

    v2: one segment = one API call (no micro-batching). The orchestrator drives
    per-review two-pass processing on top of this single-segment primitive.
    """

    def __init__(
        self,
        model_client: ModelClient,
        db: Database,
        config: EQDConfig,
        reasoning_logger: Optional["ReasoningLogger"] = None,
    ):
        self.model_client = model_client
        self.db = db
        self.config = config
        self.reasoning_logger = reasoning_logger
        # Per-segment drop counts from the most recent process_batch() call.
        # Keyed by segment_id; value = number of candidates dropped because the
        # quote was not a verbatim substring (hallucinated text).
        self.last_drop_counts: Dict[str, int] = {}

    def process_batch(self, segments: List[Segment]) -> Dict[str, List[ICCandidate]]:
        """
        Process a batch of segments, one LLM call per segment.

        Returns {segment_id: [ICCandidate, ...]} — may be empty list for a segment.
        """
        # Fetch codebook once per batch
        ic_repo = InitialCodeRepo(self.db)
        codebook = ic_repo.get_all_active()
        codebook_context = build_codebook_context(codebook)

        results: Dict[str, List[ICCandidate]] = {}
        self.last_drop_counts = {}  # reset for this batch

        for idx, segment in enumerate(segments, 1):
            logger.info(f"[CODER] Segment {idx}/{len(segments)}: {segment.id}")
            candidates, n_dropped = self._code_segment(segment, codebook_context)
            results[segment.id] = candidates
            self.last_drop_counts[segment.id] = n_dropped

        return results

    def _code_segment(
        self,
        segment: Segment,
        codebook_context: str,
    ) -> Tuple[List[ICCandidate], int]:
        """
        Process a single segment through the Coder Agent LLM.

        1. Build prompts
        2. Call LLM via instructor → SegmentCodingResult (RawICCandidate list)
        3. Ground each quote: find it verbatim in canonical_text → compute span
        4. Drop candidates whose quote is not a verbatim substring (hallucination)

        Returns (grounded_candidates, n_dropped).
        """
        system_prompt = build_coder_system_prompt(codebook_context)
        user_prompt = build_coder_user_prompt(segment.id, segment.canonical_text)

        client, model_id, params = self.model_client.get_client("coder_agent")

        # Call LLM with retry
        try:
            result = self._call_llm(
                client=client,
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
            )
        except Exception as e:
            logger.error(
                f"Coder Agent failed for segment {segment.id} after retries: {e}"
            )
            return [], 0

        # Grounding gate — locate each quote verbatim; drop hallucinated ones
        grounded = []
        for raw in result.candidates:
            candidate = self._ground_candidate(raw, segment)
            if candidate is not None:
                grounded.append(candidate)
            else:
                logger.warning(
                    f"[HALLUCINATION] Dropped candidate '{raw.ic_name}' — "
                    f"quote not found verbatim in segment {segment.id}. "
                    f"Quote: '{raw.quote_text[:60]}…'"
                )

        n_dropped = len(result.candidates) - len(grounded)
        logger.info(
            f"Segment {segment.id}: {len(result.candidates)} candidates → "
            f"{len(grounded)} grounded ({n_dropped} hallucinated)"
        )
        return grounded, n_dropped

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> SegmentCodingResult:
        """
        Instructor-patched LLM call — single segment mode.

        Returns SegmentCodingResult (validated by Pydantic).
        Uses create_with_completion() to capture reasoning traces when available.
        """
        extra_body = self.model_client.build_extra_body("coder_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=SegmentCodingResult,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("coder_agent", model_id, raw)
        return parsed

    @staticmethod
    def _ground_candidate(
        raw: RawICCandidate, segment: Segment
    ) -> Optional[ICCandidate]:
        """
        Ground a raw candidate by locating its quote verbatim in the canonical text.

        The span is computed by the system (LLMs cannot count offsets). The only
        check is the grounding gate (contract #4): the quote must be an EXACT
        substring. If it is not found, the quote contains hallucinated
        characters/words/sentences → return None (candidate dropped).

        On a verbatim match, span_start/span_end are derived from the first
        occurrence; the resulting ICCandidate satisfies
        canonical_text[span_start:span_end] == quote_text by construction.
        """
        canonical = segment.canonical_text
        quote = raw.quote_text

        idx = canonical.find(quote)
        if idx < 0:
            return None  # not verbatim → hallucinated → dropped

        if canonical.count(quote) > 1:
            logger.debug(
                f"Quote for '{raw.ic_name}' occurs {canonical.count(quote)}× in "
                f"segment {segment.id}; grounding to first occurrence at {idx}."
            )

        return ICCandidate(
            ic_name=raw.ic_name,
            definition=raw.definition,
            quote_text=quote,
            span_start=idx,
            span_end=idx + len(quote),
            confidence=raw.confidence,
            sentiment=raw.sentiment,
            existing_code_match=raw.existing_code_match,
        )
