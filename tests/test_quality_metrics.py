"""Tests for quality metrics engine — deterministic logic."""

import math
import pytest
from unittest.mock import MagicMock

from src.db import (
    Database,
    DocumentRepo,
    InitialCodeRepo,
    QualityMetricRepo,
    SegmentRepo,
    ThemeRepo,
    VerbatimQuoteRepo,
)
from src.embeddings import cosine_similarity
from src.models import (
    Document,
    InitialCode,
    ICStatus,
    QualityMetric,
    Segment,
    Theme,
    ThemeIC,
    VerbatimQuote,
)
from src.quality_metrics import QualityMetricsEngine


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def populated_db(db, sample_ics, sample_quotes):
    """DB with documents, segments, ICs, and quotes inserted."""
    doc = Document(id="doc_001", raw_text="test text")
    DocumentRepo(db).insert(doc)

    seg = Segment(
        id="seg_001", document_id="doc_001",
        canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo. Paczka była uszkodzona.",
        original_text="test", char_count=75, content_hash="hash",
    )
    SegmentRepo(db).insert(seg)

    ic_repo = InitialCodeRepo(db)
    for ic in sample_ics:
        ic_repo.insert(ic)

    vq_repo = VerbatimQuoteRepo(db)
    for vq in sample_quotes:
        vq_repo.insert(vq)

    return db


@pytest.fixture
def engine(populated_db):
    """QualityMetricsEngine with mocked embedding service."""
    emb_svc = MagicMock()
    return QualityMetricsEngine(populated_db, emb_svc)


# ── Grounding Tests ──────────────────────────────────────────────────────────

class TestGrounding:
    def test_all_quotes_verified(self, engine):
        """Both sample quotes have correct spans — should be 100% grounding."""
        result = engine.compute_grounding()
        assert result["total_quotes"] == 2
        assert result["verified"] == 2
        assert result["failed"] == 0
        assert result["grounding_rate"] == 1.0

    def test_no_quotes(self, db):
        """Empty DB should return 100% grounding (vacuously true)."""
        emb_svc = MagicMock()
        engine = QualityMetricsEngine(db, emb_svc)
        result = engine.compute_grounding()
        assert result["total_quotes"] == 0
        assert result["grounding_rate"] == 1.0


# ── Extraction Density Tests (replaces old Coverage Tests) ───────────────────

class TestExtractionDensity:
    def test_density_with_coded_segment(self, engine):
        """seg_001 has quotes — density should reflect character-level coverage."""
        result = engine.compute_extraction_density()
        assert result["total_segments"] == 1
        assert result["segments_with_codes"] == 1
        # Two quotes cover some fraction of the 75-char segment
        density = result["distribution"]["mean"]
        assert 0.0 < density <= 1.0

    def test_density_with_uncoded_segment(self, populated_db):
        """Add a segment without quotes — mean density should drop."""
        seg2 = Segment(
            id="seg_002", document_id="doc_001",
            canonical_text="Second segment without codes.",
            original_text="Second segment without codes.",
            char_count=30, content_hash="hash2",
        )
        SegmentRepo(populated_db).insert(seg2)

        emb_svc = MagicMock()
        engine = QualityMetricsEngine(populated_db, emb_svc)
        result = engine.compute_extraction_density()
        assert result["total_segments"] == 2
        assert result["segments_with_codes"] == 1
        # Mean density across 2 segments (one coded, one not) should be < first alone
        assert result["distribution"]["mean"] < 1.0
        assert result["distribution"]["min"] == 0.0  # uncoded segment

    def test_density_distribution_keys(self, engine):
        """Distribution dict should have all expected stats."""
        result = engine.compute_extraction_density()
        dist = result["distribution"]
        for key in ["mean", "median", "min", "max", "p25", "p75"]:
            assert key in dist


# ── Meaning Saturation v2 Tests ────────────────────────────────────────────

class TestMeaningSaturationV2:
    def test_no_themes_returns_empty(self, engine):
        """No themes in DB → empty result."""
        result = engine.compute_meaning_saturation_v2(
            ic_creation_segments={}, total_segments=10,
        )
        assert result == {}

    def test_theme_with_ic_creation_data(self, populated_db):
        """Theme with IC creation segments returns breadth + spread."""
        # Create a theme and assign ICs
        theme = Theme(
            id="theme_ms", name="MS Theme",
            definition="Theme for meaning saturation testing",
            rationale="test", round_finalised=1,
        )
        ThemeRepo(populated_db).insert(theme)
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_ms", ic_id="ic_001"))
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_ms", ic_id="ic_003"))

        emb_svc = MagicMock()
        engine = QualityMetricsEngine(populated_db, emb_svc)
        result = engine.compute_meaning_saturation_v2(
            ic_creation_segments={"ic_001": 0, "ic_003": 5},
            total_segments=10,
        )
        assert "MS Theme" in result
        theme_data = result["MS Theme"]
        assert "breadth" in theme_data
        assert "spread" in theme_data
        assert "ic_count" in theme_data
        # breadth = 5 / (10-1) ≈ 0.556
        assert 0.5 < theme_data["breadth"] < 0.6
        # spread uses the 3-dim test embeddings from conftest (ic_001 and ic_003)
        assert theme_data["spread"] >= 0.0


# ── Theme Coherence Tests ────────────────────────────────────────────────────

class TestThemeCoherence:
    def test_single_ic_theme_is_trivially_coherent(self, populated_db):
        """Theme with 1 IC should get coherence = 1.0."""
        theme = Theme(
            id="theme_001", name="Solo theme",
            definition="Theme with single IC for testing",
            rationale="Just one IC", round_finalised=1,
        )
        ThemeRepo(populated_db).insert(theme)
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_001", ic_id="ic_001"))

        emb_svc = MagicMock()
        # compute_theme_coherence is called with ic_ids; mock it
        emb_svc.compute_theme_coherence.return_value = 0.5  # Won't be called for single IC
        engine = QualityMetricsEngine(populated_db, emb_svc)
        coherence = engine.compute_theme_coherence()
        assert coherence["Solo theme"] == 1.0

    def test_multi_ic_theme_uses_embedding_service(self, populated_db):
        """Theme with 2+ ICs should call embedding_service.compute_theme_coherence."""
        theme = Theme(
            id="theme_002", name="Multi theme",
            definition="Theme with multiple ICs for testing coherence",
            rationale="Multiple ICs", round_finalised=1,
        )
        ThemeRepo(populated_db).insert(theme)
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_002", ic_id="ic_001"))
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_002", ic_id="ic_003"))

        emb_svc = MagicMock()
        emb_svc.compute_theme_coherence.return_value = 0.78
        engine = QualityMetricsEngine(populated_db, emb_svc)
        coherence = engine.compute_theme_coherence()
        assert coherence["Multi theme"] == 0.78
        emb_svc.compute_theme_coherence.assert_called_once_with(["ic_001", "ic_003"])


# ── Theme Distinctness Tests ─────────────────────────────────────────────────

class TestThemeDistinctness:
    def test_single_theme_returns_empty(self, populated_db):
        """Can't compute pairwise distinctness with just 1 theme."""
        theme = Theme(
            id="theme_solo", name="Only theme",
            definition="The only theme in this analysis",
            rationale="Solo", round_finalised=1,
        )
        ThemeRepo(populated_db).insert(theme)
        ThemeRepo(populated_db).assign_ic(ThemeIC(theme_id="theme_solo", ic_id="ic_001"))

        emb_svc = MagicMock()
        engine = QualityMetricsEngine(populated_db, emb_svc)
        result = engine.compute_theme_distinctness()
        assert result == []

    def test_two_themes_returns_one_pair(self, populated_db):
        """Two themes should produce exactly 1 pairwise comparison."""
        theme_a = Theme(
            id="theme_a", name="Theme Alpha",
            definition="First theme about delivery issues",
            rationale="Delivery", round_finalised=1,
        )
        theme_b = Theme(
            id="theme_b", name="Theme Beta",
            definition="Second theme about quality praise",
            rationale="Quality", round_finalised=1,
        )
        theme_repo = ThemeRepo(populated_db)
        theme_repo.insert(theme_a)
        theme_repo.insert(theme_b)
        theme_repo.assign_ic(ThemeIC(theme_id="theme_a", ic_id="ic_001"))
        theme_repo.assign_ic(ThemeIC(theme_id="theme_a", ic_id="ic_003"))
        theme_repo.assign_ic(ThemeIC(theme_id="theme_b", ic_id="ic_002"))

        emb_svc = MagicMock()
        engine = QualityMetricsEngine(populated_db, emb_svc)
        result = engine.compute_theme_distinctness()

        assert len(result) == 1
        name_a, name_b, sim = result[0]
        assert {name_a, name_b} == {"Theme Alpha", "Theme Beta"}
        # With the 3-dim test embeddings from conftest:
        # Theme Alpha centroid: mean([0.8,0.1,0.3], [0.7,0.2,0.4]) = [0.75, 0.15, 0.35]
        # Theme Beta centroid: [0.1, 0.9, 0.2]
        # These should have low similarity (different directions)
        assert sim < 0.7  # Not overlapping
