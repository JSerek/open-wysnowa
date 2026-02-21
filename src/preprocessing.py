"""
EQD-AI Layer 0: Preprocessing Pipeline.

normalize → canonicalize → segment → batch.

Key invariant: canonical_text is IMMUTABLE after creation.
All verbatim quote spans reference canonical_text, so we never lowercase
(case-preserving normalization).
"""

from __future__ import annotations

import hashlib
import unicodedata
import re
from typing import Iterator, List, Tuple

from src.db import Database, DocumentRepo, SegmentRepo
from src.models import Document, Segment, new_id


# ── Normalization ────────────────────────────────────────────────────────────

def normalize(text: str) -> Tuple[str, List[str]]:
    """
    Normalize text while preserving case (for verbatim quote grounding).

    Returns:
        (normalized_text, list_of_rules_applied)

    Rules applied in order:
    1. NFKC unicode normalization (e.g., ﬁ → fi, ² → 2)
    2. Strip leading/trailing whitespace
    3. Strip zero-width characters
    4. Collapse multiple whitespace (spaces, tabs, newlines) to single space

    NOT applied (by design):
    - Lowercasing — canonical_text must preserve case for span matching
    - Punctuation removal — quotes may include punctuation
    - Stopword removal — not appropriate for qualitative analysis
    """
    rules: List[str] = []
    result = text

    # 1. NFKC unicode normalization
    nfkc = unicodedata.normalize("NFKC", result)
    if nfkc != result:
        rules.append("nfkc_unicode")
    result = nfkc

    # 2. Strip leading/trailing whitespace
    stripped = result.strip()
    if stripped != result:
        rules.append("strip_whitespace")
    result = stripped

    # 3. Remove zero-width characters (ZWJ, ZWNJ, ZWSP, BOM, etc.)
    #    Must happen BEFORE whitespace collapse so adjacent spaces merge.
    cleaned = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", result)
    if cleaned != result:
        rules.append("remove_zero_width")
    result = cleaned

    # 4. Collapse multiple whitespace to single space
    collapsed = re.sub(r"\s+", " ", result)
    if collapsed != result:
        rules.append("collapse_whitespace")
    result = collapsed

    return result, rules


# ── Canonicalization ─────────────────────────────────────────────────────────

def canonicalize(document: Document, segment_index: int = 0) -> Segment:
    """
    Create an immutable Segment from a Document.

    One Document → one Segment (1:1 for now; multi-segment splitting
    can be added later if documents are long).

    The canonical_text is the normalized version of the raw text.
    content_hash is SHA-256 of canonical_text for integrity checks.
    """
    canonical_text, rules = normalize(document.raw_text)
    content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    return Segment(
        id=new_id(),
        document_id=document.id,
        canonical_text=canonical_text,
        original_text=document.raw_text,
        char_count=len(canonical_text),
        segment_index=segment_index,
        normalization_rules=rules,
        content_hash=content_hash,
    )


# ── Corpus Segmentation & Batching ──────────────────────────────────────────

def segment_corpus(documents: List[Document]) -> List[Segment]:
    """
    Convert a list of Documents into Segments (canonicalized).

    Currently 1:1 Document→Segment. If we later need to split long
    documents into multiple segments, this is the place to do it.
    """
    segments: List[Segment] = []
    for doc in documents:
        seg = canonicalize(doc)
        segments.append(seg)
    return segments


def batch_segments(segments: List[Segment], batch_size: int = 15) -> Iterator[List[Segment]]:
    """
    Yield batches of segments for processing.

    batch_size comes from eqd_config.yaml → processing.batch_size.
    Used by the Coder Agent to process segments in manageable chunks
    while tracking ITS (Incremental Type Saturation).
    """
    for i in range(0, len(segments), batch_size):
        yield segments[i : i + batch_size]


# ── Persistence ──────────────────────────────────────────────────────────────

def persist_documents(documents: List[Document], db: Database) -> None:
    """Insert documents into SQLite."""
    repo = DocumentRepo(db)
    for doc in documents:
        repo.insert(doc)


def persist_segments(segments: List[Segment], db: Database) -> None:
    """Insert segments into SQLite."""
    repo = SegmentRepo(db)
    for seg in segments:
        repo.insert(seg)


# ── Full Pipeline ────────────────────────────────────────────────────────────

def preprocess_documents(
    documents: List[Document],
    db: Database,
) -> List[Segment]:
    """
    Full Layer 0 pipeline: persist docs → canonicalize → persist segments.

    Returns the list of created Segments for downstream processing.
    """
    # 1. Persist raw documents
    persist_documents(documents, db)

    # 2. Canonicalize
    segments = segment_corpus(documents)

    # 3. Persist segments
    persist_segments(segments, db)

    return segments
