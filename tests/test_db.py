"""Tests for SQLite schema and repository layer."""

import json
import pytest
from datetime import datetime

from src.core.db import (
    Database,
    DocumentRepo,
    SegmentRepo,
    InitialCodeRepo,
    VerbatimQuoteRepo,
    ThemeRepo,
    DecisionLogRepo,
    QualityMetricRepo,
)
from src.core.models import (
    DecisionLog,
    DecisionType,
    Document,
    InitialCode,
    ICStatus,
    QualityMetric,
    MetricType,
    Segment,
    Theme,
    ThemeIC,
    VerbatimQuote,
)


class TestDatabase:
    def test_init_schema_creates_tables(self, db):
        with db.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        table_names = {t["name"] for t in tables}
        expected = {
            "documents", "segments", "initial_codes", "verbatim_quotes",
            "themes", "theme_ics", "decision_logs", "quality_metrics",
            "categories", "category_themes",
        }
        assert expected.issubset(table_names)

    def test_init_schema_idempotent(self, db):
        # Calling init_schema twice should not raise
        db.init_schema()
        db.init_schema()


class TestDocumentRepo:
    def test_insert_and_get(self, db, sample_documents):
        repo = DocumentRepo(db)
        doc = sample_documents[0]
        repo.insert(doc)

        retrieved = repo.get_by_id(doc.id)
        assert retrieved is not None
        assert retrieved.raw_text == doc.raw_text
        assert retrieved.metadata == doc.metadata

    def test_get_nonexistent(self, db):
        repo = DocumentRepo(db)
        assert repo.get_by_id("nonexistent") is None

    def test_get_all(self, db, sample_documents):
        repo = DocumentRepo(db)
        for doc in sample_documents:
            repo.insert(doc)
        all_docs = repo.get_all()
        assert len(all_docs) == 3


class TestSegmentRepo:
    def test_insert_and_get(self, db, sample_documents, sample_segment):
        # Insert parent document first (FK constraint)
        DocumentRepo(db).insert(sample_documents[0])
        repo = SegmentRepo(db)
        repo.insert(sample_segment)

        retrieved = repo.get_by_id(sample_segment.id)
        assert retrieved is not None
        assert retrieved.canonical_text == sample_segment.canonical_text
        assert retrieved.normalization_rules == sample_segment.normalization_rules

    def test_get_canonical_text(self, db, sample_documents, sample_segment):
        DocumentRepo(db).insert(sample_documents[0])
        repo = SegmentRepo(db)
        repo.insert(sample_segment)

        text = repo.get_canonical_text(sample_segment.id)
        assert text == sample_segment.canonical_text

    def test_get_all_for_document(self, db, sample_documents):
        DocumentRepo(db).insert(sample_documents[0])
        repo = SegmentRepo(db)
        # Insert two segments for same document
        seg1 = Segment(
            id="seg_a", document_id="doc_001",
            canonical_text="First", original_text="First",
            segment_index=0, content_hash="h1",
        )
        seg2 = Segment(
            id="seg_b", document_id="doc_001",
            canonical_text="Second", original_text="Second",
            segment_index=1, content_hash="h2",
        )
        repo.insert(seg1)
        repo.insert(seg2)
        segments = repo.get_all_for_document("doc_001")
        assert len(segments) == 2
        assert segments[0].segment_index == 0


class TestInitialCodeRepo:
    def test_insert_and_get(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        ic = sample_ics[0]
        repo.insert(ic)

        retrieved = repo.get_by_id(ic.id)
        assert retrieved is not None
        assert retrieved.name == ic.name
        assert retrieved.embedding_json == ic.embedding_json

    def test_get_all_active(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        for ic in sample_ics:
            repo.insert(ic)

        active = repo.get_all_active()
        assert len(active) == 3

    def test_update(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        ic = sample_ics[0]
        repo.insert(ic)

        ic.name = "Updated name"
        ic.definition = "Updated definition text"
        repo.update(ic)

        retrieved = repo.get_by_id(ic.id)
        assert retrieved.name == "Updated name"

    def test_count_active(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        for ic in sample_ics:
            repo.insert(ic)
        assert repo.count_active() == 3

    def test_get_by_name(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        for ic in sample_ics:
            repo.insert(ic)

        found = repo.get_by_name("Delivery speed complaint")
        assert found is not None
        assert found.id == "ic_001"

    def test_get_by_name_not_found(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        for ic in sample_ics:
            repo.insert(ic)

        assert repo.get_by_name("nonexistent") is None

    def test_get_by_name_ignores_deprecated(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        ic = sample_ics[0]
        ic.status = ICStatus.DEPRECATED
        repo.insert(ic)

        assert repo.get_by_name(ic.name) is None

    def test_deprecated_not_in_active(self, db, sample_ics):
        repo = InitialCodeRepo(db)
        ic = sample_ics[0]
        ic.status = ICStatus.DEPRECATED
        repo.insert(ic)
        repo.insert(sample_ics[1])

        active = repo.get_all_active()
        assert len(active) == 1


class TestVerbatimQuoteRepo:
    def test_insert_and_get(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        # Set up FK parents
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        ic_repo.insert(sample_ics[2])

        vq_repo = VerbatimQuoteRepo(db)
        for q in sample_quotes:
            vq_repo.insert(q)

        quotes_for_ic = vq_repo.get_all_for_ic("ic_001")
        assert len(quotes_for_ic) == 1
        assert quotes_for_ic[0].quote_text == sample_quotes[0].quote_text

    def test_get_all_for_segment(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        ic_repo.insert(sample_ics[2])

        vq_repo = VerbatimQuoteRepo(db)
        for q in sample_quotes:
            vq_repo.insert(q)

        quotes_for_seg = vq_repo.get_all_for_segment("seg_001")
        assert len(quotes_for_seg) == 2


    def test_update_embedding(self, db, sample_documents, sample_segment, sample_ics, sample_quotes):
        """Test deferred embedding update for batch processing."""
        DocumentRepo(db).insert(sample_documents[0])
        SegmentRepo(db).insert(sample_segment)
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])

        vq_repo = VerbatimQuoteRepo(db)
        quote = sample_quotes[0]
        # Insert without embedding
        assert quote.quote_embedding_json is None
        vq_repo.insert(quote)

        # Later: set embedding and update
        quote.quote_embedding_json = [0.1, 0.2, 0.3]
        vq_repo.update_embedding(quote)

        # Verify it persisted
        retrieved = vq_repo.get_all_for_ic("ic_001")
        assert len(retrieved) == 1
        assert retrieved[0].quote_embedding_json == [0.1, 0.2, 0.3]


class TestThemeRepo:
    def test_insert_and_assign_ic(self, db, sample_ics):
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        ic_repo.insert(sample_ics[1])

        theme_repo = ThemeRepo(db)
        theme = Theme(
            id="theme_001",
            name="Service quality issues",
            definition="Issues related to delivery and customer service quality",
        )
        theme_repo.insert(theme)

        tic1 = ThemeIC(theme_id="theme_001", ic_id="ic_001")
        tic2 = ThemeIC(theme_id="theme_001", ic_id="ic_002")
        theme_repo.assign_ic(tic1)
        theme_repo.assign_ic(tic2)

        ic_ids = theme_repo.get_ics_for_theme("theme_001")
        assert set(ic_ids) == {"ic_001", "ic_002"}

    def test_assign_ic_idempotent(self, db, sample_ics):
        ic_repo = InitialCodeRepo(db)
        ic_repo.insert(sample_ics[0])
        theme_repo = ThemeRepo(db)
        theme = Theme(id="t1", name="Test", definition="Test theme for testing")
        theme_repo.insert(theme)

        tic = ThemeIC(theme_id="t1", ic_id="ic_001")
        theme_repo.assign_ic(tic)
        theme_repo.assign_ic(tic)  # Should not raise (INSERT OR IGNORE)
        assert len(theme_repo.get_ics_for_theme("t1")) == 1


class TestDecisionLogRepo:
    def test_insert_and_get_all(self, db):
        repo = DecisionLogRepo(db)
        log = DecisionLog(
            decision_type=DecisionType.CODEBOOK_UPDATE,
            ic_id="ic_001",
            llm_recommendation="merge_with_existing",
            human_action="accepted",
            similarity_score=0.87,
            notes="High similarity detected",
            context={"batch": 3},
        )
        repo.insert(log)

        all_logs = repo.get_all()
        assert len(all_logs) == 1
        assert all_logs[0].context == {"batch": 3}


class TestQualityMetricRepo:
    def test_insert_and_get_by_type(self, db):
        repo = QualityMetricRepo(db)
        qm = QualityMetric(
            metric_type=MetricType.GROUNDING,
            entity_id="ic_001",
            entity_type="initial_code",
            value=0.98,
        )
        repo.insert(qm)

        metrics = repo.get_by_type("grounding")
        assert len(metrics) == 1
        assert metrics[0].value == 0.98
