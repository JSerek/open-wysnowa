"""
EQD-AI Category Agent — Higher-Order Theme Grouping.

Groups final themes into higher-order categories using a single LLM call,
then validates proposals programmatically (merge overlapping, absorb singletons).

Categories are the broadest level: Category → Theme → IC → Quote.

Uses a lightweight model (haiku) since this is a simple grouping task.
Falls back to synthesizer_agent config if category_agent not configured.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import EQDConfig, ModelClient
from src.db import CategoryRepo, Database, InitialCodeRepo, ThemeRepo
from src.embeddings import cosine_similarity
from src.models import (
    Category,
    CategoryProposal,
    CategorySynthesisOutput,
    CategoryTheme,
    Theme,
)
from src.prompts import build_category_system_prompt, build_category_user_prompt


class _CategoryMergeNameOutput(BaseModel):
    """Internal: LLM-proposed name and definition for a merged category."""

    name: str = Field(
        min_length=1,
        max_length=150,
        description="Concise 2-5 word category label that captures the essence of both merged groups.",
    )
    definition: str = Field(
        min_length=10,
        max_length=800,
        description="1-2 sentence definition covering all constituent themes from both merged categories.",
    )

logger = logging.getLogger(__name__)


def _compute_adaptive_target(theme_count: int) -> int:
    """Compute target category count: max(3, min(8, theme_count // 3))."""
    return max(3, min(8, theme_count // 3))


class CategoryAgent:
    """
    Groups final themes into higher-order categories.

    Pipeline: LLM proposal → programmatic validation (merge/absorb) → persist.
    """

    def __init__(self, model_client: ModelClient, db: Database, config: EQDConfig):
        self.model_client = model_client
        self.db = db
        self.config = config

    def synthesize(
        self,
        themes_data: List[Dict[str, Any]],
    ) -> List[CategoryProposal]:
        """
        Propose categories for the given themes.

        Args:
            themes_data: list of dicts with name, definition, ic_count, ic_names,
                         and optionally ic_details (list of {name, definition, example_quote})

        Returns validated list of CategoryProposal, or empty list on failure.
        """
        if not themes_data:
            logger.warning("No themes to categorise")
            return []

        # Adaptive target count
        target_count = _compute_adaptive_target(len(themes_data))
        logger.info(
            f"[CAT:SYNTH] {len(themes_data)} themes → "
            f"target {target_count} categories"
        )

        system_prompt = build_category_system_prompt(target_count=target_count)
        user_prompt = build_category_user_prompt(themes_data)

        # Use category_agent config if available, otherwise fall back to synthesizer_agent
        agent_name = (
            "category_agent"
            if "category_agent" in self.config.agents
            else "synthesizer_agent"
        )
        client, model_id, params = self.model_client.get_client(agent_name)

        try:
            result = self._call_llm(
                client=client,
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
            )
            # Display chain-of-thought reasoning
            if result.reasoning:
                logger.info(f"[CAT:COT] {result.reasoning}")

            proposals = result.categories
            logger.info(f"[CAT:SYNTH] Proposed {len(proposals)} categories (pre-validation)")

            # Post-hoc validation: merge overlapping, absorb singletons
            validated = self._validate_proposals(proposals, themes_data)
            logger.info(f"[CAT:VALIDATE] After validation: {len(validated)} categories")
            return validated

        except Exception as e:
            logger.error(f"[ERROR] Category Agent failed: {e}")
            return []

    def persist(
        self,
        proposals: List[CategoryProposal],
        themes: List[Theme],
    ) -> List[Category]:
        """
        Persist category proposals to the database.

        Creates Category records + CategoryTheme junction records.
        Matches theme names from proposals to actual Theme objects.

        Returns list of persisted Category objects.
        """
        category_repo = CategoryRepo(self.db)
        name_to_theme = {t.name: t for t in themes}

        persisted: List[Category] = []

        for proposal in proposals:
            category = Category(
                name=proposal.name,
                definition=proposal.definition,
            )
            category_repo.insert(category)

            assigned = 0
            for theme_name in proposal.constituent_theme_names:
                theme = name_to_theme.get(theme_name)
                if theme:
                    category_repo.assign_theme(CategoryTheme(
                        category_id=category.id,
                        theme_id=theme.id,
                    ))
                    assigned += 1
                else:
                    logger.warning(
                        f"Category '{category.name}' references theme '{theme_name}' "
                        f"which was not found — skipping assignment"
                    )

            persisted.append(category)
            logger.debug(f"Category '{category.name}': {assigned} themes assigned")

        logger.info(f"[CAT:PERSIST] Persisted {len(persisted)} categories")
        return persisted

    # ── Validation ─────────────────────────────────────────────────────────────

    def _validate_proposals(
        self,
        proposals: List[CategoryProposal],
        themes_data: List[Dict[str, Any]],
    ) -> List[CategoryProposal]:
        """
        Post-hoc programmatic validation (no extra LLM call).

        1. Merge overlapping categories (centroid similarity > merge_threshold)
        2. Absorb singletons (categories with < 2 themes) into nearest category
        """
        if len(proposals) <= 1:
            return proposals

        merge_threshold = self.config.processing.category_merge_threshold

        # Compute centroids for each proposal
        centroids = self._compute_category_centroids(proposals, themes_data)

        # Step 1: Merge overlapping categories
        proposals, centroids = self._merge_overlapping(
            proposals, centroids, merge_threshold
        )

        # Step 2: Absorb singletons
        proposals, centroids = self._absorb_singletons(proposals, centroids)

        return proposals

    def _compute_category_centroids(
        self,
        proposals: List[CategoryProposal],
        themes_data: List[Dict[str, Any]],
    ) -> List[Optional[List[float]]]:
        """
        Compute centroid embedding for each category proposal.

        Centroid = mean of IC embeddings for all ICs in the category's themes.
        Returns a list parallel to proposals (None if no embeddings found).
        """
        ic_repo = InitialCodeRepo(self.db)

        # Build a fast lookup: theme_name → list of IC names
        theme_ic_names: Dict[str, List[str]] = {}
        for t in themes_data:
            theme_ic_names[t["name"]] = t.get("ic_names", [])

        centroids: List[Optional[List[float]]] = []
        for proposal in proposals:
            embeddings: List[List[float]] = []
            for theme_name in proposal.constituent_theme_names:
                ic_names = theme_ic_names.get(theme_name, [])
                for ic_name in ic_names:
                    ic = ic_repo.get_by_name(ic_name)
                    if ic and ic.embedding_json:
                        embeddings.append(ic.embedding_json)

            if not embeddings:
                centroids.append(None)
                continue

            dim = len(embeddings[0])
            centroid = [
                sum(emb[d] for emb in embeddings) / len(embeddings)
                for d in range(dim)
            ]
            centroids.append(centroid)

        return centroids

    def _merge_overlapping(
        self,
        proposals: List[CategoryProposal],
        centroids: List[Optional[List[float]]],
        threshold: float,
    ) -> Tuple[List[CategoryProposal], List[Optional[List[float]]]]:
        """
        Merge category pairs with centroid similarity > threshold.

        Combines theme lists; keeps the longer definition.
        """
        merged_indices: set = set()
        merged_proposals: List[CategoryProposal] = []
        merged_centroids: List[Optional[List[float]]] = []

        for i in range(len(proposals)):
            if i in merged_indices:
                continue

            current = proposals[i]
            current_centroid = centroids[i]
            theme_names = list(current.constituent_theme_names)
            merged_partners: List[Tuple[str, str]] = []  # (name, definition)

            for j in range(i + 1, len(proposals)):
                if j in merged_indices:
                    continue

                c_i = current_centroid
                c_j = centroids[j]
                if c_i is None or c_j is None:
                    continue

                sim = cosine_similarity(c_i, c_j)
                if sim > threshold:
                    logger.info(
                        f"[CAT:MERGE] '{current.name}' + '{proposals[j].name}' "
                        f"(centroid sim={sim:.3f} > {threshold})"
                    )
                    merged_indices.add(j)
                    theme_names.extend(proposals[j].constituent_theme_names)
                    merged_partners.append((proposals[j].name, proposals[j].definition))

            if merged_partners:
                # LLM rename: propose a semantically accurate merged name
                merged_name, merged_def = self._llm_rename_merged(
                    name_a=current.name,
                    def_a=current.definition,
                    name_b=merged_partners[0][0],
                    def_b=merged_partners[0][1],
                    theme_names=list(dict.fromkeys(theme_names)),
                )
            else:
                merged_name = current.name
                merged_def = current.definition

            merged_proposals.append(
                CategoryProposal(
                    name=merged_name,
                    definition=merged_def,
                    constituent_theme_names=list(dict.fromkeys(theme_names)),  # dedup
                )
            )
            merged_centroids.append(current_centroid)

        if len(merged_proposals) < len(proposals):
            logger.info(
                f"[CAT:VALIDATE] Merged {len(proposals)} → {len(merged_proposals)} categories"
            )

        return merged_proposals, merged_centroids

    def _absorb_singletons(
        self,
        proposals: List[CategoryProposal],
        centroids: List[Optional[List[float]]],
    ) -> Tuple[List[CategoryProposal], List[Optional[List[float]]]]:
        """
        Absorb singleton categories (< 2 themes) into nearest category by centroid.
        """
        if len(proposals) <= 1:
            return proposals, centroids

        singletons = [
            i for i, p in enumerate(proposals)
            if len(p.constituent_theme_names) < 2
        ]

        if not singletons:
            return proposals, centroids

        non_singletons = [
            i for i in range(len(proposals))
            if i not in singletons
        ]

        if not non_singletons:
            # All are singletons — can't absorb, return as-is
            return proposals, centroids

        for s_idx in singletons:
            s_centroid = centroids[s_idx]
            best_target = None
            best_sim = -1.0

            for ns_idx in non_singletons:
                ns_centroid = centroids[ns_idx]
                if s_centroid is None or ns_centroid is None:
                    continue
                sim = cosine_similarity(s_centroid, ns_centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_target = ns_idx

            if best_target is not None:
                target = proposals[best_target]
                singleton = proposals[s_idx]
                logger.info(
                    f"[CAT:ABSORB] '{singleton.name}' "
                    f"→ '{target.name}' (sim={best_sim:.3f})"
                )
                # Add singleton's themes to target
                combined = list(target.constituent_theme_names) + list(
                    singleton.constituent_theme_names
                )
                proposals[best_target] = CategoryProposal(
                    name=target.name,
                    definition=target.definition,
                    constituent_theme_names=list(dict.fromkeys(combined)),
                )
            else:
                # No centroid match — assign to first non-singleton
                target = proposals[non_singletons[0]]
                singleton = proposals[s_idx]
                logger.info(
                    f"[CAT:ABSORB] '{singleton.name}' "
                    f"→ '{target.name}' (fallback, no centroid)"
                )
                combined = list(target.constituent_theme_names) + list(
                    singleton.constituent_theme_names
                )
                proposals[non_singletons[0]] = CategoryProposal(
                    name=target.name,
                    definition=target.definition,
                    constituent_theme_names=list(dict.fromkeys(combined)),
                )

        # Remove absorbed singletons
        result_proposals = [p for i, p in enumerate(proposals) if i not in singletons]
        result_centroids = [c for i, c in enumerate(centroids) if i not in singletons]

        if len(result_proposals) < len(proposals):
            logger.info(
                f"[CAT:VALIDATE] Absorbed {len(singletons)} singleton(s): "
                f"{len(proposals)} → {len(result_proposals)} categories"
            )

        return result_proposals, result_centroids

    # ── LLM Rename ───────────────────────────────────────────────────────────

    def _llm_rename_merged(
        self,
        name_a: str,
        def_a: str,
        name_b: str,
        def_b: str,
        theme_names: List[str],
    ) -> Tuple[str, str]:
        """
        Propose a merged category name + definition via a short LLM call (~200 tokens).

        Called when _merge_overlapping() collapses two semantically overlapping
        categories. The LLM receives both original names/definitions and the
        combined theme list, then proposes a single coherent label and definition.

        Falls back to the longer-definition heuristic on any error.
        """
        agent_name = (
            "category_agent"
            if "category_agent" in self.config.agents
            else "synthesizer_agent"
        )
        client, model_id, _ = self.model_client.get_client(agent_name)

        themes_str = ", ".join(f'"{t}"' for t in theme_names)
        system = (
            "You are renaming a merged category. Two overlapping categories were "
            "combined because their content was semantically similar. Propose a single "
            "concise name (2-5 words) and a brief definition that covers both groups. "
            "The name should be more accurate than either original."
        )
        user = (
            f"Category A: '{name_a}'\n  Definition: {def_a}\n\n"
            f"Category B: '{name_b}'\n  Definition: {def_b}\n\n"
            f"Combined themes: {themes_str}\n\n"
            f"Propose a single merged category name and definition."
        )

        try:
            result = client.chat.completions.create(
                model=model_id,
                response_model=_CategoryMergeNameOutput,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            logger.info(f"[CAT:RENAME] '{name_a}' + '{name_b}' → '{result.name}'")
            return result.name, result.definition
        except Exception as e:
            logger.warning(
                f"[CAT:RENAME] LLM rename failed ({e}) — using heuristic fallback"
            )
            # Fall back: keep whichever definition is longer
            if len(def_b) > len(def_a):
                return name_b, def_b
            return name_a, def_a

    # ── LLM Call ─────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_llm(
        self,
        client: Any,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> CategorySynthesisOutput:
        """Instructor-patched LLM call for category synthesis."""
        return client.chat.completions.create(
            model=model_id,
            response_model=CategorySynthesisOutput,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
