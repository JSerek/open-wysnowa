#!/usr/bin/env python3
"""
Load Steam reviews from CSV into EQD-AI Document objects.

Handles:
- CSV parsing with proper quoting (reviews contain commas, newlines)
- Metadata extraction (playtime, votes, sentiment, dates)
- Filtering: drops empty/very short reviews (< min_chars)
- Optional limit for testing with smaller samples

Usage:
    from scripts.load_steam_reviews import load_reviews
    docs = load_reviews("dying_light_beast_negative_full.csv", limit=100)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import Document


def load_reviews(
    csv_path: str | Path,
    limit: Optional[int] = None,
    min_chars: int = 20,
    language_filter: Optional[str] = None,
) -> List[Document]:
    """
    Load Steam reviews from CSV into Document objects.

    Args:
        csv_path: path to the CSV file
        limit: max number of reviews to load (None = all)
        min_chars: minimum review text length to include (default 20)
        language_filter: only include reviews in this language (None = all)

    Returns:
        List of Document objects ready for the EQD pipeline.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    documents: List[Document] = []
    skipped_short = 0
    skipped_lang = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            review_text = row.get("review_text", "").strip()

            # Skip empty / very short reviews
            if len(review_text) < min_chars:
                skipped_short += 1
                continue

            # Language filter
            if language_filter and row.get("language", "") != language_filter:
                skipped_lang += 1
                continue

            # Build metadata from available columns
            metadata = {}
            for key in [
                "review_id", "author_id", "language", "created_date",
                "sentiment", "voted_up", "votes_up", "votes_funny",
                "playtime_hours", "playtime_at_review_minutes",
                "steam_purchase", "received_for_free", "early_access",
            ]:
                if key in row and key != "review_text":
                    metadata[key] = row[key]

            doc = Document(
                raw_text=review_text,
                source_file=csv_path.name,
                metadata=metadata,
            )
            documents.append(doc)

            if limit and len(documents) >= limit:
                break

    print(f"Loaded {len(documents)} reviews from {csv_path.name}")
    if skipped_short:
        print(f"  Skipped {skipped_short} reviews (< {min_chars} chars)")
    if skipped_lang:
        print(f"  Skipped {skipped_lang} reviews (language filter: {language_filter})")

    return documents


if __name__ == "__main__":
    """Quick sanity check — load and preview."""
    import argparse

    parser = argparse.ArgumentParser(description="Load Steam reviews")
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument("--limit", type=int, default=10, help="Max reviews to load")
    parser.add_argument("--min-chars", type=int, default=20, help="Min review length")
    args = parser.parse_args()

    docs = load_reviews(args.csv_path, limit=args.limit, min_chars=args.min_chars)

    for i, doc in enumerate(docs[:5], 1):
        preview = doc.raw_text[:100] + "..." if len(doc.raw_text) > 100 else doc.raw_text
        playtime = doc.metadata.get("playtime_hours", "?")
        print(f"  [{i}] ({playtime}h) {preview}")
