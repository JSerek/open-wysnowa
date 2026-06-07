#!/usr/bin/env python3
"""
EQD-AI v2 Evidence-Extraction Runner — CLI entry point.

Runs L0 (preprocessing) + L1 (IC extraction + codebook building) + L1 metrics.
Theme synthesis and above were shelved in the v2 pivot (see docs/v2/).

Usage:
    # Smoke test (10 reviews, automated)
    python scripts/run_pipeline.py data/canonical_top10.csv --no-hil

    # Custom DB (useful for comparing runs)
    python scripts/run_pipeline.py data/canonical_top50.csv --db runs/run_v2.db --no-hil

    # Interactive (HIL codebook sign-off)
    python scripts/run_pipeline.py data/canonical_top30.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.load_steam_reviews import load_reviews
from src.extraction.pipeline import EQDPipeline


def main():
    parser = argparse.ArgumentParser(
        description="EQD-AI v2: Evidence-Extraction Pipeline (L0 + L1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("csv_path", help="Path to the reviews CSV file")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of reviews to process (default: all)")
    parser.add_argument("--min-chars", type=int, default=20,
                        help="Minimum review length in characters (default: 20)")
    parser.add_argument("--db", type=str, default=None,
                        help="Database filename (default: eqa_<limit>.db)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to eqd_config.yaml (default: auto-detect)")
    parser.add_argument("--no-hil", action="store_true",
                        help="Run without human-in-the-loop (auto-accept codebook)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Run seed, recorded in the run manifest (best-effort determinism)")
    parser.add_argument("--k-index", type=int, default=0,
                        help="Repetition index for this run (variance under k>1)")
    parser.add_argument("--leaderboard-db", type=str, default="runs/leaderboard.db",
                        help="Central run registry DB (default: runs/leaderboard.db)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Logging level (default: INFO)")
    parser.add_argument("--save-results", type=str, default=None,
                        help="Save results summary to JSON file")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ["httpx", "httpcore", "openai", "anthropic"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.db:
        db_path = args.db
    elif args.limit:
        db_path = f"eqa_{args.limit}.db"
    else:
        db_path = "eqa_full.db"

    db_file = Path(db_path)
    enable_hil = not args.no_hil
    config_path = Path(args.config) if args.config else None

    if db_file.exists():
        size_kb = db_file.stat().st_size / 1024
        print(f"\n⚠  Database already exists: {db_path} ({size_kb:.1f} KB)")
        print(f"   [O] Overwrite   [B] Build upon   [A] Abort")
        while True:
            choice = input("   Choice [O/B/A]: ").strip().upper()
            if choice == "O":
                db_file.unlink()
                print(f"   Deleted {db_path}. Starting fresh.\n")
                break
            elif choice == "B":
                print(f"   Building upon existing DB.\n")
                break
            elif choice == "A":
                print("   Aborted.")
                sys.exit(0)
            else:
                print("   Please enter O, B, or A.")

    print(f"\n{'='*60}")
    print(f"  EQD-AI v2 — Evidence Extraction (L0 + L1)")
    print(f"  Dataset: {args.csv_path}")
    print(f"  Limit:   {args.limit or 'all'}")
    print(f"  Mode:    {'Automated' if args.no_hil else 'Interactive (HIL)'}")
    print(f"  Database: {db_path}")
    print(f"{'='*60}\n")

    docs = load_reviews(args.csv_path, limit=args.limit, min_chars=args.min_chars)
    if not docs:
        print("No reviews loaded. Check your CSV path and filters.")
        sys.exit(1)

    pipeline = EQDPipeline(
        config_path=config_path,
        db_path=db_path,
        seed=args.seed,
        k_repeat_index=args.k_index,
        leaderboard_db_path=args.leaderboard_db,
    )
    results = pipeline.run(docs, enable_hil=enable_hil, dataset_path=args.csv_path)

    _print_summary(results, db_path)

    if args.save_results:
        serializable = _make_serializable(results)
        with open(args.save_results, "w") as f:
            json.dump(serializable, f, indent=2, default=str)
        print(f"  Results saved to: {args.save_results}")
    print()


def _print_summary(results, db_path):
    l0 = results.get("layer0", {})
    l1 = results.get("layer1", {})
    l3 = results.get("layer3", {})

    print(f"\n{'='*60}")
    print(f"  EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Documents:    {l0.get('documents', 0)}")
    print(f"  Segments:     {l0.get('segments', 0)}")
    print(f"  ICs created:  {l1.get('new_ics_created', 0)}")
    print(f"  ICs merged:   {l1.get('merged', 0)}")
    print(f"  ICs rejected: {l1.get('rejected', 0)}")

    conf = l3.get('coder_confidence', {})
    if conf and conf.get('mean_confidence') is not None:
        q1, q2, q3 = conf.get('q1_confidence'), conf.get('q2_confidence'), conf.get('q3_confidence')
        dist_str = f"  Q1={q1:.2f} Q2={q2:.2f} Q3={q3:.2f}" if q1 is not None else ""
        low_n = conf.get('low_confidence_count', 0)
        low_str = f"  ({low_n} low-confidence)" if low_n else ""
        print(f"  Confidence:   {conf['mean_confidence']:.2f} mean  "
              f"sd={conf.get('sd_confidence', 0.0):.2f}{dist_str}{low_str}")

    print(f"  Signed off:   {results.get('codebook_signoff', False)}")

    if not l3:
        print(f"\n  Database saved to: {db_path}")
        return

    grounding = l3.get("grounding", {})
    if grounding:
        print(f"  Grounding:    {grounding.get('grounding_rate', 0):.1%} "
              f"({grounding.get('verified', 0)}/{grounding.get('total_quotes', 0)} quotes)")

    ext = l3.get("extraction_density", {})
    if ext:
        dist = ext.get("distribution", {})
        if dist:
            print(f"  Extraction density: mean={dist.get('mean', 0):.2f} "
                  f"median={dist.get('median', 0):.2f} "
                  f"p25={dist.get('p25', 0):.2f} p75={dist.get('p75', 0):.2f} "
                  f"({ext.get('total_segments', 0)} segments)")
        drop = ext.get("drop_rate", {})
        if drop and drop.get("total_raw_candidates", 0) > 0:
            rate = drop.get("overall_rate", 0)
            flag = "⚠ " if rate > 0.10 else ""
            print(f"  {flag}Candidate drop rate: {rate:.1%} "
                  f"({drop.get('total_dropped', 0)}/{drop.get('total_raw_candidates', 0)})")

    ic_conc = l3.get("ic_concentration", {})
    if ic_conc and ic_conc.get("total_ics", 0) > 0:
        dist = ic_conc.get("distribution", {})
        print(f"  IC concentration: singleton_ratio={ic_conc.get('singleton_ratio', 0):.2f} "
              f"mean_quotes/IC={ic_conc.get('mean_quotes_per_ic', 0):.1f} "
              f"range=[{dist.get('min', 0)}-{dist.get('max', 0)}]")

    hall = l3.get("quote_hallucination_rate", {})
    if hall and hall.get("total_raw_candidates", 0) > 0:
        rate = hall.get("quote_hallucination_rate", 0)
        flag = "⚠ " if rate > 0.10 else ""
        print(f"  {flag}Quote hallucination rate: {rate:.1%} "
              f"({hall.get('hallucinated', 0)}/{hall.get('total_raw_candidates', 0)})")

    merge = l3.get("merge_rate", {})
    if merge and merge.get("total_candidates", 0) > 0:
        print(f"  Merge rate:   {merge.get('overall_rate', 0):.1%} "
              f"({merge.get('total_merges', 0)}/{merge.get('total_candidates', 0)})")

    conv = l3.get("cross_review_convergence", {})
    if conv and conv.get("mean_docs_per_ic", 0) > 0:
        print(f"  Convergence:  mean={conv.get('mean_docs_per_ic', 0):.1f} docs/IC, "
              f"confirmed={conv.get('confirmed_ratio', 0):.1%} (2+ docs)")

    its = l3.get("its_history", [])
    if its:
        print(f"  ITS batches:  {len(its)}")

    sat = l3.get("saturation_curve", [])
    if sat:
        last = sat[-1]
        total = last.get("total_ics", 0) if isinstance(last, dict) else getattr(last, "total_ics", 0)
        if total > 0:
            print(f"  Saturation:   {total} ICs discovered across {len(sat)} segments")

    print(f"\n  Database saved to: {db_path}")


def _make_serializable(obj):
    """Convert results dict to JSON-serializable form."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "__dict__"):
        return {k: _make_serializable(v) for k, v in obj.__dict__.items()}
    else:
        return obj


if __name__ == "__main__":
    main()
