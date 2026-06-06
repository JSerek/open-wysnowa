"""
EQD-AI Embedding Service.

Embed-on-write pattern: embeddings are computed when ICs are created/updated,
stored as JSON in SQLite. Cosine similarity for codebook comparison and
meaning saturation tracking.

Vectors stored as List[float] JSON — debuggable, sufficient for ~150 ICs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from src.core.config import EQDConfig, ModelClient
from src.core.db import Database, InitialCodeRepo, VerbatimQuoteRepo
from src.core.models import InitialCode, VerbatimQuote


# ── Cosine Similarity (pure Python — no numpy dependency for core) ───────────

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Returns value in [-1, 1]. Returns 0.0 if either vector is zero.
    Pure Python implementation — numpy is optional for batch ops.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector length mismatch: {len(vec_a)} vs {len(vec_b)}"
        )

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


# ── Similarity Result ────────────────────────────────────────────────────────

@dataclass
class SimilarityResult:
    """Result of comparing a new IC against an existing one."""
    ic_id: str
    ic_name: str
    similarity: float


# ── Embedding Service ────────────────────────────────────────────────────────

class EmbeddingService:
    """
    Manages all embedding operations for the EQD-AI system.

    Responsibilities:
    - Embed IC text (name | definition) on create/update
    - Embed verbatim quotes for meaning saturation
    - Find similar ICs in codebook (pre-filter for merge detection)
    - Compute theme coherence metrics

    Uses the embedding model configured in eqd_config.yaml → agents.embedding.
    """

    def __init__(self, model_client: ModelClient, db: Database):
        self.model_client = model_client
        self.db = db
        self._dimension: Optional[int] = None

    def embed_text(self, text: str) -> List[float]:
        """
        Get embedding vector for a text string.

        Uses the configured embedding model (e.g., text-embedding-3-small).
        """
        client, model_id = self.model_client.get_embedding_client()
        response = client.embeddings.create(
            model=model_id,
            input=text,
        )
        vector = response.data[0].embedding
        self._dimension = len(vector)
        return vector

    def embed_texts_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed multiple texts in a single API call.

        OpenAI embedding API supports batching natively.
        """
        if not texts:
            return []

        client, model_id = self.model_client.get_embedding_client()
        response = client.embeddings.create(
            model=model_id,
            input=texts,
        )
        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        vectors = [d.embedding for d in sorted_data]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def batch_embed_ics(self, ics: List[InitialCode]) -> List[InitialCode]:
        """
        Embed multiple ICs in a single API call.

        Sets embedding_json on each IC in place. Does NOT persist to DB —
        caller is responsible for inserting/updating.
        """
        if not ics:
            return ics
        texts = [ic.embedding_input_text() for ic in ics]
        embeddings = self.embed_texts_batch(texts)
        for ic, emb in zip(ics, embeddings):
            ic.embedding_json = emb
        return ics

    def batch_embed_quotes(self, quotes: List[VerbatimQuote]) -> List[VerbatimQuote]:
        """
        Embed multiple verbatim quotes in a single API call.

        Sets quote_embedding_json on each quote in place.
        """
        if not quotes:
            return quotes
        texts = [q.quote_text for q in quotes]
        embeddings = self.embed_texts_batch(texts)
        for q, emb in zip(quotes, embeddings):
            q.quote_embedding_json = emb
        return quotes

    def embed_ic(self, ic: InitialCode) -> InitialCode:
        """
        Compute and store embedding for an Initial Code (embed-on-write).

        Embeds: "{name} | {definition}"
        Updates the IC object in-place AND persists to DB.
        """
        text = ic.embedding_input_text()
        ic.embedding_json = self.embed_text(text)

        ic_repo = InitialCodeRepo(self.db)
        ic_repo.update(ic)

        return ic

    def embed_quote(self, quote: VerbatimQuote) -> VerbatimQuote:
        """
        Compute and store embedding for a verbatim quote.

        Used for meaning saturation tracking: if new quotes for an IC
        cluster close to existing ones, the IC is meaning-saturated.
        """
        quote.quote_embedding_json = self.embed_text(quote.quote_text)
        return quote

    def find_similar_ics(
        self,
        embedding: List[float],
        top_k: int = 5,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[SimilarityResult]:
        """
        Find the top-k most similar active ICs to a given embedding.

        Used by the Codebook Comparator to detect potential merges
        before creating a new IC.

        Only compares against ICs that have embeddings (skip any without).
        """
        ic_repo = InitialCodeRepo(self.db)
        active_ics = ic_repo.get_all_active()

        exclude = set(exclude_ids or [])
        results: List[SimilarityResult] = []

        for ic in active_ics:
            if ic.id in exclude:
                continue
            if not ic.embedding_json:
                continue

            sim = cosine_similarity(embedding, ic.embedding_json)
            results.append(SimilarityResult(
                ic_id=ic.id,
                ic_name=ic.name,
                similarity=sim,
            ))

        # Sort by similarity descending, take top_k
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def compute_theme_coherence(self, ic_ids: List[str]) -> float:
        """
        Internal coherence of a theme: average pairwise cosine similarity
        among its ICs' embeddings.

        Higher = more coherent theme. Analogous to intra-cluster similarity.
        Returns 0.0 if fewer than 2 ICs have embeddings.
        """
        ic_repo = InitialCodeRepo(self.db)
        embeddings: List[List[float]] = []

        for ic_id in ic_ids:
            ic = ic_repo.get_by_id(ic_id)
            if ic and ic.embedding_json:
                embeddings.append(ic.embedding_json)

        if len(embeddings) < 2:
            return 0.0

        total_sim = 0.0
        pair_count = 0
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                total_sim += cosine_similarity(embeddings[i], embeddings[j])
                pair_count += 1

        return total_sim / pair_count if pair_count > 0 else 0.0

    def compute_theme_distinctness(
        self, theme_ic_ids_list: List[List[str]]
    ) -> float:
        """
        External distinctness: average cosine similarity between theme centroids.

        Lower = more distinct themes. Analogous to inter-cluster distance.
        Returns 0.0 if fewer than 2 themes have computable centroids.
        """
        centroids: List[List[float]] = []

        ic_repo = InitialCodeRepo(self.db)
        for ic_ids in theme_ic_ids_list:
            embeddings = []
            for ic_id in ic_ids:
                ic = ic_repo.get_by_id(ic_id)
                if ic and ic.embedding_json:
                    embeddings.append(ic.embedding_json)

            if not embeddings:
                continue

            # Compute centroid (element-wise mean)
            dim = len(embeddings[0])
            centroid = [
                sum(emb[d] for emb in embeddings) / len(embeddings)
                for d in range(dim)
            ]
            centroids.append(centroid)

        if len(centroids) < 2:
            return 0.0

        total_sim = 0.0
        pair_count = 0
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                total_sim += cosine_similarity(centroids[i], centroids[j])
                pair_count += 1

        return total_sim / pair_count if pair_count > 0 else 0.0

    def compute_meaning_saturation(
        self, ic_id: str, new_quote_embedding: List[float]
    ) -> float:
        """
        Check if a new quote adds semantic novelty to an IC's evidence base.

        Returns the maximum similarity between the new quote embedding
        and existing quote embeddings for this IC.

        High value (>0.95) = redundant evidence → IC is meaning-saturated.
        Low value (<0.80) = novel evidence → IC still gaining depth.
        """
        vq_repo = VerbatimQuoteRepo(self.db)
        existing_quotes = vq_repo.get_all_for_ic(ic_id)

        if not existing_quotes:
            return 0.0  # First quote — always novel

        max_sim = 0.0
        for quote in existing_quotes:
            if quote.quote_embedding_json:
                sim = cosine_similarity(new_quote_embedding, quote.quote_embedding_json)
                max_sim = max(max_sim, sim)

        return max_sim
