"""Tests for the Category Agent and CategoryRepo."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.db import (
    CategoryRepo,
    Database,
    DocumentRepo,
    InitialCodeRepo,
    SegmentRepo,
    ThemeRepo,
    VerbatimQuoteRepo,
)
from src.models import (
    Category,
    CategoryProposal,
    CategorySynthesisOutput,
    CategoryTheme,
    Document,
    InitialCode,
    ICStatus,
    Segment,
    Theme,
    ThemeIC,
    VerbatimQuote,
    new_id,
)
from src.category_agent import CategoryAgent, _compute_adaptive_target
from src.prompts import build_category_system_prompt, build_category_user_prompt


# ── CategoryRepo Tests ──────────────────────────────────────────────────────


class TestCategoryRepo:
    def test_insert_and_get_all(self, db):
        repo = CategoryRepo(db)

        cat = Category(
            id="cat_001",
            name="Gameplay Mechanics",
            definition="All themes related to core gameplay systems and interactions",
        )
        repo.insert(cat)

        all_cats = repo.get_all()
        assert len(all_cats) == 1
        assert all_cats[0].id == "cat_001"
        assert all_cats[0].name == "Gameplay Mechanics"

    def test_assign_theme_and_get(self, db):
        repo = CategoryRepo(db)
        theme_repo = ThemeRepo(db)

        # Insert a theme first
        theme = Theme(
            id="th_001",
            name="Combat feel",
            definition="How responsive combat is",
            rationale="Multiple ICs about combat",
            round_finalised=1,
        )
        theme_repo.insert(theme)

        # Insert category
        cat = Category(
            id="cat_001",
            name="Gameplay Mechanics",
            definition="All themes related to core gameplay systems",
        )
        repo.insert(cat)

        # Assign theme to category
        repo.assign_theme(CategoryTheme(
            category_id="cat_001",
            theme_id="th_001",
        ))

        theme_ids = repo.get_themes_for_category("cat_001")
        assert theme_ids == ["th_001"]

    def test_get_category_for_theme(self, db):
        repo = CategoryRepo(db)
        theme_repo = ThemeRepo(db)

        theme = Theme(
            id="th_001", name="Combat", definition="Combat themes",
            rationale="test", round_finalised=1,
        )
        theme_repo.insert(theme)

        cat = Category(
            id="cat_001", name="Gameplay",
            definition="Gameplay category themes",
        )
        repo.insert(cat)

        repo.assign_theme(CategoryTheme(
            category_id="cat_001", theme_id="th_001",
        ))

        assert repo.get_category_for_theme("th_001") == "cat_001"
        assert repo.get_category_for_theme("nonexistent") is None

    def test_multiple_themes_per_category(self, db):
        repo = CategoryRepo(db)
        theme_repo = ThemeRepo(db)

        for i in range(3):
            theme_repo.insert(Theme(
                id=f"th_{i}", name=f"Theme {i}",
                definition=f"Theme {i} definition is at least 10 chars",
                rationale="test", round_finalised=1,
            ))

        cat = Category(
            id="cat_001", name="Big Category",
            definition="Category with multiple themes assigned",
        )
        repo.insert(cat)

        for i in range(3):
            repo.assign_theme(CategoryTheme(
                category_id="cat_001", theme_id=f"th_{i}",
            ))

        theme_ids = repo.get_themes_for_category("cat_001")
        assert len(theme_ids) == 3

    def test_schema_includes_category_tables(self, db):
        """Verify that init_schema creates category tables."""
        with db.connect() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "categories" in table_names
        assert "category_themes" in table_names


# ── Category Prompt Tests ───────────────────────────────────────────────────


class TestAdaptiveTargetCount:
    def test_9_themes(self):
        assert _compute_adaptive_target(9) == 3

    def test_15_themes(self):
        assert _compute_adaptive_target(15) == 5

    def test_30_themes(self):
        assert _compute_adaptive_target(30) == 8

    def test_minimum_clamp(self):
        assert _compute_adaptive_target(3) == 3

    def test_maximum_clamp(self):
        assert _compute_adaptive_target(100) == 8


class TestCategoryPrompts:
    def test_system_prompt_content(self):
        prompt = build_category_system_prompt(target_count=5)
        assert "CategorySynthesisOutput" in prompt
        assert "5" in prompt
        assert "higher-order" in prompt.lower()
        assert "reasoning" in prompt.lower()
        assert "chain-of-thought" in prompt.lower()

    def test_system_prompt_adaptive_range(self):
        prompt = build_category_system_prompt(target_count=4)
        assert "approximately 4" in prompt
        assert "3" in prompt  # min range
        assert "5" in prompt  # max range

    def test_user_prompt_with_themes(self):
        themes_data = [
            {
                "name": "Combat feel",
                "definition": "How responsive and satisfying combat mechanics are",
                "ic_count": 5,
                "ic_names": ["sluggish_combat", "weapon_impact"],
            },
            {
                "name": "Story pacing",
                "definition": "Narrative rhythm and plot progression",
                "ic_count": 3,
                "ic_names": ["slow_start", "engaging_mid"],
            },
        ]
        prompt = build_category_user_prompt(themes_data)
        assert "2 themes" in prompt
        assert "Combat feel" in prompt
        assert "Story pacing" in prompt
        assert "sluggish_combat" in prompt

    def test_user_prompt_with_ic_details(self):
        """Prompt should include IC definitions and example quotes when provided."""
        themes_data = [
            {
                "name": "Combat feel",
                "definition": "How responsive combat is",
                "ic_count": 1,
                "ic_names": ["sluggish_combat"],
                "ic_details": [
                    {
                        "name": "sluggish_combat",
                        "definition": "Players complain about slow combat response",
                        "example_quote": "The combat feels really sluggish and unresponsive",
                    },
                ],
            },
        ]
        prompt = build_category_user_prompt(themes_data)
        assert "sluggish_combat" in prompt
        assert "slow combat response" in prompt
        assert "sluggish and unresponsive" in prompt

    def test_user_prompt_empty(self):
        prompt = build_category_user_prompt([])
        assert "none" in prompt.lower()


# ── CategoryAgent Tests ─────────────────────────────────────────────────────


class TestCategoryAgent:
    def test_persist_creates_records(self, db):
        """Test that persist() creates Category and CategoryTheme records."""
        from src.category_agent import CategoryAgent

        theme_repo = ThemeRepo(db)

        # Create themes in DB
        themes = []
        for i in range(4):
            theme = Theme(
                id=f"th_{i}", name=f"Theme {i}",
                definition=f"Theme {i} has a definition that is at least 10 chars",
                rationale="test", round_finalised=1,
            )
            theme_repo.insert(theme)
            themes.append(theme)

        # Create proposals
        proposals = [
            CategoryProposal(
                name="Category A",
                definition="First category grouping themes 0 and 1 together nicely",
                constituent_theme_names=["Theme 0", "Theme 1"],
            ),
            CategoryProposal(
                name="Category B",
                definition="Second category grouping themes 2 and 3 together nicely",
                constituent_theme_names=["Theme 2", "Theme 3"],
            ),
        ]

        # Persist (no LLM needed)
        agent = CategoryAgent.__new__(CategoryAgent)
        agent.db = db
        persisted = agent.persist(proposals, themes)

        assert len(persisted) == 2
        assert persisted[0].name == "Category A"
        assert persisted[1].name == "Category B"

        # Verify DB
        cat_repo = CategoryRepo(db)
        all_cats = cat_repo.get_all()
        assert len(all_cats) == 2

        cat_a_themes = cat_repo.get_themes_for_category(persisted[0].id)
        assert set(cat_a_themes) == {"th_0", "th_1"}

    def test_persist_handles_missing_themes(self, db):
        """Test that persist() warns on theme name mismatches but continues."""
        from src.category_agent import CategoryAgent

        theme_repo = ThemeRepo(db)
        theme = Theme(
            id="th_0", name="Real Theme",
            definition="A real theme that exists in the database",
            rationale="test", round_finalised=1,
        )
        theme_repo.insert(theme)

        proposals = [
            CategoryProposal(
                name="Category X",
                definition="Category referencing a nonexistent theme alongside a real one",
                constituent_theme_names=["Real Theme", "Nonexistent Theme"],
            ),
        ]

        agent = CategoryAgent.__new__(CategoryAgent)
        agent.db = db
        persisted = agent.persist(proposals, [theme])

        assert len(persisted) == 1
        cat_repo = CategoryRepo(db)
        theme_ids = cat_repo.get_themes_for_category(persisted[0].id)
        assert theme_ids == ["th_0"]  # Only the real theme was assigned

    def test_synthesize_returns_empty_on_no_themes(self, db):
        """Test that synthesize() returns empty list when no themes provided."""
        from src.category_agent import CategoryAgent

        agent = CategoryAgent.__new__(CategoryAgent)
        agent.db = db
        result = agent.synthesize([])
        assert result == []


# ── Export Hierarchy Test ───────────────────────────────────────────────────


class TestExportWithCategories:
    def _setup_full_hierarchy(self, db):
        """Set up a full Category → Theme → IC → Quote hierarchy in DB."""
        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)
        ic_repo = InitialCodeRepo(db)
        vq_repo = VerbatimQuoteRepo(db)
        theme_repo = ThemeRepo(db)
        cat_repo = CategoryRepo(db)

        # Document + Segment
        doc = Document(id="doc_1", raw_text="Test review text for the export test")
        doc_repo.insert(doc)

        seg = Segment(
            id="seg_1", document_id="doc_1",
            canonical_text="Test review text for the export test",
            original_text="Test review text for the export test",
            char_count=36, segment_index=0,
            normalization_rules=[], content_hash="hash1",
        )
        seg_repo.insert(seg)

        # ICs
        ic1 = InitialCode(id="ic_1", name="ic_alpha", definition="Alpha IC definition text here", status=ICStatus.ACTIVE)
        ic2 = InitialCode(id="ic_2", name="ic_beta", definition="Beta IC definition text here", status=ICStatus.ACTIVE)
        ic_repo.insert(ic1)
        ic_repo.insert(ic2)

        # Quotes
        vq1 = VerbatimQuote(id="vq_1", ic_id="ic_1", segment_id="seg_1",
                            quote_text="Test review", span_start=0, span_end=11)
        vq2 = VerbatimQuote(id="vq_2", ic_id="ic_2", segment_id="seg_1",
                            quote_text="export test", span_start=25, span_end=36)
        vq_repo.insert(vq1)
        vq_repo.insert(vq2)

        # Themes (round 1)
        th1 = Theme(id="th_1", name="Theme Alpha", definition="Alpha theme description here",
                     rationale="test", round_finalised=1)
        th2 = Theme(id="th_2", name="Theme Beta", definition="Beta theme description here",
                     rationale="test", round_finalised=1)
        theme_repo.insert(th1)
        theme_repo.insert(th2)
        theme_repo.assign_ic(ThemeIC(theme_id="th_1", ic_id="ic_1"))
        theme_repo.assign_ic(ThemeIC(theme_id="th_2", ic_id="ic_2"))

        # Categories
        cat = Category(id="cat_1", name="Test Category",
                        definition="A test category grouping both themes together")
        cat_repo.insert(cat)
        cat_repo.assign_theme(CategoryTheme(category_id="cat_1", theme_id="th_1"))
        cat_repo.assign_theme(CategoryTheme(category_id="cat_1", theme_id="th_2"))

    def test_export_includes_categories(self, db):
        """Verify export_thematic_structure returns hierarchical format when categories exist."""
        self._setup_full_hierarchy(db)

        from src.pipeline import EQDPipeline

        # Create a minimal pipeline with our DB (skip full init)
        pipeline = EQDPipeline.__new__(EQDPipeline)
        pipeline.db = db

        structure = pipeline.export_thematic_structure()

        # Should be hierarchical: list of categories
        assert len(structure) == 1
        cat = structure[0]
        assert cat["name"] == "Test Category"
        assert cat["theme_count"] == 2

        themes = cat["themes"]
        assert len(themes) == 2
        theme_names = {t["name"] for t in themes}
        assert "Theme Alpha" in theme_names
        assert "Theme Beta" in theme_names

        # Each theme should have ICs with quotes
        for theme in themes:
            assert theme["ic_count"] >= 1
            for ic in theme["initial_codes"]:
                assert ic["quote_count"] >= 1

    def test_validation_absorbs_singletons(self, db):
        """Singleton categories (< 2 themes) should be absorbed into nearest."""
        ic_repo = InitialCodeRepo(db)
        # Create ICs with embeddings for centroid computation
        ic1 = InitialCode(
            id="ic_v1", name="ic_gameplay_1",
            definition="Gameplay code one for validation testing",
            embedding_json=[1.0, 0.0, 0.0], status=ICStatus.ACTIVE,
        )
        ic2 = InitialCode(
            id="ic_v2", name="ic_gameplay_2",
            definition="Gameplay code two for validation testing",
            embedding_json=[0.9, 0.1, 0.0], status=ICStatus.ACTIVE,
        )
        ic3 = InitialCode(
            id="ic_v3", name="ic_story_1",
            definition="Story code for validation testing",
            embedding_json=[0.8, 0.2, 0.0], status=ICStatus.ACTIVE,
        )
        ic_repo.insert(ic1)
        ic_repo.insert(ic2)
        ic_repo.insert(ic3)

        proposals = [
            CategoryProposal(
                name="Gameplay",
                definition="All gameplay-related themes in the analysis",
                constituent_theme_names=["Theme A", "Theme B"],
            ),
            CategoryProposal(
                name="Singleton",
                definition="A lonely singleton category with only one theme",
                constituent_theme_names=["Theme C"],  # singleton!
            ),
        ]

        themes_data = [
            {"name": "Theme A", "ic_names": ["ic_gameplay_1"]},
            {"name": "Theme B", "ic_names": ["ic_gameplay_2"]},
            {"name": "Theme C", "ic_names": ["ic_story_1"]},
        ]

        from unittest.mock import MagicMock
        config = MagicMock()
        config.processing.category_merge_threshold = 0.85

        agent = CategoryAgent.__new__(CategoryAgent)
        agent.db = db
        agent.config = config

        validated = agent._validate_proposals(proposals, themes_data)

        # Singleton should be absorbed → only 1 category
        assert len(validated) == 1
        assert "Theme C" in validated[0].constituent_theme_names

    def test_validation_merges_overlapping(self, db):
        """Categories with similar centroids should be merged."""
        ic_repo = InitialCodeRepo(db)

        # Two ICs with very similar embeddings
        ic1 = InitialCode(
            id="ic_m1", name="ic_merge_1",
            definition="Merge test code one for validation",
            embedding_json=[1.0, 0.0, 0.0], status=ICStatus.ACTIVE,
        )
        ic2 = InitialCode(
            id="ic_m2", name="ic_merge_2",
            definition="Merge test code two for validation",
            embedding_json=[0.99, 0.01, 0.0], status=ICStatus.ACTIVE,
        )
        ic3 = InitialCode(
            id="ic_m3", name="ic_distant",
            definition="A distant code for contrast purposes",
            embedding_json=[0.0, 0.0, 1.0], status=ICStatus.ACTIVE,
        )
        ic_repo.insert(ic1)
        ic_repo.insert(ic2)
        ic_repo.insert(ic3)

        proposals = [
            CategoryProposal(
                name="Cat A",
                definition="Category A with similar centroids to Cat B",
                constituent_theme_names=["Theme 1", "Theme 2"],
            ),
            CategoryProposal(
                name="Cat B",
                definition="Category B with similar centroids to Cat A in the embedding",
                constituent_theme_names=["Theme 3", "Theme 4"],
            ),
            CategoryProposal(
                name="Cat C",
                definition="A distant category with different embeddings",
                constituent_theme_names=["Theme 5", "Theme 6"],
            ),
        ]

        themes_data = [
            {"name": "Theme 1", "ic_names": ["ic_merge_1"]},
            {"name": "Theme 2", "ic_names": ["ic_merge_1"]},
            {"name": "Theme 3", "ic_names": ["ic_merge_2"]},
            {"name": "Theme 4", "ic_names": ["ic_merge_2"]},
            {"name": "Theme 5", "ic_names": ["ic_distant"]},
            {"name": "Theme 6", "ic_names": ["ic_distant"]},
        ]

        from unittest.mock import MagicMock
        config = MagicMock()
        config.processing.category_merge_threshold = 0.85

        agent = CategoryAgent.__new__(CategoryAgent)
        agent.db = db
        agent.config = config

        validated = agent._validate_proposals(proposals, themes_data)

        # Cat A and Cat B should merge (centroids nearly identical) → 2 categories
        assert len(validated) == 2

    def test_export_flat_without_categories(self, db):
        """Verify export returns flat structure when no categories exist."""
        # Set up themes without categories
        theme_repo = ThemeRepo(db)
        doc_repo = DocumentRepo(db)
        seg_repo = SegmentRepo(db)
        ic_repo = InitialCodeRepo(db)
        vq_repo = VerbatimQuoteRepo(db)

        doc = Document(id="doc_1", raw_text="Test review text")
        doc_repo.insert(doc)
        seg = Segment(id="seg_1", document_id="doc_1",
                       canonical_text="Test review text",
                       original_text="Test review text",
                       char_count=16, segment_index=0,
                       normalization_rules=[], content_hash="h1")
        seg_repo.insert(seg)

        ic = InitialCode(id="ic_1", name="test_ic", definition="Test IC definition text here",
                          status=ICStatus.ACTIVE)
        ic_repo.insert(ic)
        vq = VerbatimQuote(id="vq_1", ic_id="ic_1", segment_id="seg_1",
                            quote_text="Test", span_start=0, span_end=4)
        vq_repo.insert(vq)

        th = Theme(id="th_1", name="Test Theme", definition="A test theme definition",
                    rationale="test", round_finalised=1)
        theme_repo.insert(th)
        theme_repo.assign_ic(ThemeIC(theme_id="th_1", ic_id="ic_1"))

        from src.pipeline import EQDPipeline
        pipeline = EQDPipeline.__new__(EQDPipeline)
        pipeline.db = db

        structure = pipeline.export_thematic_structure()

        # Should be flat: list of theme dicts (no "themes" key)
        assert len(structure) == 1
        assert "themes" not in structure[0]
        assert structure[0]["name"] == "Test Theme"
