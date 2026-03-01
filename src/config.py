"""
EQD-AI Configuration & ModelClient.

Loads eqd_config.yaml, validates env vars, returns instructor-patched clients.
Follows best practices: OpenAI client + instructor + Pydantic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


# ── Config Pydantic models ────────────────────────────────────────────────────

class ProviderConfig(BaseModel):
    type: str  # "openai_compatible" or "anthropic"
    api_key_env: str
    base_url: Optional[str] = None
    instructor_mode: Optional[str] = None  # "json" → instructor.Mode.JSON (needed for Google/Gemini)


class NamedModel(BaseModel):
    provider: str
    model_id: str
    # Reasoning model support — omit for non-reasoning models (treated as False)
    reasoning: bool = False
    reasoning_style: Optional[str] = None  # "openai" | "gemini" | "deepseek" | "anthropic"


class AgentParams(BaseModel):
    model: str  # reference to named model
    temperature: float = 0.3
    max_tokens: int = 4000
    # Declarative reasoning effort: "off" | "low" | "medium" | "high"
    # Omit to use model default. Only applied when the model has reasoning: true.
    # "off" maps to "low" for openai style (no true off exists on those models).
    reasoning_effort: Optional[str] = None


class StudyConfig(BaseModel):
    name: str = "default_study"
    embedding_model_locked: bool = False


class MetaICFilterConfig(BaseModel):
    enabled: bool = True
    name_patterns: List[str] = Field(default_factory=list)
    definition_signals: List[str] = Field(default_factory=list)


class ThemeRefinementConfig(BaseModel):
    """Config for post-synthesis theme refinement (distinctness + splitting)."""
    distinctness_threshold: float = 0.70       # pairs above this get revision
    max_overlap_pairs: int = 10                # max pairs to address per pass
    split_min_ics: int = 8                     # minimum ICs to consider splitting
    split_max_coherence: float = 0.50          # raw coherence below this triggers split check
    split_min_overlaps: int = 3                # minimum overlap pairs to trigger split


class MetricGuidelineConfig(BaseModel):
    """Reference range for a single quality metric."""
    description: str = ""
    what_it_measures: str = ""
    healthy_min: Optional[float] = None
    healthy_max: Optional[float] = None
    low_means: str = ""
    high_means: str = ""


class AnalystGuidelinesConfig(BaseModel):
    """YAML-configurable reference ranges for Layer 4 metric interpretation."""
    grounding_rate: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    drop_rate: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    extraction_density_mean: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    singleton_ratio: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    merge_rate_final: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    triage_auto_rate: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    its_final: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    theme_coherence_mean: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    theme_distinctness_overlap_ratio: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    sentiment_purity_mean: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    thematic_coverage: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)
    cross_review_convergence: MetricGuidelineConfig = Field(default_factory=MetricGuidelineConfig)

    def to_prompt_block(self) -> str:
        """Format all guidelines as a text block for LLM prompts."""
        lines = []
        for field_name in self.model_fields:
            guideline: MetricGuidelineConfig = getattr(self, field_name)
            if not guideline.description:
                continue
            lines.append(f"{field_name}:")
            lines.append(f"  Definition: {guideline.description}")
            lines.append(f"  What it measures: {guideline.what_it_measures}")
            range_parts = []
            if guideline.healthy_min is not None:
                range_parts.append(f"min {guideline.healthy_min}")
            if guideline.healthy_max is not None:
                range_parts.append(f"max {guideline.healthy_max}")
            if range_parts:
                lines.append(f"  Guideline range: {', '.join(range_parts)}")
            if guideline.low_means:
                lines.append(f"  When low: {guideline.low_means}")
            if guideline.high_means:
                lines.append(f"  When high: {guideline.high_means}")
            lines.append("")
        return "\n".join(lines)


class ProcessingConfig(BaseModel):
    batch_size: int = 15
    segments_per_coder_call: int = 5  # micro-batch: segments per LLM call
    its_saturation_threshold: float = 0.02
    its_consecutive_batches: int = 3
    similarity_prefilter_k: int = 5
    merge_conflict_similarity_threshold: float = 0.75
    auto_new_threshold: float = 0.5      # max_sim below this → auto-NEW (skip LLM)
    auto_merge_threshold: float = 0.8    # max_sim above this → auto-MERGE (skip LLM)
    category_merge_threshold: float = 0.85  # centroid sim above this → merge categories
    coherence_threshold: float = 1.0     # normalized coherence below this → flag/dissolve
    coherence_threshold_small: float = 0.90  # threshold for themes with <5 ICs
    meta_ic_filter: MetaICFilterConfig = Field(default_factory=MetaICFilterConfig)


class EQDConfig(BaseModel):
    providers: Dict[str, ProviderConfig]
    models: Dict[str, NamedModel]
    agents: Dict[str, AgentParams]
    study: StudyConfig
    processing: ProcessingConfig
    theme_refinement: ThemeRefinementConfig = Field(default_factory=ThemeRefinementConfig)
    analyst_guidelines: AnalystGuidelinesConfig = Field(default_factory=AnalystGuidelinesConfig)


def load_config(config_path: Optional[Path] = None) -> EQDConfig:
    """Load and validate YAML config file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "eqd_config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    # Parse providers
    providers = {
        k: ProviderConfig(**v) for k, v in raw.get("providers", {}).items()
    }
    models = {
        k: NamedModel(**v) for k, v in raw.get("models", {}).items()
    }
    agents = {
        k: AgentParams(**v) for k, v in raw.get("agents", {}).items()
    }
    study = StudyConfig(**raw.get("study", {}))
    processing = ProcessingConfig(**raw.get("processing", {}))
    theme_refinement = ThemeRefinementConfig(**raw.get("theme_refinement", {}))

    # Parse analyst guidelines — each metric is a nested dict
    raw_guidelines = raw.get("analyst_guidelines", {})
    guidelines_parsed = {}
    for metric_name, metric_data in raw_guidelines.items():
        if isinstance(metric_data, dict):
            guidelines_parsed[metric_name] = MetricGuidelineConfig(**metric_data)
    analyst_guidelines = AnalystGuidelinesConfig(**guidelines_parsed)

    return EQDConfig(
        providers=providers, models=models, agents=agents,
        study=study, processing=processing,
        theme_refinement=theme_refinement,
        analyst_guidelines=analyst_guidelines,
    )


# ── ModelClient ───────────────────────────────────────────────────────────────

class ModelClient:
    """
    Thin wrapper: reads config, returns instructor-patched client per agent.

    Usage:
        config = load_config()
        mc = ModelClient(config)
        client, model_id, params = mc.get_client("coder_agent")
        result = client.chat.completions.create(
            model=model_id,
            response_model=SomePydanticModel,
            messages=[...],
            temperature=params.temperature,
        )
    """

    def __init__(self, config: EQDConfig, env_path: Optional[Path] = None):
        self.config = config
        # Load .env if present
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        self._clients: Dict[str, Any] = {}
        self._validate_providers()

    def _validate_providers(self) -> None:
        """Fail fast: check that required env vars exist for configured agents."""
        needed_providers = set()
        for agent_cfg in self.config.agents.values():
            model_cfg = self.config.models.get(agent_cfg.model)
            if model_cfg:
                needed_providers.add(model_cfg.provider)

        for provider_name in needed_providers:
            provider = self.config.providers.get(provider_name)
            if not provider:
                raise ValueError(f"Provider '{provider_name}' referenced but not configured")
            api_key = os.environ.get(provider.api_key_env, "")
            if not api_key:
                raise EnvironmentError(
                    f"Environment variable '{provider.api_key_env}' is not set. "
                    f"Required for provider '{provider_name}'. "
                    f"Set it in your .env file."
                )

    def get_client(self, agent_name: str) -> Tuple[Any, str, AgentParams]:
        """
        Return (instructor_patched_client, model_id, agent_params) for an agent.

        Routes based on provider type:
        - openai_compatible → instructor.patch(OpenAI(...))
        - anthropic → instructor.from_anthropic(Anthropic(...))
        """
        agent_cfg = self.config.agents.get(agent_name)
        if not agent_cfg:
            raise ValueError(f"Unknown agent: '{agent_name}'")

        model_cfg = self.config.models.get(agent_cfg.model)
        if not model_cfg:
            raise ValueError(f"Unknown model: '{agent_cfg.model}'")

        provider = self.config.providers.get(model_cfg.provider)
        if not provider:
            raise ValueError(f"Unknown provider: '{model_cfg.provider}'")

        client = self._get_or_create_client(model_cfg.provider, provider)
        return client, model_cfg.model_id, agent_cfg

    def get_embedding_client(self) -> Tuple[Any, str]:
        """
        Return (raw_openai_client, model_id) for embedding operations.

        Embedding API uses different method (client.embeddings.create) so
        we return the raw client, not instructor-patched.
        """
        agent_cfg = self.config.agents.get("embedding")
        if not agent_cfg:
            raise ValueError("No 'embedding' agent configured")

        model_cfg = self.config.models.get(agent_cfg.model)
        if not model_cfg:
            raise ValueError(f"Unknown model: '{agent_cfg.model}'")

        provider = self.config.providers.get(model_cfg.provider)
        if not provider:
            raise ValueError(f"Unknown provider: '{model_cfg.provider}'")

        # Return raw client (not instructor-patched) for embeddings
        cache_key = f"raw_{model_cfg.provider}"
        if cache_key not in self._clients:
            api_key = os.environ.get(provider.api_key_env, "")
            if provider.type == "openai_compatible":
                from openai import OpenAI
                kwargs: Dict[str, Any] = {"api_key": api_key}
                if provider.base_url:
                    kwargs["base_url"] = provider.base_url
                self._clients[cache_key] = OpenAI(**kwargs)
            else:
                raise ValueError(
                    f"Embedding via provider type '{provider.type}' not yet supported. "
                    f"Use an openai_compatible provider."
                )

        return self._clients[cache_key], model_cfg.model_id

    def build_extra_body(self, agent_name: str) -> dict:
        """
        Return provider-specific extra_body params for reasoning effort control.

        Returns an empty dict if:
          - the agent's model has no reasoning (reasoning: false / omitted)
          - no reasoning_effort is configured for the agent
          - the reasoning_style is not recognised

        Translation table:
          openai style  → {"reasoning_effort": "low"|"medium"|"high"}
                          ("off" maps to "low" — OpenAI has no true off)
          gemini style  → {"generationConfig": {"thinkingConfig": {"thinkingBudget": N}}}
                          N: off=0, low=512, medium=4096, high=8192
          deepseek style → no effort control param supported yet; returns {}
          anthropic style → not handled here (thinking requires message-level param); returns {}

        New reasoning_style values can be added to _EFFORT_TRANSLATORS below.
        """
        agent_cfg = self.config.agents.get(agent_name)
        if not agent_cfg or not agent_cfg.reasoning_effort:
            return {}

        model_cfg = self.config.models.get(agent_cfg.model)
        if not model_cfg or not model_cfg.reasoning:
            return {}

        effort = agent_cfg.reasoning_effort.lower()
        style = (model_cfg.reasoning_style or "").lower()

        _OPENAI_EFFORT = {"off": "low", "low": "low", "medium": "medium", "high": "high"}
        _GEMINI_BUDGET = {"off": 0, "low": 512, "medium": 4096, "high": 8192}

        if style == "openai":
            mapped = _OPENAI_EFFORT.get(effort)
            return {"reasoning_effort": mapped} if mapped else {}

        elif style == "gemini":
            budget = _GEMINI_BUDGET.get(effort)
            if budget is not None:
                return {"generationConfig": {"thinkingConfig": {"thinkingBudget": budget}}}
            return {}

        # deepseek / anthropic / unknown: no effort param yet
        return {}

    def _get_or_create_client(self, provider_name: str, provider: ProviderConfig) -> Any:
        """Lazy-init and cache instructor-patched clients."""
        if provider_name in self._clients:
            return self._clients[provider_name]

        import instructor

        api_key = os.environ.get(provider.api_key_env, "")

        if provider.type == "openai_compatible":
            from openai import OpenAI
            kwargs: Dict[str, Any] = {"api_key": api_key}
            if provider.base_url:
                kwargs["base_url"] = provider.base_url
            raw = OpenAI(**kwargs)
            # Google's OpenAI-compat endpoint can't handle instructor's default tool-call
            # mode when Pydantic models contain List fields (generates multiple tool calls).
            # JSON mode forces a single JSON object response, which works correctly.
            if provider.instructor_mode == "json":
                client = instructor.from_openai(raw, mode=instructor.Mode.JSON)
            else:
                client = instructor.from_openai(raw)

        elif provider.type == "anthropic":
            from anthropic import Anthropic
            # Extended output beta: enables up to 128k output tokens.
            # Sent as a default header so all calls through this client benefit
            # without touching individual call sites.
            raw = Anthropic(
                api_key=api_key,
                default_headers={"anthropic-beta": "output-128k-2025-02-19"},
            )
            client = instructor.from_anthropic(raw)

        else:
            raise ValueError(f"Unknown provider type: '{provider.type}'")

        self._clients[provider_name] = client
        return client
