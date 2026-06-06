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

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import load_config
from src.core.db import Database
from src.core.embeddings import EmbeddingService
from src.core.models import Document
from src.core.reasoning_log import ReasoningLogger
from src.eval.l1_metrics import L1MetricsEngine
from src.extraction.codebook_signoff import CodebookSignoff
from src.extraction.orchestrator import Layer1Orchestrator
from src.core.config import ModelClient
from src.preprocessing import preprocess_documents

logger = logging.getLogger(__name__)


class EQDPipeline:
    """
    EQD-AI v2 evidence-extraction pipeline (L0 + L1 + L1 metrics).

    Supports both interactive (HIL) and automated (--no-hil) modes.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        db_path: str = "eqa_ai.db",
    ):
        self.config = load_config(config_path)

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
        )
        self.signoff = CodebookSignoff(self.db, self.embedding_service)
        self.metrics_engine = L1MetricsEngine(self.db, self.embedding_service)

    def run(
        self,
        documents: List[Document],
        enable_hil: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the evidence-extraction pipeline (L0 → L1 → L1 metrics).

        Args:
            documents: raw Document objects to analyse
            enable_hil: if True, interactive codebook sign-off after L1

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
            triage_stats=layer1_summary.get("triage_stats", {}),
            batch_merge_rates=layer1_summary.get("batch_merge_rates", []),
            grey_zone_decisions=layer1_summary.get("grey_zone_decisions", []),
            total_dropped=layer1_summary.get("total_dropped", 0),
            total_candidates=layer1_summary.get("total_candidates", 0),
            dropped_per_segment=layer1_summary.get("dropped_per_segment", {}),
            new_ic_confidences=layer1_summary.get("new_ic_confidences", []),
            coder_flagged_match=layer1_summary.get("coder_flagged_match", 0),
            coder_new_comp_new=layer1_summary.get("coder_new_comp_new", 0),
            coder_new_comp_merge=layer1_summary.get("coder_new_comp_merge", 0),
            coder_new_comp_reject=layer1_summary.get("coder_new_comp_reject", 0),
        )

        # Cumulative saturation curve from Layer 1
        sat_curve = layer1_summary.get("saturation_curve", [])
        quality_results["saturation_curve"] = [
            pt.model_dump() if hasattr(pt, "model_dump") else pt
            for pt in sat_curve
        ]

        results["layer3"] = quality_results
        logger.info("[PIPELINE] Complete")
        return results
