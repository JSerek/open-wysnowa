"""Tests for theme HIL — display logic, diff computation."""

import pytest

from src.models import ThemeFeedback, ThemeFeedbackOption, ThemeProposal
from src.theme_hil import display_all_themes, display_revision_diff, display_theme_proposal


class TestDisplayThemeProposal:
    """Test single theme display formatting."""

    def test_displays_theme_info(self, capsys):
        theme = ThemeProposal(
            name="Gameplay frustrations",
            definition="Players express dissatisfaction with core gameplay mechanics",
            rationale="Groups combat and parkour ICs",
            constituent_ic_names=["clunky_parkour", "repetitive_combat", "bad_ai"],
        )
        display_theme_proposal(
            theme, theme_num=1, total_themes=3,
            ic_quote_counts={"clunky_parkour": 5, "repetitive_combat": 3, "bad_ai": 2},
            coherence_score=0.72,
        )
        captured = capsys.readouterr()
        assert "Gameplay frustrations" in captured.out
        assert "1/3" in captured.out
        assert "3" in captured.out  # 3 ICs
        assert "high" in captured.out  # 0.72 > 0.7

    def test_displays_low_coherence_warning(self, capsys):
        theme = ThemeProposal(
            name="Misc",
            definition="Miscellaneous feedback that doesn't fit elsewhere",
            rationale="Catch-all",
            constituent_ic_names=["code_a", "code_b"],
        )
        display_theme_proposal(
            theme, theme_num=1, total_themes=1,
            ic_quote_counts={"code_a": 1, "code_b": 1},
            coherence_score=0.25,
        )
        captured = capsys.readouterr()
        assert "low" in captured.out

    def test_no_coherence_score(self, capsys):
        theme = ThemeProposal(
            name="Test theme",
            definition="A theme for testing display",
            rationale="Testing",
            constituent_ic_names=["code_x"],
        )
        display_theme_proposal(
            theme, theme_num=1, total_themes=1,
            ic_quote_counts={"code_x": 3},
            coherence_score=None,
        )
        captured = capsys.readouterr()
        assert "Test theme" in captured.out
        assert "Coherence" not in captured.out  # Should not appear


class TestDisplayAllThemes:
    """Test overview display with warnings."""

    def test_flags_unassigned_ics(self, capsys):
        themes = [
            ThemeProposal(
                name="Theme 1",
                definition="First theme covering some codes",
                rationale="Groups A codes",
                constituent_ic_names=["code_a", "code_b"],
            ),
        ]
        ic_quote_counts = {"code_a": 5, "code_b": 3, "code_c": 2, "code_d": 1}
        display_all_themes(themes, ic_quote_counts)
        captured = capsys.readouterr()
        assert "2 IC(s) not assigned" in captured.out  # code_c and code_d
        assert "code_c" in captured.out
        assert "code_d" in captured.out

    def test_no_unassigned_warning_when_all_covered(self, capsys):
        themes = [
            ThemeProposal(
                name="All-inclusive",
                definition="Covers everything in the codebook",
                rationale="All codes",
                constituent_ic_names=["code_a", "code_b"],
            ),
        ]
        ic_quote_counts = {"code_a": 5, "code_b": 3}
        display_all_themes(themes, ic_quote_counts)
        captured = capsys.readouterr()
        assert "not assigned" not in captured.out

    def test_shows_distinctness_warnings(self, capsys):
        themes = [
            ThemeProposal(
                name="Theme A",
                definition="Theme about A things",
                rationale="Groups A-related codes together",
                constituent_ic_names=["code_a"],
            ),
        ]
        warnings = [("Theme A", "Theme B", 0.85)]
        display_all_themes(
            themes,
            ic_quote_counts={"code_a": 1},
            distinctness_warnings=warnings,
        )
        captured = capsys.readouterr()
        assert "Theme A" in captured.out
        assert "Theme B" in captured.out
        assert "0.85" in captured.out


class TestDisplayRevisionDiff:
    """Test revision diff display."""

    def test_shows_added_and_removed(self, capsys):
        old = [
            ThemeProposal(name="Theme A", definition="Def A long enough", rationale="Rat A", constituent_ic_names=["a"]),
            ThemeProposal(name="Theme B", definition="Def B long enough", rationale="Rat B", constituent_ic_names=["b"]),
        ]
        new = [
            ThemeProposal(name="Theme A", definition="Def A long enough", rationale="Rat A", constituent_ic_names=["a"]),
            ThemeProposal(name="Theme C", definition="Def C long enough", rationale="Rat C", constituent_ic_names=["c"]),
        ]
        display_revision_diff(old, new)
        captured = capsys.readouterr()
        assert "Theme C" in captured.out  # Added
        assert "Theme B" in captured.out  # Removed
        assert "2 → 2" in captured.out

    def test_shows_ic_changes_in_kept_themes(self, capsys):
        old = [
            ThemeProposal(name="Theme X", definition="Some definition here", rationale="Reason here", constituent_ic_names=["a", "b"]),
        ]
        new = [
            ThemeProposal(name="Theme X", definition="Some definition here", rationale="Reason here", constituent_ic_names=["a", "c"]),
        ]
        display_revision_diff(old, new)
        captured = capsys.readouterr()
        assert "+1 ICs" in captured.out  # c added
        assert "-1 ICs" in captured.out  # b removed
