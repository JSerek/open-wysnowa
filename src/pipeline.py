"""
EQD-AI Full Pipeline Orchestrator.

Ties together all layers:
  Layer 0: Documents → Segments (preprocessing)
  Layer 1: Segments → IC Candidates → Codebook (coder + comparator + HIL)
           → Codebook Sign-Off (HIL Level 2)
  Layer 2: Codebook → Theme Proposals → Iterate (max 3 rounds) → Final Themes
  Layer 3: Compute all 6 quality metrics → Generate report

Entry point: EQDPipeline.run(documents)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.category_agent import CategoryAgent
from src.codebook_signoff import CodebookSignoff
from src.config import EQDConfig, ModelClient, load_config
from src.db import CategoryRepo, Database, DecisionLogRepo, InitialCodeRepo, VerbatimQuoteRepo
from src.embeddings import EmbeddingService
from src.models import Document, ThemeProposal
from src.orchestrator import Layer1Orchestrator
from src.preprocessing import preprocess_documents
from src.quality_metrics import QualityMetricsEngine
from src.quality_report import display_codebook_report, display_final_report, display_theme_report
from src.synthesizer_agent import SynthesizerAgent
from src.theme_hil import (
    collect_all_feedback,
    display_all_themes,
    display_revision_diff,
    prompt_signoff_themes,
)

logger = logging.getLogger(__name__)

MAX_THEME_ROUNDS = 3


class EQDPipeline:
    """
    Full EQD-AI analysis pipeline.

    Orchestrates all 4 layers from raw documents to final report.
    Supports both interactive (HIL) and automated modes.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        db_path: str = "eqa_ai.db",
    ):
        # Load config
        self.config = load_config(config_path)

        # Init DB
        self.db = Database(db_path)
        self.db.init_schema()

        # Init shared services
        self.model_client = ModelClient(self.config)
        self.embedding_service = EmbeddingService(self.model_client, self.db)

        # Init layer components
        self.layer1 = Layer1Orchestrator(self.model_client, self.db, self.config)
        self.signoff = CodebookSignoff(self.db, self.embedding_service)
        self.synthesizer = SynthesizerAgent(self.model_client, self.db, self.config)
        self.quality_engine = QualityMetricsEngine(self.db, self.embedding_service)
        self.category_agent = CategoryAgent(self.model_client, self.db, self.config)

    def run(
        self,
        documents: List[Document],
        enable_hil: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the full EQD-AI analysis pipeline.

        Args:
            documents: raw Document objects to analyse
            enable_hil: if True, interactive review at all HIL checkpoints

        Returns comprehensive results dict.
        """
        results: Dict[str, Any] = {
            "layer0": {},
            "layer1": {},
            "codebook_signoff": False,
            "layer2": {},
            "layer3": {},
        }

        # ── Layer 0: Preprocessing ────────────────────────────────────────
        logger.info(f"[PIPELINE] Layer 0: Preprocessing {len(documents)} documents")
        segments = preprocess_documents(documents, self.db)
        results["layer0"] = {
            "documents": len(documents),
            "segments": len(segments),
        }
        logger.info(f"[PIPELINE] Layer 0 complete: {len(segments)} segments")

        if not segments:
            logger.warning("No segments produced — stopping pipeline")
            return results

        # ── Layer 1: IC Extraction ────────────────────────────────────────
        logger.info("[PIPELINE] Layer 1: IC extraction + codebook building")
        layer1_summary = self.layer1.run(segments, enable_hil=enable_hil)
        results["layer1"] = layer1_summary
        logger.info(
            f"[PIPELINE] Layer 1 complete: {layer1_summary.get('new_ics_created', 0)} ICs, "
            f"{layer1_summary.get('batches_processed', 0)} batches"
        )

        # ── Codebook Sign-Off (HIL Level 2) ──────────────────────────────
        if enable_hil:
            logger.info("[PIPELINE] Codebook sign-off (HIL Level 2)")
            signed_off = self.signoff.run()
            results["codebook_signoff"] = signed_off

            if not signed_off:
                logger.warning("Codebook not signed off — stopping pipeline")
                return results
        else:
            results["codebook_signoff"] = True
            logger.info("[PIPELINE] Codebook sign-off skipped (HIL disabled)")

        # ── Layer 2: Theme Synthesis ──────────────────────────────────────
        logger.info("[PIPELINE] Layer 2: Theme synthesis")
        themes, round_number = self._run_layer2(enable_hil)
        results["layer2"] = {
            "themes_proposed": len(themes),
            "rounds": round_number,
        }
        logger.info(f"[PIPELINE] Layer 2 complete: {len(themes)} themes in {round_number} round(s)")

        # Persist final themes
        if themes:
            persisted = self.synthesizer.persist_themes(themes, round_number)
            results["layer2"]["themes_persisted"] = len(persisted)

        # ── Layer 2.5: Post-Synthesis Coherence Gate ──────────────────
        if themes:
            from src.hil import display_flagged_theme, prompt_theme_dissolve
            from src.db import ThemeRepo as _ThemeRepo

            logger.info("[PIPELINE] Coherence quality gate")
            coherence_eval = self.quality_engine.evaluate_theme_coherence(
                coherence_threshold=self.config.processing.coherence_threshold,
                coherence_threshold_small=self.config.processing.coherence_threshold_small,
            )
            flagged = coherence_eval.get("flagged_themes", [])

            dissolved_themes = []  # track for IC redistribution
            if flagged:
                dissolved_count = 0
                theme_repo = _ThemeRepo(self.db)
                if enable_hil:
                    for ft in flagged:
                        display_flagged_theme(ft)
                        if prompt_theme_dissolve():
                            # Collect orphaned ICs before dissolving
                            orphaned_ics = theme_repo.get_ics_for_theme(ft["theme_id"])
                            theme_repo.dissolve_theme(ft["theme_id"])
                            dissolved_themes.append({
                                "theme_name": ft["theme_name"],
                                "orphaned_ic_ids": orphaned_ics,
                            })
                            dissolved_count += 1
                            logger.info(f"[COHERENCE] Dissolved '{ft['theme_name']}' ({len(orphaned_ics)} ICs orphaned)")
                else:
                    for ft in flagged:
                        orphaned_ics = theme_repo.get_ics_for_theme(ft["theme_id"])
                        theme_repo.dissolve_theme(ft["theme_id"])
                        dissolved_themes.append({
                            "theme_name": ft["theme_name"],
                            "orphaned_ic_ids": orphaned_ics,
                        })
                        dissolved_count += 1
                        logger.info(
                            f"[COHERENCE] Auto-dissolved '{ft['theme_name']}' "
                            f"(norm={ft['normalized']:.3f}, {len(orphaned_ics)} ICs orphaned)"
                        )
                results["layer2"]["themes_dissolved"] = dissolved_count

                # ── Orphaned IC Redistribution ──────────────────────────
                if dissolved_themes:
                    redistributed, unassigned = self._redistribute_orphaned_ics(
                        dissolved_themes, theme_repo
                    )
                    results["layer2"]["ics_redistributed"] = redistributed
                    results["layer2"]["ics_unassigned"] = len(unassigned)
                    if unassigned:
                        results["layer2"]["unassigned_ic_ids"] = unassigned

            results["layer2"]["coherence_gate"] = coherence_eval
            results["layer2"]["dissolved_theme_names"] = [
                dt["theme_name"] for dt in dissolved_themes
            ]

        # ── Category Synthesis ──────────────────────────────────────────
        if themes:
            logger.info("[PIPELINE] Category synthesis")
            categories_result = self._run_category_synthesis()
            results["categories"] = categories_result
            logger.info(
                f"[PIPELINE] Category synthesis complete: "
                f"{categories_result.get('categories_created', 0)} categories"
            )

        # ── Layer 3: Quality Metrics + Report ─────────────────────────────
        logger.info("[PIPELINE] Layer 3: Quality metrics computation")
        its_history = self.layer1.its_tracker.history
        quality_results = self.quality_engine.compute_all(
            its_history=its_history,
            ic_creation_segments=layer1_summary.get("ic_creation_segments", {}),
            total_segments=layer1_summary.get("total_segments", 0),
            triage_stats=layer1_summary.get("triage_stats", {}),
            batch_merge_rates=layer1_summary.get("batch_merge_rates", []),
            grey_zone_decisions=layer1_summary.get("grey_zone_decisions", []),
            total_dropped=layer1_summary.get("total_dropped", 0),
            total_candidates=layer1_summary.get("total_candidates", 0),
            dropped_per_segment=layer1_summary.get("dropped_per_segment", {}),
            ic_stability_scores=layer1_summary.get("ic_stability_scores", []),
        )

        # Add cumulative saturation curve from Layer 1
        sat_curve = layer1_summary.get("saturation_curve", [])
        quality_results["saturation_curve"] = [
            pt.model_dump() if hasattr(pt, "model_dump") else pt
            for pt in sat_curve
        ]

        results["layer3"] = quality_results

        # Export the analytical product: Theme → IC → Quote hierarchy
        results["thematic_structure"] = self.export_thematic_structure()

        # Display reports
        if enable_hil:
            display_final_report(
                quality_results,
                decision_log_summary=self._get_decision_summary(),
            )
        else:
            logger.info("Final report display skipped (HIL disabled)")

        logger.info("[PIPELINE] Complete")
        return results

    # ── Layer 2 Implementation ────────────────────────────────────────────────

    def _run_layer2(
        self,
        enable_hil: bool,
    ) -> tuple[List[ThemeProposal], int]:
        """
        Run Layer 2: theme synthesis with iterative feedback.

        Returns (final_themes, round_number).
        Max 3 rounds of iteration.
        """
        # Round 1: initial synthesis
        themes = self.synthesizer.synthesize()
        if not themes:
            return [], 0

        round_number = 1
        ic_quote_counts = self._get_ic_quote_counts()

        if not enable_hil:
            return themes, round_number

        # Interactive iteration loop (max 3 rounds)
        while round_number <= MAX_THEME_ROUNDS:
            # Display current themes
            coherence_scores = self._compute_live_coherence(themes)
            distinctness_warnings = self._compute_live_distinctness(themes)

            display_all_themes(
                themes, ic_quote_counts,
                coherence_scores=coherence_scores,
                distinctness_warnings=distinctness_warnings,
            )

            # Check: sign off or provide feedback?
            if round_number > 1:
                # For rounds 2+, show the diff first
                pass  # diff was already shown after revision

            signed_off = prompt_signoff_themes()
            if signed_off:
                logger.info(f"Themes signed off at round {round_number}")
                break

            if round_number >= MAX_THEME_ROUNDS:
                logger.warning(
                    f"Max theme rounds ({MAX_THEME_ROUNDS}) reached. "
                    f"Finalising current themes."
                )
                break

            # Collect feedback
            feedback = collect_all_feedback(
                themes, ic_quote_counts,
                coherence_scores=coherence_scores,
            )

            if not feedback:
                logger.info("No feedback provided — keeping current themes")
                break

            # Revise
            old_themes = themes
            revised = self.synthesizer.revise(themes, feedback)
            if revised is None:
                logger.error("Revision failed — keeping current themes")
                break

            themes = revised
            round_number += 1

            # Show revision diff
            display_revision_diff(old_themes, themes)

        return themes, round_number

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_ic_quote_counts(self) -> Dict[str, int]:
        """Get {ic_name: quote_count} for all active ICs."""
        ic_repo = InitialCodeRepo(self.db)
        vq_repo = VerbatimQuoteRepo(self.db)

        codebook = ic_repo.get_all_active()
        counts: Dict[str, int] = {}
        for ic in codebook:
            quotes = vq_repo.get_all_for_ic(ic.id)
            counts[ic.name] = len(quotes)
        return counts

    def _compute_live_coherence(
        self, themes: List[ThemeProposal]
    ) -> Dict[str, float]:
        """
        Compute coherence for theme proposals (before persistence).

        Looks up IC IDs by name, then delegates to EmbeddingService.
        """
        ic_repo = InitialCodeRepo(self.db)
        active_ics = ic_repo.get_all_active()
        name_to_id = {ic.name: ic.id for ic in active_ics}

        coherence_map: Dict[str, float] = {}
        for theme in themes:
            ic_ids = [
                name_to_id[name] for name in theme.constituent_ic_names
                if name in name_to_id
            ]
            if len(ic_ids) < 2:
                coherence_map[theme.name] = 1.0
            else:
                coherence_map[theme.name] = self.embedding_service.compute_theme_coherence(ic_ids)

        return coherence_map

    def _compute_live_distinctness(
        self, themes: List[ThemeProposal]
    ) -> List[tuple[str, str, float]]:
        """
        Compute distinctness warnings for theme proposals.

        Returns pairs with similarity > 0.70.
        """
        from src.embeddings import cosine_similarity

        ic_repo = InitialCodeRepo(self.db)
        active_ics = ic_repo.get_all_active()
        name_to_id = {ic.name: ic.id for ic in active_ics}

        # Build centroids
        centroids: List[tuple[str, Optional[List[float]]]] = []
        for theme in themes:
            embeddings = []
            for ic_name in theme.constituent_ic_names:
                ic_id = name_to_id.get(ic_name)
                if ic_id:
                    ic = ic_repo.get_by_id(ic_id)
                    if ic and ic.embedding_json:
                        embeddings.append(ic.embedding_json)

            if not embeddings:
                centroids.append((theme.name, None))
                continue

            dim = len(embeddings[0])
            centroid = [
                sum(emb[d] for emb in embeddings) / len(embeddings)
                for d in range(dim)
            ]
            centroids.append((theme.name, centroid))

        # Find overlapping pairs
        warnings: List[tuple[str, str, float]] = []
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                name_a, centroid_a = centroids[i]
                name_b, centroid_b = centroids[j]
                if centroid_a is None or centroid_b is None:
                    continue
                sim = cosine_similarity(centroid_a, centroid_b)
                if sim > 0.70:
                    warnings.append((name_a, name_b, sim))

        return warnings

    def _redistribute_orphaned_ics(
        self,
        dissolved_themes: List[Dict],
        theme_repo,
        min_similarity: float = 0.5,
    ) -> tuple[int, List[str]]:
        """
        Redistribute orphaned ICs from dissolved themes to the nearest surviving theme.

        For each orphaned IC, compute embedding similarity to each surviving theme's
        centroid. Assign to the best match if above min_similarity, otherwise mark as
        unassigned.

        Returns (redistributed_count, unassigned_ic_ids).
        """
        from src.embeddings import cosine_similarity

        # Collect all orphaned IC IDs (only those not in any other theme)
        all_orphaned = []
        for dt in dissolved_themes:
            for ic_id in dt["orphaned_ic_ids"]:
                # Check if this IC is still assigned to another theme
                with self.db.connect() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM theme_ics WHERE ic_id=?", (ic_id,)
                    ).fetchone()
                    if row["cnt"] == 0:
                        all_orphaned.append(ic_id)

        if not all_orphaned:
            return 0, []

        # Get surviving themes and compute centroids
        surviving_themes, _ = theme_repo.get_latest_round()
        theme_centroids: Dict[str, List[float]] = {}
        for theme in surviving_themes:
            ic_ids = theme_repo.get_ics_for_theme(theme.id)
            if not ic_ids:
                continue  # dissolved theme (0 ICs)
            embeddings = []
            for ic_id in ic_ids:
                ic = self.layer1.ic_repo.get_by_id(ic_id)
                if ic and ic.embedding_json:
                    embeddings.append(ic.embedding_json)
            if embeddings:
                # Compute centroid as mean embedding
                dim = len(embeddings[0])
                centroid = [
                    sum(e[d] for e in embeddings) / len(embeddings)
                    for d in range(dim)
                ]
                theme_centroids[theme.id] = centroid

        if not theme_centroids:
            return 0, all_orphaned

        redistributed = 0
        unassigned = []

        for ic_id in all_orphaned:
            ic = self.layer1.ic_repo.get_by_id(ic_id)
            if not ic or not ic.embedding_json:
                unassigned.append(ic_id)
                continue

            # Find best matching theme
            best_theme_id = None
            best_sim = -1.0
            for theme_id, centroid in theme_centroids.items():
                sim = cosine_similarity(ic.embedding_json, centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_theme_id = theme_id

            if best_sim >= min_similarity and best_theme_id:
                # Assign IC to the best theme
                theme_repo.assign_ic_to_theme(best_theme_id, ic_id)
                redistributed += 1
                # Find theme name for logging
                theme_name = next(
                    (t.name for t in surviving_themes if t.id == best_theme_id),
                    best_theme_id,
                )
                logger.info(
                    f"[COHERENCE] Redistributed '{ic.name}' → '{theme_name}' "
                    f"(sim={best_sim:.3f})"
                )
            else:
                unassigned.append(ic_id)
                logger.info(
                    f"[COHERENCE] '{ic.name}' unassigned (best_sim={best_sim:.3f} "
                    f"< min={min_similarity})"
                )

        return redistributed, unassigned

    def _run_category_synthesis(self) -> Dict[str, Any]:
        """
        Run the CategoryAgent on final themes.

        Fetches IC details (definitions + example quotes) for richer prompt context.
        Returns summary dict with categories_created count.
        """
        from src.db import ThemeRepo
        theme_repo = ThemeRepo(self.db)
        ic_repo = InitialCodeRepo(self.db)
        vq_repo = VerbatimQuoteRepo(self.db)

        final_themes, _ = theme_repo.get_latest_round()
        if not final_themes:
            return {"categories_created": 0}

        # Build themes_data with IC details for richer prompt context
        themes_data = []
        for theme in final_themes:
            ic_ids = theme_repo.get_ics_for_theme(theme.id)
            ic_names = []
            ic_details = []

            for ic_id in ic_ids:
                ic = ic_repo.get_by_id(ic_id)
                if not ic:
                    continue
                ic_names.append(ic.name)

                # Fetch first example quote for grounding
                quotes = vq_repo.get_all_for_ic(ic_id)
                example_quote = quotes[0].quote_text if quotes else ""

                ic_details.append({
                    "name": ic.name,
                    "definition": ic.definition,
                    "example_quote": example_quote,
                })

            themes_data.append({
                "name": theme.name,
                "definition": theme.definition,
                "ic_count": len(ic_ids),
                "ic_names": ic_names,
                "ic_details": ic_details,
            })

        # Call the LLM + validate
        proposals = self.category_agent.synthesize(themes_data)
        if not proposals:
            return {"categories_created": 0}

        # Persist
        persisted = self.category_agent.persist(proposals, final_themes)

        return {
            "categories_created": len(persisted),
            "category_names": [c.name for c in persisted],
        }

    def export_thematic_structure(self) -> List[Dict[str, Any]]:
        """
        Export the full Category → Theme → IC → Quote hierarchy.

        Only includes themes from the **latest synthesis round** to avoid
        duplicates from earlier rounds.

        If categories exist, returns a list of category dicts wrapping themes.
        If no categories, returns a flat list of theme dicts (backward-compatible).

        This is the primary analytical product of the pipeline.
        """
        ic_repo = InitialCodeRepo(self.db)
        vq_repo = VerbatimQuoteRepo(self.db)

        from src.db import ThemeRepo
        theme_repo = ThemeRepo(self.db)

        # Get only latest-round themes (fixes theme duplication bug)
        final_themes, _round = theme_repo.get_latest_round()

        # Build theme exports keyed by theme ID
        theme_exports: Dict[str, Dict[str, Any]] = {}

        for theme in final_themes:
            theme_id = theme.id
            ic_ids = theme_repo.get_ics_for_theme(theme_id)

            ics_export: List[Dict[str, Any]] = []
            for ic_id in ic_ids:
                ic = ic_repo.get_by_id(ic_id)
                if not ic:
                    continue

                quotes = vq_repo.get_all_for_ic(ic_id)
                quotes_export = [
                    {
                        "quote_text": q.quote_text,
                        "span_start": q.span_start,
                        "span_end": q.span_end,
                        "segment_id": q.segment_id,
                        "is_verified": q.is_verified,
                    }
                    for q in quotes
                ]

                ics_export.append({
                    "id": ic.id,
                    "name": ic.name,
                    "definition": ic.definition,
                    "quote_count": len(quotes),
                    "quotes": quotes_export,
                })

            theme_exports[theme_id] = {
                "id": theme_id,
                "name": theme.name,
                "definition": theme.definition,
                "rationale": theme.rationale,
                "ic_count": len(ics_export),
                "initial_codes": ics_export,
            }

        # Check for categories
        category_repo = CategoryRepo(self.db)
        categories = category_repo.get_all()

        if categories:
            # Hierarchical export: Category → Theme → IC → Quote
            categories_export: List[Dict[str, Any]] = []
            assigned_theme_ids: set = set()

            for cat in categories:
                cat_theme_ids = category_repo.get_themes_for_category(cat.id)
                cat_themes = []
                for tid in cat_theme_ids:
                    if tid in theme_exports:
                        cat_themes.append(theme_exports[tid])
                        assigned_theme_ids.add(tid)

                categories_export.append({
                    "id": cat.id,
                    "name": cat.name,
                    "definition": cat.definition,
                    "theme_count": len(cat_themes),
                    "themes": cat_themes,
                })

            # Add uncategorized themes (if any)
            uncategorized = [
                t for tid, t in theme_exports.items()
                if tid not in assigned_theme_ids
            ]
            if uncategorized:
                categories_export.append({
                    "id": "uncategorized",
                    "name": "Uncategorized",
                    "definition": "Themes not assigned to any category",
                    "theme_count": len(uncategorized),
                    "themes": uncategorized,
                })

            return categories_export
        else:
            # Flat export (backward-compatible): Theme → IC → Quote
            return list(theme_exports.values())

    def _get_decision_summary(self) -> Dict[str, int]:
        """Summarise decision log actions for the final report."""
        decision_repo = DecisionLogRepo(self.db)
        logs = decision_repo.get_all()

        summary: Dict[str, int] = {}
        for log in logs:
            action = log.human_action or "unknown"
            summary[action] = summary.get(action, 0) + 1

        return summary
