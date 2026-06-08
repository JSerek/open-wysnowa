"""
EQD-AI v2 — Evidence-Extraction Pipeline (L0 + L1).

Slim orchestrator for the v2 evidence-extraction focus:

    L0  preprocessing (segmentation/normalization)
    L1  IC extraction + codebook building (coder + comparator triage)
    L1  optional codebook sign-off (HIL)
    L3  L1 quality metrics (reference-free)

Theme synthesis (L2), category synthesis, the full L3 metric suite, and the
analyst brief (L4) were shelved in the v2 pivot — recover them from the
`v1-full-pipeline` git tag / `archive/full-pipeline` branch. See docs/v2/.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import EQDConfig, load_config
from src.core.db import Database
from src.core.embeddings import EmbeddingService
from src.core.models import Document
from src.core.reasoning_log import ReasoningLogger
from src.eval.l1_metrics import L1MetricsEngine
from src.extraction.codebook_signoff import CodebookSignoff
from src.extraction.orchestrator import Layer1Orchestrator
from src.extraction.prompts import (
    build_comparator_system_prompt,
    build_comparator_system_prompt_simblind,
    build_coder_system_prompt,
)
from src.core.config import ModelClient
from src.leaderboard.registry import RunManifest, RunRegistry
from src.preprocessing import preprocess_documents

logger = logging.getLogger(__name__)


# Metric direction map (Appendix A): "more" = higher is better, "less" = lower is
# better, "" = descriptive (no inherent direction).
_METRIC_DIRECTIONS: Dict[str, str] = {
    "grounding_rate": "more",
    "extraction_density_mean": "",
    "candidate_drop_rate": "less",
    "quote_hallucination_rate": "less",
    "singleton_ratio": "",
    "merge_rate": "",
    "mean_coder_confidence": "",
    "cross_review_convergence": "more",
    # Pass-2 (omitted-text audit) — Appendix A
    "density_pass1": "",
    "density_pass2": "",
    "density_delta": "less",
    "recovery_rate": "",
    "accidental_omission_ratio": "less",
    "deliberate_omission_ratio": "",
    # Phase 3 — embedding evaluation
    "embedding_separation_auc": "more",
}


def _git_sha() -> Optional[str]:
    """Best-effort short git SHA of the working tree (None if unavailable)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EQDPipeline:
    """
    EQD-AI v2 evidence-extraction pipeline (L0 + L1 + L1 metrics).

    Supports both interactive (HIL) and automated (--no-hil) modes.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        db_path: str = "eqa_ai.db",
        config: Optional[EQDConfig] = None,
        seed: Optional[int] = None,
        k_repeat_index: int = 0,
        leaderboard_db_path: Optional[str] = "runs/leaderboard.db",
        eval_mode: bool = False,
    ):
        # Accept a ready-made Config (leaderboard harness overrides model ids
        # programmatically) or load from disk. Explicit config wins over path.
        self.config = config if config is not None else load_config(config_path)
        self.db_path = db_path
        self.seed = seed
        self.k_repeat_index = k_repeat_index
        self.leaderboard_db_path = leaderboard_db_path
        # Eval (sim-blind) mode: the judge sees no cosine values and (cosine,
        # verdict) pairs are collected for embedding_separation_auc (Phase 3).
        self.eval_mode = eval_mode

        self.db = Database(db_path)
        self.db.init_schema()

        # run_id: study_name + UTC timestamp (filesystem-safe)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.run_id = f"{self.config.study.name}_{ts}"

        log_dir = Path(db_path).parent
        self.reasoning_logger = ReasoningLogger(
            run_id=self.run_id,
            log_dir=log_dir,
            mode=self.config.processing.reasoning_log_mode,
        )

        self.model_client = ModelClient(self.config)
        self.embedding_service = EmbeddingService(self.model_client, self.db)

        self.layer1 = Layer1Orchestrator(
            self.model_client, self.db, self.config, self.reasoning_logger,
            eval_mode=eval_mode,
        )
        self.signoff = CodebookSignoff(self.db, self.embedding_service)
        self.metrics_engine = L1MetricsEngine(self.db, self.embedding_service)

    def run(
        self,
        documents: List[Document],
        enable_hil: bool = True,
        dataset_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the evidence-extraction pipeline (L0 → L1 → L1 metrics).

        Args:
            documents: raw Document objects to analyse
            enable_hil: if True, interactive codebook sign-off after L1
            dataset_path: source dataset path (for the run manifest hash);
                falls back to hashing the document texts when not given

        Returns a results dict with layer0/layer1/codebook_signoff/layer3.
        """
        results: Dict[str, Any] = {
            "layer0": {},
            "layer1": {},
            "codebook_signoff": False,
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

        # ── Layer 1: IC Extraction + codebook building ────────────────────
        logger.info("[PIPELINE] Layer 1: IC extraction + codebook building")
        layer1_summary = self.layer1.run(segments, enable_hil=enable_hil)
        results["layer1"] = layer1_summary
        logger.info(
            f"[PIPELINE] Layer 1 complete: {layer1_summary.get('new_ics_created', 0)} ICs, "
            f"{layer1_summary.get('batches_processed', 0)} batches"
        )

        # ── Codebook Sign-Off (HIL) ───────────────────────────────────────
        if enable_hil:
            logger.info("[PIPELINE] Codebook sign-off (HIL)")
            low_conf_ids = layer1_summary.get("low_confidence_ic_ids", [])
            signed_off = self.signoff.run(low_confidence_ic_ids=low_conf_ids)
            results["codebook_signoff"] = signed_off
            if not signed_off:
                logger.warning("Codebook not signed off — stopping before metrics")
                return results
        else:
            results["codebook_signoff"] = True
            logger.info("[PIPELINE] Codebook sign-off skipped (HIL disabled)")

        # ── Layer 3: L1 Quality Metrics ───────────────────────────────────
        logger.info("[PIPELINE] L1 quality metrics computation")
        its_history = self.layer1.its_tracker.history
        quality_results = self.metrics_engine.compute_all(
            its_history=its_history,
            batch_merge_rates=layer1_summary.get("batch_merge_rates", []),
            total_dropped=layer1_summary.get("total_dropped", 0),
            total_candidates=layer1_summary.get("total_candidates", 0),
            dropped_per_segment=layer1_summary.get("dropped_per_segment", {}),
            new_ic_confidences=layer1_summary.get("new_ic_confidences", []),
            coder_flagged_match=layer1_summary.get("coder_flagged_match", 0),
            coder_new_comp_new=layer1_summary.get("coder_new_comp_new", 0),
            coder_new_comp_merge=layer1_summary.get("coder_new_comp_merge", 0),
            coder_new_comp_reject=layer1_summary.get("coder_new_comp_reject", 0),
            # Pass-2 two-point density + omitted-text audit diagnostics
            density_snapshots=layer1_summary.get("density_snapshots", []),
            pass2_stats=layer1_summary.get("pass2_stats", {}),
            # Phase 3 — (cosine, sim-blind verdict) pairs for the AUC metric
            auc_pairs=layer1_summary.get("auc_pairs", []),
        )

        # Cumulative saturation curve from Layer 1
        sat_curve = layer1_summary.get("saturation_curve", [])
        quality_results["saturation_curve"] = [
            pt.model_dump() if hasattr(pt, "model_dump") else pt
            for pt in sat_curve
        ]

        results["layer3"] = quality_results

        # ── Run manifest + central registry ───────────────────────────────
        try:
            self._register_run(documents, dataset_path, quality_results)
        except Exception as e:  # never let bookkeeping fail the pipeline
            logger.warning(f"[REGISTRY] Failed to register run: {e}")

        logger.info("[PIPELINE] Complete")
        return results

    # ── Run registry helpers ──────────────────────────────────────────────

    def _register_run(
        self,
        documents: List[Document],
        dataset_path: Optional[str],
        quality_results: Dict[str, Any],
    ) -> None:
        """Build the run manifest, register it, and record final metrics."""
        if not self.leaderboard_db_path:
            return

        manifest = self._build_manifest(documents, dataset_path)
        metrics, directions = self._flatten_metrics(quality_results)

        registry = RunRegistry(self.leaderboard_db_path)
        registry.register_run(manifest)
        registry.record_metrics(self.run_id, metrics, directions)
        logger.info(
            f"[REGISTRY] Registered run '{self.run_id}' "
            f"({len(metrics)} metrics) → {self.leaderboard_db_path}"
        )

    def _build_manifest(
        self, documents: List[Document], dataset_path: Optional[str]
    ) -> RunManifest:
        cfg = self.config
        coder_agent = cfg.agents["coder_agent"]
        gen_model_id = cfg.models[coder_agent.model].model_id
        embed_model_id = cfg.models[cfg.agents["embedding"].model].model_id

        # Prompt fingerprints (template-level, with empty codebook context).
        # In eval mode the judge runs the sim-blind prompt — fingerprint that one.
        coder_prompt_hash = _sha256(build_coder_system_prompt(""))
        judge_prompt_hash = _sha256(
            build_comparator_system_prompt_simblind()
            if self.eval_mode
            else build_comparator_system_prompt()
        )

        if dataset_path and Path(dataset_path).exists():
            dataset_hash = _sha256(Path(dataset_path).read_text(encoding="utf-8", errors="ignore"))
        else:
            dataset_hash = _sha256("\n".join(d.raw_text for d in documents))

        proc = cfg.processing
        config_snapshot = {
            "batch_size": proc.batch_size,
            "segments_per_coder_call": proc.segments_per_coder_call,
            "similarity_prefilter_k": proc.similarity_prefilter_k,
            "its_saturation_threshold": proc.its_saturation_threshold,
            "its_consecutive_batches": proc.its_consecutive_batches,
            "reasoning_log_mode": proc.reasoning_log_mode,
        }

        return RunManifest(
            run_id=self.run_id,
            generation_model_id=gen_model_id,
            embedding_model_id=embed_model_id,
            coder_prompt_hash=coder_prompt_hash,
            judge_prompt_hash=judge_prompt_hash,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            dataset_size=len(documents),
            temperature=coder_agent.temperature,
            seed=self.seed,
            k_repeat_index=self.k_repeat_index,
            config_snapshot=config_snapshot,
            run_db_path=self.db_path,
            git_sha=_git_sha(),
        )

    @staticmethod
    def _flatten_metrics(
        quality_results: Dict[str, Any],
    ) -> tuple[Dict[str, float], Dict[str, str]]:
        """Extract scalar leaderboard metrics from the nested metric results."""
        def _get(path: List[str]) -> Optional[float]:
            node: Any = quality_results
            for key in path:
                if not isinstance(node, dict):
                    return None
                node = node.get(key)
            return node if isinstance(node, (int, float)) else None

        metrics: Dict[str, float] = {
            "grounding_rate": _get(["grounding", "grounding_rate"]),
            "extraction_density_mean": _get(["extraction_density", "distribution", "mean"]),
            "candidate_drop_rate": _get(["extraction_density", "drop_rate", "overall_rate"]),
            "quote_hallucination_rate": _get(["quote_hallucination_rate", "quote_hallucination_rate"]),
            "singleton_ratio": _get(["ic_concentration", "singleton_ratio"]),
            "merge_rate": _get(["merge_rate", "overall_rate"]),
            "mean_coder_confidence": _get(["coder_confidence", "mean_confidence"]),
            "cross_review_convergence": _get(["cross_review_convergence", "confirmed_ratio"]),
            # Pass-2 two-point density + omitted-text audit (Phase 2)
            "density_pass1": _get(["density_passes", "density_pass1"]),
            "density_pass2": _get(["density_passes", "density_pass2"]),
            "density_delta": _get(["density_passes", "density_delta"]),
            "recovery_rate": _get(["density_passes", "recovery_rate"]),
            "accidental_omission_ratio": _get(["omission_stats", "accidental_omission_ratio"]),
            "deliberate_omission_ratio": _get(["omission_stats", "deliberate_omission_ratio"]),
            # Phase 3 — embedding evaluation (None outside eval mode / one-class)
            "embedding_separation_auc": _get(["embedding_separation", "auc"]),
        }
        metrics = {k: v for k, v in metrics.items() if v is not None}
        directions = {k: _METRIC_DIRECTIONS.get(k, "") for k in metrics}
        return metrics, directions
