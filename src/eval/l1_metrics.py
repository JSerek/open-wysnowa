"""
EQD-AI v2 — L1 Evidence-Extraction Metrics.

Reference-free metrics for the evidence-extraction layer. Extracted from v1's
Layer-3 QualityMetricsEngine; the theme/category (L2+) metrics were shelved with
the full pipeline (see the `v1-full-pipeline` tag).

DATA INTEGRITY:
  - Grounding — are all verbatim quotes verifiable against canonical text?
  - Extraction Density — character-level segment coverage by IC quotes
    (+ Candidate Drop Rate — candidates rejected by the grounding gate)
  - Quote Hallucination Rate — fraction of candidates whose quote was not a
    verbatim substring (v2 leaderboard axis; offsets are computed by the system,
    so the only quote failure is hallucinated/non-verbatim text)

CODEBOOK HEALTH:
  - IC Concentration — evidence distribution across ICs (singleton ratio)
  - Merge Rate Over Time — per-batch merge/candidate ratio

(Triage Efficiency and Comparator Agreement were removed in the v2 raw-measurement
pivot — there are no operating thresholds left to characterise; embedding quality
is assessed threshold-free via AUC in Phase 3.)

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
                - batch_merge_rates: List[Dict] — per-batch merge data
                - total_dropped: int — candidates dropped by the grounding gate
                - total_candidates: int — valid candidates processed by the judge
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
        results["quote_hallucination_rate"] = self.compute_quote_hallucination_rate(
            total_dropped=total_dropped,
            total_valid_candidates=total_candidates,
        )

        # ── CODEBOOK HEALTH ───────────────────────────────────────────────
        results["ic_concentration"] = self.compute_ic_concentration()
        results["merge_rate"] = self.compute_merge_rate(
            kwargs.get("batch_merge_rates", [])
        )

        # ── PASS-2 (OMITTED-TEXT AUDIT) ───────────────────────────────────
        # Two-point density measured per review from in-memory snapshots
        # (contract #13), not a DB end-of-run aggregate.
        results["density_passes"] = self.compute_density_passes(
            kwargs.get("density_snapshots", [])
        )
        results["omission_stats"] = self.compute_omission_stats(
            kwargs.get("pass2_stats", {})
        )

        # ── EMBEDDING EVALUATION (Phase 3) ────────────────────────────────
        # Threshold-free AUC over (top-1 cosine, sim-blind judge verdict) pairs.
        results["embedding_separation"] = self.compute_embedding_separation_auc(
            kwargs.get("auc_pairs", [])
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
        dropped by the grounding gate (quote not a verbatim substring). In v2 the
        grounding gate is the only drop path (no silent auto-repair), so this
        equals quote_hallucination_rate; it is kept for continuity and reported
        here alongside density.

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

    def compute_density_passes(
        self, density_snapshots: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Two-point extraction density from per-review in-memory snapshots (contract #13).

        Each snapshot carries {segment_id, char_count, density_pass1,
        density_pass2, recovered}. density_passN = union(span) / char_count for
        that review's accepted quotes after pass N (pass2 ⊇ pass1 by construction,
        so density_pass2 ≥ density_pass1 per review).

        Metrics:
          - density_pass1 / density_pass2 — mean over reviews (descriptive).
          - density_delta = density_pass2 − density_pass1 (mean of per-review
            deltas) — internally-referenced, LESS is better: a large delta means
            pass 1 missed a lot (poorly calibrated attention).
          - recovery_rate = reviews where pass 2 recovered ≥1 accepted evidence /
            total reviews — internally-referenced (reads with density_delta).
        """
        if not density_snapshots:
            return {
                "density_pass1": None, "density_pass2": None,
                "density_delta": None, "recovery_rate": None,
                "total_reviews": 0, "reviews_with_recovery": 0,
            }

        n = len(density_snapshots)
        d1 = [s.get("density_pass1", 0.0) or 0.0 for s in density_snapshots]
        d2 = [s.get("density_pass2", 0.0) or 0.0 for s in density_snapshots]
        deltas = [b - a for a, b in zip(d1, d2)]
        reviews_with_recovery = sum(1 for s in density_snapshots if s.get("recovered"))

        density_pass1 = sum(d1) / n
        density_pass2 = sum(d2) / n
        density_delta = sum(deltas) / n
        recovery_rate = reviews_with_recovery / n

        for mtype, value in (
            (MetricType.DENSITY_PASS1, density_pass1),
            (MetricType.DENSITY_PASS2, density_pass2),
            (MetricType.DENSITY_DELTA, density_delta),
            (MetricType.RECOVERY_RATE, recovery_rate),
        ):
            self.qm_repo.insert(QualityMetric(metric_type=mtype, value=value))

        logger.info(
            f"Density two-point: pass1={density_pass1:.1%}, pass2={density_pass2:.1%}, "
            f"delta={density_delta:.1%} | recovery_rate={recovery_rate:.1%} "
            f"({reviews_with_recovery}/{n} reviews)"
        )
        return {
            "density_pass1": round(density_pass1, 4),
            "density_pass2": round(density_pass2, 4),
            "density_delta": round(density_delta, 4),
            "recovery_rate": round(recovery_rate, 4),
            "total_reviews": n,
            "reviews_with_recovery": reviews_with_recovery,
        }

    def compute_omission_stats(
        self, pass2_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Diagnostics over the pass-2 omitted-fragment assessments.

        accidental_omission_ratio = accidental / (accidental + deliberate) — the
        key discriminator of model attention; LESS is better (fewer genuine
        misses). deliberate_omission_ratio is its complement (descriptive).

        Also surfaces the 2×2 omission_type × contains_evidence signal and the
        pass-2 gate drops (grounding / overlap) for transparency (DESIGN #7).
        """
        deliberate = int(pass2_stats.get("deliberate", 0))
        accidental = int(pass2_stats.get("accidental", 0))
        total = deliberate + accidental

        if total == 0:
            accidental_ratio = None
            deliberate_ratio = None
        else:
            accidental_ratio = accidental / total
            deliberate_ratio = deliberate / total
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.ACCIDENTAL_OMISSION_RATIO,
                value=accidental_ratio,
            ))
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.DELIBERATE_OMISSION_RATIO,
                value=deliberate_ratio,
            ))

        logger.info(
            f"Omission stats: {accidental} accidental / {deliberate} deliberate "
            f"(accidental_ratio="
            f"{accidental_ratio if accidental_ratio is None else round(accidental_ratio, 3)})"
        )
        return {
            "fragments_total": int(pass2_stats.get("fragments_total", 0)),
            "deliberate": deliberate,
            "accidental": accidental,
            "accidental_omission_ratio": (
                None if accidental_ratio is None else round(accidental_ratio, 4)
            ),
            "deliberate_omission_ratio": (
                None if deliberate_ratio is None else round(deliberate_ratio, 4)
            ),
            "contains_evidence_true": int(pass2_stats.get("contains_evidence_true", 0)),
            "recovered_candidates": int(pass2_stats.get("recovered_candidates", 0)),
            "recovered_accepted": int(pass2_stats.get("recovered_accepted", 0)),
            "recovered_hallucinated": int(pass2_stats.get("recovered_hallucinated", 0)),
            "overlap_drops": int(pass2_stats.get("overlap_drops", 0)),
        }

    def compute_embedding_separation_auc(
        self, auc_pairs: List[Tuple[float, str]]
    ) -> Dict[str, Any]:
        """
        Threshold-free embedding evaluation (Phase 3, contract #7).

        Input: (top-1 cosine, sim-blind judge verdict) pairs, one per judged
        candidate against a non-empty codebook. MERGE is the positive class (the
        embedding should rank these HIGH); NEW is the negative class (LOW). REJECT
        and empty-codebook NEWs are excluded upstream.

        AUC = P(cosine of a MERGE pair > cosine of a NEW pair), i.e. the probability
        that the embedding's similarity separates the two verdicts. Computed as the
        Mann-Whitney U statistic normalised by n_merge·n_new, using average ranks
        for ties (no external dependency):
            AUC = (R_merge − n_merge·(n_merge+1)/2) / (n_merge · n_new)
        where R_merge is the summed rank of the MERGE cosines in the pooled sample.

        AUC ≈ 1.0 → embedding cleanly separates merges from new; ≈ 0.5 → no signal.
        Direction: more = better. Returns auc=None when either class is empty
        (separation is undefined with only one class present).
        """
        merges = [s for s, v in auc_pairs if v == "MERGE"]
        news = [s for s, v in auc_pairs if v == "NEW"]
        n_merge, n_new = len(merges), len(news)

        if n_merge == 0 or n_new == 0:
            return {
                "auc": None, "n_merge": n_merge, "n_new": n_new,
                "n_pairs": len(auc_pairs),
            }

        # Average-rank assignment over the pooled cosines (1-indexed).
        pooled = sorted(
            [(s, "m") for s in merges] + [(s, "n") for s in news],
            key=lambda x: x[0],
        )
        ranks: List[float] = [0.0] * len(pooled)
        i = 0
        while i < len(pooled):
            j = i
            while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
                j += 1
            avg_rank = (i + 1 + j + 1) / 2.0  # mean of tied 1-indexed positions
            for k in range(i, j + 1):
                ranks[k] = avg_rank
            i = j + 1

        r_merge = sum(r for r, (_, lbl) in zip(ranks, pooled) if lbl == "m")
        u_merge = r_merge - n_merge * (n_merge + 1) / 2.0
        auc = u_merge / (n_merge * n_new)

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.EMBEDDING_SEPARATION_AUC,
            value=auc,
        ))

        logger.info(
            f"Embedding separation AUC: {auc:.3f} "
            f"({n_merge} merge / {n_new} new pairs)"
        )
        return {
            "auc": round(auc, 4),
            "n_merge": n_merge,
            "n_new": n_new,
            "n_pairs": len(auc_pairs),
        }

    def compute_quote_hallucination_rate(
        self,
        total_dropped: int = 0,
        total_valid_candidates: int = 0,
    ) -> Dict[str, Any]:
        """
        Quote Hallucination Rate (v2 Phase 1): raw faithfulness of the evidence.

        Formula: hallucinated / (grounded_candidates + hallucinated)

        Spans are computed by the system (the model never emits offsets), so the
        only way a quote can fail is by not being a verbatim substring of the
        canonical text — i.e. the model invented/altered characters, words, or
        merged non-adjacent fragments. Every such candidate is dropped and counts
        against the model.

        Direction: less = better. In Phase 1 this coincides numerically with
        candidate_drop_rate (the grounding gate is the only drop path); it is the
        explicit, named faithfulness signal the leaderboard ranks on.
        """
        total_raw = total_valid_candidates + total_dropped
        rate = total_dropped / total_raw if total_raw > 0 else 0.0

        if total_raw > 0:
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.QUOTE_HALLUCINATION_RATE,
                value=rate,
            ))

        logger.info(
            f"Quote hallucination rate: {rate:.1%} ({total_dropped}/{total_raw} candidates)"
        )
        return {
            "quote_hallucination_rate": round(rate, 4),
            "hallucinated": total_dropped,
            "total_raw_candidates": total_raw,
        }

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
