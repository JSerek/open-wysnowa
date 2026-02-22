"""
EQD-AI Layer 2: Synthesizer Agent.

Builds themes from the signed-off codebook. Uses LLM (instructor + Pydantic)
to propose themes, then revises based on human feedback (max 3 rounds).

Pattern: same instructor + tenacity + Pydantic as Layer 1 agents.
Model config: synthesizer_agent (claude_sonnet, temp 0.3, max 8000 tokens).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import EQDConfig, ModelClient
from src.db import Database, InitialCodeRepo, ThemeRepo, VerbatimQuoteRepo
from src.models import (
    RevisionOutput,
    SynthesisOutput,
    Theme,
    ThemeFeedback,
    ThemeIC,
    ThemeProposal,
)
from src.prompts import (
    build_revision_system_prompt,
    build_revision_user_prompt,
    build_synthesizer_system_prompt,
    build_synthesizer_user_prompt,
)

logger = logging.getLogger(__name__)


class SynthesizerAgent:
    """
    Theme synthesis from the signed-off codebook.

    Two modes:
    1. synthesize() — initial theme proposal (round 1)
    2. revise() — apply human feedback and re-synthesize (rounds 2-3)

    Themes are ThemeProposal objects until persisted. The pipeline
    handles persistence after final sign-off.
    """

    def __init__(self, model_client: ModelClient, db: Database, config: EQDConfig):
        self.model_client = model_client
        self.db = db
        self.config = config

    def synthesize(self) -> List[ThemeProposal]:
        """
        Initial theme synthesis from the full codebook (round 1).

        1. Fetch all active ICs with quote counts + example quotes
        2. Build prompts
        3. Call LLM → SynthesisOutput
        4. Return list of ThemeProposal

        Returns empty list on LLM failure.
        """
        codebook_data = self._build_codebook_data()

        if not codebook_data:
            logger.warning("Empty codebook — cannot synthesize themes")
            return []

        system_prompt = build_synthesizer_system_prompt()
        user_prompt = build_synthesizer_user_prompt(codebook_data)

        client, model_id, params = self.model_client.get_client("synthesizer_agent")

        try:
            result = self._call_synthesis_llm(
                client=client,
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
            )
            logger.info(f"[THEME:SYNTH] Proposed {len(result.themes)} themes")
            # Display chain-of-thought reasoning
            if result.reasoning:
                logger.info(f"[THEME:COT] {result.reasoning}")
            return result.themes

        except Exception as e:
            logger.error(f"[ERROR] Synthesizer Agent failed: {e}")
            return []

    def revise(
        self,
        current_themes: List[ThemeProposal],
        feedback: List[ThemeFeedback],
    ) -> Optional[List[ThemeProposal]]:
        """
        Revise themes based on human feedback (rounds 2-3).

        Args:
            current_themes: current theme proposals
            feedback: list of structured feedback items

        Returns revised themes, or None on failure.
        """
        if not feedback:
            logger.info("No feedback provided — returning current themes unchanged")
            return current_themes

        system_prompt = build_revision_system_prompt()
        user_prompt = build_revision_user_prompt(current_themes, feedback)

        client, model_id, params = self.model_client.get_client("synthesizer_agent")

        try:
            result = self._call_revision_llm(
                client=client,
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
            )
            logger.info(
                f"[THEME:REVISE] Revision complete: {len(result.themes)} themes. "
                f"Changes: {result.changes_summary}"
            )
            return result.themes

        except Exception as e:
            logger.error(f"[ERROR] Synthesizer revision failed: {e}")
            return None

    def persist_themes(
        self,
        themes: List[ThemeProposal],
        round_number: int,
    ) -> List[Theme]:
        """
        Persist final themes to the database.

        Creates Theme + ThemeIC junction records.
        Returns list of created Theme objects.

        Called by the pipeline after final sign-off.
        """
        ic_repo = InitialCodeRepo(self.db)
        theme_repo = ThemeRepo(self.db)

        # Build IC name → ID lookup
        active_ics = ic_repo.get_all_active()
        name_to_id = {ic.name: ic.id for ic in active_ics}

        persisted: List[Theme] = []

        for proposal in themes:
            theme = Theme(
                name=proposal.name,
                definition=proposal.definition,
                rationale=proposal.rationale,
                round_finalised=round_number,
            )
            theme_repo.insert(theme)

            # Create M:N junctions
            for ic_name in proposal.constituent_ic_names:
                ic_id = name_to_id.get(ic_name)
                if ic_id:
                    theme_repo.assign_ic(ThemeIC(
                        theme_id=theme.id,
                        ic_id=ic_id,
                    ))
                else:
                    logger.warning(
                        f"Theme '{theme.name}' references IC '{ic_name}' "
                        f"which is not in the active codebook — skipping assignment"
                    )

            persisted.append(theme)

        logger.info(f"[THEME:PERSIST] Persisted {len(persisted)} themes (round {round_number})")
        return persisted

    # ── Internal Methods ─────────────────────────────────────────────────────

    def _build_codebook_data(self) -> List[Dict[str, Any]]:
        """
        Build codebook data for the synthesizer prompt.

        Returns list of dicts: {name, definition, quote_count, example_quotes}.
        """
        ic_repo = InitialCodeRepo(self.db)
        vq_repo = VerbatimQuoteRepo(self.db)

        codebook = ic_repo.get_all_active()
        data: List[Dict[str, Any]] = []

        for ic in codebook:
            quotes = vq_repo.get_all_for_ic(ic.id)
            example_quotes = [q.quote_text for q in quotes[:3]]

            data.append({
                "name": ic.name,
                "definition": ic.definition,
                "quote_count": len(quotes),
                "example_quotes": example_quotes,
            })

        return data

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
    ) -> SynthesisOutput:
        """Instructor-patched LLM call for initial synthesis."""
        # Extended output beta: Claude models support up to 128k output tokens with this header.
        # Without it, the API caps at 8,192 regardless of max_tokens value.
        extra = {}
        if "claude" in model_id.lower():
            extra["betas"] = ["output-128k-2025-02-19"]
        return client.chat.completions.create(
            model=model_id,
            response_model=SynthesisOutput,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **extra,
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_revision_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> RevisionOutput:
        """Instructor-patched LLM call for theme revision."""
        extra = {}
        if "claude" in model_id.lower():
            extra["betas"] = ["output-128k-2025-02-19"]
        return client.chat.completions.create(
            model=model_id,
            response_model=RevisionOutput,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **extra,
        )
