"""Tests for quality metrics v2: extraction density, meaning saturation (breadth+spread)."""

import pytest
from datetime import datetime

from src.db import (
    Database,
    DocumentRepo,
    InitialCodeRepo,
    SegmentRepo,
    ThemeRepo,
    VerbatimQuoteRepo,
)
from src.models import (
    Document,
    InitialCode,
    ICStatus,
    Segment,
    Theme,
    ThemeIC,
    VerbatimQuote,
)
from src.quality_metrics import QualityMetricsEngine


# ── Extraction Density ─────────────────────────────────────────────────────


class TestMergeSpans:
    """Unit tests for the interval merging helper."""

    def test_empty_spans(self):
        assert QualityMetricsEngine._merge_spans([]) == 0

    def test_single_span(self):
        assert QualityMetricsEngine._merge_spans([(5, 15)]) == 10

    def test_non_overlapping(self):
        spans = [(0, 10), (20, 30)]
        assert QualityMetricsEngine._merge_spans(spans) == 20

    def test_overlapping_spans(self):
        spans = [(0, 15), (10, 25)]
        assert QualityMetricsEngine._merge_spans(spans) == 25

    def test_nested_spans(self):
        """Span fully contained within another."""
        spans = [(0, 30), (5, 10)]
        assert QualityMetricsEngine._merge_spans(spans) == 30

    def test_adjacent_spans(self):
        spans = [(0, 10), (10, 20)]
        assert QualityMetricsEngine._merge_spans(spans) == 20

    def test_unsorted_spans(self):
        """Spans given out of order should still merge correctly."""
        spans = [(20, 30), (0, 10), (5, 25)]
        assert QualityMetricsEngine._merge_spans(spans) == 30

    def test_multiple_overlapping_groups(self):
        spans = [(0, 5), (3, 8), (20, 25), (22, 28)]
        # Group 1: 0-8 = 8, Group 2: 20-28 = 8
        assert QualityMetricsEngine._merge_spans(spans) == 16


class TestExtractionDensity:
    """Integration tests for extraction density computation."""

    def _setup_segment_with_quotes(self, db, seg_text, spans):
        """Helper: create a segment with quotes at given spans."""
        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)
        vq_repo = VerbatimQuoteRepo(db)
        ic_repo = InitialCodeRepo(db)

        # Only insert doc if not yet present
        try:
            doc = Document(id="doc_ed", raw_text=seg_text)
            doc_repo.insert(doc)
        except Exception:
            pass

        seg_id = f"seg_{len(spans)}_{hash(str(spans)) % 10000}"
        seg = Segment(
            id=seg_id, document_id="doc_ed",
            canonical_text=seg_text, original_text=seg_text,
            char_count=len(seg_text), segment_index=0,
            normalization_rules=[], content_hash=f"h_{seg_id}",
        )
        seg_repo.insert(seg)

        # Create an IC for quotes
        try:
            ic = InitialCode(
                id="ic_ed", name="test_ic_ed",
                definition="Test IC for extraction density testing",
                status=ICStatus.ACTIVE,
            )
            ic_repo.insert(ic)
        except Exception:
            pass

        for i, (start, end) in enumerate(spans):
            vq = VerbatimQuote(
                id=f"vq_{seg_id}_{i}", ic_id="ic_ed", segment_id=seg_id,
                quote_text=seg_text[start:end],
                span_start=start, span_end=end,
            )
            vq_repo.insert(vq)

        return seg_id

    def test_density_single_segment_full_coverage(self, db):
        """100% coverage: quote covers entire segment."""
        from unittest.mock import MagicMock

        text = "Hello world test"
        self._setup_segment_with_quotes(db, text, [(0, len(text))])

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_extraction_density()

        assert result["total_segments"] == 1
        assert result["distribution"]["mean"] == 1.0

    def test_density_partial_coverage(self, db):
        """Partial coverage: quote covers first half."""
        from unittest.mock import MagicMock

        text = "abcdefghijklmnopqrst"  # 20 chars
        self._setup_segment_with_quotes(db, text, [(0, 10)])

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_extraction_density()

        # 10/20 = 0.5
        assert result["total_segments"] == 1
        assert result["distribution"]["mean"] == 0.5

    def test_density_no_quotes(self, db):
        """Segment with no quotes should have density 0."""
        from unittest.mock import MagicMock

        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)

        doc = Document(id="doc_empty", raw_text="Empty segment")
        doc_repo.insert(doc)
        seg = Segment(
            id="seg_empty", document_id="doc_empty",
            canonical_text="Empty segment", original_text="Empty segment",
            char_count=13, segment_index=0,
            normalization_rules=[], content_hash="h_empty",
        )
        seg_repo.insert(seg)

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_extraction_density()

        assert result["total_segments"] == 1
        assert result["distribution"]["mean"] == 0.0

    def test_density_empty_db(self, db):
        """No segments at all."""
        from unittest.mock import MagicMock

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_extraction_density()
        assert result["total_segments"] == 0


# ── Meaning Saturation v2 ─────────────────────────────────────────────────


class TestPairwiseSpread:
    """Unit tests for _compute_pairwise_spread."""

    def test_single_embedding(self):
        """Single IC → spread = 0."""
        from unittest.mock import MagicMock
        engine = QualityMetricsEngine.__new__(QualityMetricsEngine)
        assert engine._compute_pairwise_spread([[1.0, 0.0, 0.0]]) == 0.0

    def test_identical_embeddings(self):
        """Identical embeddings → spread = 0 (sim=1 → distance=0)."""
        from unittest.mock import MagicMock
        engine = QualityMetricsEngine.__new__(QualityMetricsEngine)
        v = [1.0, 0.0, 0.0]
        assert engine._compute_pairwise_spread([v, v]) == pytest.approx(0.0)

    def test_orthogonal_embeddings(self):
        """Orthogonal vectors → spread = 1.0 (sim=0 → distance=1)."""
        from unittest.mock import MagicMock
        engine = QualityMetricsEngine.__new__(QualityMetricsEngine)
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        assert engine._compute_pairwise_spread([v1, v2]) == pytest.approx(1.0)

    def test_known_spread(self):
        """Three vectors: two close, one far → intermediate spread."""
        import math
        engine = QualityMetricsEngine.__new__(QualityMetricsEngine)
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.9, 0.1, 0.0]  # close to v1
        v3 = [0.0, 1.0, 0.0]  # far from both
        spread = engine._compute_pairwise_spread([v1, v2, v3])
        assert 0.3 < spread < 0.8  # intermediate value


class TestMeaningSaturationV2:
    """Integration tests for breadth + spread meaning saturation."""

    def _setup_themed_data(self, db, ic_creation_map, embeddings_map):
        """
        Helper: create ICs, themes, quotes for testing saturation.

        ic_creation_map: {ic_name: (ic_id, seg_index)}
        embeddings_map: {ic_name: embedding_vector}
        """
        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)
        ic_repo = InitialCodeRepo(db)
        vq_repo = VerbatimQuoteRepo(db)

        # Create doc + enough segments
        doc = Document(id="doc_ms", raw_text="Test")
        doc_repo.insert(doc)

        max_seg = max(v[1] for v in ic_creation_map.values()) + 1
        for i in range(max_seg):
            seg = Segment(
                id=f"seg_ms_{i}", document_id="doc_ms",
                canonical_text=f"Segment {i} text content for testing",
                original_text=f"Segment {i} text content for testing",
                char_count=40, segment_index=i,
                normalization_rules=[], content_hash=f"h_ms_{i}",
            )
            seg_repo.insert(seg)

        # Create ICs with embeddings
        for ic_name, (ic_id, seg_idx) in ic_creation_map.items():
            emb = embeddings_map.get(ic_name)
            ic = InitialCode(
                id=ic_id, name=ic_name,
                definition=f"Definition for {ic_name} is long enough",
                embedding_json=emb,
                status=ICStatus.ACTIVE,
            )
            ic_repo.insert(ic)

            # Create a quote on the segment where IC was created
            vq = VerbatimQuote(
                id=f"vq_{ic_id}", ic_id=ic_id,
                segment_id=f"seg_ms_{seg_idx}",
                quote_text="quote text", span_start=0, span_end=10,
            )
            vq_repo.insert(vq)

    def test_breadth_early_saturation(self, db):
        """All ICs discovered in first segment → breadth = 0."""
        from unittest.mock import MagicMock

        self._setup_themed_data(
            db,
            ic_creation_map={
                "ic_a": ("ic_a", 0),
                "ic_b": ("ic_b", 0),
            },
            embeddings_map={
                "ic_a": [1.0, 0.0, 0.0],
                "ic_b": [0.0, 1.0, 0.0],
            },
        )

        # Create a theme
        theme_repo = ThemeRepo(db)
        theme = Theme(
            id="th_ms1", name="Test Theme",
            definition="Theme for saturation test",
            rationale="test", round_finalised=1,
        )
        theme_repo.insert(theme)
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms1", ic_id="ic_a"))
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms1", ic_id="ic_b"))

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_meaning_saturation_v2(
            ic_creation_segments={"ic_a": 0, "ic_b": 0},
            total_segments=10,
        )

        assert "Test Theme" in result
        assert result["Test Theme"]["breadth"] == 0.0

    def test_breadth_late_discovery(self, db):
        """Last IC discovered at last segment → breadth = 1.0."""
        from unittest.mock import MagicMock

        self._setup_themed_data(
            db,
            ic_creation_map={
                "ic_c": ("ic_c", 0),
                "ic_d": ("ic_d", 9),  # last of 10 segments
            },
            embeddings_map={
                "ic_c": [1.0, 0.0, 0.0],
                "ic_d": [0.0, 1.0, 0.0],
            },
        )

        theme_repo = ThemeRepo(db)
        theme = Theme(
            id="th_ms2", name="Late Theme",
            definition="Theme with late IC discovery",
            rationale="test", round_finalised=1,
        )
        theme_repo.insert(theme)
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms2", ic_id="ic_c"))
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms2", ic_id="ic_d"))

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_meaning_saturation_v2(
            ic_creation_segments={"ic_c": 0, "ic_d": 9},
            total_segments=10,
        )

        assert result["Late Theme"]["breadth"] == 1.0

    def test_spread_diverse_ics(self, db):
        """Orthogonal IC embeddings → spread = 1.0."""
        from unittest.mock import MagicMock

        self._setup_themed_data(
            db,
            ic_creation_map={
                "ic_e": ("ic_e", 0),
                "ic_f": ("ic_f", 1),
            },
            embeddings_map={
                "ic_e": [1.0, 0.0, 0.0],
                "ic_f": [0.0, 1.0, 0.0],
            },
        )

        theme_repo = ThemeRepo(db)
        theme = Theme(
            id="th_ms3", name="Diverse Theme",
            definition="Theme with diverse IC embeddings",
            rationale="test", round_finalised=1,
        )
        theme_repo.insert(theme)
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms3", ic_id="ic_e"))
        theme_repo.assign_ic(ThemeIC(theme_id="th_ms3", ic_id="ic_f"))

        engine = QualityMetricsEngine(db, MagicMock())
        result = engine.compute_meaning_saturation_v2(
            ic_creation_segments={"ic_e": 0, "ic_f": 1},
            total_segments=5,
        )

        assert result["Diverse Theme"]["spread"] == pytest.approx(1.0, abs=0.01)


# ── Codebook Comparator Triage ─────────────────────────────────────────────


class TestEmbeddingFirstTriage:
    """Tests for the auto-NEW/auto-MERGE triage in codebook_comparator."""

    def test_auto_new_below_threshold(self):
        """max_sim < auto_new_threshold → auto-NEW, no LLM."""
        from src.models import ComparatorRecommendation
        from src.codebook_comparator import CodebookComparator
        from src.embeddings import SimilarityResult
        from unittest.mock import MagicMock

        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        comparator = CodebookComparator.__new__(CodebookComparator)
        comparator.config = config
        comparator.top_k = 5
        comparator.embedding_service = MagicMock()
        comparator.db = MagicMock()
        comparator.model_client = MagicMock()

        # Mock top-K results with low similarity
        low_result = SimilarityResult(ic_id="ic_1", ic_name="existing", similarity=0.3)
        comparator.embedding_service.find_similar_ics.return_value = [low_result]

        from src.models import ICCandidate
        candidate = ICCandidate(
            ic_name="new_code",
            definition="A totally new code",
            quote_text="some quote",
            span_start=0, span_end=10, confidence=0.9,
        )

        output, top_k, _meta = comparator.evaluate(candidate, precomputed_embedding=[0.1, 0.2])

        assert output.recommendation == ComparatorRecommendation.NEW
        assert "Auto-triage" in output.reasoning
        # LLM should NOT have been called
        comparator.model_client.get_client.assert_not_called()

    def test_auto_merge_above_threshold(self):
        """max_sim > auto_merge_threshold → auto-MERGE, no LLM."""
        from src.models import ComparatorRecommendation
        from src.codebook_comparator import CodebookComparator
        from src.embeddings import SimilarityResult
        from unittest.mock import MagicMock

        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        comparator = CodebookComparator.__new__(CodebookComparator)
        comparator.config = config
        comparator.top_k = 5
        comparator.embedding_service = MagicMock()
        comparator.db = MagicMock()
        comparator.model_client = MagicMock()

        high_result = SimilarityResult(ic_id="ic_1", ic_name="existing", similarity=0.95)
        comparator.embedding_service.find_similar_ics.return_value = [high_result]

        from src.models import ICCandidate
        candidate = ICCandidate(
            ic_name="duplicate_code",
            definition="A near-duplicate code",
            quote_text="some quote",
            span_start=0, span_end=10, confidence=0.9,
        )

        output, top_k, _meta = comparator.evaluate(candidate, precomputed_embedding=[0.1, 0.2])

        assert output.recommendation == ComparatorRecommendation.MERGE
        assert output.merge_target_name == "existing"
        assert "Auto-triage" in output.reasoning
        comparator.model_client.get_client.assert_not_called()

    def test_grey_zone_calls_llm(self):
        """Similarity in grey zone (0.5-0.9) → should call LLM."""
        from src.codebook_comparator import CodebookComparator
        from src.embeddings import SimilarityResult
        from src.db import InitialCodeRepo
        from src.models import ComparatorOutput, ComparatorRecommendation, ICCandidate
        from unittest.mock import MagicMock, patch

        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        comparator = CodebookComparator.__new__(CodebookComparator)
        comparator.config = config
        comparator.top_k = 5
        comparator.embedding_service = MagicMock()
        comparator.db = MagicMock()
        comparator.model_client = MagicMock()

        grey_result = SimilarityResult(ic_id="ic_1", ic_name="existing", similarity=0.7)
        comparator.embedding_service.find_similar_ics.return_value = [grey_result]

        # Mock the LLM call
        mock_output = ComparatorOutput(
            recommendation=ComparatorRecommendation.NEW,
            reasoning="LLM decided this is new after comparison.",
        )
        comparator._get_llm_recommendation = MagicMock(return_value=mock_output)

        # Mock InitialCodeRepo for the grey zone path
        mock_ic = MagicMock()
        mock_ic.definition = "existing definition"
        with patch.object(InitialCodeRepo, 'get_by_id', return_value=mock_ic):
            candidate = ICCandidate(
                ic_name="ambiguous_code",
                definition="Could be new or merge",
                quote_text="some quote",
                span_start=0, span_end=10, confidence=0.9,
            )
            output, top_k, _meta = comparator.evaluate(candidate, precomputed_embedding=[0.1, 0.2])

        assert comparator._get_llm_recommendation.called

    def test_empty_codebook_auto_new(self):
        """Empty codebook → auto-NEW without any similarity check."""
        from src.codebook_comparator import CodebookComparator
        from src.models import ComparatorRecommendation, ICCandidate
        from unittest.mock import MagicMock

        config = MagicMock()
        config.processing.similarity_prefilter_k = 5
        config.processing.auto_new_threshold = 0.5
        config.processing.auto_merge_threshold = 0.9

        comparator = CodebookComparator.__new__(CodebookComparator)
        comparator.config = config
        comparator.top_k = 5
        comparator.embedding_service = MagicMock()
        comparator.db = MagicMock()
        comparator.model_client = MagicMock()

        comparator.embedding_service.find_similar_ics.return_value = []

        candidate = ICCandidate(
            ic_name="first_code",
            definition="First code in empty codebook",
            quote_text="some quote",
            span_start=0, span_end=10, confidence=0.9,
        )
        output, top_k, _meta = comparator.evaluate(candidate, precomputed_embedding=[0.1, 0.2])

        assert output.recommendation == ComparatorRecommendation.NEW
        assert "empty" in output.reasoning.lower()
