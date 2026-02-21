"""Tests for the Synthesizer Agent — mocked LLM, real persistence."""

import pytest
from unittest.mock import MagicMock, patch

from src.db import Database, InitialCodeRepo, ThemeRepo, DocumentRepo, SegmentRepo
from src.models import (
    Document,
    InitialCode,
    ICStatus,
    Segment,
    SynthesisOutput,
    Theme,
    ThemeIC,
    ThemeProposal,
    ThemeFeedback,
    ThemeFeedbackOption,
    RevisionOutput,
)
from src.synthesizer_agent import SynthesizerAgent


class TestSynthesizerBuildCodebookData:
    """Test _build_codebook_data which reads DB and formats for prompts."""

    def test_builds_from_db(self, db, sample_ics, sample_quotes):
        # Setup DB
        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)
        ic_repo = InitialCodeRepo(db)
        from src.db import VerbatimQuoteRepo
        vq_repo = VerbatimQuoteRepo(db)

        doc = Document(id="doc_001", raw_text="test")
        doc_repo.insert(doc)
        seg = Segment(
            id="seg_001", document_id="doc_001",
            canonical_text="Produkt jest świetny, ale dostawa trwała zbyt długo. Paczka była uszkodzona.",
            original_text="test", char_count=75, content_hash="hash",
        )
        seg_repo.insert(seg)
        for ic in sample_ics:
            ic_repo.insert(ic)
        for vq in sample_quotes:
            vq_repo.insert(vq)

        mc = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        data = agent._build_codebook_data()

        assert len(data) == 3  # 3 active ICs
        names = [d["name"] for d in data]
        assert "Delivery speed complaint" in names
        assert "Product quality praise" in names

        # Check quote counts
        delivery = next(d for d in data if d["name"] == "Delivery speed complaint")
        assert delivery["quote_count"] == 1

    def test_empty_codebook(self, db):
        mc = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)
        data = agent._build_codebook_data()
        assert data == []


class TestSynthesizerPersistThemes:
    """Test theme persistence with M:N junction records."""

    def test_persist_creates_themes_and_junctions(self, db, sample_ics):
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        mc = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        proposals = [
            ThemeProposal(
                name="Delivery issues",
                definition="Customers report problems with delivery speed and packaging",
                rationale="Groups delivery-related ICs",
                constituent_ic_names=["Delivery speed complaint", "Packaging damage"],
            ),
            ThemeProposal(
                name="Quality praise",
                definition="Positive feedback about product quality",
                rationale="Groups quality-related ICs",
                constituent_ic_names=["Product quality praise"],
            ),
        ]

        themes = agent.persist_themes(proposals, round_number=1)

        assert len(themes) == 2
        assert themes[0].name == "Delivery issues"
        assert themes[0].round_finalised == 1

        # Check junctions
        theme_repo = ThemeRepo(db)
        ics_for_delivery = theme_repo.get_ics_for_theme(themes[0].id)
        assert len(ics_for_delivery) == 2
        assert "ic_001" in ics_for_delivery
        assert "ic_003" in ics_for_delivery

        ics_for_quality = theme_repo.get_ics_for_theme(themes[1].id)
        assert len(ics_for_quality) == 1
        assert "ic_002" in ics_for_quality

    def test_persist_warns_on_unknown_ic(self, db, sample_ics, caplog):
        ic_repo = InitialCodeRepo(db)
        for ic in sample_ics:
            ic_repo.insert(ic)

        mc = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        proposals = [
            ThemeProposal(
                name="Mixed theme",
                definition="Contains a code that doesn't exist in codebook",
                rationale="Test missing IC",
                constituent_ic_names=["Delivery speed complaint", "nonexistent_code"],
            ),
        ]

        import logging
        with caplog.at_level(logging.WARNING):
            themes = agent.persist_themes(proposals, round_number=1)

        assert len(themes) == 1
        # Only the existing IC should be linked
        theme_repo = ThemeRepo(db)
        ics = theme_repo.get_ics_for_theme(themes[0].id)
        assert len(ics) == 1
        assert "ic_001" in ics


class TestSynthesizerRevise:
    """Test revision with mocked LLM."""

    def test_no_feedback_returns_unchanged(self):
        mc = MagicMock()
        db = MagicMock()
        config = MagicMock()
        agent = SynthesizerAgent(mc, db, config)

        themes = [
            ThemeProposal(
                name="Theme A",
                definition="Some theme about things",
                rationale="Because reasons",
                constituent_ic_names=["code_1"],
            ),
        ]
        result = agent.revise(themes, feedback=[])
        assert result == themes  # Unchanged
