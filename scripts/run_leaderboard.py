#!/usr/bin/env python3
"""
EQD-AI v2 — Leaderboard runner (Phase 3) — CLI entry point.

Runs the L1 pipeline across a matrix of (generation model × embedding model ×
k-repetition), records each run in the central registry, and prints the resulting
metric × model matrix (with directions and, for k>1, variance).

Usage:
    python scripts/run_leaderboard.py \
        --gen-models or_smart,or_fast --embed-models embed_openai \
        --dataset data/canonical_top10.csv -k 1 --seed 42

Model names are the named keys from eqd_config.yaml (`models:`), e.g.
or_smart / or_fast / embed_openai. Every run is headless and sim-blind (eval mode).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.load_steam_reviews import load_reviews
from src.leaderboard.harness import run_leaderboard
from src.leaderboard.registry import RunRegistry
from src.leaderboard.report import render_matrix_csv, render_matrix_markdown


def _csv_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="EQD-AI v2: L1 leaderboard (gen × embed × k matrix)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--gen-models", type=_csv_list, required=True,
                        help="Comma-separated generative model keys (e.g. or_smart,or_fast)")
    parser.add_argument("--embed-models", type=_csv_list, required=True,
                        help="Comma-separated embedding model keys (e.g. embed_openai)")
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to the reviews CSV file")
    parser.add_argument("-k", "--k", type=int, default=1,
                        help="Repetitions per combo (variance under k>1; default 1)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Run seed, recorded in each manifest (best-effort determinism)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to eqd_config.yaml (default: auto-detect)")
    parser.add_argument("--leaderboard-db", type=str, default="runs/leaderboard.db",
                        help="Central run registry DB (default: runs/leaderboard.db)")
    parser.add_argument("--run-db-dir", type=str, default="runs",
                        help="Directory for per-run isolated DBs (default: runs)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of reviews to process (default: all)")
    parser.add_argument("--min-chars", type=int, default=20,
                        help="Minimum review length in characters (default: 20)")
    parser.add_argument("--csv-out", type=str, default=None,
                        help="Optional path to write the matrix as CSV")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Logging level (default: INFO)")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ["httpx", "httpcore", "openai", "anthropic"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    docs = load_reviews(args.dataset, limit=args.limit, min_chars=args.min_chars)
    if not docs:
        print("No reviews loaded. Check your CSV path and filters.")
        sys.exit(1)

    n_combos = len(args.gen_models) * len(args.embed_models) * args.k
    print(f"\n{'='*60}")
    print(f"  EQD-AI v2 — L1 Leaderboard")
    print(f"  Gen models:   {', '.join(args.gen_models)}")
    print(f"  Embed models: {', '.join(args.embed_models)}")
    print(f"  Dataset:      {args.dataset} ({len(docs)} reviews)")
    print(f"  k:            {args.k}  →  {n_combos} runs")
    print(f"{'='*60}\n")

    records = run_leaderboard(
        gen_models=args.gen_models,
        embed_models=args.embed_models,
        documents=docs,
        dataset_path=args.dataset,
        k=args.k,
        seed=args.seed,
        base_config_path=Path(args.config) if args.config else None,
        leaderboard_db_path=args.leaderboard_db,
        run_db_dir=args.run_db_dir,
    )

    registry = RunRegistry(args.leaderboard_db)
    matrix = registry.load_matrix()

    print(f"\n{'='*60}")
    print(f"  LEADERBOARD MATRIX  ({len(records)} runs registered)")
    print(f"{'='*60}\n")
    print(render_matrix_markdown(matrix))
    print()

    if args.csv_out:
        Path(args.csv_out).write_text(render_matrix_csv(matrix), encoding="utf-8")
        print(f"  Matrix CSV written to: {args.csv_out}\n")


if __name__ == "__main__":
    main()
