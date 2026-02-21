"""Tests for the Steam reviews data loader."""

import csv
import os
import pytest
import tempfile


class TestLoadSteamReviews:
    """Test CSV loading logic."""

    @pytest.fixture
    def sample_csv(self, tmp_path):
        """Create a minimal CSV matching the Steam reviews format."""
        csv_path = tmp_path / "test_reviews.csv"
        rows = [
            {
                "review_id": "1001",
                "author_id": "user_a",
                "review_text": "The worst game in the series. Terrible gameplay and bugs everywhere.",
                "language": "english",
                "created_date": "2026-02-10T12:00:00",
                "sentiment": "negative",
                "voted_up": "False",
                "votes_up": "5",
                "votes_funny": "1",
                "playtime_hours": "24.5",
                "playtime_at_review_minutes": "1470",
                "steam_purchase": "True",
                "received_for_free": "False",
                "early_access": "False",
            },
            {
                "review_id": "1002",
                "author_id": "user_b",
                "review_text": "ok",  # Very short — should be filtered
                "language": "english",
                "created_date": "2026-02-10T13:00:00",
                "sentiment": "negative",
                "voted_up": "False",
                "votes_up": "0",
                "votes_funny": "0",
                "playtime_hours": "0.5",
                "playtime_at_review_minutes": "30",
                "steam_purchase": "True",
                "received_for_free": "False",
                "early_access": "False",
            },
            {
                "review_id": "1003",
                "author_id": "user_c",
                "review_text": "Parkour feels clunky compared to the original. Combat is repetitive after a few hours.",
                "language": "english",
                "created_date": "2026-02-11T08:00:00",
                "sentiment": "negative",
                "voted_up": "False",
                "votes_up": "10",
                "votes_funny": "0",
                "playtime_hours": "15.2",
                "playtime_at_review_minutes": "912",
                "steam_purchase": "True",
                "received_for_free": "False",
                "early_access": "False",
            },
            {
                "review_id": "1004",
                "author_id": "user_d",
                "review_text": "",  # Empty — should be filtered
                "language": "english",
                "created_date": "2026-02-11T09:00:00",
                "sentiment": "negative",
                "voted_up": "False",
                "votes_up": "0",
                "votes_funny": "0",
                "playtime_hours": "0.1",
                "playtime_at_review_minutes": "6",
                "steam_purchase": "True",
                "received_for_free": "False",
                "early_access": "False",
            },
        ]

        fieldnames = rows[0].keys()
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return csv_path

    def test_loads_reviews(self, sample_csv):
        from scripts.load_steam_reviews import load_reviews
        docs = load_reviews(sample_csv)
        # 2 valid reviews (1001 and 1003); 1002 is too short, 1004 is empty
        assert len(docs) == 2

    def test_respects_min_chars(self, sample_csv):
        from scripts.load_steam_reviews import load_reviews
        # With min_chars=1, even "ok" should be included (but empty still filtered)
        docs = load_reviews(sample_csv, min_chars=1)
        assert len(docs) == 3  # 1001, 1002, 1003 (1004 is empty)

    def test_respects_limit(self, sample_csv):
        from scripts.load_steam_reviews import load_reviews
        docs = load_reviews(sample_csv, limit=1)
        assert len(docs) == 1

    def test_preserves_metadata(self, sample_csv):
        from scripts.load_steam_reviews import load_reviews
        docs = load_reviews(sample_csv)
        doc = docs[0]
        assert doc.metadata["review_id"] == "1001"
        assert doc.metadata["playtime_hours"] == "24.5"
        assert doc.metadata["sentiment"] == "negative"

    def test_sets_source_file(self, sample_csv):
        from scripts.load_steam_reviews import load_reviews
        docs = load_reviews(sample_csv)
        assert docs[0].source_file == "test_reviews.csv"

    def test_file_not_found(self, tmp_path):
        from scripts.load_steam_reviews import load_reviews
        with pytest.raises(FileNotFoundError):
            load_reviews(tmp_path / "nonexistent.csv")
