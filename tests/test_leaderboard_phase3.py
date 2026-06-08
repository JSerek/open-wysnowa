"""
Phase 3 tests — leaderboard: AUC metric, sim-blind judge prompt, harness matrix,
report aggregation.

All fixtures are synthetic (no data files, no API calls): the harness is exercised
through an injected stub pipeline that writes to the registry directly.
"""

from __future__ import annotations

import uuid

import pytest

from src.core.config import (
    AgentParams,
    EQDConfig,
    NamedModel,
    ProcessingConfig,
    ProviderConfig,
    StudyConfig,
)
from src.core.models import Document
from src.eval.l1_metrics import L1MetricsEngine
from src.extraction.prompts import (
    build_comparator_user_prompt,
    build_comparator_user_prompt_simblind,
)
from src.leaderboard.harness import run_leaderboard
from src.leaderboard.registry import RunManifest, RunRegistry
from src.leaderboard.report import (
    aggregate_cell,
    render_matrix_csv,
    render_matrix_markdown,
)


# ── 3.2 embedding_separation_auc ─────────────────────────────────────────────

class TestEmbeddingSeparationAUC:
    def _auc(self, db, pairs):
        return L1MetricsEngine(db).compute_embedding_separation_auc(pairs)

    def test_perfect_separation_is_one(self, db):
        # Every MERGE cosine above every NEW cosine → AUC = 1.0.
        pairs = [(0.95, "MERGE"), (0.90, "MERGE"), (0.20, "NEW"), (0.10, "NEW")]
        res = self._auc(db, pairs)
        assert res["auc"] == pytest.approx(1.0)
        assert res["n_merge"] == 2 and res["n_new"] == 2

    def test_symmetric_interleave_is_half(self, db):
        # MERGE at the middle, NEW at the extremes → no separation → AUC = 0.5.
        pairs = [(0.2, "MERGE"), (0.3, "MERGE"), (0.1, "NEW"), (0.4, "NEW")]
        res = self._auc(db, pairs)
        assert res["auc"] == pytest.approx(0.5)

    def test_all_ties_is_half(self, db):
        # Identical cosines → average ranks → AUC = 0.5 (embedding gives no signal).
        pairs = [(0.5, "MERGE"), (0.5, "MERGE"), (0.5, "NEW")]
        res = self._auc(db, pairs)
        assert res["auc"] == pytest.approx(0.5)

    def test_inverted_separation_is_zero(self, db):
        # MERGE below NEW (embedding ranks backwards) → AUC = 0.0.
        pairs = [(0.1, "MERGE"), (0.2, "MERGE"), (0.9, "NEW"), (0.95, "NEW")]
        res = self._auc(db, pairs)
        assert res["auc"] == pytest.approx(0.0)

    def test_one_class_returns_none(self, db):
        assert self._auc(db, [(0.9, "MERGE"), (0.8, "MERGE")])["auc"] is None
        assert self._auc(db, [])["auc"] is None

    def test_persisted_to_quality_metrics(self, db):
        self._auc(db, [(0.9, "MERGE"), (0.1, "NEW")])
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT value FROM quality_metrics WHERE metric_type=?",
                ("embedding_separation_auc",),
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["value"] == pytest.approx(1.0)


# ── 3.1 sim-blind judge prompt ───────────────────────────────────────────────

class TestSimBlindPrompt:
    TOP_K = [("ic1", "weapon_variety_lacking", "Limited weapon selection", 0.876)]

    def test_simblind_user_prompt_hides_cosine(self):
        out = build_comparator_user_prompt_simblind(
            "combat_poor", "Combat feels bad", "the combat is awful", self.TOP_K
        )
        assert "0.876" not in out          # the cosine value itself
        assert "(similarity:" not in out   # the non-blind score annotation
        # the neighbour is still shown by name + definition
        assert "weapon_variety_lacking" in out
        assert "Limited weapon selection" in out

    def test_regular_user_prompt_shows_cosine(self):
        # Contrast: the non-blind prompt DOES surface the score (circular for AUC).
        out = build_comparator_user_prompt(
            "combat_poor", "Combat feels bad", "the combat is awful", self.TOP_K
        )
        assert "0.876" in out
        assert "(similarity:" in out


# ── 3.3 harness matrix (stub pipeline, no API) ───────────────────────────────

def _synthetic_config() -> EQDConfig:
    """A fully synthetic config — three named models, no real providers hit."""
    return EQDConfig(
        providers={"p": ProviderConfig(type="openai_compatible", api_key_env="X")},
        models={
            "gen_a": NamedModel(provider="p", model_id="model-A"),
            "gen_b": NamedModel(provider="p", model_id="model-B"),
            "emb_x": NamedModel(provider="p", model_id="embed-X"),
        },
        agents={
            "coder_agent": AgentParams(model="gen_a", temperature=0.2),
            "codebook_comparator": AgentParams(model="gen_a", temperature=0.1),
            "embedding": AgentParams(model="emb_x"),
        },
        study=StudyConfig(name="synthetic"),
        processing=ProcessingConfig(),
    )


class _StubPipeline:
    """Stand-in for EQDPipeline: records a manifest + a metric, no API calls."""

    captured: list = []  # (gen_model_id, embed_model_id, eval_mode, k_repeat_index)

    def __init__(self, *, config, db_path, seed, k_repeat_index,
                 leaderboard_db_path, eval_mode):
        self.config = config
        self.leaderboard_db_path = leaderboard_db_path
        self.k_repeat_index = k_repeat_index
        self.eval_mode = eval_mode
        self.run_id = f"{config.study.name}_{uuid.uuid4().hex[:8]}"

    def run(self, documents, enable_hil=True, dataset_path=None):
        cfg = self.config
        gen_id = cfg.models[cfg.agents["coder_agent"].model].model_id
        emb_id = cfg.models[cfg.agents["embedding"].model].model_id
        type(self).captured.append(
            (gen_id, emb_id, self.eval_mode, self.k_repeat_index)
        )
        reg = RunRegistry(self.leaderboard_db_path)
        reg.register_run(RunManifest(
            run_id=self.run_id,
            generation_model_id=gen_id,
            embedding_model_id=emb_id,
            coder_prompt_hash="c", judge_prompt_hash="j",
            k_repeat_index=self.k_repeat_index,
        ))
        reg.record_metrics(
            self.run_id,
            {"embedding_separation_auc": 0.7 + 0.1 * self.k_repeat_index},
            {"embedding_separation_auc": "more"},
        )
        return {}


class TestHarnessMatrix:
    def test_two_gen_one_embed_k1(self, tmp_path):
        _StubPipeline.captured = []
        lb_db = str(tmp_path / "leaderboard.db")
        records = run_leaderboard(
            gen_models=["gen_a", "gen_b"],
            embed_models=["emb_x"],
            documents=[Document(raw_text="synthetic review")],
            base_config=_synthetic_config(),
            k=1,
            leaderboard_db_path=lb_db,
            run_db_dir=str(tmp_path / "runs"),
            pipeline_factory=_StubPipeline,
        )
        assert len(records) == 2

        # Every run was headless + eval (sim-blind), with the overridden gen ids.
        assert {c[0] for c in _StubPipeline.captured} == {"model-A", "model-B"}
        assert all(c[1] == "embed-X" for c in _StubPipeline.captured)
        assert all(c[2] is True for c in _StubPipeline.captured)  # eval_mode

        matrix = RunRegistry(lb_db).load_matrix()
        assert set(matrix["columns"]) == {"model-A×embed-X", "model-B×embed-X"}
        cells = matrix["cells"]["embedding_separation_auc"]
        assert cells["model-A×embed-X"] == [pytest.approx(0.7)]
        assert cells["model-B×embed-X"] == [pytest.approx(0.7)]
        assert matrix["directions"]["embedding_separation_auc"] == "more"

    def test_k2_produces_two_values_per_combo(self, tmp_path):
        _StubPipeline.captured = []
        lb_db = str(tmp_path / "leaderboard.db")
        run_leaderboard(
            gen_models=["gen_a"],
            embed_models=["emb_x"],
            documents=[Document(raw_text="synthetic review")],
            base_config=_synthetic_config(),
            k=2,
            leaderboard_db_path=lb_db,
            run_db_dir=str(tmp_path / "runs"),
            pipeline_factory=_StubPipeline,
        )
        assert {c[3] for c in _StubPipeline.captured} == {0, 1}  # k indices
        cells = RunRegistry(lb_db).load_matrix()["cells"]["embedding_separation_auc"]
        vals = sorted(cells["model-A×embed-X"])
        assert vals == [pytest.approx(0.7), pytest.approx(0.8)]

    def test_unknown_model_fails_fast(self, tmp_path):
        with pytest.raises(ValueError, match="not defined"):
            run_leaderboard(
                gen_models=["nope"],
                embed_models=["emb_x"],
                documents=[Document(raw_text="x")],
                base_config=_synthetic_config(),
                leaderboard_db_path=str(tmp_path / "lb.db"),
                run_db_dir=str(tmp_path / "runs"),
                pipeline_factory=_StubPipeline,
            )


# ── 3.4 report aggregation ───────────────────────────────────────────────────

class TestReport:
    def test_aggregate_single_value(self):
        agg = aggregate_cell([0.8])
        assert agg["mean"] == pytest.approx(0.8)
        assert agg["sd"] is None and agg["n"] == 1

    def test_aggregate_mean_and_sd(self):
        agg = aggregate_cell([0.8, 0.6])
        assert agg["mean"] == pytest.approx(0.7)
        assert agg["sd"] == pytest.approx(0.1414, abs=1e-3)
        assert agg["n"] == 2

    def test_markdown_shows_direction_and_variance(self):
        matrix = {
            "columns": ["model-A×embed-X"],
            "directions": {"embedding_separation_auc": "more", "density_delta": "less"},
            "cells": {
                "embedding_separation_auc": {"model-A×embed-X": [0.8, 0.6]},
                "density_delta": {"model-A×embed-X": [0.1]},
            },
        }
        md = render_matrix_markdown(matrix)
        assert "embedding_separation_auc ↑" in md
        assert "density_delta ↓" in md
        assert "0.700 ± 0.141" in md          # k>1 mean ± sd
        assert "0.100" in md                  # k=1 mean only (no ± )

    def test_markdown_empty_matrix(self):
        assert "no metrics" in render_matrix_markdown(
            {"columns": [], "directions": {}, "cells": {}}
        )

    def test_csv_has_mean_and_sd_columns(self):
        matrix = {
            "columns": ["model-A×embed-X"],
            "directions": {"auc": "more"},
            "cells": {"auc": {"model-A×embed-X": [0.8, 0.6]}},
        }
        csv_out = render_matrix_csv(matrix)
        assert "model-A×embed-X" in csv_out
        assert "model-A×embed-X_sd" in csv_out
        assert "0.7" in csv_out
