"""
EQD-AI v2 — Leaderboard harness (Phase 3).

Runs the L1 pipeline across a matrix of (generation model × embedding model ×
k-repetition) and lets each run record its manifest + metrics into the central
registry. The matrix — not a single composite score — is what a human reads
(contract #8); aggregation/rendering lives in `report.py`.

Design:
  - One named generative slot drives coder + comparator + pass-2 + refinement
    (contract #9); one named embedding slot drives retrieval. The harness only
    overrides `agents.{coder_agent,codebook_comparator}.model` (gen) and
    `agents.embedding.model` (embed) on a deep copy of the base config — no
    layer touches provider-specific logic (DESIGN #6).
  - Every run is headless (`enable_hil=False`, contract #10) and runs in EVAL
    (sim-blind) mode so the embedding is scored threshold-free via AUC.
  - `k_repeat_index` is threaded from the start (architecture under k=N,
    contract #11) even though k=1 is the default.
  - Each combo gets its own run DB (embedding cache is isolated per run DB) and a
    distinct study name → distinct `run_id`, so same-second runs never collide in
    the registry.
  - `pipeline_factory` is injectable: tests pass a stub to exercise the matrix
    orchestration without any API calls.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.core.config import EQDConfig, load_config
from src.core.models import Document
from src.extraction.pipeline import EQDPipeline

logger = logging.getLogger(__name__)


def _safe(name: str) -> str:
    """Filesystem-safe token from a model key."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def run_leaderboard(
    gen_models: List[str],
    embed_models: List[str],
    documents: List[Document],
    *,
    dataset_path: Optional[str] = None,
    k: int = 1,
    seed: Optional[int] = None,
    base_config_path: Optional[Path] = None,
    base_config: Optional[EQDConfig] = None,
    leaderboard_db_path: str = "runs/leaderboard.db",
    run_db_dir: str = "runs",
    pipeline_factory: Callable[..., Any] = EQDPipeline,
) -> List[Dict[str, Any]]:
    """
    Run the (gen × embed × k) matrix, registering each run in the registry.

    Args:
        gen_models: named generative model keys (must exist in config.models).
        embed_models: named embedding model keys (must exist in config.models).
        documents: raw Documents to analyse (same input for every combo).
        dataset_path: source path for the run manifest hash (optional).
        k: repetitions per combo (variance under k>1); run as k_repeat_index 0..k-1.
        seed: best-effort run seed, recorded in each manifest.
        base_config_path / base_config: base config to clone+override (one wins;
            base_config takes precedence, else load from path/default).
        leaderboard_db_path: central registry DB shared across all runs.
        run_db_dir: directory for per-run isolated DBs.
        pipeline_factory: constructs the pipeline (injectable for tests).

    Returns:
        One record dict per run: {gen, embed, k_repeat_index, run_id, run_db_path}.
    """
    base = base_config if base_config is not None else load_config(base_config_path)

    # Fail fast on unknown model keys before launching any run.
    for name in [*gen_models, *embed_models]:
        if name not in base.models:
            raise ValueError(
                f"Model '{name}' is not defined in config.models "
                f"(available: {sorted(base.models)})"
            )

    Path(run_db_dir).mkdir(parents=True, exist_ok=True)
    records: List[Dict[str, Any]] = []

    for gen in gen_models:
        for embed in embed_models:
            for k_index in range(k):
                cfg = base.model_copy(deep=True)
                cfg.agents["coder_agent"].model = gen
                cfg.agents["codebook_comparator"].model = gen
                cfg.agents["embedding"].model = embed
                # Distinct study name → distinct run_id even within one second.
                cfg.study.name = f"{base.study.name}_{_safe(gen)}_{_safe(embed)}_k{k_index}"

                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                run_db_path = str(
                    Path(run_db_dir)
                    / f"lb_{_safe(gen)}_{_safe(embed)}_k{k_index}_{ts}.db"
                )

                logger.info(
                    f"[LEADERBOARD] Run gen={gen} embed={embed} k={k_index} → {run_db_path}"
                )
                pipeline = pipeline_factory(
                    config=cfg,
                    db_path=run_db_path,
                    seed=seed,
                    k_repeat_index=k_index,
                    leaderboard_db_path=leaderboard_db_path,
                    eval_mode=True,
                )
                pipeline.run(
                    documents, enable_hil=False, dataset_path=dataset_path,
                )

                records.append({
                    "gen": gen,
                    "embed": embed,
                    "k_repeat_index": k_index,
                    "run_id": getattr(pipeline, "run_id", None),
                    "run_db_path": run_db_path,
                })

    logger.info(f"[LEADERBOARD] Completed {len(records)} runs")
    return records
