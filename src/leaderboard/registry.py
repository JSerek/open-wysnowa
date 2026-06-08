"""
EQD-AI v2 — Central run registry for the L1 leaderboard.

Every pipeline run writes (a) its own isolated run DB (the working artifacts) and
(b) one row in a *central* registry DB here: a full parameterisation of the run
(`RunManifest`) plus its final L1 metrics in long format. This is what makes runs
comparable across (generation model × embedding model × repetition) without
re-reading per-run databases — the leaderboard matrix (Phase 3) pivots
`run_metrics`.

Design:
  - Standalone sqlite (not the core EQD schema) — the registry outlives any single
    run DB and has a different lifecycle.
  - Long-format `run_metrics` (run_id, metric_name, value, direction) → trivial to
    pivot into a metric × model matrix.
  - `k_repeat_index` is first-class from the start (architecture under k=N), even
    though k=1 is the only value used now.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


PIPELINE_VERSION = "v2-phase2"


# ── Manifest ──────────────────────────────────────────────────────────────────

class RunManifest(BaseModel):
    """Full parameterisation of one pipeline run (one registry row)."""

    run_id: str
    generation_model_id: str
    embedding_model_id: str
    coder_prompt_hash: str
    judge_prompt_hash: str
    dataset_path: Optional[str] = None
    dataset_hash: str = ""
    dataset_size: int = 0
    temperature: Optional[float] = None
    seed: Optional[int] = None
    k_repeat_index: int = 0
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    run_db_path: str = ""
    pipeline_version: str = PIPELINE_VERSION
    git_sha: Optional[str] = None


# ── Registry ──────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id              TEXT PRIMARY KEY,
    generation_model_id TEXT NOT NULL,
    embedding_model_id  TEXT NOT NULL,
    coder_prompt_hash   TEXT NOT NULL,
    judge_prompt_hash   TEXT NOT NULL,
    dataset_path        TEXT,
    dataset_hash        TEXT NOT NULL DEFAULT '',
    dataset_size        INTEGER NOT NULL DEFAULT 0,
    temperature         REAL,
    seed                INTEGER,
    k_repeat_index      INTEGER NOT NULL DEFAULT 0,
    config_snapshot     TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    run_db_path         TEXT NOT NULL DEFAULT '',
    pipeline_version    TEXT NOT NULL DEFAULT '',
    git_sha             TEXT
);

CREATE TABLE IF NOT EXISTS run_metrics (
    run_id      TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value       REAL NOT NULL,
    direction   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, metric_name),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_run_metrics_metric ON run_metrics(metric_name);
"""


class RunRegistry:
    """SQLite-backed central registry of runs + their final metrics."""

    def __init__(self, db_path: str | Path = "runs/leaderboard.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def register_run(self, manifest: RunManifest) -> None:
        """Insert (or replace) a run row from its manifest."""
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, generation_model_id, embedding_model_id,
                    coder_prompt_hash, judge_prompt_hash, dataset_path,
                    dataset_hash, dataset_size, temperature, seed,
                    k_repeat_index, config_snapshot, created_at, run_db_path,
                    pipeline_version, git_sha
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    manifest.run_id, manifest.generation_model_id,
                    manifest.embedding_model_id, manifest.coder_prompt_hash,
                    manifest.judge_prompt_hash, manifest.dataset_path,
                    manifest.dataset_hash, manifest.dataset_size,
                    manifest.temperature, manifest.seed, manifest.k_repeat_index,
                    json.dumps(manifest.config_snapshot), manifest.created_at,
                    manifest.run_db_path, manifest.pipeline_version,
                    manifest.git_sha,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def record_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        directions: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record final scalar metrics for a run (long format)."""
        directions = directions or {}
        conn = self._connect()
        try:
            for name, value in metrics.items():
                if value is None:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO run_metrics (run_id, metric_name, value, direction)
                    VALUES (?,?,?,?)
                    """,
                    (run_id, name, float(value), directions.get(name, "")),
                )
            conn.commit()
        finally:
            conn.close()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return a single run row as a dict (config_snapshot parsed), or None."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        d = dict(row)
        d["config_snapshot"] = json.loads(d.get("config_snapshot") or "{}")
        return d

    def load_matrix(self) -> Dict[str, Any]:
        """
        Pivot run_metrics into a metric × (gen_model × embed_model) matrix.

        Returns:
            {
                "columns": [ "<gen>×<embed>", ... ],   # one per model combo
                "directions": { metric_name: direction },
                "cells": { metric_name: { column: [values across runs/k] } },
            }

        Aggregation (mean ± sd across k>1) is left to the report layer (Phase 3);
        here we collect the raw values per (metric, column).
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT r.generation_model_id AS gen,
                       r.embedding_model_id  AS emb,
                       m.metric_name         AS metric,
                       m.value               AS value,
                       m.direction           AS direction
                FROM run_metrics m
                JOIN runs r ON r.run_id = m.run_id
                """
            ).fetchall()
        finally:
            conn.close()

        columns: List[str] = []
        directions: Dict[str, str] = {}
        cells: Dict[str, Dict[str, List[float]]] = {}

        for row in rows:
            col = f"{row['gen']}×{row['emb']}"
            if col not in columns:
                columns.append(col)
            metric = row["metric"]
            directions.setdefault(metric, row["direction"] or "")
            cells.setdefault(metric, {}).setdefault(col, []).append(row["value"])

        return {"columns": columns, "directions": directions, "cells": cells}
