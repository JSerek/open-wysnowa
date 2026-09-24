"""Tests for the central run registry (src.leaderboard.registry)."""

import pytest

from src.leaderboard.registry import RunManifest, RunRegistry


@pytest.fixture
def registry(tmp_path):
    return RunRegistry(str(tmp_path / "leaderboard.db"))


def _manifest(run_id="run_1", gen="gen-a", emb="emb-a"):
    return RunManifest(
        run_id=run_id,
        generation_model_id=gen,
        embedding_model_id=emb,
        coder_prompt_hash="coderhash",
        judge_prompt_hash="judgehash",
        dataset_path="data/x.csv",
        dataset_hash="datahash",
        dataset_size=10,
        temperature=0.2,
        seed=42,
        k_repeat_index=0,
        config_snapshot={"batch_size": 10, "similarity_prefilter_k": 5},
        run_db_path="runs/run_1.db",
    )


class TestRunRegistry:
    def test_register_and_get_run(self, registry):
        registry.register_run(_manifest())
        row = registry.get_run("run_1")
        assert row is not None
        assert row["generation_model_id"] == "gen-a"
        assert row["embedding_model_id"] == "emb-a"
        assert row["dataset_size"] == 10
        assert row["seed"] == 42
        # config_snapshot round-trips as a dict
        assert row["config_snapshot"]["batch_size"] == 10

    def test_record_metrics_and_matrix(self, registry):
        registry.register_run(_manifest())
        registry.record_metrics(
            "run_1",
            {"grounding_rate": 1.0, "span_error_rate": 0.1, "mean_coder_confidence": None},
            {"grounding_rate": "more", "span_error_rate": "less"},
        )
        matrix = registry.load_matrix()
        assert "gen-a×emb-a" in matrix["columns"]
        assert matrix["cells"]["grounding_rate"]["gen-a×emb-a"] == [1.0]
        assert matrix["directions"]["span_error_rate"] == "less"
        # None-valued metrics are skipped
        assert "mean_coder_confidence" not in matrix["cells"]

    def test_matrix_collects_across_models(self, registry):
        registry.register_run(_manifest(run_id="run_a", gen="gen-a"))
        registry.register_run(_manifest(run_id="run_b", gen="gen-b"))
        registry.record_metrics("run_a", {"span_error_rate": 0.1})
        registry.record_metrics("run_b", {"span_error_rate": 0.2})
        matrix = registry.load_matrix()
        assert set(matrix["columns"]) == {"gen-a×emb-a", "gen-b×emb-a"}
        cells = matrix["cells"]["span_error_rate"]
        assert cells["gen-a×emb-a"] == [0.1]
        assert cells["gen-b×emb-a"] == [0.2]

    def test_get_missing_run_returns_none(self, registry):
        assert registry.get_run("nope") is None

    def test_matrix_filters_to_current_version(self, registry):
        from src.leaderboard.registry import PIPELINE_VERSION
        old = _manifest(run_id="run_old", gen="gen-a")
        old.pipeline_version = "v2-phase2"
        registry.register_run(old)
        registry.register_run(_manifest(run_id="run_new", gen="gen-a"))
        registry.record_metrics("run_old", {"merge_rate": 0.9})
        registry.record_metrics("run_new", {"merge_rate": 0.1})

        matrix = registry.load_matrix()
        assert PIPELINE_VERSION == "v2-p0"
        assert matrix["pipeline_version"] == "v2-p0"
        assert matrix["cells"]["merge_rate"]["gen-a×emb-a"] == [0.1]
        assert matrix["excluded_runs"] == 1

        everything = registry.load_matrix(pipeline_version=None)
        assert sorted(everything["cells"]["merge_rate"]["gen-a×emb-a"]) == [0.1, 0.9]
        assert everything["excluded_runs"] == 0
        assert everything["pipeline_version"] is None

    def test_empty_version_rows_are_excluded(self, registry):
        legacy = _manifest(run_id="run_legacy")
        legacy.pipeline_version = ""
        registry.register_run(legacy)
        registry.record_metrics("run_legacy", {"merge_rate": 0.5})
        matrix = registry.load_matrix()
        assert matrix["cells"] == {}
        assert matrix["excluded_runs"] == 1
