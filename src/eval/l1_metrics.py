"""
EQD-AI v2 — L1 Evidence-Extraction Metrics.

Reference-free metrics for the evidence-extraction layer. Extracted from v1's
Layer-3 QualityMetricsEngine; the theme/category (L2+) metrics were shelved with
the full pipeline (see the `v1-full-pipeline` tag).

DATA INTEGRITY:
  - Grounding — are all verbatim quotes verifiable against canonical text?
  - Extraction Density — character-level segment coverage by IC quotes
    (+ Candidate Drop Rate — candidates rejected by span validation)

CODEBOOK HEALTH:
  - IC Concentration — evidence distribution across ICs (singleton ratio)
  - Merge Rate Over Time — per-batch merge/candidate ratio
  - Triage Efficiency — auto-decisions / total new candidates
  - Comparator Agreement — LLM vs embedding alignment in grey zone

SATURATION / EVIDENCE:
  - ITS — Incremental Type Saturation curve across batches (passed in)
  - Coder Confidence — coder agent self-assessed novelty confidence
  - Quote Coverage per IC — per-IC per-segment coverage
  - Cross-Review Convergence — ICs with evidence from 2+ source documents
    (judgment-call L1/L2 metric; kept for v2 — confirm scope)

All metrics are signals for the analyst — none are automated gates.
Single-float metrics are persisted to the quality_metrics table.
"""

from __future__ import annotations

import logging
import statistics as _stats
from typing import Any, Dict, List, Optional, Tuple

from src.core.db import (
    Database,
    InitialCodeRepo,
    QualityMetricRepo,
    SegmentRepo,
    VerbatimQuoteRepo,
)
from src.core.embeddings import EmbeddingService
from src.preprocessing import verify_quote
from src.core.models import (
    BatchITS,
    MetricType,
    QualityMetric,
)

logger = logging.getLogger(__name__)


class L1MetricsEngine:
    """
    Compute and persist evidence-extraction (L1) quality metrics.

    Called after Layer 1 (IC extraction + codebook building). `embedding_service`
    is accepted for API compatibility with the orchestrator wiring but is not
    required by any L1 metric.
    """

    def __init__(
        self,
        db: Database,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.db = db
        self.embedding_service = embedding_service
        self.ic_repo = InitialCodeRepo(db)
        self.vq_repo = VerbatimQuoteRepo(db)
        self.seg_repo = SegmentRepo(db)
        self.qm_repo = QualityMetricRepo(db)

    def compute_all(
        self,
        its_history: Optional[List[BatchITS]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Compute all L1 quality metrics and persist single-float ones to DB.

        Args:
            its_history: ITS tracking data from Layer 1 (optional, for display)
            **kwargs: additional context from the orchestrator:
                - triage_stats: Dict[str, int] — auto_new/auto_merge/grey_zone counts
                - batch_merge_rates: List[Dict] — per-batch merge data
                - grey_zone_decisions: List[Dict] — LLM vs embedding agreement data
                - total_dropped: int — candidates dropped by span validation
                - total_candidates: int — valid candidates processed by comparator
                - dropped_per_segment: Dict[str, int] — {segment_id: n_dropped}
                - new_ic_confidences: List[float] — novelty confidence of new ICs
                - coder_flagged_match / coder_new_comp_* : int — coder↔comparator matrix

        Returns dict with all computed results.
        """
        results: Dict[str, Any] = {}

        # ── DATA INTEGRITY ────────────────────────────────────────────────
        results["grounding"] = self.compute_grounding()

        total_dropped = kwargs.get("total_dropped", 0)
        total_candidates = kwargs.get("total_candidates", 0)
        dropped_per_segment = kwargs.get("dropped_per_segment", {})
        results["extraction_density"] = self.compute_extraction_density(
            total_dropped=total_dropped,
            total_valid_candidates=total_candidates,
            dropped_per_segment=dropped_per_segment,
        )

        # ── CODEBOOK HEALTH ───────────────────────────────────────────────
        results["ic_concentration"] = self.compute_ic_concentration()
        results["merge_rate"] = self.compute_merge_rate(
            kwargs.get("batch_merge_rates", [])
        )
        results["triage_efficiency"] = self.compute_triage_efficiency(
            kwargs.get("triage_stats", {})
        )
        results["comparator_agreement"] = self.compute_comparator_agreement(
            kwargs.get("grey_zone_decisions", [])
        )

        # ── SATURATION / EVIDENCE ─────────────────────────────────────────
        results["its_history"] = its_history or []
        results["cross_review_convergence"] = self.compute_cross_review_convergence()
        results["coder_confidence"] = self.compute_coder_confidence(
            kwargs.get("new_ic_confidences", [])
        )
        results["quote_coverage"] = self.compute_quote_coverage_per_ic()

        # Coder Reuse Rate (2×2 matrix: coder flagged vs comparator outcome)
        results["coder_reuse"] = {
            "flagged_match": kwargs.get("coder_flagged_match", 0),
            "new_comp_new": kwargs.get("coder_new_comp_new", 0),
            "new_comp_merge": kwargs.get("coder_new_comp_merge", 0),
            "new_comp_reject": kwargs.get("coder_new_comp_reject", 0),
        }

        logger.info("All L1 quality metrics computed")
        return results

    def compute_coder_confidence(
        self, confidences: List[float]
    ) -> Dict[str, Any]:
        """
        Summarise coder agent self-assessed confidence across new ICs.

        Confidence (0–1) is recorded at IC creation time from ICCandidate.confidence.
        Only accepted NEW ICs are included — merged and rejected candidates are excluded.

        Interpretation:
        - mean > 0.8  = coder is highly certain; codebook is well-established or data is clear
        - mean 0.6-0.8 = healthy uncertainty; normal for exploratory runs
        - mean < 0.6  = coder is frequently uncertain; review low-confidence ICs in codebook
        - low_confidence_count > 20% of ICs = consider HIL review of flagged codes
        """
        if not confidences:
            return {
                "mean_confidence": None,
                "sd_confidence": None,
                "q1_confidence": None,
                "q2_confidence": None,
                "q3_confidence": None,
                "iqr_confidence": None,
                "min_confidence": None,
                "max_confidence": None,
                "low_confidence_count": 0,
                "low_confidence_ratio": 0.0,
                "total_new_ics": 0,
            }

        n = len(confidences)
        low = [c for c in confidences if c < 0.6]
        mean = sum(confidences) / n
        sd = _stats.stdev(confidences) if n > 1 else 0.0

        # Quartiles — statistics.quantiles requires n >= 2 for quartile interpolation
        if n >= 4:
            qs = _stats.quantiles(confidences, n=4)
            q1, q2, q3 = qs[0], qs[1], qs[2]
        elif n >= 2:
            sorted_c = sorted(confidences)
            q1 = sorted_c[0]
            q2 = _stats.median(confidences)
            q3 = sorted_c[-1]
        else:
            q1 = q2 = q3 = confidences[0]

        result = {
            "mean_confidence": round(mean, 4),
            "sd_confidence": round(sd, 4),
            "q1_confidence": round(q1, 4),
            "q2_confidence": round(q2, 4),
            "q3_confidence": round(q3, 4),
            "iqr_confidence": round(q3 - q1, 4),
            "min_confidence": round(min(confidences), 4),
            "max_confidence": round(max(confidences), 4),
            "low_confidence_count": len(low),
            "low_confidence_ratio": round(len(low) / n, 4),
            "total_new_ics": n,
        }
        return result

    def compute_grounding(self) -> Dict[str, Any]:
        """
        Re-verify all verbatim quotes against their canonical texts.

        Returns:
            {
                "total_quotes": int,
                "verified": int,
                "failed": int,
                "grounding_rate": float,
                "failures": [(quote_id, ic_id, reason), ...]
            }
        """
        codebook = self.ic_repo.get_all_active()
        total = 0
        verified = 0
        failures: List[Tuple[str, str, str]] = []

        for ic in codebook:
            quotes = self.vq_repo.get_all_for_ic(ic.id)
            for quote in quotes:
                total += 1
                canonical = self.seg_repo.get_canonical_text(quote.segment_id)
                if canonical is None:
                    failures.append((quote.id, ic.id, "segment not found"))
                    continue

                if verify_quote(quote, canonical):
                    verified += 1
                else:
                    failures.append((quote.id, ic.id, "span mismatch"))

        rate = verified / total if total > 0 else 1.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.GROUNDING,
            value=rate,
        ))

        result = {
            "total_quotes": total,
            "verified": verified,
            "failed": len(failures),
            "grounding_rate": rate,
            "failures": failures,
        }
        logger.info(f"Grounding: {verified}/{total} ({rate:.1%})")
        return result

    def compute_extraction_density(
        self,
        total_dropped: int = 0,
        total_valid_candidates: int = 0,
        dropped_per_segment: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Compute per-segment extraction density: fraction of segment text
        captured by IC quotes (character-level).

        Also computes candidate drop rate: proportion of LLM-proposed candidates
        dropped due to span validation failure (all 3 tiers failed).

        Args:
            total_dropped: candidates dropped across all batches (from orchestrator)
            total_valid_candidates: candidates that passed validation (from orchestrator)
            dropped_per_segment: {segment_id: n_dropped} mapping (from orchestrator)
        """
        dropped_per_segment = dropped_per_segment or {}
        with self.db.connect() as conn:
            seg_rows = conn.execute(
                "SELECT id, char_count, canonical_text FROM segments ORDER BY segment_index"
            ).fetchall()

        if not seg_rows:
            return {"total_segments": 0, "segments_with_codes": 0,
                    "distribution": {}, "per_segment": [],
                    "high_density": [], "low_density": []}

        per_segment = []
        densities = []
        segments_with_codes = 0

        for seg in seg_rows:
            seg_id = seg["id"]
            char_count = seg["char_count"]
            canonical = seg["canonical_text"]

            quotes = self.vq_repo.get_all_for_segment(seg_id)
            spans = [(q.span_start, q.span_end) for q in quotes
                     if q.span_start is not None and q.span_end is not None]

            covered_chars = self._merge_spans(spans)
            density = covered_chars / char_count if char_count > 0 else 0.0

            if quotes:
                segments_with_codes += 1

            per_segment.append({
                "segment_id": seg_id,
                "density": round(density, 3),
                "char_count": char_count,
                "covered_chars": covered_chars,
                "preview": (canonical[:80] + "...") if len(canonical) > 80 else canonical,
            })
            densities.append(density)

        sorted_d = sorted(densities)
        n = len(sorted_d)
        distribution = {
            "mean": round(sum(sorted_d) / n, 3),
            "median": round(sorted_d[n // 2], 3),
            "min": round(sorted_d[0], 3),
            "max": round(sorted_d[-1], 3),
            "p25": round(sorted_d[n // 4], 3),
            "p75": round(sorted_d[3 * n // 4], 3),
        }

        high_density = sorted(
            [s for s in per_segment if s["density"] > 0.80],
            key=lambda x: -x["density"],
        )[:3]
        low_density = sorted(
            [s for s in per_segment if s["density"] < 0.20 and s["density"] > 0],
            key=lambda x: x["density"],
        )[:3]

        # ── Candidate Drop Rate ────────────────────────────────────────────
        total_raw = total_valid_candidates + total_dropped
        overall_drop_rate = total_dropped / total_raw if total_raw > 0 else 0.0

        seg_preview_map = {s["segment_id"]: s["preview"] for s in per_segment}
        drop_segments = []
        for seg_id, n_dropped in sorted(
            dropped_per_segment.items(), key=lambda x: -x[1]
        ):
            if n_dropped > 0:
                drop_segments.append({
                    "segment_id": seg_id,
                    "n_dropped": n_dropped,
                    "preview": seg_preview_map.get(seg_id, seg_id[:12]),
                })

        drop_rate_data = {
            "overall_rate": round(overall_drop_rate, 3),
            "total_dropped": total_dropped,
            "total_raw_candidates": total_raw,
            "segments_with_drops": len(drop_segments),
            "top_drop_segments": drop_segments[:3],
        }

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.COVERAGE,
            value=distribution["mean"],
        ))
        if total_raw > 0:
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.CANDIDATE_DROP_RATE,
                value=overall_drop_rate,
            ))

        result = {
            "total_segments": n,
            "segments_with_codes": segments_with_codes,
            "distribution": distribution,
            "per_segment": per_segment,
            "high_density": high_density,
            "low_density": low_density,
            "drop_rate": drop_rate_data,
        }
        logger.info(
            f"Extraction density: mean={distribution['mean']:.1%}, "
            f"median={distribution['median']:.1%} across {n} segments | "
            f"Drop rate: {overall_drop_rate:.1%} ({total_dropped}/{total_raw} candidates)"
        )
        return result

    @staticmethod
    def _merge_spans(spans: List[Tuple[int, int]]) -> int:
        """
        Compute total characters covered by spans, merging overlaps.

        Standard interval merging: sort by start, merge adjacent/overlapping.
        """
        if not spans:
            return 0

        sorted_spans = sorted(spans, key=lambda x: x[0])
        merged = [sorted_spans[0]]

        for start, end in sorted_spans[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        return sum(end - start for start, end in merged)

    def compute_ic_concentration(self) -> Dict[str, Any]:
        """
        IC Concentration / Evidence Distribution.

        Measures how evenly evidence is distributed across ICs.

        Key outputs:
        - singleton_ratio: fraction of ICs with exactly 1 quote (no merges)
        - mean_quotes_per_ic: average evidence per IC
        - distribution: {min, max, p25, p50, p75}

        Interpretation:
        - High singleton_ratio (>0.6) = many unconfirmed ICs, consider merging
        - Low singleton_ratio (<0.3) = healthy evidence distribution
        """
        codebook = self.ic_repo.get_all_active()
        if not codebook:
            return {"total_ics": 0, "singleton_ratio": 0.0,
                    "mean_quotes_per_ic": 0.0, "distribution": {}}

        quote_counts = []
        singletons = 0

        for ic in codebook:
            quotes = self.vq_repo.get_all_for_ic(ic.id)
            count = len(quotes)
            quote_counts.append(count)
            if count == 1:
                singletons += 1

        total_ics = len(codebook)
        singleton_ratio = singletons / total_ics if total_ics > 0 else 0.0
        mean_quotes = sum(quote_counts) / total_ics if total_ics > 0 else 0.0

        sorted_counts = sorted(quote_counts)
        n = len(sorted_counts)
        distribution = {
            "min": sorted_counts[0],
            "max": sorted_counts[-1],
            "p25": sorted_counts[n // 4],
            "p50": sorted_counts[n // 2],
            "p75": sorted_counts[3 * n // 4],
        }

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.IC_CONCENTRATION,
            value=singleton_ratio,
        ))

        result = {
            "total_ics": total_ics,
            "singletons": singletons,
            "singleton_ratio": round(singleton_ratio, 3),
            "mean_quotes_per_ic": round(mean_quotes, 2),
            "distribution": distribution,
        }
        logger.info(
            f"IC Concentration: {singletons}/{total_ics} singletons "
            f"({singleton_ratio:.1%}), mean={mean_quotes:.1f} quotes/IC"
        )
        return result

    def compute_merge_rate(
        self, batch_merge_rates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge Rate Over Time: per-batch merge/candidate ratio.

        Formula per batch: merges / new_candidates
        Overall: total_merges / total_new_candidates

        Interpretation:
        - Rising merge rate across batches = codebook maturing, more redundancy
        - Flat near 0 = every candidate is novel (early stage or fragmented)
        - Steady >0.5 = many duplicates, consider larger batches or stricter triage
        """
        if not batch_merge_rates:
            return {"overall_rate": 0.0, "per_batch": [], "total_candidates": 0,
                    "total_merges": 0}

        total_candidates = 0
        total_merges = 0
        per_batch = []

        for batch in batch_merge_rates:
            cands = batch.get("new_candidates", 0)
            merges = batch.get("merges", 0)
            total_candidates += cands
            total_merges += merges
            rate = merges / cands if cands > 0 else 0.0
            per_batch.append({
                "batch_num": batch.get("batch_num", 0),
                "new_candidates": cands,
                "merges": merges,
                "rate": round(rate, 3),
            })

        overall_rate = total_merges / total_candidates if total_candidates > 0 else 0.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.MERGE_RATE,
            value=overall_rate,
        ))

        result = {
            "overall_rate": round(overall_rate, 3),
            "total_candidates": total_candidates,
            "total_merges": total_merges,
            "per_batch": per_batch,
        }
        logger.info(
            f"Merge rate: {total_merges}/{total_candidates} "
            f"({overall_rate:.1%} overall)"
        )
        return result

    def compute_triage_efficiency(
        self, triage_stats: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Triage Efficiency: fraction of decisions made without LLM.

        Formula: (auto_new + auto_merge) / (auto_new + auto_merge + grey_zone)
        Excludes empty_codebook (trivial, doesn't reflect threshold quality).

        Interpretation:
        - >0.7 = thresholds well-tuned, most decisions are clear-cut
        - 0.3-0.7 = healthy grey zone, LLM adds value
        - <0.3 = thresholds too narrow, LLM called for almost everything
        """
        auto_new = triage_stats.get("auto_new", 0)
        auto_merge = triage_stats.get("auto_merge", 0)
        grey_zone = triage_stats.get("grey_zone", 0)
        empty_codebook = triage_stats.get("empty_codebook", 0)

        auto_total = auto_new + auto_merge
        non_trivial = auto_total + grey_zone  # excludes empty_codebook
        efficiency = auto_total / non_trivial if non_trivial > 0 else 0.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.TRIAGE_EFFICIENCY,
            value=efficiency,
        ))

        result = {
            "efficiency": round(efficiency, 3),
            "auto_new": auto_new,
            "auto_merge": auto_merge,
            "grey_zone": grey_zone,
            "empty_codebook": empty_codebook,
            "llm_calls_saved": auto_total,
            "total_non_trivial": non_trivial,
        }
        logger.info(
            f"Triage efficiency: {auto_total}/{non_trivial} auto-decided "
            f"({efficiency:.1%}), {grey_zone} LLM calls"
        )
        return result

    def compute_comparator_agreement(
        self, grey_zone_decisions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Comparator Agreement Rate: LLM vs embedding alignment in grey zone.

        For each grey-zone decision, compare:
        - sim_direction: based on max_sim vs midpoint → "NEW" or "MERGE"
        - llm_recommendation: what the LLM actually decided

        Agreement = both say NEW or both say MERGE.

        Interpretation:
        - >0.8 = embeddings and LLM aligned, triage could be more aggressive
        - 0.5-0.8 = healthy disagreement, LLM catching nuances
        - <0.5 = embeddings and LLM systematically disagree, check thresholds
        """
        if not grey_zone_decisions:
            return {"agreement_rate": 0.0, "total_grey_zone": 0,
                    "agreed": 0, "disagreed": 0}

        agreed = 0
        disagreed = 0

        for decision in grey_zone_decisions:
            sim_dir = decision.get("sim_direction", "")
            llm_rec = decision.get("llm_recommendation", "")

            if llm_rec in ("NEW", "REJECT"):
                llm_dir = "NEW"
            else:  # MERGE
                llm_dir = "MERGE"

            if sim_dir == llm_dir:
                agreed += 1
            else:
                disagreed += 1

        total = agreed + disagreed
        rate = agreed / total if total > 0 else 0.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.COMPARATOR_AGREEMENT,
            value=rate,
        ))

        result = {
            "agreement_rate": round(rate, 3),
            "total_grey_zone": total,
            "agreed": agreed,
            "disagreed": disagreed,
        }
        logger.info(
            f"Comparator agreement: {agreed}/{total} "
            f"({rate:.1%} LLM agrees with embedding direction)"
        )
        return result

    def compute_cross_review_convergence(self) -> Dict[str, Any]:
        """
        For each IC, count unique source documents that contributed quotes.

        An IC confirmed by 8 reviews is robust; an IC from 1 review is unconfirmed.
        This is an inter-rater reliability proxy — independent data sources arriving
        at the same concept.

        Requires joining: quotes → segments → documents to trace provenance.

        NOTE: judgment-call L1/L2 metric — kept in the v2 L1 set for now; revisit
        whether it belongs here (see docs/v2/V2_FOUNDATION.md).
        """
        codebook = self.ic_repo.get_all_active()
        if not codebook:
            return {
                "mean_docs_per_ic": 0.0,
                "confirmed_ratio": 0.0,
                "strong_convergence_ratio": 0.0,
                "per_ic": [],
            }

        per_ic = []
        confirmed = 0
        strong = 0

        for ic in codebook:
            quotes = self.vq_repo.get_all_for_ic(ic.id)
            doc_ids = set()
            for quote in quotes:
                with self.db.connect() as conn:
                    row = conn.execute(
                        "SELECT document_id FROM segments WHERE id=?",
                        (quote.segment_id,),
                    ).fetchone()
                    if row:
                        doc_ids.add(row["document_id"])

            doc_count = len(doc_ids)
            per_ic.append({"ic_name": ic.name, "doc_count": doc_count})
            if doc_count >= 2:
                confirmed += 1
            if doc_count >= 3:
                strong += 1

        total = len(codebook)
        mean_docs = sum(p["doc_count"] for p in per_ic) / total if total > 0 else 0.0
        confirmed_ratio = confirmed / total if total > 0 else 0.0
        strong_ratio = strong / total if total > 0 else 0.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.CROSS_REVIEW_CONVERGENCE,
            value=confirmed_ratio,
        ))

        result = {
            "mean_docs_per_ic": round(mean_docs, 2),
            "confirmed_ratio": round(confirmed_ratio, 3),
            "strong_convergence_ratio": round(strong_ratio, 3),
            "per_ic": sorted(per_ic, key=lambda x: x["doc_count"], reverse=True),
        }
        logger.info(
            f"Cross-review convergence: mean={mean_docs:.1f} docs/IC, "
            f"confirmed={confirmed_ratio:.1%}, strong={strong_ratio:.1%}"
        )
        return result

    def compute_quote_coverage_per_ic(self) -> Dict[str, Any]:
        """
        Per-IC quote coverage: what fraction of each segment's characters are
        covered by that IC's evidence quotes.

        For ICs with multiple quotes from the SAME segment, uses interval union
        (inclusion-exclusion) to avoid double-counting overlapping spans:
            covered = union of all [span_start, span_end] intervals
        Quotes from DIFFERENT segments are independent — each gets its own ratio.

        Coverage ratio = union_chars / segment_char_count
        """
        with self.db.connect() as conn:
            quote_rows = conn.execute(
                "SELECT ic_id, segment_id, span_start, span_end "
                "FROM verbatim_quotes"
            ).fetchall()
            seg_rows = conn.execute(
                "SELECT id, char_count FROM segments"
            ).fetchall()

        seg_lengths: Dict[str, int] = {r["id"]: r["char_count"] for r in seg_rows}

        ic_seg_spans: Dict[str, Dict[str, List[Tuple[int, int]]]] = {}
        for row in quote_rows:
            ic_id = row["ic_id"]
            seg_id = row["segment_id"]
            span = (row["span_start"], row["span_end"])
            ic_seg_spans.setdefault(ic_id, {}).setdefault(seg_id, []).append(span)

        def _interval_union(intervals: List[Tuple[int, int]]) -> int:
            """Compute total chars covered by the union of intervals."""
            if not intervals:
                return 0
            sorted_ivs = sorted(intervals)
            merged_end = sorted_ivs[0][1]
            total = sorted_ivs[0][1] - sorted_ivs[0][0]
            for start, end in sorted_ivs[1:]:
                if start < merged_end:          # overlap — extend current
                    if end > merged_end:
                        total += end - merged_end
                        merged_end = end
                else:                           # gap — new interval
                    total += end - start
                    merged_end = end
            return total

        codebook = self.ic_repo.get_all_active()
        ic_names: Dict[str, str] = {ic.id: ic.name for ic in codebook}

        per_ic = []
        all_coverages: List[float] = []

        for ic_id, seg_spans in ic_seg_spans.items():
            coverages = []
            for seg_id, spans in seg_spans.items():
                seg_len = seg_lengths.get(seg_id, 0)
                if seg_len == 0:
                    continue
                union_chars = _interval_union(spans)
                ratio = union_chars / seg_len
                coverages.append(round(ratio, 4))

            if not coverages:
                continue

            all_coverages.extend(coverages)
            high_count = sum(1 for c in coverages if c > 0.70)
            per_ic.append({
                "ic_id": ic_id,
                "ic_name": ic_names.get(ic_id, ic_id),
                "coverages": coverages,
                "mean_coverage": round(sum(coverages) / len(coverages), 4),
                "max_coverage": round(max(coverages), 4),
                "high_coverage_segments": high_count,
            })

        per_ic.sort(key=lambda x: x["max_coverage"], reverse=True)

        overall_mean_frac = sum(all_coverages) / len(all_coverages) if all_coverages else 0.0
        overall_max_frac = max(all_coverages) if all_coverages else 0.0
        overall_mean = round(overall_mean_frac * 100, 2)
        overall_max = round(overall_max_frac * 100, 2)
        high_coverage_count = sum(1 for c in all_coverages if c > 0.70)

        logger.info(
            f"Quote coverage per IC: mean={overall_mean:.1f}%, "
            f"max={overall_max:.1f}%, high-coverage pairs={high_coverage_count}"
        )
        return {
            "per_ic": per_ic,
            "overall_mean_pct": overall_mean,
            "overall_max_pct": overall_max,
            "high_coverage_count": high_coverage_count,
            "total_ic_segment_pairs": len(all_coverages),
        }
