"""
EQD-AI Layer 4: Analyst Intelligence Agent.

Three-call LLM architecture:
  Call 1: Metrics Interpretation — assess each quality metric
  Call 2: Structural Diagnostics — evaluate thematic structure
  Call 3: Synthesis & Recommendations — combine into actionable guidance

All calls use Sonnet 4.5 (configurable via analyst_agent in YAML).
Layer 4 failure is non-fatal — the pipeline still completes without it.

Pattern: same instructor + tenacity + Pydantic as other agents.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import EQDConfig, ModelClient
from src.reasoning_log import ReasoningLogger
from src.models import (
    AnalyticalBrief,
    AnalystSynthesis,
    MetricsInterpretation,
    StructuralDiagnostics,
)
from src.prompts import (
    build_analyst_synthesis_system_prompt,
    build_analyst_synthesis_user_prompt,
    build_metrics_interpretation_system_prompt,
    build_metrics_interpretation_user_prompt,
    build_structural_diagnostics_system_prompt,
    build_structural_diagnostics_user_prompt,
)

logger = logging.getLogger(__name__)


class AnalystAgent:
    """
    Layer 4: LLM-powered analytical interpretation.

    Consumes the full results dict from the pipeline and produces
    a structured AnalyticalBrief with three components:
      - MetricsInterpretation (quality metrics assessment)
      - StructuralDiagnostics (thematic structure evaluation)
      - AnalystSynthesis (overall recommendations)
    """

    def __init__(
        self,
        model_client: ModelClient,
        config: EQDConfig,
        reasoning_logger: Optional["ReasoningLogger"] = None,
    ):
        self.model_client = model_client
        self.config = config
        self.reasoning_logger = reasoning_logger

    def analyze(self, results: Dict[str, Any]) -> AnalyticalBrief:
        """
        Run all 3 analysis calls and return combined brief.

        Args:
            results: full pipeline results dict with layer0-3,
                     thematic_structure, categories, etc.

        Returns:
            AnalyticalBrief containing all three call outputs.

        Raises:
            Exception: if any of the 3 calls fail (caller handles).
        """
        logger.info("[ANALYST] Call 1/3: Metrics interpretation")
        metrics_interp = self._interpret_metrics(results)
        logger.info("[ANALYST] Call 1/3 complete")

        logger.info("[ANALYST] Call 2/3: Structural diagnostics")
        structural_diag = self._diagnose_structure(results)
        logger.info("[ANALYST] Call 2/3 complete")

        logger.info("[ANALYST] Call 3/3: Synthesis & recommendations")
        synthesis = self._synthesize(metrics_interp, structural_diag, results)
        logger.info("[ANALYST] Call 3/3 complete")

        return AnalyticalBrief(
            metrics=metrics_interp,
            structure=structural_diag,
            synthesis=synthesis,
        )

    # ── Call 1: Metrics Interpretation ─────────────────────────────────────

    def _interpret_metrics(self, results: Dict[str, Any]) -> MetricsInterpretation:
        """Call 1: interpret all quality metrics against guidelines."""
        client, model_id, params = self.model_client.get_client("analyst_agent")

        # Build run summary with enough context for the LLM
        layer0 = results.get("layer0", {})
        layer1 = results.get("layer1", {})
        layer3 = results.get("layer3", {})
        ic_conc = layer3.get("ic_concentration", {})

        # Drop rate comes from layer1 (candidates dropped / total)
        total_cand = layer1.get("total_candidates", 0)
        dropped = layer1.get("total_dropped", 0)
        drop_rate = (dropped / total_cand) if total_cand else None

        # Count themes + categories from thematic_structure
        ts = results.get("thematic_structure", [])
        n_cats = len(ts)
        n_themes = sum(len(c.get("themes", [])) for c in ts)

        run_summary = {
            "n_documents": layer0.get("documents", 0),
            "n_segments": layer0.get("segments", 0),
            "n_ics": ic_conc.get("total_ics", layer1.get("new_ics_created", 0)),
            "n_themes": n_themes,
            "n_categories": n_cats,
            "drop_rate": drop_rate,
        }

        system_prompt = build_metrics_interpretation_system_prompt()
        user_prompt = build_metrics_interpretation_user_prompt(
            results.get("layer3", {}),
            self.config.analyst_guidelines,
            run_summary,
        )

        return self._call_metrics_llm(
            client, model_id, system_prompt, user_prompt,
            params.temperature, params.max_tokens,
        )

    # ── Call 2: Structural Diagnostics ─────────────────────────────────────

    def _diagnose_structure(self, results: Dict[str, Any]) -> StructuralDiagnostics:
        """Call 2: evaluate the thematic structure."""
        client, model_id, params = self.model_client.get_client("analyst_agent")

        thematic_structure = results.get("thematic_structure", [])
        layer2_results = results.get("layer2", {})
        layer3 = results.get("layer3", {})

        # Build coherence data subset for the prompt
        coherence_data = {
            "theme_coherence": layer3.get("theme_coherence", {}),
            "theme_distinctness": layer3.get("theme_distinctness", {}),
            "sentiment_purity": layer3.get("sentiment_purity", {}),
        }

        system_prompt = build_structural_diagnostics_system_prompt()
        user_prompt = build_structural_diagnostics_user_prompt(
            thematic_structure, layer2_results, coherence_data,
        )

        return self._call_structural_llm(
            client, model_id, system_prompt, user_prompt,
            params.temperature, params.max_tokens,
        )

    # ── Call 3: Synthesis & Recommendations ────────────────────────────────

    def _synthesize(
        self,
        metrics_interp: MetricsInterpretation,
        structural_diag: StructuralDiagnostics,
        results: Dict[str, Any],
    ) -> AnalystSynthesis:
        """Call 3: synthesise metrics + structure into recommendations."""
        client, model_id, params = self.model_client.get_client("analyst_agent")

        # Build config summary (relevant processing params)
        proc = self.config.processing
        refine = self.config.theme_refinement
        config_summary = {
            "batch_size": proc.batch_size,
            "segments_per_coder_call": proc.segments_per_coder_call,
            "auto_merge_threshold": proc.auto_merge_threshold,
            "auto_new_threshold": proc.auto_new_threshold,
            "coherence_threshold": proc.coherence_threshold,
            "category_merge_threshold": proc.category_merge_threshold,
            "distinctness_threshold": refine.distinctness_threshold,
            "split_min_ics": refine.split_min_ics,
            "split_max_coherence": refine.split_max_coherence,
        }

        # Build run summary
        layer0 = results.get("layer0", {})
        layer1 = results.get("layer1", {})
        layer2 = results.get("layer2", {})
        ic_conc = results.get("layer3", {}).get("ic_concentration", {})
        run_summary = {
            "documents": layer0.get("documents", 0),
            "segments": layer0.get("segments", 0),
            "active_ics": ic_conc.get("active_ics", 0),
            "themes": layer2.get("themes_after_refinement", layer2.get("themes_proposed", 0)),
            "categories": results.get("categories", {}).get("categories_created", 0),
            "mode": "Discovery",
        }

        system_prompt = build_analyst_synthesis_system_prompt()
        user_prompt = build_analyst_synthesis_user_prompt(
            metrics_interp.model_dump(),
            structural_diag.model_dump(),
            config_summary,
            run_summary,
        )

        return self._call_synthesis_llm(
            client, model_id, system_prompt, user_prompt,
            params.temperature, params.max_tokens,
        )

    # ── LLM Call Methods ──────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_metrics_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> MetricsInterpretation:
        """Instructor-patched LLM call for metrics interpretation."""
        extra_body = self.model_client.build_extra_body("analyst_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=MetricsInterpretation,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("analyst_agent", model_id, raw)
        return parsed

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_structural_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> StructuralDiagnostics:
        """Instructor-patched LLM call for structural diagnostics."""
        extra_body = self.model_client.build_extra_body("analyst_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=StructuralDiagnostics,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("analyst_agent", model_id, raw)
        return parsed

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_synthesis_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AnalystSynthesis:
        """Instructor-patched LLM call for synthesis & recommendations."""
        extra_body = self.model_client.build_extra_body("analyst_agent")
        parsed, raw = client.chat.completions.create_with_completion(
            model=model_id,
            response_model=AnalystSynthesis,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        if self.reasoning_logger:
            self.reasoning_logger.log("analyst_agent", model_id, raw)
        return parsed
