"""
EQD-AI Layer 3: Quality Metrics Engine.

Computes 12 quality metrics across 4 domains:

DATA INTEGRITY:
  1. Grounding — are all verbatim quotes verifiable against canonical text?
  2. Extraction Density — character-level segment coverage by IC quotes

CODEBOOK HEALTH:
  3. IC Concentration — evidence distribution across ICs (singleton ratio)
  4. Merge Rate Over Time — per-batch merge/candidate ratio
  5. Triage Efficiency — auto-decisions / total new candidates
  6. Comparator Agreement — LLM vs embedding alignment in grey zone

SATURATION:
  7. ITS — Incremental Type Saturation curve across batches
  8. Meaning Saturation — per-theme breadth + spread

THEME QUALITY:
  9. Theme Coherence — intra-theme IC similarity
  10. Theme Distinctness — inter-theme centroid distance
  11. Coherence Normalized — raw coherence / baseline coherence
  12. Cross-Theme IC Sharing — ICs appearing in 2+ themes

All metrics are signals for the analyst — none are automated gates.
Results are persisted to the quality_metrics table.
"""

from __future__ import annotations

import logging
import math
import statistics as _stats
from typing import Any, Dict, List, Optional, Tuple

from src.db import (
    Database,
    InitialCodeRepo,
    QualityMetricRepo,
    SegmentRepo,
    ThemeRepo,
    VerbatimQuoteRepo,
)
from src.embeddings import EmbeddingService, cosine_similarity
from src.grounding import verify_quote
from src.models import (
    BatchITS,
    MetricType,
    QualityMetric,
)

logger = logging.getLogger(__name__)


class QualityMetricsEngine:
    """
    Compute and persist all quality metrics for the analysis.

    Called by the pipeline after theme finalization (Layer 3).
    """

    def __init__(
        self,
        db: Database,
        embedding_service: EmbeddingService,
    ):
        self.db = db
        self.embedding_service = embedding_service
        self.ic_repo = InitialCodeRepo(db)
        self.vq_repo = VerbatimQuoteRepo(db)
        self.seg_repo = SegmentRepo(db)
        self.theme_repo = ThemeRepo(db)
        self.qm_repo = QualityMetricRepo(db)

    def evaluate_theme_coherence(
        self,
        coherence_threshold: float = 1.0,
        coherence_threshold_small: float = 0.90,
    ) -> Dict[str, Any]:
        """
        Quick coherence check for post-synthesis quality gate.

        Computes per-theme coherence, normalizes against baseline,
        flags themes below threshold.

        Returns {
            "baseline": float,
            "per_theme": {name: {"raw", "normalized", "ic_count", "theme_id", "flagged"}},
            "flagged_themes": [{theme_id, theme_name, normalized, raw, ic_count}],
        }
        """
        # 1. Get latest themes
        final_themes, _ = self.theme_repo.get_latest_round()
        if not final_themes:
            return {"baseline": 0.0, "per_theme": {}, "flagged_themes": []}

        # 2. Compute raw coherence per theme
        raw_coherence: Dict[str, Tuple[str, float, int]] = {}  # name → (theme_id, score, ic_count)
        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)
            ic_count = len(ic_ids)
            if ic_count < 2:
                raw_coherence[theme.name] = (theme.id, 1.0, ic_count)
                continue
            score = self.embedding_service.compute_theme_coherence(ic_ids)
            raw_coherence[theme.name] = (theme.id, score, ic_count)

        # 3. Compute baseline (all-IC avg pairwise sim)
        codebook = self.ic_repo.get_all_active()
        all_embeddings = [
            ic.embedding_json for ic in codebook
            if ic.embedding_json is not None
        ]

        baseline = 0.0
        if len(all_embeddings) >= 2:
            total_sim = 0.0
            pair_count = 0
            for i in range(len(all_embeddings)):
                for j in range(i + 1, len(all_embeddings)):
                    total_sim += cosine_similarity(all_embeddings[i], all_embeddings[j])
                    pair_count += 1
            baseline = total_sim / pair_count if pair_count > 0 else 0.0

        # 4. Normalize and flag
        per_theme: Dict[str, Dict[str, Any]] = {}
        flagged_themes: List[Dict[str, Any]] = []

        for theme_name, (theme_id, raw_score, ic_count) in raw_coherence.items():
            norm = raw_score / baseline if baseline > 0 else 0.0
            # Adaptive threshold: lenient for small themes (high variance)
            effective_threshold = (
                coherence_threshold_small if ic_count < 5
                else coherence_threshold
            )
            flagged = norm < effective_threshold and ic_count >= 2

            per_theme[theme_name] = {
                "raw": round(raw_score, 3),
                "normalized": round(norm, 3),
                "ic_count": ic_count,
                "theme_id": theme_id,
                "flagged": flagged,
                "threshold_used": round(effective_threshold, 2),
            }

            if flagged:
                flagged_themes.append({
                    "theme_id": theme_id,
                    "theme_name": theme_name,
                    "normalized": round(norm, 3),
                    "raw": round(raw_score, 3),
                    "ic_count": ic_count,
                    "threshold_used": round(effective_threshold, 2),
                })

        logger.info(
            f"[COHERENCE-GATE] baseline={baseline:.3f}, "
            f"{len(flagged_themes)} themes flagged below {coherence_threshold}"
        )

        return {
            "baseline": round(baseline, 3),
            "per_theme": per_theme,
            "flagged_themes": flagged_themes,
        }

    def compute_all(
        self,
        its_history: Optional[List[BatchITS]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Compute all quality metrics and persist to DB.

        Args:
            its_history: ITS tracking data from Layer 1 (optional, for display)
            **kwargs: additional context from pipeline:
                - ic_creation_segments: Dict[str, int] — {ic_id → segment_index}
                - total_segments: int — total segments processed
                - triage_stats: Dict[str, int] — auto_new/auto_merge/grey_zone counts
                - batch_merge_rates: List[Dict] — per-batch merge data
                - grey_zone_decisions: List[Dict] — LLM vs embedding agreement data
                - total_dropped: int — candidates dropped by span validation across all batches
                - total_candidates: int — valid candidates processed by comparator
                - dropped_per_segment: Dict[str, int] — {segment_id: n_dropped}

        Returns dict with all computed results.
        """
        results: Dict[str, Any] = {}

        # ── DATA INTEGRITY ────────────────────────────────────────────────
        # 1. Grounding
        grounding = self.compute_grounding()
        results["grounding"] = grounding

        # 2. Extraction density + candidate drop rate
        total_dropped = kwargs.get("total_dropped", 0)
        total_candidates = kwargs.get("total_candidates", 0)
        dropped_per_segment = kwargs.get("dropped_per_segment", {})
        extraction_density = self.compute_extraction_density(
            total_dropped=total_dropped,
            total_valid_candidates=total_candidates,
            dropped_per_segment=dropped_per_segment,
        )
        results["extraction_density"] = extraction_density

        # ── CODEBOOK HEALTH ───────────────────────────────────────────────
        # 3. IC Concentration
        ic_concentration = self.compute_ic_concentration()
        results["ic_concentration"] = ic_concentration

        # 4. Merge Rate Over Time
        batch_merge_rates = kwargs.get("batch_merge_rates", [])
        merge_rate = self.compute_merge_rate(batch_merge_rates)
        results["merge_rate"] = merge_rate

        # 5. Triage Efficiency
        triage_stats = kwargs.get("triage_stats", {})
        triage_efficiency = self.compute_triage_efficiency(triage_stats)
        results["triage_efficiency"] = triage_efficiency

        # 6. Comparator Agreement
        grey_zone_decisions = kwargs.get("grey_zone_decisions", [])
        comparator_agreement = self.compute_comparator_agreement(grey_zone_decisions)
        results["comparator_agreement"] = comparator_agreement

        # ── SATURATION ────────────────────────────────────────────────────
        # 7. ITS summary
        results["its_history"] = its_history or []

        # 8. Meaning saturation (breadth + spread per theme)
        ic_creation_segments = kwargs.get("ic_creation_segments", {})
        total_segments = kwargs.get("total_segments", 0)
        theme_saturation = self.compute_meaning_saturation_v2(
            ic_creation_segments=ic_creation_segments,
            total_segments=total_segments,
        )
        results["meaning_saturation_per_theme"] = theme_saturation

        # ── THEME QUALITY ─────────────────────────────────────────────────
        # 9. Theme coherence
        coherence = self.compute_theme_coherence()
        results["theme_coherence"] = coherence

        # 10. Theme distinctness
        distinctness = self.compute_theme_distinctness()
        results["theme_distinctness"] = distinctness

        # 11. Coherence Normalized (needs raw coherence computed first)
        coherence_normalized = self.compute_coherence_normalized(coherence)
        results["coherence_normalized"] = coherence_normalized

        # 12. Cross-Theme IC Sharing
        cross_theme = self.compute_cross_theme_ic_sharing()
        results["cross_theme_ic_sharing"] = cross_theme

        # 13. IC Stability Index
        ic_stability_scores = kwargs.get("ic_stability_scores", [])
        ic_stability = self.compute_ic_stability(ic_stability_scores)
        results["ic_stability"] = ic_stability

        # 14. Orphaned IC Count
        orphaned = self.compute_orphaned_ic_count()
        results["orphaned_ics"] = orphaned

        # 15. Thematic Coverage Ratio
        coverage = self.compute_thematic_coverage()
        results["thematic_coverage"] = coverage

        # 16. Cross-Review Convergence
        convergence = self.compute_cross_review_convergence()
        results["cross_review_convergence"] = convergence

        # 17. Sentiment Purity
        sentiment_purity = self.compute_sentiment_purity()
        results["sentiment_purity"] = sentiment_purity

        # 18. Coder Confidence
        new_ic_confidences = kwargs.get("new_ic_confidences", [])
        coder_confidence = self.compute_coder_confidence(new_ic_confidences)
        results["coder_confidence"] = coder_confidence

        # Quote Coverage Per IC
        results["quote_coverage"] = self.compute_quote_coverage_per_ic()

        # Coder Reuse Rate (2×2 matrix: coder flagged vs comparator outcome)
        results["coder_reuse"] = {
            "flagged_match": kwargs.get("coder_flagged_match", 0),
            "new_comp_new": kwargs.get("coder_new_comp_new", 0),
            "new_comp_merge": kwargs.get("coder_new_comp_merge", 0),
            "new_comp_reject": kwargs.get("coder_new_comp_reject", 0),
        }

        logger.info("All quality metrics computed (18 metrics)")
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

        # coder_confidence is a multi-field dict, not a single float, so it doesn't
        # map to QualityMetric (float value). compute_all() stores it in results["coder_confidence"]
        # which is written to the JSON results file — no separate DB persistence needed.
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

        # Persist metric
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

        Replaces the old segment-level coverage metric (which was always ~100%).

        Args:
            total_dropped: candidates dropped across all batches (from orchestrator)
            total_valid_candidates: candidates that passed validation (from orchestrator)
            dropped_per_segment: {segment_id: n_dropped} mapping (from orchestrator)

        Returns:
            {
                "total_segments": int,
                "segments_with_codes": int,
                "distribution": {mean, median, min, max, p25, p75},
                "per_segment": [{segment_id, density, char_count, covered_chars}],
                "high_density": [{segment_id, density, preview}],  # density > 0.80
                "low_density": [{segment_id, density, preview}],   # density < 0.20
                "drop_rate": {
                    "overall_rate": float,
                    "total_dropped": int,
                    "total_raw_candidates": int,
                    "segments_with_drops": int,
                    "top_drop_segments": [{segment_id, n_dropped, preview}],
                },
            }
        """
        dropped_per_segment = dropped_per_segment or {}
        # Get all segments
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

        # Distribution stats
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

        # Flag high and low density (top 3 each)
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

        # Per-segment drop info: join drop counts with segment previews
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

        # Persist metrics
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
                # Overlapping or adjacent — extend
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        return sum(end - start for start, end in merged)

    def compute_meaning_saturation_v2(
        self,
        ic_creation_segments: Dict[str, int],
        total_segments: int,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Per-theme meaning saturation with two dimensions:

        1. Breadth — when did ICs for this theme emerge?
           Formula: last_ic_segment / (total_segments - 1)
           Low = saturated early (all ICs discovered quickly)
           High = still discovering (new ICs appearing late in dataset)

        2. Spread — semantic diversity of ICs within the theme
           Formula: avg pairwise cosine distance between IC embeddings
           Low = ICs tightly clustered (semantically narrow)
           High = ICs dispersed (conceptually diverse)

        Returns:
            {theme_name: {breadth, spread, ic_count, last_ic_segment, ics: [...]}}
        """
        final_themes, _ = self.theme_repo.get_latest_round()
        results: Dict[str, Dict[str, Any]] = {}

        # Fallback: if ic_creation_segments is empty, reconstruct from DB
        if not ic_creation_segments:
            ic_creation_segments = self._reconstruct_ic_creation_segments()

        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)

            # ── Breadth ──
            seg_indices = []
            ic_details = []
            embeddings = []

            for ic_id in ic_ids:
                ic = self.ic_repo.get_by_id(ic_id)
                if not ic:
                    continue

                seg_idx = ic_creation_segments.get(ic_id)
                if seg_idx is not None:
                    seg_indices.append(seg_idx)
                    ic_details.append({
                        "ic_name": ic.name,
                        "segment_introduced": seg_idx,
                    })

                if ic.embedding_json:
                    embeddings.append(ic.embedding_json)

            if seg_indices and total_segments > 1:
                last_seg = max(seg_indices)
                breadth = last_seg / (total_segments - 1)
            elif seg_indices:
                breadth = 0.0  # single segment → trivially saturated
            else:
                breadth = 0.0

            # ── Spread ──
            spread = self._compute_pairwise_spread(embeddings)

            # Persist
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.MEANING_SATURATION,
                entity_id=theme.id,
                entity_type="theme_breadth",
                value=breadth,
            ))
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.MEANING_SATURATION,
                entity_id=theme.id,
                entity_type="theme_spread",
                value=spread,
            ))

            results[theme.name] = {
                "breadth": round(breadth, 3),
                "spread": round(spread, 3),
                "ic_count": len(ic_details),
                "last_ic_segment": max(seg_indices) if seg_indices else -1,
                "ics": ic_details,
            }

        logger.info(f"Meaning saturation v2 (breadth+spread) computed for {len(results)} themes")
        return results

    def _compute_pairwise_spread(self, embeddings: List[List[float]]) -> float:
        """
        Average pairwise cosine distance between embeddings.

        Returns 0.0 for < 2 embeddings (single-IC themes have no spread).
        """
        if len(embeddings) < 2:
            return 0.0

        total_dist = 0.0
        pair_count = 0
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = cosine_similarity(embeddings[i], embeddings[j])
                total_dist += (1.0 - sim)
                pair_count += 1

        return total_dist / pair_count if pair_count > 0 else 0.0

    def _reconstruct_ic_creation_segments(self) -> Dict[str, int]:
        """
        Fallback: reconstruct IC creation segment indices from DB.

        For each IC, finds its first VerbatimQuote and maps to segment_index.
        Used when ic_creation_segments isn't passed from orchestrator
        (e.g., metrics recomputed from an existing DB).
        """
        codebook = self.ic_repo.get_all_active()
        result: Dict[str, int] = {}

        for ic in codebook:
            quotes = self.vq_repo.get_all_for_ic(ic.id)
            if not quotes:
                continue
            # Get the segment for the first quote
            first_quote = quotes[0]
            seg = self.seg_repo.get_by_id(first_quote.segment_id)
            if seg:
                result[ic.id] = seg.segment_index

        return result

    def compute_theme_coherence(self) -> Dict[str, float]:
        """
        Per-theme coherence: average pairwise IC cosine similarity.

        Higher = ICs in the theme are semantically related.
        Reuses EmbeddingService.compute_theme_coherence().

        Only uses themes from the latest synthesis round.

        Returns {theme_name: coherence_score}.
        """
        final_themes, _ = self.theme_repo.get_latest_round()

        coherence_map: Dict[str, float] = {}

        for theme in final_themes:
            theme_id = theme.id
            theme_name = theme.name

            ic_ids = self.theme_repo.get_ics_for_theme(theme_id)
            if len(ic_ids) == 0:
                continue  # Skip dissolved themes (0 ICs)
            if len(ic_ids) < 2:
                coherence_map[theme_name] = 1.0  # Single-IC theme is trivially coherent
                continue

            score = self.embedding_service.compute_theme_coherence(ic_ids)
            coherence_map[theme_name] = score

            # Persist
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.THEME_COHERENCE,
                entity_id=theme_id,
                entity_type="theme",
                value=score,
            ))

        logger.info(f"Theme coherence computed for {len(coherence_map)} themes")
        return coherence_map

    def compute_theme_distinctness(self) -> List[Tuple[str, str, float]]:
        """
        Pairwise theme distinctness: inter-centroid cosine similarity.

        Lower = more distinct themes. Flags pairs > 0.70.
        Only uses themes from the latest synthesis round.

        Returns list of (theme_a_name, theme_b_name, similarity) for all pairs.
        """
        final_themes, _ = self.theme_repo.get_latest_round()

        if len(final_themes) < 2:
            return []

        # Build theme centroids (skip dissolved themes with 0 ICs)
        theme_data: List[Tuple[str, str, List[str]]] = []  # (id, name, [ic_ids])
        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)
            if not ic_ids:
                continue  # Skip dissolved themes
            theme_data.append((theme.id, theme.name, ic_ids))

        # Compute centroids
        centroids: List[Tuple[str, str, Optional[List[float]]]] = []
        for theme_id, theme_name, ic_ids in theme_data:
            embeddings = []
            for ic_id in ic_ids:
                ic = self.ic_repo.get_by_id(ic_id)
                if ic and ic.embedding_json:
                    embeddings.append(ic.embedding_json)

            if not embeddings:
                centroids.append((theme_id, theme_name, None))
                continue

            dim = len(embeddings[0])
            centroid = [
                sum(emb[d] for emb in embeddings) / len(embeddings)
                for d in range(dim)
            ]
            centroids.append((theme_id, theme_name, centroid))

        # Compute pairwise similarities
        pairs: List[Tuple[str, str, float]] = []
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                _, name_a, centroid_a = centroids[i]
                _, name_b, centroid_b = centroids[j]

                if centroid_a is None or centroid_b is None:
                    continue

                sim = cosine_similarity(centroid_a, centroid_b)
                pairs.append((name_a, name_b, sim))

                if sim > 0.70:
                    logger.warning(
                        f"Theme overlap: \"{name_a}\" ↔ \"{name_b}\" (sim={sim:.3f})"
                    )

        # Persist overall distinctness (avg inter-theme similarity)
        if pairs:
            avg_sim = sum(s for _, _, s in pairs) / len(pairs)
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.THEME_DISTINCTNESS,
                value=avg_sim,
            ))

        logger.info(f"Theme distinctness: {len(pairs)} pairs computed")
        return pairs

    # ── NEW METRICS ───────────────────────────────────────────────────────────

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
            n = len(quotes)
            quote_counts.append(n)
            if n == 1:
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

        # Persist
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

        # Persist
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

        # Persist
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

            # Map LLM recommendations to direction
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

        # Persist
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

    def compute_coherence_normalized(
        self, raw_coherence: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Coherence Normalization: raw theme coherence / all-IC baseline.

        The baseline is the average pairwise cosine similarity across ALL
        active ICs (regardless of theme assignment). This represents what
        you'd get by random grouping.

        Normalized = raw_coherence / baseline
        - >1.0 = theme is more coherent than random (good)
        - ~1.0 = no better than random grouping (suspect)
        - <1.0 = worse than random (problematic — shouldn't normally happen)

        Makes coherence scores comparable across embedding models and runs.
        """
        if not raw_coherence:
            return {"baseline": 0.0, "per_theme": {}, "avg_normalized": 0.0}

        # Compute baseline: all-IC pairwise similarity
        codebook = self.ic_repo.get_all_active()
        all_embeddings = [
            ic.embedding_json for ic in codebook
            if ic.embedding_json is not None
        ]

        baseline = 0.0
        if len(all_embeddings) >= 2:
            total_sim = 0.0
            pair_count = 0
            for i in range(len(all_embeddings)):
                for j in range(i + 1, len(all_embeddings)):
                    total_sim += cosine_similarity(all_embeddings[i], all_embeddings[j])
                    pair_count += 1
            baseline = total_sim / pair_count if pair_count > 0 else 0.0

        # Normalize each theme's coherence
        per_theme: Dict[str, Dict[str, float]] = {}
        normalized_values = []

        for theme_name, raw_score in raw_coherence.items():
            if baseline > 0:
                norm = raw_score / baseline
            else:
                norm = 0.0
            per_theme[theme_name] = {
                "raw": round(raw_score, 3),
                "normalized": round(norm, 3),
            }
            normalized_values.append(norm)

            # Persist per-theme normalized coherence
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.COHERENCE_NORMALIZED,
                entity_type="theme",
                value=norm,
            ))

        avg_normalized = (
            sum(normalized_values) / len(normalized_values)
            if normalized_values else 0.0
        )

        result = {
            "baseline": round(baseline, 3),
            "avg_normalized": round(avg_normalized, 3),
            "per_theme": per_theme,
        }
        logger.info(
            f"Coherence normalized: baseline={baseline:.3f}, "
            f"avg_norm={avg_normalized:.3f} across {len(per_theme)} themes"
        )
        return result

    def compute_cross_theme_ic_sharing(self) -> Dict[str, Any]:
        """
        Cross-Theme IC Sharing: fraction of ICs that appear in 2+ themes.

        In Braun & Clarke thematic analysis, M:N IC↔Theme mapping is valid.
        This metric tracks how much ICs are shared.

        Key outputs:
        - sharing_ratio: ICs in 2+ themes / total ICs
        - shared_ics: [{ic_name, theme_count, themes: [name, ...]}]

        Interpretation:
        - 0.0 = no sharing, themes are fully disjoint
        - 0.05-0.15 = healthy cross-cutting concepts
        - >0.25 = excessive sharing, themes may lack conceptual boundaries
        """
        final_themes, _ = self.theme_repo.get_latest_round()
        if not final_themes:
            return {"sharing_ratio": 0.0, "total_ics": 0, "shared_count": 0,
                    "shared_ics": []}

        # Build IC → [theme_names] mapping
        ic_to_themes: Dict[str, List[str]] = {}
        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)
            for ic_id in ic_ids:
                if ic_id not in ic_to_themes:
                    ic_to_themes[ic_id] = []
                ic_to_themes[ic_id].append(theme.name)

        total_ics = len(ic_to_themes)
        shared_ics = []

        for ic_id, theme_names in ic_to_themes.items():
            if len(theme_names) >= 2:
                ic = self.ic_repo.get_by_id(ic_id)
                ic_name = ic.name if ic else ic_id
                shared_ics.append({
                    "ic_name": ic_name,
                    "theme_count": len(theme_names),
                    "themes": theme_names,
                })

        shared_count = len(shared_ics)
        sharing_ratio = shared_count / total_ics if total_ics > 0 else 0.0

        # Persist
        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.CROSS_THEME_IC_SHARING,
            value=sharing_ratio,
        ))

        result = {
            "sharing_ratio": round(sharing_ratio, 3),
            "total_ics": total_ics,
            "shared_count": shared_count,
            "shared_ics": shared_ics,
        }
        logger.info(
            f"Cross-theme IC sharing: {shared_count}/{total_ics} "
            f"({sharing_ratio:.1%}) ICs in 2+ themes"
        )
        return result

    # ── P4c: IC Stability Index ──────────────────────────────────────────────

    def compute_ic_stability(
        self, stability_scores: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Measures how much IC definitions changed during refinement.

        Pre/post refinement embedding cosine similarity captured per IC.
        Per-IC drift score: 1.0 = unchanged, 0.7 = major rewrite.

        Aggregate:
        - mean_stability: mean across refined ICs
        - substantially_rewritten: count of ICs with stability < 0.85

        Interpretation:
        - High (~0.95+): coder agent's initial extraction was precise, refinement is polish
        - Low (~0.80): initial definitions were imprecise, refinement is corrective

        Args:
            stability_scores: List of {ic_name, stability} from orchestrator refinement.

        Returns {
            "mean_stability": float,
            "refined_count": int,
            "substantially_rewritten": int,
            "per_ic": [{ic_name, stability}],
        }
        """
        if not stability_scores:
            return {
                "mean_stability": 1.0,
                "refined_count": 0,
                "substantially_rewritten": 0,
                "per_ic": [],
            }

        mean_stability = (
            sum(s["stability"] for s in stability_scores)
            / len(stability_scores)
        )
        substantially_rewritten = sum(
            1 for s in stability_scores if s["stability"] < 0.85
        )

        # Persist
        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.IC_STABILITY,
            value=mean_stability,
        ))

        result = {
            "mean_stability": round(mean_stability, 4),
            "refined_count": len(stability_scores),
            "substantially_rewritten": substantially_rewritten,
            "per_ic": sorted(stability_scores, key=lambda x: x["stability"]),
        }
        logger.info(
            f"IC stability: mean={mean_stability:.4f}, "
            f"{substantially_rewritten}/{len(stability_scores)} substantially rewritten"
        )
        return result

    # ── P4a: Orphaned IC Count ─────────────────────────────────────────────

    def compute_orphaned_ic_count(self) -> Dict[str, Any]:
        """
        Count ICs not assigned to any theme.

        After dissolution, some ICs may become orphaned (no theme assignment).
        Simple: count active ICs in codebook minus ICs in theme_ics table.

        Returns {
            "total_active_ics": int,
            "themed_ics": int,
            "orphaned_count": int,
            "orphaned_ratio": float,
            "orphaned_names": [str],
        }
        """
        codebook = self.ic_repo.get_all_active()
        total_active = len(codebook)

        # Get all IC IDs that have at least one theme assignment
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ic_id FROM theme_ics"
            ).fetchall()
        themed_ic_ids = {r["ic_id"] for r in rows}

        orphaned = []
        for ic in codebook:
            if ic.id not in themed_ic_ids:
                orphaned.append(ic.name)

        orphaned_count = len(orphaned)
        orphaned_ratio = orphaned_count / total_active if total_active > 0 else 0.0

        result = {
            "total_active_ics": total_active,
            "themed_ics": total_active - orphaned_count,
            "orphaned_count": orphaned_count,
            "orphaned_ratio": round(orphaned_ratio, 3),
            "orphaned_names": orphaned,
        }
        logger.info(
            f"Orphaned ICs: {orphaned_count}/{total_active} "
            f"({orphaned_ratio:.1%}) not in any theme"
        )
        return result

    # ── P4b: Thematic Coverage Ratio ───────────────────────────────────────

    def compute_thematic_coverage(self) -> Dict[str, Any]:
        """
        What fraction of total quotes are reachable through the thematic structure?

        After dissolution, some quotes become orphaned (their IC has no theme).
        Formula: quotes_in_themed_ICs / total_quotes.

        Target: >95%.

        Returns {
            "total_quotes": int,
            "covered_quotes": int,
            "coverage_ratio": float,
        }
        """
        # Get all themed IC IDs
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ic_id FROM theme_ics"
            ).fetchall()
        themed_ic_ids = {r["ic_id"] for r in rows}

        # Count quotes per IC
        codebook = self.ic_repo.get_all_active()
        total_quotes = 0
        covered_quotes = 0

        for ic in codebook:
            quotes = self.vq_repo.get_all_for_ic(ic.id)
            q_count = len(quotes)
            total_quotes += q_count
            if ic.id in themed_ic_ids:
                covered_quotes += q_count

        coverage = covered_quotes / total_quotes if total_quotes > 0 else 1.0

        # Persist
        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.THEMATIC_COVERAGE,
            value=coverage,
        ))

        result = {
            "total_quotes": total_quotes,
            "covered_quotes": covered_quotes,
            "coverage_ratio": round(coverage, 3),
        }
        logger.info(
            f"Thematic coverage: {covered_quotes}/{total_quotes} "
            f"({coverage:.1%}) quotes reachable through themes"
        )
        return result

    # ── P4d: Cross-Review Convergence ──────────────────────────────────────

    def compute_cross_review_convergence(self) -> Dict[str, Any]:
        """
        For each IC, count unique source documents that contributed quotes.

        An IC confirmed by 8 reviews is robust; an IC from 1 review is unconfirmed.
        This is an inter-rater reliability proxy — independent data sources arriving
        at the same concept.

        Requires joining: quotes → segments → documents to trace provenance.

        Returns {
            "mean_docs_per_ic": float,
            "confirmed_ratio": float,  # % of ICs in 2+ docs
            "strong_convergence_ratio": float,  # % of ICs in 3+ docs
            "per_ic": [{ic_name, doc_count}],
        }
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
            # Trace quotes → segments → documents
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

        # Persist
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

    # ── P4e: Theme Sentiment Purity ───────────────────────────────────────────

    def compute_sentiment_purity(self) -> Dict[str, Any]:
        """
        Per-theme sentiment purity: dominant_sentiment_count / total_quotes_with_sentiment.

        Each VerbatimQuote carries a sentiment (positive/negative/neutral/mixed)
        assigned by the coder agent. For each theme, we trace:
        theme → ICs → quotes → sentiment, then compute the distribution.

        Purity = count_of_dominant_sentiment / total_quotes_with_sentiment.
        Flagged when purity < 0.70.

        This is a SIGNAL, not a gate. Mixed-sentiment themes may be legitimate
        contested phenomena (e.g., "Difficulty Polarisation").

        Returns {
            "per_theme": {
                theme_name: {
                    "purity": float,
                    "dominant": str,
                    "distribution": {"positive": int, "negative": int, "neutral": int, "mixed": int},
                    "total_with_sentiment": int,
                    "flagged": bool,
                }
            },
            "avg_purity": float,
            "flagged_count": int,
        }
        """
        final_themes, _ = self.theme_repo.get_latest_round()
        if not final_themes:
            return {"per_theme": {}, "avg_purity": 1.0, "flagged_count": 0}

        per_theme: Dict[str, Dict[str, Any]] = {}
        purities = []
        flagged_count = 0

        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)
            if not ic_ids:
                continue  # Skip dissolved themes

            # Collect sentiment counts from all quotes across this theme's ICs
            sentiment_counts: Dict[str, int] = {
                "positive": 0, "negative": 0, "neutral": 0, "mixed": 0,
            }
            total_with_sentiment = 0

            for ic_id in ic_ids:
                quotes = self.vq_repo.get_all_for_ic(ic_id)
                for q in quotes:
                    if q.sentiment and q.sentiment in sentiment_counts:
                        sentiment_counts[q.sentiment] += 1
                        total_with_sentiment += 1

            if total_with_sentiment == 0:
                per_theme[theme.name] = {
                    "purity": 1.0,
                    "dominant": "unknown",
                    "distribution": sentiment_counts,
                    "total_with_sentiment": 0,
                    "flagged": False,
                }
                continue

            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)
            dominant_count = sentiment_counts[dominant_sentiment]
            purity = dominant_count / total_with_sentiment

            flagged = purity < 0.70
            if flagged:
                flagged_count += 1

            purities.append(purity)

            per_theme[theme.name] = {
                "purity": round(purity, 3),
                "dominant": dominant_sentiment,
                "distribution": sentiment_counts,
                "total_with_sentiment": total_with_sentiment,
                "flagged": flagged,
            }

            # Persist per-theme
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.SENTIMENT_PURITY,
                entity_id=theme.id,
                entity_type="theme",
                value=purity,
            ))

        avg_purity = sum(purities) / len(purities) if purities else 1.0

        result = {
            "per_theme": per_theme,
            "avg_purity": round(avg_purity, 3),
            "flagged_count": flagged_count,
        }
        logger.info(
            f"Sentiment purity: avg={avg_purity:.3f}, "
            f"{flagged_count} themes flagged (<0.70)"
        )
        return result

    # ── P5: Quote Coverage Per IC ─────────────────────────────────────────────

    def compute_quote_coverage_per_ic(self) -> Dict[str, Any]:
        """
        Per-IC quote coverage: what fraction of each segment's characters are
        covered by that IC's evidence quotes.

        For ICs with multiple quotes from the SAME segment, uses interval union
        (inclusion-exclusion) to avoid double-counting overlapping spans:
            covered = union of all [span_start, span_end] intervals
        Quotes from DIFFERENT segments are independent — each gets its own ratio.

        Coverage ratio = union_chars / segment_char_count

        Returns {
            "per_ic": [
                {
                    "ic_id": str,
                    "ic_name": str,
                    "coverages": [float, ...],   # one per (ic, segment) pair
                    "mean_coverage": float,
                    "max_coverage": float,
                    "high_coverage_segments": int,  # segments where coverage > 0.70
                },
                ...
            ],
            "overall_mean_pct": float,  # mean coverage as percentage (0–100)
            "overall_max_pct": float,   # max coverage as percentage (0–100)
            "high_coverage_count": int,   # (ic, segment) pairs > 70%
            "total_ic_segment_pairs": int,
        }
        """
        # Single query: all quotes with spans
        with self.db.connect() as conn:
            quote_rows = conn.execute(
                "SELECT ic_id, segment_id, span_start, span_end "
                "FROM verbatim_quotes"
            ).fetchall()
            seg_rows = conn.execute(
                "SELECT id, char_count FROM segments"
            ).fetchall()

        seg_lengths: Dict[str, int] = {r["id"]: r["char_count"] for r in seg_rows}

        # Group spans: {ic_id: {segment_id: [(start, end), ...]}}
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
        # Convert to percentage for storage — display and JSON are now on the same scale.
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
