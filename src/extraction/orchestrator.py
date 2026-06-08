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

from src.extraction.coder_agent import CoderAgent
from src.extraction.codebook_comparator import CodebookComparator
from src.extraction.second_pass_agent import SecondPassAgent
from src.core.config import EQDConfig, ModelClient
from src.core.reasoning_log import ReasoningLogger
from src.core.db import (
    Database,
    DecisionLogRepo,
    InitialCodeRepo,
    SegmentRepo,
    VerbatimQuoteRepo,
)
from src.core.embeddings import EmbeddingService, SimilarityResult
from src.extraction.hil import (
    CONTEXT_WINDOW,
    display_batch_header,
    display_batch_summary,
    display_candidate_review,
    display_its_status,
    prompt_decision,
    prompt_edit_candidate,
    prompt_saturation_checkpoint,
)
from src.core.models import (
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
from src.extraction.prompts import build_ic_refinement_prompt
from src.preprocessing import batch_segments

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        model_client: ModelClient,
        db: Database,
        config: EQDConfig,
        reasoning_logger: Optional["ReasoningLogger"] = None,
        eval_mode: bool = False,
    ):
        self.model_client = model_client
        self.db = db
        self.config = config
        self.reasoning_logger = reasoning_logger
        self.eval_mode = eval_mode

        # Sub-components
        self.coder_agent = CoderAgent(model_client, db, config, reasoning_logger)
        self.embedding_service = EmbeddingService(model_client, db)
        self.comparator = CodebookComparator(
            model_client, self.embedding_service, db, config, reasoning_logger,
            eval_mode=eval_mode,
        )
        # Pass-2 (omitted-text audit) agent — same generative slot as the coder.
        self.second_pass_agent = SecondPassAgent(
            model_client, db, config, reasoning_logger,
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

        # Decision-path tracking (v2: empty_codebook shortcut vs LLM judge).
        # No operating thresholds → no auto_new/auto_merge paths anymore.
        self.decision_paths: Dict[str, int] = {
            "empty_codebook": 0,
            "llm": 0,
        }
        # Per-batch merge rates: [{batch_num, new_candidates, merges, batch_new}]
        self.batch_merge_rates: List[Dict[str, Any]] = []

    def run(
        self,
        segments: List[Segment],
        enable_hil: bool = True,
    ) -> Dict[str, Any]:
        """
        Process segments through the full Layer 1 pipeline (v2 two-pass).

        The unit of two-pass processing is the REVIEW (segment): for each review
        we run pass 1 (coder → decision track), snapshot pass-1 density, build the
        omitted-view, run pass 2 (omitted-text audit → recover → DEDUP overlap →
        same decision track), snapshot pass-2 density — then move to the next
        review. ITS / saturation tracking stays per BATCH (groups of reviews).

        Args:
            segments: preprocessed Segment objects to code
            enable_hil: if True, prompt human for each new IC (default True)

        Returns:
            Summary dict with statistics (incl. density_snapshots + pass2_stats).
        """
        batch_size = self.config.processing.batch_size
        total_batches = math.ceil(len(segments) / batch_size) if segments else 0

        summary: Dict[str, Any] = {
            "total_segments": len(segments),
            "total_batches": total_batches,
            "batches_processed": 0,
            "total_candidates": 0,   # pass-1 grounded candidates (drop-rate denom)
            "new_ics_created": 0,
            "merged": 0,
            "rejected": 0,
            "quit_early": False,
            # Span-error tracking (candidates failing the Tier 1 grounding gate)
            "total_dropped": 0,
            "dropped_per_segment": {},  # {segment_id: n_dropped}
            # Coder confidence — collected for new ICs only (not merges or rejects)
            "new_ic_confidences": [],
            # IDs of new ICs whose coder confidence fell below 0.6 — surfaced at sign-off
            "low_confidence_ic_ids": [],
            # Coder reuse rate: tracks coder↔codebook alignment (logged signal only —
            # existing_code_match no longer routes; every candidate goes to the judge).
            # coder_flagged_match: coder set existing_code_match (recognised its own codebook)
            # coder_new_comp_new:   coder said new → judge confirmed NEW
            # coder_new_comp_merge: coder said new → judge flipped to MERGE
            # coder_new_comp_reject: coder said new → judge rejected
            "coder_flagged_match": 0,
            "coder_new_comp_new": 0,
            "coder_new_comp_merge": 0,
            "coder_new_comp_reject": 0,
            # ── Pass-2 (omitted-text audit) ────────────────────────────────
            # Per-review two-point density snapshots (contract #13): in-memory,
            # not a DB end-of-run aggregate.
            "density_snapshots": [],  # [{segment_id, char_count, density_pass1,
                                      #   density_pass2, recovered}]
            "pass2_stats": {
                "fragments_total": 0,        # omitted fragments assessed
                "deliberate": 0,             # omission_type counts
                "accidental": 0,
                "contains_evidence_true": 0,
                "recovered_candidates": 0,   # raw recovered before grounding
                "recovered_hallucinated": 0, # dropped by the pass-2 grounding gate
                "overlap_drops": 0,          # dropped by the DEDUP-overlap gate
                "recovered_accepted": 0,     # passed the judge (NEW or MERGE)
            },
        }

        batch_num = 0
        for batch in batch_segments(segments, batch_size):
            batch_num += 1
            logger.info(f"[BATCH] Batch {batch_num}: {len(batch)} reviews (two-pass)")

            if enable_hil:
                its_history = self.its_tracker.history
                latest_its = its_history[-1].its_value if its_history else None
                display_batch_header(
                    batch_num, total_batches,
                    self.ic_repo.count_active(), len(batch),
                    its_value=latest_its,
                    session_new=summary["new_ics_created"],
                    session_merged=summary["merged"],
                    session_rejected=summary["rejected"],
                )

            deferred_quotes: List[VerbatimQuote] = []
            # Single-step undo context shared across the whole batch (both passes).
            undo_state: Dict[str, Any] = {
                "ctx": None, "deferred_quotes": deferred_quotes, "ic_defs": {},
            }
            batch_new_count = 0
            batch_merge_count = 0
            batch_judged_count = 0  # candidates that reached the judge (merge-rate denom)

            for segment in batch:
                seg_idx = self.its_tracker.record_segment()
                rev = self._process_review(
                    segment, seg_idx, summary, deferred_quotes,
                    enable_hil, undo_state,
                )
                batch_new_count += rev["n_new"]
                batch_merge_count += rev["n_merge"]
                batch_judged_count += rev["n_judged"]
                summary["density_snapshots"].append({
                    "segment_id": segment.id,
                    "char_count": rev["char_count"],
                    "density_pass1": rev["density_pass1"],
                    "density_pass2": rev["density_pass2"],
                    "recovered": rev["recovered"],
                })
                if rev["quit_early"]:
                    summary["quit_early"] = True
                    break

            # Record per-batch merge rate (denominator = all candidates judged)
            self.batch_merge_rates.append({
                "batch_num": batch_num,
                "new_candidates": batch_judged_count,
                "merges": batch_merge_count,
                "batch_new": batch_new_count,
            })

            # ── Batch-embed all deferred quotes (1 API call) ─────────────
            if deferred_quotes:
                logger.debug(f"[EMBED] Batch-embedding {len(deferred_quotes)} quotes")
                self.embedding_service.batch_embed_quotes(deferred_quotes)
                for quote in deferred_quotes:
                    self.quote_repo.update_embedding(quote)

            if summary["quit_early"]:
                logger.info(f"Human quit at batch {batch_num}")
                break

            # ── Track ITS ─────────────────────────────────────────────────
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

            # ── Saturation checkpoint ─────────────────────────────────────
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

        # Expose decision-path + merge tracking for metrics
        summary["decision_paths"] = dict(self.decision_paths)
        summary["batch_merge_rates"] = list(self.batch_merge_rates)

        # Eval mode: (top-1 cosine, sim-blind verdict) pairs for the AUC metric.
        summary["auc_pairs"] = list(self.comparator.eval_pairs)

        # IC stability scores from refinement
        summary["ic_stability_scores"] = getattr(self, "_ic_stability_scores", [])

        # Summarise coder confidence (already collected per-new-IC above)
        confidences = summary.get("new_ic_confidences", [])
        if confidences:
            summary["mean_coder_confidence"] = sum(confidences) / len(confidences)
            summary["low_confidence_ic_count"] = sum(1 for c in confidences if c < 0.6)
        else:
            summary["mean_coder_confidence"] = None
            summary["low_confidence_ic_count"] = 0

        return summary

    # ── Per-review two-pass processing ───────────────────────────────────────

    def _process_review(
        self,
        segment: Segment,
        seg_idx: int,
        summary: Dict[str, Any],
        deferred_quotes: List[VerbatimQuote],
        enable_hil: bool,
        undo_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run the full two-pass flow for ONE review (segment).

        pass1: coder.extract (fresh codebook) → decision track → density_pass1
        pass2: omitted-view → audit → ground → DEDUP overlap → decision track
               → density_pass2

        Returns per-review stats: n_new, n_merge, n_judged, char_count,
        density_pass1, density_pass2, recovered (bool), quit_early (bool).
        """
        seg_id = segment.id
        seg_text = segment.canonical_text
        char_count = segment.char_count or len(seg_text)
        seg_index_map = {seg_id: seg_idx}
        n_new = n_merge = n_judged = 0
        quit_early = False

        # ── PASS 1 ────────────────────────────────────────────────────────
        # One LLM call for this review; process_batch refetches the codebook,
        # so review N's pass 1 sees ICs created by earlier reviews in the batch.
        coding = self.coder_agent.process_batch([segment])
        pass1_cands = coding.get(seg_id, [])
        n_dropped = self.coder_agent.last_drop_counts.get(seg_id, 0)
        summary["total_dropped"] += n_dropped
        summary["dropped_per_segment"][seg_id] = (
            summary["dropped_per_segment"].get(seg_id, 0) + n_dropped
        )
        summary["total_candidates"] += len(pass1_cands)

        pass1_spans: List[Tuple[int, int]] = []
        pass1_embeddings = self._embed_candidates(pass1_cands)
        for i, cand in enumerate(pass1_cands):
            emb = pass1_embeddings[i] if pass1_embeddings else None
            result, quote = self._decide_and_apply(
                cand, seg_id, seg_text, emb, summary, deferred_quotes,
                enable_hil, i + 1, len(pass1_cands), seg_index_map,
                undo_state, pass_num=1,
            )
            if result == "quit":
                quit_early = True
                break
            n_judged += 1
            if result == "new":
                n_new += 1
            elif result == "merge":
                n_merge += 1
            if quote is not None:
                pass1_spans.append((quote.span_start, quote.span_end))

        density_pass1 = self._density(pass1_spans, char_count)

        if quit_early:
            return {
                "n_new": n_new, "n_merge": n_merge, "n_judged": n_judged,
                "char_count": char_count, "density_pass1": density_pass1,
                "density_pass2": density_pass1, "recovered": False,
                "quit_early": True,
            }

        # ── PASS 2: omitted-text audit ────────────────────────────────────
        second = self.second_pass_agent.assess_omitted(segment, pass1_spans)
        recovered: List[Tuple[ICCandidate, Dict[str, Any]]] = []

        for frag in second.fragments:
            otype = frag.omission_type.value  # "deliberate" | "accidental"
            summary["pass2_stats"]["fragments_total"] += 1
            summary["pass2_stats"][otype] = summary["pass2_stats"].get(otype, 0) + 1
            if frag.contains_evidence:
                summary["pass2_stats"]["contains_evidence_true"] += 1

            # Log the fragment assessment itself (pass:2) — even with no recovery.
            if self.reasoning_logger:
                self.reasoning_logger.log_record({
                    "type": "omitted_fragment",
                    "pass": 2,
                    "segment_id": seg_id,
                    "omitted_text": frag.omitted_text,
                    "reasoning": frag.reasoning,
                    "omission_type": otype,
                    "contains_evidence": frag.contains_evidence,
                    "recovered_count": len(frag.recovered_evidence or []),
                })

            for raw in (frag.recovered_evidence or []):
                summary["pass2_stats"]["recovered_candidates"] += 1
                # Grounding gate (Tier 1) — span via find(); hallucination → drop.
                cand = CoderAgent._ground_candidate(raw, segment)
                if cand is None:
                    summary["pass2_stats"]["recovered_hallucinated"] += 1
                    if self.reasoning_logger:
                        self.reasoning_logger.log_record({
                            "type": "pass2_grounding_drop",
                            "pass": 2, "segment_id": seg_id,
                            "ic_name": raw.ic_name, "quote_text": raw.quote_text,
                            "omission_type": otype, "grounded": False,
                            "final_action": "grounding_drop",
                        })
                    continue
                # DEDUP overlap gate — drop if span overlaps any accepted pass-1 span.
                if self._overlaps_any((cand.span_start, cand.span_end), pass1_spans):
                    summary["pass2_stats"]["overlap_drops"] += 1
                    if self.reasoning_logger:
                        self.reasoning_logger.log_record({
                            "type": "candidate", "pass": 2, "segment_id": seg_id,
                            "ic_name": cand.ic_name, "quote_text": cand.quote_text,
                            "span_start": cand.span_start, "span_end": cand.span_end,
                            "grounded": True, "omission_type": otype,
                            "contains_evidence": frag.contains_evidence,
                            "reasoning": frag.reasoning,
                            "pass2_overlap_drop": True,
                            "final_action": "overlap_drop",
                        })
                    continue
                recovered.append((cand, {
                    "omission_type": otype,
                    "contains_evidence": frag.contains_evidence,
                    "reasoning": frag.reasoning,
                    "pass2_overlap_drop": False,
                }))

        pass2_spans: List[Tuple[int, int]] = []
        rec_embeddings = self._embed_candidates([c for c, _ in recovered])
        for i, (cand, pass2_fields) in enumerate(recovered):
            emb = rec_embeddings[i] if rec_embeddings else None
            result, quote = self._decide_and_apply(
                cand, seg_id, seg_text, emb, summary, deferred_quotes,
                enable_hil, i + 1, len(recovered), seg_index_map,
                undo_state, pass_num=2, pass2_fields=pass2_fields,
            )
            if result == "quit":
                quit_early = True
                break
            n_judged += 1
            if result in ("new", "merge"):
                summary["pass2_stats"]["recovered_accepted"] += 1
            if result == "new":
                n_new += 1
            elif result == "merge":
                n_merge += 1
            if quote is not None:
                pass2_spans.append((quote.span_start, quote.span_end))

        density_pass2 = self._density(pass1_spans + pass2_spans, char_count)
        return {
            "n_new": n_new, "n_merge": n_merge, "n_judged": n_judged,
            "char_count": char_count,
            "density_pass1": density_pass1,
            "density_pass2": density_pass2,
            "recovered": len(pass2_spans) > 0,
            "quit_early": quit_early,
        }

    def _decide_and_apply(
        self,
        cand: ICCandidate,
        seg_id: str,
        seg_text: str,
        cand_embedding: Optional[List[float]],
        summary: Dict[str, Any],
        deferred_quotes: List[VerbatimQuote],
        enable_hil: bool,
        cand_num: int,
        total_in_pass: int,
        segment_indices: Dict[str, int],
        undo_state: Dict[str, Any],
        pass_num: int,
        pass2_fields: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[VerbatimQuote]]:
        """
        Run ONE candidate through the shared decision track:
        judge → (HIL or auto-accept) → apply → summary counters → reasoning_log.

        Used by both pass 1 and pass 2 (DRY). Returns (result, quote) where
        result ∈ {"new","merge","reject","quit"} and quote is the persisted
        VerbatimQuote for new/merge (carries the accepted span), else None.
        """
        # Logged signal only (coder_reuse matrix) — does NOT route.
        if cand.existing_code_match is not None:
            summary["coder_flagged_match"] += 1

        # 1. Judge (embedding shortlist already computed)
        comp_output, top_k, decision_meta = self.comparator.evaluate(
            cand, precomputed_embedding=cand_embedding
        )
        decision_path = decision_meta.get("decision_path", "unknown")
        if decision_path in self.decision_paths:
            self.decision_paths[decision_path] += 1

        if enable_hil:
            ic_defs: Dict[str, str] = {}
            for sim in top_k:
                ic = self.ic_repo.get_by_id(sim.ic_id)
                if ic:
                    ic_defs[sim.ic_id] = ic.definition
            display_candidate_review(
                cand, comp_output, top_k, seg_text,
                cand_num, total_in_pass, segment_id=seg_id, ic_definitions=ic_defs,
            )
            undo_state["ic_defs"] = ic_defs
            action, target_idx, notes = self._hil_loop(
                cand, comp_output, top_k, seg_text,
                cand_num, total_in_pass, seg_id=seg_id, undo_state=undo_state,
            )
            if action == "Q":
                return "quit", None
        else:
            action = comp_output.recommendation.value[0]  # N, M, R → first char
            target_idx = 1 if action == "M" and top_k else None
            notes = "auto-accepted (HIL disabled)"

        # 2. Apply decision (IC embed/persist immediate for NEW; quote embed deferred)
        result, quote, new_ic_id = self._apply_decision(
            action=action, candidate=cand, segment_id=seg_id,
            comp_output=comp_output, top_k=top_k, target_idx=target_idx,
            notes=notes, defer_quote_embed=True,
        )

        if quote is not None:
            deferred_quotes.append(quote)

        if result == "new":
            summary["new_ics_created"] += 1
            summary["coder_new_comp_new"] += 1
            if cand.confidence is not None:
                summary["new_ic_confidences"].append(cand.confidence)
                if cand.confidence < 0.6 and new_ic_id:
                    summary["low_confidence_ic_ids"].append(new_ic_id)
            seg_idx = segment_indices.get(seg_id)
            if seg_idx is not None:
                prev = self.its_tracker._new_ics_per_segment.get(seg_idx, 0)
                self.its_tracker._new_ics_per_segment[seg_idx] = prev + 1
                if new_ic_id:
                    self.ic_creation_segments[new_ic_id] = seg_idx
            undo_state["ctx"] = {
                "action": "new", "description": f"NEW: {cand.ic_name}",
                "ic_id": new_ic_id, "quote_id": quote.id if quote else None,
                "deferred_quote_ref": quote,
            }
        elif result == "merge":
            summary["merged"] += 1
            summary["coder_new_comp_merge"] += 1
            target_name = top_k[target_idx - 1].ic_name if target_idx and top_k else "?"
            undo_state["ctx"] = {
                "action": "merge",
                "description": f"MERGE: {cand.ic_name} → {target_name}",
                "ic_id": None, "quote_id": quote.id if quote else None,
                "deferred_quote_ref": quote,
            }
        elif result == "reject":
            summary["rejected"] += 1
            summary["coder_new_comp_reject"] += 1
            undo_state["ctx"] = {
                "action": "reject", "description": f"REJECT: {cand.ic_name}",
                "ic_id": None, "quote_id": None, "deferred_quote_ref": None,
            }

        # 3. Full per-candidate traceability (Appendix B). pass2_fields adds
        #    omission_type / contains_evidence / reasoning / pass2_overlap_drop.
        if self.reasoning_logger:
            record: Dict[str, Any] = {
                "pass": pass_num,
                "segment_id": seg_id,
                "ic_name": cand.ic_name,
                "quote_text": cand.quote_text,
                "span_start": cand.span_start,
                "span_end": cand.span_end,
                "grounded": True,
                "coder_existing_code_match": cand.existing_code_match,
                "top_k": [
                    {"ic_id": s.ic_id, "ic_name": s.ic_name,
                     "sim": round(s.similarity, 4)}
                    for s in top_k
                ],
                "decision_path": decision_path,
                "judge_verdict": comp_output.recommendation.value,
                "judge_reasoning": comp_output.reasoning,
                "final_action": result,
            }
            if pass2_fields:
                record.update(pass2_fields)
            self.reasoning_logger.log_candidate(record)

        return result, quote

    # ── Small span helpers ───────────────────────────────────────────────────

    def _embed_candidates(
        self, candidates: List[ICCandidate]
    ) -> List[List[float]]:
        """Batch-embed candidate texts (name | definition); [] when empty."""
        if not candidates:
            return []
        texts = [f"{c.ic_name} | {c.definition}" for c in candidates]
        return self.embedding_service.embed_texts_batch(texts)

    @staticmethod
    def _covered_chars(spans: List[Tuple[int, int]]) -> int:
        """Total characters covered by the union of spans (merging overlaps)."""
        if not spans:
            return 0
        sorted_spans = sorted(spans)
        merged = [list(sorted_spans[0])]
        for start, end in sorted_spans[1:]:
            if start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        return sum(end - start for start, end in merged)

    def _density(self, spans: List[Tuple[int, int]], char_count: int) -> float:
        """Span-union coverage as a fraction of the review's character count."""
        if char_count <= 0:
            return 0.0
        return round(self._covered_chars(spans) / char_count, 4)

    @staticmethod
    def _overlaps_any(
        span: Tuple[int, int], others: List[Tuple[int, int]]
    ) -> bool:
        """True if `span` overlaps any interval in `others` (max(s,s1)<min(e,e1))."""
        s, e = span
        return any(max(s, s1) < min(e, e1) for s1, e1 in others)

    # ── HIL Interaction Loop ─────────────────────────────────────────────────

    def _hil_loop(
        self,
        candidate: ICCandidate,
        comp_output: ComparatorOutput,
        top_k: List[SimilarityResult],
        seg_text: str,
        candidate_num: int,
        total_candidates: int,
        seg_id: str = "",
        undo_state: Optional[Dict] = None,
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """
        HIL loop that handles Edit (re-display after edit), Undo (reverse previous
        decision), and Context expand ([C] / [C N]) commands.

        undo_state is a mutable dict shared with the caller:
          {"ctx": undo_context_or_None, "deferred_quotes": list, "ic_defs": dict}

        Returns: (action, target_idx, notes)
        """
        current_candidate = candidate
        undo_state = undo_state or {}
        context_window = CONTEXT_WINDOW   # starts at default, analyst can expand

        while True:
            ic_defs = undo_state.get("ic_defs", {})
            undo_ctx = undo_state.get("ctx")
            action, target_idx, notes = prompt_decision(
                top_k,
                full_reasoning=comp_output.reasoning or "",
                ic_definitions=ic_defs,
                can_undo=undo_ctx is not None,
                last_decision_desc=undo_ctx.get("description", "") if undo_ctx else "",
                current_context_window=context_window,
            )

            if action == "C":
                # target_idx carries the requested window size (None → full segment)
                context_window = target_idx if target_idx is not None else len(seg_text)
                display_candidate_review(
                    current_candidate, comp_output, top_k, seg_text,
                    candidate_num, total_candidates,
                    segment_id=seg_id, ic_definitions=ic_defs,
                    context_window=context_window,
                )
                continue

            if action == "E":
                current_candidate = prompt_edit_candidate(current_candidate)
                display_candidate_review(
                    current_candidate, comp_output, top_k, seg_text,
                    candidate_num, total_candidates,
                    segment_id=seg_id, ic_definitions=ic_defs,
                    context_window=context_window,
                )
                continue

            if action == "U" and undo_ctx:
                self._undo_last_decision(undo_ctx, undo_state.get("deferred_quotes", []))
                undo_state["ctx"] = None   # consumed — prevent double-undo
                print(f"\n  ↩ Undone: {undo_ctx['description']}")
                display_candidate_review(
                    current_candidate, comp_output, top_k, seg_text,
                    candidate_num, total_candidates,
                    segment_id=seg_id, ic_definitions=ic_defs,
                    context_window=context_window,
                )
                continue

            return action, target_idx, notes

    # ── Undo ─────────────────────────────────────────────────────────────────

    def _undo_last_decision(self, ctx: Dict, deferred_quotes: List) -> None:
        """
        Reverse the most recent HIL decision.

        NEW:    hard-delete IC + quote from DB; remove from deferred_quotes.
        MERGE:  hard-delete quote from DB; remove from deferred_quotes.
        REJECT: no DB writes were made — nothing to reverse.

        The undo context (ctx) must be the dict built immediately after
        _apply_decision() returned. Once consumed, ctx["ic_id"] etc. are stale.
        """
        action = ctx.get("action", "")
        ic_id   = ctx.get("ic_id")
        quote_id = ctx.get("quote_id")
        deferred_ref = ctx.get("deferred_quote_ref")

        if action == "new":
            if ic_id:
                self.ic_repo.hard_delete(ic_id)
            if quote_id:
                self.quote_repo.delete_by_id(quote_id)
        elif action == "merge":
            if quote_id:
                self.quote_repo.delete_by_id(quote_id)
        # reject: nothing was written, nothing to delete

        # Remove from deferred embed list if present
        if deferred_ref and deferred_ref in deferred_quotes:
            deferred_quotes.remove(deferred_ref)

        logger.info(f"[UNDO] Reversed: {ctx.get('description', action)}")

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

        elif action == "M" and target_idx and top_k:
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
        # Create IC — store coder's confidence at creation time
        ic = InitialCode(
            name=candidate.ic_name,
            definition=candidate.definition,
            status=ICStatus.ACTIVE,
            confidence=candidate.confidence,
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

                extra_body = self.model_client.build_extra_body(agent_name)
                refined_parsed, refined_raw = client.chat.completions.create_with_completion(
                    model=model_id,
                    response_model=RefinedICOutput,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=800,
                    **({"extra_body": extra_body} if extra_body else {}),
                )
                if self.reasoning_logger:
                    self.reasoning_logger.log("ic_refinement", model_id, refined_raw)

                old_def = ic.definition
                ic.definition = refined_parsed.refined_definition

                # Non-destructive (DESIGN_PRINCIPLES #5 / contract #15): log the
                # pre-refinement definition before overwriting, so the original is
                # always recoverable from the trace.
                if self.reasoning_logger:
                    self.reasoning_logger.log_record({
                        "type": "ic_refinement",
                        "ic_id": ic.id,
                        "ic_name": ic.name,
                        "original_definition": old_def,
                        "refined_definition": refined_parsed.refined_definition,
                        "change_summary": refined_parsed.change_summary,
                        "quote_count": len(quotes),
                    })

                # Re-embed with updated definition
                ic = self.embedding_service.embed_ic(ic)

                # Compute stability score (cosine similarity between old and new embedding)
                if old_embedding and ic.embedding_json:
                    from src.core.embeddings import cosine_similarity as _cos_sim
                    stability = _cos_sim(old_embedding, ic.embedding_json)
                    stability_scores.append({
                        "ic_name": ic.name,
                        "stability": round(stability, 4),
                    })

                # Persist
                self.ic_repo.update(ic)
                refined_count += 1

                logger.info(
                    f"[IC:REFINE] '{ic.name}': {refined_parsed.change_summary}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to refine IC '{ic.name}': {e} — keeping original"
                )

        logger.info(f"[IC:REFINE] Complete: {refined_count}/{len(candidates)} refined")

        # Store stability scores on the orchestrator for later retrieval
        self._ic_stability_scores = stability_scores

        return refined_count
