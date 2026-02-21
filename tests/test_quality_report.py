"""Tests for quality report display functions."""

import pytest
from src.models import BatchITS
from src.quality_report import (
    _mini_bar,
    display_codebook_report,
    display_final_report,
    display_theme_report,
)


class TestMiniBar:
    def test_full_bar(self):
        bar = _mini_bar(1.0, max_val=1.0, width=15)
        assert len(bar) == 15
        assert bar.count("█") == 15
        assert bar.count("░") == 0

    def test_half_bar(self):
        bar = _mini_bar(0.5, max_val=1.0, width=10)
        assert len(bar) == 10
        assert bar.count("█") == 5
        assert bar.count("░") == 5

    def test_empty_bar(self):
        bar = _mini_bar(0.0, max_val=1.0, width=10)
        assert len(bar) == 10
        assert bar.count("█") == 0
        assert bar.count("░") == 10

    def test_over_max_clamps(self):
        bar = _mini_bar(2.0, max_val=1.0, width=10)
        assert bar.count("█") == 10  # Clamped to max

    def test_zero_max_returns_empty(self):
        bar = _mini_bar(5.0, max_val=0.0, width=10)
        assert len(bar) == 10


class TestDisplayCodebookReport:
    def test_displays_grounding(self, capsys):
        metrics = {
            "grounding": {
                "total_quotes": 50,
                "verified": 48,
                "failed": 2,
                "grounding_rate": 0.96,
                "failures": [("q1", "ic1", "mismatch"), ("q2", "ic2", "mismatch")],
            },
        }
        display_codebook_report(metrics)
        captured = capsys.readouterr()
        assert "GROUNDING" in captured.out
        assert "48/50" in captured.out
        assert "96.0%" in captured.out
        assert "2 verification failure" in captured.out

    def test_displays_coverage(self, capsys):
        metrics = {
            "coverage": {
                "total_segments": 100,
                "coded_segments": 85,
                "coverage_rate": 0.85,
            },
        }
        display_codebook_report(metrics)
        captured = capsys.readouterr()
        assert "COVERAGE" in captured.out
        assert "85/100" in captured.out

    def test_displays_its_curve(self, capsys):
        metrics = {
            "its_history": [
                BatchITS(batch_number=1, ics_before=0, new_ics_created=8, its_value=1.0, consecutive_low=0, is_checkpoint=False),
                BatchITS(batch_number=2, ics_before=8, new_ics_created=3, its_value=0.375, consecutive_low=0, is_checkpoint=False),
                BatchITS(batch_number=3, ics_before=11, new_ics_created=0, its_value=0.0, consecutive_low=1, is_checkpoint=False),
            ],
        }
        display_codebook_report(metrics)
        captured = capsys.readouterr()
        assert "ITS" in captured.out
        assert "1.0000" in captured.out
        assert "0.3750" in captured.out

    def test_handles_empty_metrics(self, capsys):
        display_codebook_report({})
        captured = capsys.readouterr()
        assert "CODEBOOK QUALITY REPORT" in captured.out


class TestDisplayThemeReport:
    def test_displays_coherence(self, capsys):
        metrics = {
            "theme_coherence": {
                "Gameplay issues": 0.72,
                "Story complaints": 0.45,
            },
        }
        display_theme_report(metrics)
        captured = capsys.readouterr()
        assert "COHERENCE" in captured.out
        assert "Gameplay issues" in captured.out
        assert "0.720" in captured.out
        assert "high" in captured.out  # 0.72 > 0.7
        assert "moderate" in captured.out  # 0.45

    def test_displays_distinctness_overlap(self, capsys):
        metrics = {
            "theme_distinctness": [
                ("Theme A", "Theme B", 0.82),
                ("Theme A", "Theme C", 0.35),
            ],
        }
        display_theme_report(metrics)
        captured = capsys.readouterr()
        assert "DISTINCTNESS" in captured.out
        assert "OVERLAP" in captured.out  # 0.82 > 0.70


class TestDisplayFinalReport:
    def test_displays_summary(self, capsys):
        metrics = {
            "grounding": {"grounding_rate": 0.98, "total_quotes": 100, "verified": 98, "failed": 2, "failures": []},
            "coverage": {"coverage_rate": 0.87, "total_segments": 50, "coded_segments": 43},
            "its_history": [
                BatchITS(batch_number=3, ics_before=25, new_ics_created=1, its_value=0.04, consecutive_low=0, is_checkpoint=False),
            ],
            "theme_coherence": {"Theme 1": 0.65},
            "theme_distinctness": [],
            "meaning_saturation": [],
        }
        display_final_report(metrics, decision_log_summary={"CREATE": 20, "MERGE": 5, "REJECT": 3})
        captured = capsys.readouterr()
        assert "FINAL ANALYSIS REPORT" in captured.out
        assert "98.0%" in captured.out
        assert "87.0%" in captured.out
        assert "CREATE: 20" in captured.out
        assert "END OF REPORT" in captured.out
