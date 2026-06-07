"""Tests for EQDPipeline config injection + run manifest building (Phase 1.5)."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.config import load_config
from src.core.models import Document
from src.extraction.pipeline import EQDPipeline


CONFIG_PATH = Path(__file__).parent.parent / "eqd_config.yaml"

_ENV = {
    "ANTHROPIC_API_KEY": "test-key",
    "OPENAI_API_KEY": "test-key",
    "GOOGLE_API_KEY": "test-key",
    "OPENROUTER_API_KEY": "test-key",
}


@patch.dict(os.environ, _ENV)
def test_pipeline_accepts_ready_made_config(tmp_path):
    cfg = load_config(CONFIG_PATH)
    pipe = EQDPipeline(
        config=cfg,
        db_path=str(tmp_path / "run.db"),
        leaderboard_db_path=None,
    )
    # The provided Config object is used as-is (no reload from disk)
    assert pipe.config is cfg


@patch.dict(os.environ, _ENV)
def test_manifest_honours_overridden_model_ids(tmp_path):
    cfg = load_config(CONFIG_PATH)
    # Harness-style programmatic override of the generation + embedding model ids
    cfg.models[cfg.agents["coder_agent"].model].model_id = "override/gen-model"
    cfg.models[cfg.agents["embedding"].model].model_id = "override/embed-model"

    pipe = EQDPipeline(
        config=cfg,
        db_path=str(tmp_path / "run.db"),
        seed=7,
        k_repeat_index=2,
        leaderboard_db_path=None,
    )
    docs = [Document(raw_text="hello world"), Document(raw_text="second review")]
    manifest = pipe._build_manifest(docs, dataset_path=None)

    assert manifest.generation_model_id == "override/gen-model"
    assert manifest.embedding_model_id == "override/embed-model"
    assert manifest.seed == 7
    assert manifest.k_repeat_index == 2
    assert manifest.dataset_size == 2
    assert manifest.coder_prompt_hash  # prompt fingerprints are populated
    assert manifest.judge_prompt_hash
    assert manifest.dataset_hash       # falls back to hashing document texts
