"""
EQD-AI Layer 1: Orchestrator.

Main batch-processing loop that ties together:
- Coder Agent (extract IC candidates from segments)
- Codebook Comparator (evaluate new candidates vs codebook)
- HIL (human reviews each new candidate)
- Persistence (create/merge/reject ICs, embed, log decisions)
- ITS tracking (detect codebook saturation)

Entry point: Layer1Orchestrator.run(segments)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from src.coder_agent import CoderAgent
from src.codebook_comparator import CodebookComparator
from src.config import EQDConfig, ModelClient
from src.db import (
    Database,
    DecisionLogRepo,
    InitialCodeRepo,
    SegmentRepo,
    VerbatimQuoteRepo,
)
from src.embeddings import EmbeddingService, SimilarityResult
from src.hil import (
    display_batch_header,
    display_batch_summary,
    display_candidate_review,
    display_its_status,
    display_meta_commentary_warning,
    prompt_decision,
    prompt_edit_candidate,
    prompt_saturation_checkpoint,
)
from src.models import (
    BatchITS,
    ComparatorOutput,
    ComparatorRecommendation,
    DecisionLog,
    DecisionType,
    ICCandidate,
    ICStatus,
    InitialCode,
    RefinedICOutput,
    SaturationPoint,
    Segment,
    VerbatimQuote,
)
from src.prompts import build_ic_refinement_prompt
from src.preprocessing import batch_segments

logger = logging.getLogger(__name__)


# ── Meta-IC Filtering ────────────────────────────────────────────────────────


def is_meta_commentary(
    candidate: ICCandidate,
    name_patterns: List[str],
    definition_signals: List[str],
) -> Tuple[bool, str]:
    """
    Lightweight heuristic: does this IC describe a meta-level verdict
    rather than a specific product experience?

    Patterns are loaded from eqd_config.yaml → processing.meta_ic_filter.
    Empty lists = no heuristic filtering (prompt rule #9 is the primary defense).

    Returns (is_meta, reason). No LLM calls.
    """
    name_lower = candidate.ic_name.lower()
    def_lower = candidate.definition.lower()

    for pattern in name_patterns:
        if pattern in name_lower:
            return True, f"name_pattern:{pattern}"

    for signal in definition_signals:
        if signal in def_lower:
            return True, f"definition_signal:{signal}"

    return False, ""


# ── ITS Tracker ──────────────────────────────────────────────────────────────

class ITSTracker:
    """
    Tracks Incremental Type Saturation across batches, plus a cumulative
    IC discovery curve per segment.

    ITS = new_ics_created / ics_before_batch
    Saturation: ITS < threshold for N consecutive batches.

    Cumulative curve: for each segment processed, what fraction of the
    final codebook has been discovered so far.  Plottable as x=segment_index,
    y=fraction (resembles a CDF — steep at start, flattens as saturation).
    """

    def __init__(self, threshold: float, consecutive_needed: int):
        self.threshold = threshold
        self.consecutive_needed = consecutive_needed
        self.history: List[BatchITS] = []
        self._consecutive_low: int = 0

        # Cumulative saturation tracking
        self._segment_index: int = 0  # running counter across all batches
        self._new_ics_per_segment: Dict[int, int] = {}  # seg_index → # new ICs

    def record_batch(
        self, batch_number: int, ics_before: int, new_ics_created: int
    ) -> BatchITS:
        """Record ITS for a batch and check for saturation."""
        if ics_before == 0:
            its_value = 1.0 if new_ics_created > 0 else 0.0
        else:
            its_value = new_ics_created / ics_before

        # Track consecutive low-ITS batches
        if its_value < self.threshold:
            self._consecutive_low += 1
        else:
            self._consecutive_low = 0

        is_checkpoint = self._consecutive_low >= self.consecutive_needed

        batch_its = BatchITS(
            batch_number=batch_number,
            ics_before=ics_before,
            new_ics_created=new_ics_created,
            its_value=its_value,
            consecutive_low=self._consecutive_low,
            is_checkpoint=is_checkpoint,
        )
        self.history.append(batch_its)
        return batch_its

    def record_segment(self, new_ics_count: int = 0) -> int:
        """
        Mark that one segment has been fully processed.

        Args:
            new_ics_count: how many *new* ICs were created from this segment.

        Returns: the segment_index assigned.
        """
        idx = self._segment_index
        self._new_ics_per_segment[idx] = new_ics_count
        self._segment_index += 1
        return idx

    def build_saturation_curve(self) -> List[SaturationPoint]:
        """
        Build the cumulative IC discovery curve after all segments processed.

        Returns a list of SaturationPoint, one per segment, ordered by
        processing order.  fraction = cumulative_ics / total_ics.
        """
        if not self._new_ics_per_segment:
            return []

        total_ics = sum(self._new_ics_per_segment.values())
        if total_ics == 0:
            # No new ICs at all — flat line at 0
            return [
                SaturationPoint(
                    segment_index=i, cumulative_ics=0,
                    total_ics=0, fraction=0.0, new_ics_in_segment=0,
                )
                for i in range(self._segment_index)
            ]

        curve: List[SaturationPoint] = []
        cumulative = 0
        for i in range(self._segment_index):
            new_count = self._new_ics_per_segment.get(i, 0)
            cumulative += new_count
            curve.append(SaturationPoint(
                segment_index=i,
                cumulative_ics=cumulative,
                total_ics=total_ics,
                fraction=cumulative / total_ics,
                new_ics_in_segment=new_count,
            ))

        return curve


# ── Orchestrator ─────────────────────────────────────────────────────────────

class Layer1Orchestrator:
    """
    Main entry point for Layer 1 processing.

    Orchestrates the full pipeline:
    segments → coder agent → comparator → HIL → persistence → ITS tracking
    """

    def __init__(self, model_client: ModelClient, db: Database, config: EQDConfig):
        self.model_client = model_client
        self.db = db
        self.config = config

        # Sub-components
        self.coder_agent = CoderAgent(model_client, db, config)
        self.embedding_service = EmbeddingService(model_client, db)
        self.comparator = CodebookComparator(
            model_client, self.embedding_service, db, config,
        )

        # ITS tracking
        self.its_tracker = ITSTracker(
            threshold=config.processing.its_saturation_threshold,
            consecutive_needed=config.processing.its_consecutive_batches,
        )

        # Repositories
        self.ic_repo = InitialCodeRepo(db)
        self.segment_repo = SegmentRepo(db)
        self.quote_repo = VerbatimQuoteRepo(db)
        self.decision_repo = DecisionLogRepo(db)

        # IC creation tracking: {ic_id → segment_index} for breadth saturation
        self.ic_creation_segments: Dict[str, int] = {}

        # Triage tracking: accumulate per-batch and overall
        self.triage_stats: Dict[str, int] = {
            "auto_new": 0,
            "auto_merge": 0,
            "grey_zone": 0,
            "empty_codebook": 0,
        }
        # Per-batch merge rates: [{batch_num, new_candidates, merges, batch_new}]
        self.batch_merge_rates: List[Dict[str, Any]] = []
        # Grey-zone agreement tracking: [{max_sim, llm_rec, sim_direction}]
        self.grey_zone_decisions: List[Dict[str, Any]] = []

    def run(
        self,
        segments: List[Segment],
        enable_hil: bool = True,
    ) -> Dict[str, Any]:
        """
        Process segments through the full Layer 1 pipeline.

        Args:
            segments: preprocessed Segment objects to code
            enable_hil: if True, prompt human for each new IC (default True)

        Returns:
            Summary dict with statistics.
        """
        batch_size = self.config.processing.batch_size
        total_batches = math.ceil(len(segments) / batch_size) if segments else 0

        summary: Dict[str, Any] = {
            "total_segments": len(segments),
            "total_batches": total_batches,
            "batches_processed": 0,
            "total_candidates": 0,
            "existing_matches": 0,
            "new_ics_created": 0,
            "merged": 0,
            "rejected": 0,
            "quit_early": False,
            # Drop rate tracking (candidates failing span validation in coder agent)
            "total_dropped": 0,
            "dropped_per_segment": {},  # {segment_id: n_dropped}
            # Meta-IC filtering
            "meta_filtered": 0,
            "meta_flagged": 0,
        }

        batch_num = 0
        for batch in batch_segments(segments, batch_size):
            batch_num += 1

            # ── 1. Run Coder Agent ────────────────────────────────────────
            logger.info(f"[BATCH] Batch {batch_num}: coding {len(batch)} segments")
            coding_results = self.coder_agent.process_batch(batch)

            # Accumulate drop counts (span validation failures) from this batch
            for seg_id, n_dropped in self.coder_agent.last_drop_counts.items():
                summary["total_dropped"] += n_dropped
                prev = summary["dropped_per_segment"].get(seg_id, 0)
                summary["dropped_per_segment"][seg_id] = prev + n_dropped

            # ── 2. Flatten and categorize candidates ──────────────────────
            # (candidate, segment_id, canonical_text)
            new_candidates: List[Tuple[ICCandidate, str, str]] = []
            existing_matches: List[Tuple[ICCandidate, str, str]] = []

            # Track saturation: assign a segment_index to each segment
            segment_indices: Dict[str, int] = {}
            for segment in batch:
                segment_indices[segment.id] = self.its_tracker.record_segment()

            for segment in batch:
                candidates = coding_results.get(segment.id, [])
                summary["total_candidates"] += len(candidates)

                for cand in candidates:
                    if cand.existing_code_match is not None:
                        existing_matches.append((cand, segment.id, segment.canonical_text))
                    else:
                        new_candidates.append((cand, segment.id, segment.canonical_text))

            # ── 3. Handle existing matches (skip comparator) ─────────────
            # Collect quotes for batch embedding later
            deferred_quotes: List[VerbatimQuote] = []

            for cand, seg_id, _ in existing_matches:
                quote = self._apply_existing_match(cand, seg_id, defer_embed=True)
                if quote:
                    deferred_quotes.append(quote)
                summary["existing_matches"] += 1

            # ── 4. Pre-embed all new candidate texts (1 batch API call) ──
            batch_new_count = 0
            precomputed_embeddings: List[List[float]] = []

            if new_candidates:
                candidate_texts = [
                    f"{c.ic_name} | {c.definition}" for c, _, _ in new_candidates
                ]
                logger.debug(
                    f"[EMBED] Batch-embedding {len(candidate_texts)} candidate texts"
                )
                precomputed_embeddings = self.embedding_service.embed_texts_batch(
                    candidate_texts
                )

            # ── 5. Process new candidates through comparator + HIL ────────
            if enable_hil and new_candidates:
                display_batch_header(
                    batch_num, total_batches,
                    self.ic_repo.count_active(), len(new_candidates),
                )

            batch_merge_count = 0

            for idx, (cand, seg_id, seg_text) in enumerate(new_candidates, 1):
                # 5a. Run Codebook Comparator with precomputed embedding
                cand_embedding = precomputed_embeddings[idx - 1] if precomputed_embeddings else None
                comp_output, top_k, triage_meta = self.comparator.evaluate(
                    cand, precomputed_embedding=cand_embedding
                )

                # Track triage path
                triage_path = triage_meta.get("triage_path", "unknown")
                if triage_path in self.triage_stats:
                    self.triage_stats[triage_path] += 1

                # Track grey-zone decisions for comparator agreement metric
                if triage_path == "grey_zone":
                    max_sim = triage_meta.get("max_sim", 0)
                    llm_rec = triage_meta.get("llm_recommendation", "")
                    # Similarity direction: if max_sim > midpoint → embedding says MERGE
                    midpoint = (
                        self.config.processing.auto_new_threshold +
                        self.config.processing.auto_merge_threshold
                    ) / 2
                    sim_direction = "MERGE" if max_sim > midpoint else "NEW"
                    self.grey_zone_decisions.append({
                        "max_sim": max_sim,
                        "llm_recommendation": llm_rec,
                        "sim_direction": sim_direction,
                    })

                # ── Meta-IC filtering ─────────────────────────────────────
                meta_cfg = self.config.processing.meta_ic_filter
                is_meta = False
                meta_reason = ""
                if meta_cfg.enabled:
                    is_meta, meta_reason = is_meta_commentary(
                        cand,
                        name_patterns=meta_cfg.name_patterns,
                        definition_signals=meta_cfg.definition_signals,
                    )
                if is_meta:
                    if not enable_hil:
                        # Auto-reject
                        self._apply_reject(cand, comp_output, f"meta-commentary-filtered: {meta_reason}")
                        summary["meta_filtered"] += 1
                        summary["rejected"] += 1
                        logger.info(f"[META-FILTER] Auto-rejected '{cand.ic_name}' ({meta_reason})")
                        continue  # skip to next candidate
                    else:
                        # Flag for human — display warning, then proceed to normal HIL
                        display_meta_commentary_warning(cand, meta_reason)
                        summary["meta_flagged"] += 1

                if enable_hil:
                    # 5b. Display for human review
                    display_candidate_review(
                        cand, comp_output, top_k, seg_text,
                        idx, len(new_candidates),
                    )

                    # 5c. Get human decision (may loop for edit)
                    action, target_idx, notes = self._hil_loop(cand, comp_output, top_k, seg_text, idx, len(new_candidates))

                    if action == "Q":
                        summary["quit_early"] = True
                        break
                else:
                    # Auto-accept LLM recommendation
                    action = comp_output.recommendation.value[0]  # N, M, S, R → first char
                    target_idx = 1 if action in ("M", "S") and top_k else None
                    notes = "auto-accepted (HIL disabled)"

                # 5d. Apply decision (IC embed + persist happens immediately
                #     for NEW so next candidate's comparator sees it;
                #     quote embed is deferred)
                result, quote, new_ic_id = self._apply_decision(
                    action=action,
                    candidate=cand,
                    segment_id=seg_id,
                    comp_output=comp_output,
                    top_k=top_k,
                    target_idx=target_idx,
                    notes=notes,
                    defer_quote_embed=True,
                )

                if quote:
                    deferred_quotes.append(quote)

                if result == "new":
                    summary["new_ics_created"] += 1
                    batch_new_count += 1
                    # Track cumulative saturation: which segment introduced this IC
                    seg_idx = segment_indices.get(seg_id)
                    if seg_idx is not None:
                        prev = self.its_tracker._new_ics_per_segment.get(seg_idx, 0)
                        self.its_tracker._new_ics_per_segment[seg_idx] = prev + 1
                    # Track IC creation segment for meaning saturation breadth
                    if new_ic_id and seg_idx is not None:
                        self.ic_creation_segments[new_ic_id] = seg_idx
                elif result == "merge":
                    summary["merged"] += 1
                    batch_merge_count += 1
                elif result == "reject":
                    summary["rejected"] += 1

            # Record per-batch merge rate
            self.batch_merge_rates.append({
                "batch_num": batch_num,
                "new_candidates": len(new_candidates),
                "merges": batch_merge_count,
                "batch_new": batch_new_count,
            })

            # ── 6. Batch-embed all deferred quotes (1 API call) ──────────
            if deferred_quotes:
                logger.debug(f"[EMBED] Batch-embedding {len(deferred_quotes)} quotes")
                self.embedding_service.batch_embed_quotes(deferred_quotes)
                # Update DB with embeddings
                for quote in deferred_quotes:
                    self.quote_repo.update_embedding(quote)

            if summary["quit_early"]:
                logger.info(f"Human quit at batch {batch_num}")
                break

            # ── 7. Track ITS ──────────────────────────────────────────────
            ics_before = self.ic_repo.count_active()
            batch_its = self.its_tracker.record_batch(
                batch_num, ics_before, batch_new_count,
            )

            if enable_hil:
                display_batch_summary(
                    batch_num, batch_new_count,
                    summary["merged"], summary["rejected"],
                )
                display_its_status(batch_its)

            # ── 8. Saturation checkpoint ──────────────────────────────────
            if batch_its.is_checkpoint and enable_hil:
                should_continue = prompt_saturation_checkpoint()
                if not should_continue:
                    logger.info("Human stopped at saturation checkpoint")
                    summary["quit_early"] = True
                    break

            summary["batches_processed"] += 1

        # ── 9. IC Definition Refinement ──────────────────────────────────
        # Refine definitions for ICs that received 3+ merges (definition drift)
        refined_count = self._refine_ic_definitions()
        summary["ics_refined"] = refined_count

        # Build cumulative saturation curve
        summary["saturation_curve"] = self.its_tracker.build_saturation_curve()

        # Expose IC creation tracking for meaning saturation breadth
        summary["ic_creation_segments"] = self.ic_creation_segments
        summary["total_segments"] = len(segments)

        # Expose triage and comparator tracking for new metrics
        summary["triage_stats"] = dict(self.triage_stats)
        summary["batch_merge_rates"] = list(self.batch_merge_rates)
        summary["grey_zone_decisions"] = list(self.grey_zone_decisions)

        # IC stability scores from refinement
        summary["ic_stability_scores"] = getattr(self, "_ic_stability_scores", [])

        return summary

    # ── HIL Interaction Loop ─────────────────────────────────────────────────

    def _hil_loop(
        self,
        candidate: ICCandidate,
        comp_output: ComparatorOutput,
        top_k: List[SimilarityResult],
        seg_text: str,
        candidate_num: int,
        total_candidates: int,
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """
        HIL loop that handles the Edit action (re-display after edit).

        Returns: (action, target_idx, notes)
        """
        current_candidate = candidate

        while True:
            action, target_idx, notes = prompt_decision(top_k)

            if action == "E":
                current_candidate = prompt_edit_candidate(current_candidate)
                # Re-display the edited candidate
                display_candidate_review(
                    current_candidate, comp_output, top_k, seg_text,
                    candidate_num, total_candidates,
                )
                continue  # Loop back for a decision on the edited version

            return action, target_idx, notes

    # ── Decision Application ─────────────────────────────────────────────────

    def _apply_decision(
        self,
        action: str,
        candidate: ICCandidate,
        segment_id: str,
        comp_output: ComparatorOutput,
        top_k: List[SimilarityResult],
        target_idx: Optional[int],
        notes: Optional[str],
        defer_quote_embed: bool = False,
    ) -> Tuple[str, Optional[VerbatimQuote]]:
        """
        Apply a decision (N/M/S/R) and persist results.

        Args:
            defer_quote_embed: if True, create quote without embedding
                (caller will batch-embed later). IC embedding still happens
                immediately for NEW so subsequent comparator calls see it.

        Returns: (result_type, quote_or_none, new_ic_id_or_none)
            result_type: "new", "merge", or "reject"
            quote_or_none: VerbatimQuote needing deferred embedding, or None
            new_ic_id_or_none: IC id if action was NEW, else None
        """
        if action == "N":
            ic, quote = self._apply_new(
                candidate, segment_id, comp_output, notes,
                defer_quote_embed=defer_quote_embed,
            )
            return "new", quote, ic.id

        elif action in ("M", "S") and target_idx and top_k:
            target = top_k[target_idx - 1]  # 1-indexed
            quote = self._apply_merge(
                candidate, segment_id, target.ic_id, comp_output, notes,
                defer_quote_embed=defer_quote_embed,
            )
            return "merge", quote, None

        elif action == "R":
            self._apply_reject(candidate, comp_output, notes)
            return "reject", None, None

        else:
            logger.warning(f"Unknown action '{action}' — treating as reject")
            self._apply_reject(candidate, comp_output, notes)
            return "reject", None, None

    def _apply_new(
        self,
        candidate: ICCandidate,
        segment_id: str,
        comp_output: ComparatorOutput,
        notes: Optional[str],
        defer_quote_embed: bool = False,
    ) -> Tuple[InitialCode, Optional[VerbatimQuote]]:
        """
        Create a new IC from candidate: embed IC → persist IC → persist quote → log.

        IC embedding always happens immediately (so subsequent comparator calls
        can find it). Quote embedding is deferred if defer_quote_embed=True.

        Returns: (ic, quote_needing_embed_or_none)
        """
        # Create IC
        ic = InitialCode(
            name=candidate.ic_name,
            definition=candidate.definition,
            status=ICStatus.ACTIVE,
        )

        # Embed IC (embed-on-write) — always immediate
        ic = self.embedding_service.embed_ic(ic)

        # Persist IC
        self.ic_repo.insert(ic)

        # Create verbatim quote (propagate sentiment from candidate)
        quote = VerbatimQuote(
            ic_id=ic.id,
            segment_id=segment_id,
            quote_text=candidate.quote_text,
            span_start=candidate.span_start,
            span_end=candidate.span_end,
            sentiment=candidate.sentiment.value if hasattr(candidate, 'sentiment') and candidate.sentiment else None,
        )

        # Verify quote against canonical text
        segment = self.segment_repo.get_by_id(segment_id)
        if segment:
            quote.verify(segment.canonical_text)

        if defer_quote_embed:
            # Insert without embedding — caller will batch-embed later
            self.quote_repo.insert(quote)
        else:
            # Embed quote immediately (original behavior)
            quote = self.embedding_service.embed_quote(quote)
            self.quote_repo.insert(quote)

        # Log decision
        self.decision_repo.insert(DecisionLog(
            decision_type=DecisionType.CODEBOOK_UPDATE,
            ic_id=ic.id,
            llm_recommendation=comp_output.recommendation.value,
            human_action="CREATE",
            similarity_score=None,
            notes=notes,
            context={"candidate_name": candidate.ic_name},
        ))

        logger.info(f"[IC:NEW] {ic.name}")
        return ic, (quote if defer_quote_embed else None)

    def _apply_merge(
        self,
        candidate: ICCandidate,
        segment_id: str,
        target_ic_id: str,
        comp_output: ComparatorOutput,
        notes: Optional[str],
        defer_quote_embed: bool = False,
    ) -> Optional[VerbatimQuote]:
        """
        Merge candidate into existing IC: add quote → log.

        Returns: quote needing deferred embedding, or None.
        """
        target_ic = self.ic_repo.get_by_id(target_ic_id)
        if not target_ic:
            logger.error(f"Merge target {target_ic_id} not found — treating as reject")
            self._apply_reject(candidate, comp_output, notes)
            return None

        # Create verbatim quote for the existing IC (propagate sentiment)
        quote = VerbatimQuote(
            ic_id=target_ic.id,
            segment_id=segment_id,
            quote_text=candidate.quote_text,
            span_start=candidate.span_start,
            span_end=candidate.span_end,
            sentiment=candidate.sentiment.value if hasattr(candidate, 'sentiment') and candidate.sentiment else None,
        )

        segment = self.segment_repo.get_by_id(segment_id)
        if segment:
            quote.verify(segment.canonical_text)

        if defer_quote_embed:
            self.quote_repo.insert(quote)
        else:
            quote = self.embedding_service.embed_quote(quote)
            self.quote_repo.insert(quote)

        # Log decision
        self.decision_repo.insert(DecisionLog(
            decision_type=DecisionType.CODEBOOK_UPDATE,
            ic_id=target_ic.id,
            llm_recommendation=comp_output.recommendation.value,
            human_action="MERGE",
            notes=notes,
            context={
                "candidate_name": candidate.ic_name,
                "merged_into": target_ic.name,
            },
        ))

        logger.info(f"[IC:MERGE] '{candidate.ic_name}' → '{target_ic.name}'")
        return quote if defer_quote_embed else None

    def _apply_reject(
        self,
        candidate: ICCandidate,
        comp_output: ComparatorOutput,
        notes: Optional[str],
    ) -> None:
        """Reject candidate: log only, no IC created."""
        self.decision_repo.insert(DecisionLog(
            decision_type=DecisionType.CODEBOOK_UPDATE,
            ic_id=None,
            llm_recommendation=comp_output.recommendation.value,
            human_action="REJECT",
            notes=notes,
            context={"candidate_name": candidate.ic_name},
        ))

        logger.info(f"[IC:REJECT] {candidate.ic_name}")

    def _apply_existing_match(
        self,
        candidate: ICCandidate,
        segment_id: str,
        defer_embed: bool = False,
    ) -> Optional[VerbatimQuote]:
        """
        Handle a candidate that the Coder Agent matched to an existing IC.

        Skips the comparator entirely — just adds the verbatim quote.

        Returns: quote needing deferred embedding, or None.
        """
        # Find the existing IC by name.
        # The coder occasionally returns matches with a number prefix and/or
        # brackets, e.g. "24. [parkour_system_buggy_and_lacks_momentum]" or
        # "6. graphics_positive_assessment". Strip these before looking up.
        import re as _re
        raw_match = candidate.existing_code_match or ""
        clean_match = _re.sub(r"^\d+\.\s*", "", raw_match).strip().strip("[]")

        codebook = self.ic_repo.get_all_active()
        target_ic = None
        for ic in codebook:
            if ic.name == clean_match:
                target_ic = ic
                break

        if not target_ic:
            logger.warning(
                f"Coder Agent matched '{candidate.ic_name}' to "
                f"'{raw_match}' (cleaned: '{clean_match}') but IC not found in codebook. "
                f"Skipping."
            )
            return None

        # Create verbatim quote (propagate sentiment)
        quote = VerbatimQuote(
            ic_id=target_ic.id,
            segment_id=segment_id,
            quote_text=candidate.quote_text,
            span_start=candidate.span_start,
            span_end=candidate.span_end,
            sentiment=candidate.sentiment.value if hasattr(candidate, 'sentiment') and candidate.sentiment else None,
        )

        segment = self.segment_repo.get_by_id(segment_id)
        if segment:
            quote.verify(segment.canonical_text)

        if defer_embed:
            self.quote_repo.insert(quote)
        else:
            quote = self.embedding_service.embed_quote(quote)
            self.quote_repo.insert(quote)

        logger.debug(
            f"[IC:QUOTE] +quote to '{target_ic.name}' from seg {segment_id[:8]}"
        )
        return quote if defer_embed else None

    # ── IC Definition Refinement ──────────────────────────────────────────────

    def _refine_ic_definitions(self, min_quotes: int = 2) -> int:
        """
        Refine definitions for ICs that accumulated merges.

        After all segments are processed, ICs with >= min_quotes quotes
        may have definitions that no longer reflect their full evidence.
        For each, one LLM call synthesises a refined definition, then
        the IC is re-embedded.

        Args:
            min_quotes: minimum quote count to trigger refinement (default 2,
                        meaning the IC was created + received 1+ merges)

        Returns: number of ICs refined.
        """
        codebook = self.ic_repo.get_all_active()
        candidates = []

        for ic in codebook:
            quotes = self.quote_repo.get_all_for_ic(ic.id)
            if len(quotes) >= min_quotes:
                candidates.append((ic, quotes))

        if not candidates:
            logger.info(f"[IC:REFINE] No ICs with {min_quotes}+ quotes — skipping")
            return 0

        logger.info(
            f"[IC:REFINE] Refining {len(candidates)} ICs with {min_quotes}+ quotes"
        )

        # Get LLM client (reuse coder_agent config — cheap, fast)
        agent_name = (
            "coder_agent"
            if "coder_agent" in self.config.agents
            else "codebook_comparator"
        )
        client, model_id, params = self.model_client.get_client(agent_name)

        refined_count = 0
        stability_scores: List[Dict[str, Any]] = []

        for ic, quotes in candidates:
            quote_texts = [q.quote_text for q in quotes]
            merge_count = len(quotes) - 1  # first quote is from creation

            prompt = build_ic_refinement_prompt(
                ic_name=ic.name,
                original_definition=ic.definition,
                merge_count=merge_count,
                quote_texts=quote_texts,
            )

            try:
                # Capture pre-refinement embedding for stability measurement
                old_embedding = ic.embedding_json

                result = client.chat.completions.create(
                    model=model_id,
                    response_model=RefinedICOutput,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=800,
                )

                old_def = ic.definition
                ic.definition = result.refined_definition

                # Re-embed with updated definition
                ic = self.embedding_service.embed_ic(ic)

                # Compute stability score (cosine similarity between old and new embedding)
                if old_embedding and ic.embedding_json:
                    from src.embeddings import cosine_similarity as _cos_sim
                    stability = _cos_sim(old_embedding, ic.embedding_json)
                    stability_scores.append({
                        "ic_name": ic.name,
                        "stability": round(stability, 4),
                    })

                # Persist
                self.ic_repo.update(ic)
                refined_count += 1

                logger.info(
                    f"[IC:REFINE] '{ic.name}': {result.change_summary}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to refine IC '{ic.name}': {e} — keeping original"
                )

        logger.info(f"[IC:REFINE] Complete: {refined_count}/{len(candidates)} refined")

        # Store stability scores on the orchestrator for later retrieval
        self._ic_stability_scores = stability_scores

        return refined_count
