#!/usr/bin/env python3
"""
One-time database initialization script.

Usage:
    python -m scripts.init_db [--db-path eqa_ai.db]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import Database


def main():
    parser = argparse.ArgumentParser(description="Initialize EQD-AI database")
    parser.add_argument(
        "--db-path",
        default="eqa_ai.db",
        help="Path to SQLite database file (default: eqa_ai.db)",
    )
    args = parser.parse_args()

    db = Database(args.db_path)
    db.init_schema()
    print(f"Database initialized at: {args.db_path}")


if __name__ == "__main__":
    main()
