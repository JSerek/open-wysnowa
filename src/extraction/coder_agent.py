"""
EQD-AI Layer 1: Coder Agent.

Processes segments against the current codebook and produces IC candidates.
Each candidate includes a verbatim quote with exact character-level spans.

Pattern: instructor + Pydantic + tenacity retry.
Span validation uses a 3-tier strategy:
  1. Strict match: canonical_text[start:end] == quote_text
  2. Realignment: quote_text found elsewhere in canonical_text → fix spans
  3. Fuzzy match: near-miss search (strip whitespace/punctuation, substring)
Only candidates that fail all 3 tiers are dropped.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import EQDConfig, ModelClient
from src.core.reasoning_log import ReasoningLogger
from src.core.db import Database, InitialCodeRepo
from src.core.models import BatchCodingResult, ICCandidate, InitialCode, Segment, SegmentCodingResult
from src.extraction.prompts import (
    build_codebook_context,
    build_coder_system_prompt,
    build_coder_user_prompt,
    build_coder_user_prompt_batch,
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
        # Keyed by segment_id; value = number of candidates dropped due to span validation failure.
        self.last_drop_counts: Dict[str, int] = {}

    def process_batch(self, segments: List[Segment]) -> Dict[str, List[ICCandidate]]:
        """
        Process a batch of segments and extract IC candidates.

        Sends segments in micro-batches (segments_per_coder_call) to reduce
        API calls. Falls back to single-segment mode when micro_batch_size == 1.

        Returns {segment_id: [ICCandidate, ...]} — may be empty list for a segment.
        """
        # Fetch codebook once per batch
        ic_repo = InitialCodeRepo(self.db)
        codebook = ic_repo.get_all_active()
        codebook_context = build_codebook_context(codebook)

        results: Dict[str, List[ICCandidate]] = {}
        self.last_drop_counts = {}  # reset for this batch
        micro_batch_size = self.config.processing.segments_per_coder_call

        # Split into micro-batches for LLM calls
        total_sub_batches = -(-len(segments) // micro_batch_size)  # ceil division
        for i in range(0, len(segments), micro_batch_size):
            micro_batch = segments[i : i + micro_batch_size]
            sub_batch_num = (i // micro_batch_size) + 1
            logger.info(
                f"[CODER] Sub-batch {sub_batch_num}/{total_sub_batches}: "
                f"{len(micro_batch)} segments"
            )

            if len(micro_batch) == 1:
                # Single segment → original flow
                candidates, n_dropped = self._code_segment(micro_batch[0], codebook_context)
                results[micro_batch[0].id] = candidates
                self.last_drop_counts[micro_batch[0].id] = n_dropped
            else:
                # Multi-segment → batch call (_code_segments_batch updates self.last_drop_counts)
                batch_results = self._code_segments_batch(micro_batch, codebook_context)
                results.update(batch_results)

        return results

    def _code_segment(
        self,
        segment: Segment,
        codebook_context: str,
    ) -> Tuple[List[ICCandidate], int]:
        """
        Process a single segment through the Coder Agent LLM.

        1. Build prompts
        2. Call LLM via instructor → SegmentCodingResult
        3. Post-validate spans against canonical_text
        4. Drop candidates with invalid spans

        Returns (validated_candidates, n_dropped).
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

        # Post-validate: verify every candidate's span
        validated = []
        for candidate in result.candidates:
            if self._validate_span(candidate, segment):
                validated.append(candidate)
            else:
                logger.warning(
                    f"Dropped candidate '{candidate.ic_name}' — "
                    f"quote not found in segment {segment.id} "
                    f"(all 3 tiers failed). "
                    f"Quote: '{candidate.quote_text[:60]}…'"
                )

        n_dropped = len(result.candidates) - len(validated)
        logger.info(
            f"Segment {segment.id}: {len(result.candidates)} candidates → "
            f"{len(validated)} valid ({n_dropped} dropped)"
        )
        return validated, n_dropped

    def _code_segments_batch(
        self,
        segments: List[Segment],
        codebook_context: str,
    ) -> Dict[str, List[ICCandidate]]:
        """
        Process multiple segments in a single LLM call.

        1. Build multi-segment prompt
        2. Call LLM via instructor → BatchCodingResult
        3. Post-validate spans for each segment's candidates
        4. Return {segment_id: [validated candidates]}
        """
        system_prompt = build_coder_system_prompt(codebook_context)
        segment_data = [(seg.id, seg.canonical_text) for seg in segments]
        user_prompt = build_coder_user_prompt_batch(segment_data)

        # Build a lookup for span validation
        seg_map = {seg.id: seg for seg in segments}

        client, model_id, params = self.model_client.get_client("coder_agent")

        # Scale max_tokens with number of segments
        scaled_max_tokens = min(params.max_tokens * len(segments), 16000)

        try:
            result = self._call_llm_batch(
                client=client,
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=params.temperature,
                max_tokens=scaled_max_tokens,
            )
        except Exception as e:
            logger.error(
                f"Batch Coder Agent failed for {len(segments)} segments: {e}. "
                f"Falling back to single-segment mode."
            )
            # Fallback: process each segment individually
            results: Dict[str, List[ICCandidate]] = {}
            for seg in segments:
                validated, n_dropped = self._code_segment(seg, codebook_context)
                results[seg.id] = validated
                self.last_drop_counts[seg.id] = n_dropped
            return results

        # Map and validate results per segment
        results: Dict[str, List[ICCandidate]] = {seg.id: [] for seg in segments}

        for seg_result in result.segment_results:
            segment = seg_map.get(seg_result.segment_id)
            if not segment:
                logger.warning(
                    f"BatchCodingResult references unknown segment_id: "
                    f"{seg_result.segment_id} — skipping"
                )
                continue

            validated = []
            for candidate in seg_result.candidates:
                if self._validate_span(candidate, segment):
                    validated.append(candidate)
                else:
                    logger.warning(
                        f"Dropped candidate '{candidate.ic_name}' — "
                        f"quote not found in segment {segment.id} "
                        f"(all 3 tiers failed). "
                        f"Quote: '{candidate.quote_text[:60]}…'"
                    )

            n_dropped = len(seg_result.candidates) - len(validated)
            logger.info(
                f"Segment {segment.id}: {len(seg_result.candidates)} candidates → "
                f"{len(validated)} valid ({n_dropped} dropped)"
            )
            results[segment.id] = validated
            self.last_drop_counts[segment.id] = n_dropped

        # Targeted retry: segments missing from batch response → retry individually
        responded_ids = {sr.segment_id for sr in result.segment_results}
        for seg in segments:
            if seg.id not in responded_ids:
                logger.warning(
                    f"Batch response missing segment {seg.id} — retrying individually"
                )
                validated, n_dropped = self._code_segment(seg, codebook_context)
                results[seg.id] = validated
                self.last_drop_counts[seg.id] = n_dropped
                if validated:
                    logger.info(
                        f"Targeted retry recovered {len(validated)} candidates for {seg.id}"
                    )
                else:
                    logger.warning(
                        f"Targeted retry found no candidates for {seg.id}"
                    )

        return results

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_llm_batch(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> BatchCodingResult:
        """
        Instructor-patched LLM call — multi-segment batch mode.

        Returns BatchCodingResult (validated by Pydantic).
        Uses create_with_completion() to capture reasoning traces when available.
        """
        extra_body = self.model_client.build_extra_body("coder_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=BatchCodingResult,
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
    def _validate_span(candidate: ICCandidate, segment: Segment) -> bool:
        """
        3-tier span validation with realignment.

        Tier 1: Strict — canonical_text[start:end] == quote_text
        Tier 2: Realign — quote_text exists in canonical_text at different offset
        Tier 3: Fuzzy — stripped/trimmed quote_text found as substring

        If Tier 2 or 3 succeeds, candidate.span_start/span_end are corrected
        in place so downstream code gets valid spans.

        Returns True if any tier succeeds, False only if quote is truly
        not grounded in the canonical text.
        """
        canonical = segment.canonical_text
        start, end = candidate.span_start, candidate.span_end
        quote = candidate.quote_text

        # ── Tier 1: strict match ──────────────────────────────────────────
        if end <= len(canonical) and canonical[start:end] == quote:
            return True

        # ── Tier 2: exact realignment ─────────────────────────────────────
        # Quote text is correct but LLM got the offsets wrong (very common)
        idx = canonical.find(quote)
        if idx >= 0:
            candidate.span_start = idx
            candidate.span_end = idx + len(quote)
            logger.debug(
                f"Realigned '{candidate.ic_name}' span "
                f"[{start}:{end}] → [{idx}:{idx + len(quote)}]"
            )
            return True

        # ── Tier 3: fuzzy match ───────────────────────────────────────────
        # Handle common LLM mistakes: extra/missing punctuation, whitespace,
        # trailing period, off-by-one at boundaries

        # 3a: Strip leading/trailing whitespace and punctuation from quote
        stripped = quote.strip().strip(".,;:!?…\"'""''«»")
        if stripped and stripped != quote:
            idx = canonical.find(stripped)
            if idx >= 0:
                candidate.quote_text = stripped
                candidate.span_start = idx
                candidate.span_end = idx + len(stripped)
                logger.debug(
                    f"Fuzzy-matched '{candidate.ic_name}' after stripping "
                    f"punctuation: '{quote[:40]}…' → '{stripped[:40]}…'"
                )
                return True

        # 3b: Try finding a substantial substring (drop first/last few chars)
        # This catches off-by-1 or off-by-2 at boundaries
        for trim_start in range(min(4, len(quote) // 4)):
            for trim_end in range(min(4, len(quote) // 4)):
                if trim_start == 0 and trim_end == 0:
                    continue  # Already tried exact
                sub = quote[trim_start:len(quote) - trim_end if trim_end else len(quote)]
                if len(sub) < 10:
                    continue  # Don't match tiny fragments
                idx = canonical.find(sub)
                if idx >= 0:
                    # Expand back to a clean word boundary if possible
                    new_start = idx
                    new_end = idx + len(sub)
                    candidate.quote_text = canonical[new_start:new_end]
                    candidate.span_start = new_start
                    candidate.span_end = new_end
                    logger.debug(
                        f"Fuzzy-matched '{candidate.ic_name}' by trimming "
                        f"{trim_start} from start, {trim_end} from end"
                    )
                    return True

        # All tiers failed — quote is not grounded
        return False
