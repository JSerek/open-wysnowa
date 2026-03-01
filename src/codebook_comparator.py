"""
EQD-AI Layer 1: Codebook Comparator.

Evaluates new IC candidates against the existing codebook.
Pipeline: embed candidate → find top-K similar → LLM reasoning → recommendation.

The Comparator never sees the full segment — only the IC candidate + top-K.
This forces focused comparison rather than re-coding the text.

Model config: codebook_comparator (temp 0.1 — lowest for consistency).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import EQDConfig, ModelClient
from src.reasoning_log import ReasoningLogger
from src.db import Database, InitialCodeRepo
from src.embeddings import EmbeddingService, SimilarityResult
from src.models import (
    ComparatorOutput,
    ComparatorRecommendation,
    ICCandidate,
)
from src.prompts import build_comparator_system_prompt, build_comparator_user_prompt

logger = logging.getLogger(__name__)


class CodebookComparator:
    """
    Evaluates new IC candidates for codebook inclusion.

    Four-step process (per architecture doc Section 5.3):
    1. EMBED: Compute embedding for new IC candidate
    2. SIMILARITY: Find top-K similar active ICs
    3. LLM REASONING: Compare and recommend (NEW/MERGE/REJECT)
    4. Return recommendation for HIL review

    Steps 1-3 happen here. Step 4 (HIL) is in hil.py.
    """

    def __init__(
        self,
        model_client: ModelClient,
        embedding_service: EmbeddingService,
        db: Database,
        config: EQDConfig,
        reasoning_logger: Optional["ReasoningLogger"] = None,
    ):
        self.model_client = model_client
        self.embedding_service = embedding_service
        self.db = db
        self.config = config
        self.top_k = config.processing.similarity_prefilter_k
        self.reasoning_logger = reasoning_logger

    def evaluate(
        self,
        candidate: ICCandidate,
        precomputed_embedding: Optional[List[float]] = None,
    ) -> Tuple[ComparatorOutput, List[SimilarityResult], Dict[str, Any]]:
        """
        Evaluate a new IC candidate against the existing codebook.

        Returns: (ComparatorOutput, top_k_similar_results, triage_meta)
            triage_meta: {
                "triage_path": "empty_codebook" | "auto_new" | "auto_merge" | "grey_zone",
                "max_sim": float | None,
                "llm_recommendation": str | None,  # only for grey_zone
            }

        If precomputed_embedding is provided, skip the embed step (batch
        optimization — orchestrator pre-embeds all candidates in one call).

        If the codebook is empty (first batch), returns NEW immediately
        without calling the LLM — no comparison possible.
        """
        # 1. Embed candidate (skip if pre-computed)
        if precomputed_embedding is not None:
            candidate_embedding = precomputed_embedding
        else:
            candidate_text = f"{candidate.ic_name} | {candidate.definition}"
            candidate_embedding = self.embedding_service.embed_text(candidate_text)

        # 2. Find top-K similar existing ICs
        top_k_results = self.embedding_service.find_similar_ics(
            embedding=candidate_embedding,
            top_k=self.top_k,
        )

        # 3. Empty codebook → immediate NEW (no LLM call needed)
        if not top_k_results:
            logger.debug(f"[TRIAGE] Codebook empty — '{candidate.ic_name}' → NEW")
            output = ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning="Codebook is empty; this is the first code.",
            )
            meta = {"triage_path": "empty_codebook", "max_sim": None, "llm_recommendation": None}
            return output, top_k_results, meta

        # 4. Embedding-first triage — skip LLM for clear-cut cases
        max_sim = top_k_results[0].similarity
        auto_new_thresh = self.config.processing.auto_new_threshold
        auto_merge_thresh = self.config.processing.auto_merge_threshold

        if max_sim < auto_new_thresh:
            logger.info(
                f"[TRIAGE] Auto-NEW: '{candidate.ic_name}' "
                f"(max_sim={max_sim:.3f} < {auto_new_thresh})"
            )
            output = ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning=(
                    f"Auto-triage: similarity to nearest code too low "
                    f"({max_sim:.3f} < {auto_new_thresh}); clearly novel."
                ),
            )
            meta = {"triage_path": "auto_new", "max_sim": max_sim, "llm_recommendation": None}
            return output, top_k_results, meta

        if max_sim > auto_merge_thresh:
            merge_target = top_k_results[0]
            logger.info(
                f"[TRIAGE] Auto-MERGE: '{candidate.ic_name}' → '{merge_target.ic_name}' "
                f"(max_sim={max_sim:.3f} > {auto_merge_thresh})"
            )
            output = ComparatorOutput(
                recommendation=ComparatorRecommendation.MERGE,
                merge_target_name=merge_target.ic_name,
                reasoning=(
                    f"Auto-triage: similarity to '{merge_target.ic_name}' very high "
                    f"({max_sim:.3f} > {auto_merge_thresh}); semantically equivalent."
                ),
            )
            meta = {"triage_path": "auto_merge", "max_sim": max_sim, "llm_recommendation": None}
            return output, top_k_results, meta

        # 5. Grey zone — call LLM for nuanced reasoning
        logger.info(
            f"[TRIAGE] Grey zone: '{candidate.ic_name}' "
            f"(max_sim={max_sim:.3f}) → LLM comparator"
        )

        ic_repo = InitialCodeRepo(self.db)
        top_k_with_defs: List[Tuple[str, str, str, float]] = []
        for result in top_k_results:
            ic = ic_repo.get_by_id(result.ic_id)
            if ic:
                top_k_with_defs.append(
                    (result.ic_id, result.ic_name, ic.definition, result.similarity)
                )

        try:
            output = self._get_llm_recommendation(
                candidate=candidate,
                top_k_with_defs=top_k_with_defs,
            )
        except Exception as e:
            logger.error(f"[ERROR] Comparator LLM failed for '{candidate.ic_name}': {e}")
            output = ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning=f"LLM comparison failed ({e}); defaulting to NEW for human review.",
            )

        meta = {
            "triage_path": "grey_zone",
            "max_sim": max_sim,
            "llm_recommendation": output.recommendation.value,
        }
        return output, top_k_results, meta

    def _get_llm_recommendation(
        self,
        candidate: ICCandidate,
        top_k_with_defs: List[Tuple[str, str, str, float]],
    ) -> ComparatorOutput:
        """
        Call the Codebook Comparator LLM to reason about the candidate.

        Uses instructor for structured output → ComparatorOutput.
        """
        system_prompt = build_comparator_system_prompt()
        user_prompt = build_comparator_user_prompt(
            candidate_name=candidate.ic_name,
            candidate_definition=candidate.definition,
            candidate_quote=candidate.quote_text,
            top_k=top_k_with_defs,
        )

        client, model_id, params = self.model_client.get_client("codebook_comparator")

        return self._call_llm(
            client=client,
            model_id=model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
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
    ) -> ComparatorOutput:
        """Instructor-patched LLM call with retry.
        Uses create_with_completion() to capture reasoning traces when available.
        """
        extra_body = self.model_client.build_extra_body("codebook_comparator")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=ComparatorOutput,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("codebook_comparator", model_id, raw)
        return parsed
