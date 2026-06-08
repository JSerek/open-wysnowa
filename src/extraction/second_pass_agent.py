"""
EQD-AI Layer 1: Second-Pass Agent (v2 — omitted-text audit).

After pass 1 codes a review, this agent re-examines what was left behind. It is
shown the whole review with every un-extracted fragment wrapped in
`<omitted>...</omitted>` (built by `omitted.build_omitted_view`) and, for each
fragment, classifies the omission (deliberate vs accidental) and may recover
evidence the first pass missed.

Contract:
  - Same generative slot as the coder (contract #3/#9): uses the `coder_agent`
    model config. Pass 2 of a review sees the codebook state AFTER that review's
    own pass 1 (contract #2) — the codebook context is fetched fresh here.
  - One API call per review. response_model=SecondPassResult.
  - Recovered evidence reuses RawICCandidate (no offsets). Grounding (span via
    find) + the DEDUP-overlap gate + the shared decision track happen in the
    orchestrator, exactly as for pass 1 — this agent only produces the raw audit.

Pattern: instructor + Pydantic + tenacity retry (mirrors CoderAgent).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import EQDConfig, ModelClient
from src.core.db import Database, InitialCodeRepo
from src.core.models import Segment, SecondPassResult
from src.core.reasoning_log import ReasoningLogger
from src.extraction.omitted import build_omitted_view
from src.extraction.prompts import (
    build_codebook_context,
    build_second_pass_system_prompt,
    build_second_pass_user_prompt,
)

logger = logging.getLogger(__name__)


class SecondPassAgent:
    """
    Audits the un-extracted portion of a review and recovers missed evidence.

    Input: one Segment (the review) + the accepted pass-1 quote spans.
    Output: SecondPassResult — one assessment per `<omitted>` fragment.

    The same generative slot as the coder is used (contract #3/#9). The codebook
    context is read fresh per call so pass 2 sees the post-pass-1 state.
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

    def assess_omitted(
        self,
        segment: Segment,
        pass1_spans: List[Tuple[int, int]],
    ) -> SecondPassResult:
        """
        Run the omitted-text audit for one review.

        1. Build the omitted-view from the accepted pass-1 spans.
        2. Read the current codebook (post-pass-1 state) for context.
        3. One instructor call → SecondPassResult.

        On LLM failure (after retries) returns an empty SecondPassResult so the
        pipeline degrades gracefully (DESIGN_PRINCIPLES #7 — logged, not silent).
        """
        omitted_view = build_omitted_view(segment.canonical_text, pass1_spans)

        # If nothing was omitted, there is nothing to audit — skip the call.
        if "<omitted>" not in omitted_view:
            logger.info(
                f"[PASS2] Segment {segment.id}: full pass-1 coverage — no omitted text"
            )
            return SecondPassResult(segment_id=segment.id, fragments=[])

        # Fresh codebook context — reflects this review's own pass-1 contributions.
        codebook = InitialCodeRepo(self.db).get_all_active()
        codebook_context = build_codebook_context(codebook)

        system_prompt = build_second_pass_system_prompt(codebook_context)
        user_prompt = build_second_pass_user_prompt(segment.id, omitted_view)

        client, model_id, params = self.model_client.get_client("coder_agent")

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
                f"[PASS2] Second-pass agent failed for segment {segment.id} "
                f"after retries: {e}"
            )
            return SecondPassResult(segment_id=segment.id, fragments=[])

        # Normalise segment_id (models sometimes echo a different value).
        result.segment_id = segment.id
        logger.info(
            f"[PASS2] Segment {segment.id}: {len(result.fragments)} omitted "
            f"fragment(s) assessed"
        )
        return result

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
    ) -> SecondPassResult:
        """
        Instructor-patched LLM call for the omitted-text audit.

        Returns SecondPassResult (validated by Pydantic).
        Uses create_with_completion() to capture reasoning traces when available.
        """
        extra_body = self.model_client.build_extra_body("coder_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=SecondPassResult,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("second_pass_agent", model_id, raw)
        return parsed
