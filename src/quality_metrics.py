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
            flagged = norm < coherence_threshold and ic_count >= 2

            per_theme[theme_name] = {
                "raw": round(raw_score, 3),
                "normalized": round(norm, 3),
                "ic_count": ic_count,
                "theme_id": theme_id,
                "flagged": flagged,
            }

            if flagged:
                flagged_themes.append({
                    "theme_id": theme_id,
                    "theme_name": theme_name,
                    "normalized": round(norm, 3),
                    "raw": round(raw_score, 3),
                    "ic_count": ic_count,
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

        logger.info("All quality metrics computed (12 metrics)")
        return results

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

        # Build theme centroids
        theme_data: List[Tuple[str, str, List[str]]] = []  # (id, name, [ic_ids])
        for theme in final_themes:
            ic_ids = self.theme_repo.get_ics_for_theme(theme.id)
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

        Agreement = both say NEW or both say MERGE/SUBCODE.

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
            else:  # MERGE, SUBCODE
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
