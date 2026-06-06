"""Tests for YAML config loading and ModelClient."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.config import (
    EQDConfig,
    load_config,
    ModelClient,
    ProviderConfig,
    NamedModel,
    AgentParams,
    StudyConfig,
    ProcessingConfig,
)


# Path to the actual config file
CONFIG_PATH = Path(__file__).parent.parent / "eqd_config.yaml"


class TestLoadConfig:
    def test_loads_valid_config(self):
        config = load_config(CONFIG_PATH)
        assert isinstance(config, EQDConfig)

    def test_has_providers(self):
        config = load_config(CONFIG_PATH)
        # v2 keeps openai (embeddings), google (gemini direct swap), openrouter (active)
        assert "openai" in config.providers
        assert "openrouter" in config.providers
        assert config.providers["openai"].type == "openai_compatible"
        assert config.providers["openrouter"].type == "openai_compatible"

    def test_has_models(self):
        config = load_config(CONFIG_PATH)
        assert "or_smart" in config.models
        assert "embed_openai" in config.models

    def test_has_agents(self):
        config = load_config(CONFIG_PATH)
        assert "coder_agent" in config.agents
        assert "embedding" in config.agents
        assert config.agents["coder_agent"].temperature == 0.2

    def test_processing_defaults(self):
        config = load_config(CONFIG_PATH)
        assert config.processing.batch_size == 10
        assert config.processing.its_saturation_threshold == 0.02
        # v2 L1 thresholds
        assert config.processing.auto_new_threshold == 0.55
        assert config.processing.auto_merge_threshold == 0.65

    def test_meta_ic_filter_config(self):
        config = load_config(CONFIG_PATH)
        meta = config.processing.meta_ic_filter
        assert meta.enabled is True
        assert isinstance(meta.name_patterns, list)
        assert isinstance(meta.definition_signals, list)

    def test_study_config(self):
        config = load_config(CONFIG_PATH)
        # Study name comes from eqd_config.yaml (may be customized)
        assert isinstance(config.study.name, str)
        assert len(config.study.name) > 0
        assert config.study.embedding_model_locked is False

    def test_missing_config_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.yaml"))


class TestModelClient:
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key-123",
        "OPENAI_API_KEY": "test-openai-key",
        "GOOGLE_API_KEY": "test-key",
    })
    def test_init_validates_providers(self):
        config = load_config(CONFIG_PATH)
        # Should not raise — required keys are set
        mc = ModelClient(config)
        assert mc is not None

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.core.config.load_dotenv")  # Prevent .env from re-loading keys
    def test_missing_env_var_raises(self, mock_dotenv):
        config = load_config(CONFIG_PATH)
        with pytest.raises(EnvironmentError, match="not set"):
            ModelClient(config)

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "OPENAI_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key",
    })
    def test_get_client_unknown_agent(self):
        config = load_config(CONFIG_PATH)
        mc = ModelClient(config)
        with pytest.raises(ValueError, match="Unknown agent"):
            mc.get_client("nonexistent_agent")

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "OPENAI_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key",
    })
    def test_get_client_returns_tuple(self):
        config = load_config(CONFIG_PATH)
        mc = ModelClient(config)
        client, model_id, params = mc.get_client("coder_agent")
        assert model_id == "google/gemini-3-flash-preview"  # active config: or_smart block (2026-03-04)
        assert params.temperature == 0.2

    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "OPENAI_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key",
    })
    def test_get_embedding_client(self):
        config = load_config(CONFIG_PATH)
        mc = ModelClient(config)
        client, model_id = mc.get_embedding_client()
        assert model_id == "text-embedding-3-small"
