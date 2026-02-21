"""
Shared pytest fixtures for EQD-AI tests.

Uses in-memory SQLite for speed. Sample data uses Polish product reviews
to match the intended use case.
"""

import pytest
from datetime import datetime

from src.db import Database
from src.models import (
    Document,
    InitialCode,
    ICStatus,
    Segment,
    VerbatimQuote,
    Theme,
    ThemeIC,
    new_id,
)


@pytest.fixture
def db():
    """In-memory SQLite database with schema initialized."""
    database = Database(":memory:")
    database.init_schema()
    return database


@pytest.fixture
def sample_documents():
    """Sample Polish product review documents."""
    return [
        Document(
            id="doc_001",
            source_file="reviews_batch1.csv",
            raw_text="Produkt jest świetny, ale  dostawa   trwała zbyt długo. Paczka była uszkodzona.",
            metadata={"source": "allegro", "rating": 3},
        ),
        Document(
            id="doc_002",
            source_file="reviews_batch1.csv",
            raw_text="Jakość materiału jest\tznakomita. Polecam każdemu!",
            metadata={"source": "allegro", "rating": 5},
        ),
        Document(
            id="doc_003",
            source_file="reviews_batch1.csv",
            raw_text="  Zwrot pieniędzy trwał 2 tygodnie. Obsługa klienta nie odpowiadała na maile.  ",
            metadata={"source": "ceneo", "rating": 1},
        ),
    ]


@pytest.fixture
def sample_segment():
    """A pre-built segment with known canonical text."""
    return Segment(
        id="seg_001",
        document_id="doc_001",
        canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo. Paczka była uszkodzona.",
        original_text="Produkt jest świetny, ale  dostawa   trwała zbyt długo. Paczka była uszkodzona.",
        char_count=75,
        segment_index=0,
        normalization_rules=["collapse_whitespace"],
        content_hash="placeholder_hash",
    )


@pytest.fixture
def sample_ics():
    """Sample Initial Codes with known embeddings (3-dim for testing)."""
    return [
        InitialCode(
            id="ic_001",
            name="Delivery speed complaint",
            definition="Customer expresses dissatisfaction with the time taken for delivery",
            embedding_json=[0.8, 0.1, 0.3],
            status=ICStatus.ACTIVE,
        ),
        InitialCode(
            id="ic_002",
            name="Product quality praise",
            definition="Customer praises the quality of materials or workmanship",
            embedding_json=[0.1, 0.9, 0.2],
            status=ICStatus.ACTIVE,
        ),
        InitialCode(
            id="ic_003",
            name="Packaging damage",
            definition="Customer reports that the package arrived damaged or broken",
            embedding_json=[0.7, 0.2, 0.4],
            status=ICStatus.ACTIVE,
        ),
    ]


@pytest.fixture
def sample_quotes(sample_segment):
    """Verbatim quotes with correct spans against sample_segment's canonical_text."""
    canonical = sample_segment.canonical_text
    # "dostawa trwała zbyt długo"
    q1_text = "dostawa trwała zbyt długo"
    q1_start = canonical.index(q1_text)
    # "Paczka była uszkodzona"
    q2_text = "Paczka była uszkodzona"
    q2_start = canonical.index(q2_text)

    return [
        VerbatimQuote(
            id="vq_001",
            ic_id="ic_001",
            segment_id="seg_001",
            quote_text=q1_text,
            span_start=q1_start,
            span_end=q1_start + len(q1_text),
        ),
        VerbatimQuote(
            id="vq_002",
            ic_id="ic_003",
            segment_id="seg_001",
            quote_text=q2_text,
            span_start=q2_start,
            span_end=q2_start + len(q2_text),
        ),
    ]
