"""
EQD-AI Layer 1: Coder Agent (v2 — single-pass, raw measurement).

Processes one segment per LLM call. The model returns only verbatim quote text
(plus name/definition/confidence/sentiment) — it never produces character offsets.
LLMs cannot count offsets reliably (empirically ~93% wrong, drift growing with
length), so the system computes the span deterministically by locating the quote
in the canonical text.

Grounding gate (v2 contract #4 — hard gate, no repair):
    the quote must be an EXACT verbatim substring of canonical_text. The span is
    located by `src.preprocessing.locate_quote` (first free occurrence when the
    phrase repeats). A non-verbatim quote is DROPPED; the drop is classified
    (normalized_ws / case / ellipsis_stitch / unmatched) and exposed in
    `last_drops` for the reasoning log. No realignment, no fuzzy acceptance.

Pattern: instructor + Pydantic + tenacity retry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import EQDConfig, ModelClient
from src.core.reasoning_log import ReasoningLogger
from src.core.db import Database, InitialCodeRepo
from src.core.models import ICCandidate, RawICCandidate, Segment, SegmentCodingResult
from src.preprocessing.grounding import DropClass, QuoteMatch, locate_quote
from src.extraction.prompts import (
    build_codebook_context,
    build_coder_system_prompt,
    build_coder_user_prompt,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GroundingDrop:
    """One candidate dropped by the grounding gate (full quote for the audit log)."""
    ic_name: str
    quote_text: str
    drop_class: DropClass


def ground_candidate(
    raw: RawICCandidate,
    canonical: str,
    claimed_spans: Sequence[Tuple[int, int]] = (),
) -> Tuple[Optional[ICCandidate], QuoteMatch]:
    """
    Ground a raw candidate against canonical text (shared by pass 1 and pass 2).

    Returns (candidate, match). candidate is None when the quote is not an exact
    substring; match.drop_class then says why. On success
    canonical[span_start:span_end] == quote_text holds by construction.
    """
    match = locate_quote(raw.quote_text, canonical, claimed_spans)
    if match.span is None:
        return None, match
    start, end = match.span
    return ICCandidate(
        ic_name=raw.ic_name,
        definition=raw.definition,
        quote_text=raw.quote_text,
        span_start=start,
        span_end=end,
        confidence=raw.confidence,
        sentiment=raw.sentiment,
        existing_code_match=raw.existing_code_match,
        n_occurrences=match.n_occurrences,
        occurrence_resolution=match.resolution,
    ), match


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
        # Full drop records from the most recent process_batch() call (for the
        # reasoning log + drop-class metrics). Keyed by segment_id.
        self.last_drops: Dict[str, List[GroundingDrop]] = {}

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
        self.last_drops = {}

        for idx, segment in enumerate(segments, 1):
            logger.info(f"[CODER] Segment {idx}/{len(segments)}: {segment.id}")
            candidates, drops = self._code_segment(segment, codebook_context)
            results[segment.id] = candidates
            self.last_drops[segment.id] = drops
            self.last_drop_counts[segment.id] = len(drops)

        return results

    def _code_segment(
        self,
        segment: Segment,
        codebook_context: str,
    ) -> Tuple[List[ICCandidate], List[GroundingDrop]]:
        """
        Process a single segment through the Coder Agent LLM.

        1. Build prompts
        2. Call LLM via instructor → SegmentCodingResult (RawICCandidate list)
        3. Ground each quote: find it verbatim in canonical_text → compute span
        4. Drop candidates whose quote is not a verbatim substring (hallucination)

        Returns (grounded_candidates, drops).
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
            return [], []

        # Grounding gate — locate each quote verbatim; drop (and classify) the rest.
        # Earlier accepted spans are "claimed" so a repeated phrase quoted by two
        # candidates lands on two different occurrences.
        grounded: List[ICCandidate] = []
        drops: List[GroundingDrop] = []
        claimed: List[Tuple[int, int]] = []
        for raw in result.candidates:
            candidate, match = ground_candidate(raw, segment.canonical_text, claimed)
            if candidate is None:
                drops.append(GroundingDrop(raw.ic_name, raw.quote_text, match.drop_class))
                logger.warning(
                    f"[HALLUCINATION] Dropped candidate '{raw.ic_name}' "
                    f"({match.drop_class.value}) — quote not found verbatim in "
                    f"segment {segment.id}. Quote: '{raw.quote_text[:60]}…'"
                )
                continue
            grounded.append(candidate)
            claimed.append((candidate.span_start, candidate.span_end))

        logger.info(
            f"Segment {segment.id}: {len(result.candidates)} candidates → "
            f"{len(grounded)} grounded ({len(drops)} hallucinated)"
        )
        return grounded, drops

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
