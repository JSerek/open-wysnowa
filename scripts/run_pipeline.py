#!/usr/bin/env python3
"""
EQD-AI Pipeline Runner — CLI entry point.

Run the full analysis pipeline on Steam reviews.

Usage:
    # Smoke test (5 reviews, interactive)
    python scripts/run_pipeline.py dying_light_beast_negative_full.csv --limit 5

    # Full run (100 reviews, interactive)
    python scripts/run_pipeline.py dying_light_beast_negative_full.csv --limit 100

    # Automated (no HIL, useful for benchmarking)
    python scripts/run_pipeline.py dying_light_beast_negative_full.csv --limit 100 --no-hil

    # Custom DB name (useful for comparing runs)
    python scripts/run_pipeline.py dying_light_beast_negative_full.csv --limit 50 --db smoke_test.db
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
from src.pipeline import EQDPipeline


def main():
    parser = argparse.ArgumentParser(
        description="EQD-AI: Exploratory Qualitative Data Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Smoke test:   python scripts/run_pipeline.py reviews.csv --limit 5
  Full run:     python scripts/run_pipeline.py reviews.csv --limit 100
  Automated:    python scripts/run_pipeline.py reviews.csv --limit 100 --no-hil
  Compare:      python scripts/run_pipeline.py reviews.csv --limit 50 --db run_v2.db
        """,
    )

    parser.add_argument(
        "csv_path",
        help="Path to the Steam reviews CSV file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of reviews to process (default: all)",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=20,
        help="Minimum review length in characters (default: 20)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Database filename (default: eqa_<limit>.db)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to eqd_config.yaml (default: auto-detect)",
    )
    parser.add_argument(
        "--no-hil",
        action="store_true",
        help="Run without human-in-the-loop (auto-accept all decisions)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--save-results",
        type=str,
        default=None,
        help="Save results summary to JSON file",
    )

    args = parser.parse_args()

    # Setup logging — semantic tags, silence noisy libraries
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Silence noisy HTTP / embedding loggers — only surface on error
    for noisy in ["httpx", "httpcore", "openai", "anthropic"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Determine DB path
    if args.db:
        db_path = args.db
    elif args.limit:
        db_path = f"eqa_{args.limit}.db"
    else:
        db_path = "eqa_full.db"

    # DB existence check — prevent accidental credit waste
    db_file = Path(db_path)
    if db_file.exists():
        size_kb = db_file.stat().st_size / 1024
        print(f"\n⚠  Database already exists: {db_path} ({size_kb:.1f} KB)")
        print(f"   [O] Overwrite — delete existing DB and start fresh")
        print(f"   [B] Build upon — append to existing DB (incremental run)")
        print(f"   [A] Abort — cancel and exit")
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

    # Load reviews
    print(f"\n{'='*60}")
    print(f"  EQD-AI Pipeline")
    print(f"  Dataset: {args.csv_path}")
    print(f"  Limit: {args.limit or 'all'}")
    print(f"  Mode: {'Automated' if args.no_hil else 'Interactive (HIL)'}")
    print(f"  Database: {db_path}")
    print(f"{'='*60}\n")

    docs = load_reviews(
        args.csv_path,
        limit=args.limit,
        min_chars=args.min_chars,
    )

    if not docs:
        print("No reviews loaded. Check your CSV path and filters.")
        sys.exit(1)

    # Run pipeline
    config_path = Path(args.config) if args.config else None
    pipeline = EQDPipeline(config_path=config_path, db_path=db_path)

    enable_hil = not args.no_hil
    results = pipeline.run(docs, enable_hil=enable_hil)

    # Auto-export thematic structure to JSON next to the DB file
    structure = results.get("thematic_structure")
    if structure:
        db_stem = Path(db_path).stem
        db_dir = Path(db_path).parent
        structure_path = db_dir / f"{db_stem}_thematic_structure.json"
        with open(structure_path, "w", encoding="utf-8") as f:
            json.dump(structure, f, indent=2, default=str)
        print(f"  Thematic structure: {structure_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Documents:    {results['layer0'].get('documents', 0)}")
    print(f"  Segments:     {results['layer0'].get('segments', 0)}")
    print(f"  ICs created:  {results['layer1'].get('new_ics_created', 0)}")
    print(f"  ICs merged:   {results['layer1'].get('merged', 0)}")
    print(f"  ICs rejected: {results['layer1'].get('rejected', 0)}")
    mean_conf = results['layer1'].get('mean_coder_confidence')
    low_conf = results['layer1'].get('low_confidence_ic_count', 0)
    if mean_conf is not None:
        low_str = f"  ({low_conf} low-confidence)" if low_conf else ""
        print(f"  Confidence:   {mean_conf:.2f} mean{low_str}")
    meta_f = results['layer1'].get('meta_filtered', 0)
    meta_fl = results['layer1'].get('meta_flagged', 0)
    if meta_f or meta_fl:
        print(f"  Meta-IC:      {meta_f} auto-rejected, {meta_fl} flagged")
    print(f"  Signed off:   {results.get('codebook_signoff', False)}")
    print(f"  Themes:       {results['layer2'].get('themes_proposed', 0)}")
    print(f"  Rounds:       {results['layer2'].get('rounds', 0)}")
    dissolved = results.get('layer2', {}).get('themes_dissolved', 0)
    if dissolved:
        print(f"  Dissolved:    {dissolved} low-coherence themes")
        redist = results.get('layer2', {}).get('ics_redistributed', 0)
        unassigned = results.get('layer2', {}).get('ics_unassigned', 0)
        if redist or unassigned:
            print(f"  Redistributed: {redist} ICs reassigned, {unassigned} unassigned")

    l3 = results.get("layer3", {})
    if l3:
        grounding = l3.get("grounding", {})
        if grounding:
            print(f"  Grounding:    {grounding.get('grounding_rate', 0):.1%} "
                  f"({grounding.get('verified', 0)}/{grounding.get('total_quotes', 0)} quotes)")

        # Extraction density + candidate drop rate (data integrity)
        ext_density = l3.get("extraction_density", {})
        if ext_density:
            dist = ext_density.get("distribution", {})
            if dist:
                print(f"  Extraction density:")
                print(f"    mean={dist.get('mean', 0):.2f}  "
                      f"median={dist.get('median', 0):.2f}  "
                      f"p25={dist.get('p25', 0):.2f}  p75={dist.get('p75', 0):.2f}")
                print(f"    min={dist.get('min', 0):.2f}  max={dist.get('max', 0):.2f}  "
                      f"({ext_density.get('total_segments', 0)} segments)")
            high = ext_density.get("high_density", [])
            low = ext_density.get("low_density", [])
            if high:
                print(f"    ⚠ {len(high)} high-density (>0.80):")
                for s in high[:3]:
                    preview = s.get("preview", "")[:60]
                    print(f"      {s.get('density', 0):.2f}  \"{preview}\"")
            if low:
                print(f"    ⚠ {len(low)} low-density (<0.20):")
                for s in low[:3]:
                    preview = s.get("preview", "")[:60]
                    print(f"      {s.get('density', 0):.2f}  \"{preview}\"")

            # Candidate drop rate (same data integrity domain)
            drop = ext_density.get("drop_rate", {})
            if drop and drop.get("total_raw_candidates", 0) > 0:
                rate = drop.get("overall_rate", 0)
                total_d = drop.get("total_dropped", 0)
                total_r = drop.get("total_raw_candidates", 0)
                segs_d = drop.get("segments_with_drops", 0)
                flag = "⚠ " if rate > 0.10 else ""
                print(f"  {flag}Candidate drop rate: {rate:.1%} "
                      f"({total_d}/{total_r} candidates, {segs_d} segments affected)")
                for ds in drop.get("top_drop_segments", []):
                    print(f"    {ds.get('n_dropped', 0)} dropped  \"{ds.get('preview', '')[:60]}\"")
            elif drop and drop.get("total_raw_candidates", 0) == 0:
                print(f"  Candidate drop rate: n/a (no drop tracking data)")

        # ITS history
        its = l3.get("its_history", [])
        if its:
            print(f"  ITS batches:  {len(its)}")

        # Cumulative saturation curve
        sat_curve = l3.get("saturation_curve", [])
        if sat_curve:
            total = sat_curve[-1].get("total_ics", 0) if isinstance(sat_curve[-1], dict) else getattr(sat_curve[-1], "total_ics", 0)
            if total > 0:
                print(f"  Saturation:   {total} ICs discovered across {len(sat_curve)} segments")
                for threshold_pct in [0.50, 0.80, 0.95, 1.0]:
                    for pt in sat_curve:
                        frac = pt.get("fraction", 0) if isinstance(pt, dict) else getattr(pt, "fraction", 0)
                        idx = pt.get("segment_index", 0) if isinstance(pt, dict) else getattr(pt, "segment_index", 0)
                        if frac >= threshold_pct:
                            print(f"    {threshold_pct:.0%} codebook at segment {idx + 1}/{len(sat_curve)}")
                            break

        # Meaning saturation v2 — breadth + spread per theme
        ms_theme = l3.get("meaning_saturation_per_theme", {})
        if ms_theme:
            breadths = []
            spreads = []
            for tdata in ms_theme.values():
                if isinstance(tdata, dict):
                    breadths.append(tdata.get("breadth", 0))
                    spreads.append(tdata.get("spread", 0))
            avg_breadth = sum(breadths) / len(breadths) if breadths else 0
            avg_spread = sum(spreads) / len(spreads) if spreads else 0
            print(f"  Meaning sat:  breadth={avg_breadth:.2f}  spread={avg_spread:.2f}  "
                  f"({len(ms_theme)} themes)")
            for tname, tdata in ms_theme.items():
                if isinstance(tdata, dict):
                    b = tdata.get("breadth", 0)
                    s = tdata.get("spread", 0)
                    ic_c = tdata.get("ic_count", 0)
                    last = tdata.get("last_ic_segment", "?")
                    print(f"    b={b:.2f} s={s:.2f}  {tname} ({ic_c} ICs, last@seg {last})")

        # Theme coherence
        coherence = l3.get("theme_coherence", {})
        if coherence:
            vals = list(coherence.values())
            avg_coh = sum(vals) / len(vals) if vals else 0
            print(f"  Coherence:    avg={avg_coh:.3f} across {len(vals)} themes")
            for name, score in coherence.items():
                print(f"    {score:.3f}  {name}")

        # Theme distinctness
        distinctness = l3.get("theme_distinctness", [])
        if distinctness:
            sims = [s for _, _, s in distinctness]
            avg_dist = sum(sims) / len(sims) if sims else 0
            print(f"  Distinctness: avg pairwise sim={avg_dist:.3f} ({len(distinctness)} pairs)")
            overlaps = [(a, b, s) for a, b, s in distinctness if s > 0.70]
            if overlaps:
                print(f"    ⚠ {len(overlaps)} overlapping pairs (sim > 0.70):")
                for a, b, s in overlaps:
                    print(f"      {a} ↔ {b}: {s:.3f}")

        # IC Concentration
        ic_conc = l3.get("ic_concentration", {})
        if ic_conc and ic_conc.get("total_ics", 0) > 0:
            sr = ic_conc.get("singleton_ratio", 0)
            mean_q = ic_conc.get("mean_quotes_per_ic", 0)
            dist = ic_conc.get("distribution", {})
            print(f"  IC Concentration: singleton_ratio={sr:.2f}  "
                  f"mean_quotes/IC={mean_q:.1f}  "
                  f"range=[{dist.get('min', 0)}-{dist.get('max', 0)}]")

        # Merge Rate Over Time
        merge_rate = l3.get("merge_rate", {})
        if merge_rate and merge_rate.get("total_candidates", 0) > 0:
            overall = merge_rate.get("overall_rate", 0)
            per_batch = merge_rate.get("per_batch", [])
            print(f"  Merge rate:    {overall:.1%} overall "
                  f"({merge_rate.get('total_merges', 0)}/{merge_rate.get('total_candidates', 0)})")
            for b in per_batch:
                print(f"    batch {b.get('batch_num', 0)}: "
                      f"{b.get('rate', 0):.1%} "
                      f"({b.get('merges', 0)}/{b.get('new_candidates', 0)})")

        # Triage Efficiency
        triage = l3.get("triage_efficiency", {})
        if triage and triage.get("total_non_trivial", 0) > 0:
            eff = triage.get("efficiency", 0)
            print(f"  Triage eff:   {eff:.1%} auto-decided "
                  f"({triage.get('llm_calls_saved', 0)} saved, "
                  f"{triage.get('grey_zone', 0)} LLM calls)")
            print(f"    auto_new={triage.get('auto_new', 0)}  "
                  f"auto_merge={triage.get('auto_merge', 0)}  "
                  f"grey_zone={triage.get('grey_zone', 0)}  "
                  f"empty_codebook={triage.get('empty_codebook', 0)}")

        # Comparator Agreement
        comp_agree = l3.get("comparator_agreement", {})
        if comp_agree and comp_agree.get("total_grey_zone", 0) > 0:
            rate = comp_agree.get("agreement_rate", 0)
            print(f"  Comparator:   {rate:.1%} LLM-embedding agreement "
                  f"({comp_agree.get('agreed', 0)}/{comp_agree.get('total_grey_zone', 0)} "
                  f"grey-zone decisions)")

        # Coherence Normalized
        coh_norm = l3.get("coherence_normalized", {})
        if coh_norm and coh_norm.get("per_theme"):
            baseline = coh_norm.get("baseline", 0)
            avg_n = coh_norm.get("avg_normalized", 0)
            print(f"  Coh. norm:    avg={avg_n:.2f}x baseline  "
                  f"(baseline={baseline:.3f})")
            for tname, tvals in coh_norm.get("per_theme", {}).items():
                raw = tvals.get("raw", 0)
                norm = tvals.get("normalized", 0)
                print(f"    {norm:.2f}x  {tname} (raw={raw:.3f})")

        # Cross-Theme IC Sharing
        cross = l3.get("cross_theme_ic_sharing", {})
        if cross and cross.get("total_ics", 0) > 0:
            sr = cross.get("sharing_ratio", 0)
            print(f"  IC sharing:   {sr:.1%} ICs in 2+ themes "
                  f"({cross.get('shared_count', 0)}/{cross.get('total_ics', 0)})")
            for shared in cross.get("shared_ics", [])[:5]:
                print(f"    {shared.get('ic_name', '?')} → "
                      f"{', '.join(shared.get('themes', []))}")

        # IC Stability Index
        ic_stab = l3.get("ic_stability", {})
        if ic_stab and ic_stab.get("refined_count", 0) > 0:
            ms = ic_stab.get("mean_stability", 0)
            rewritten = ic_stab.get("substantially_rewritten", 0)
            total_r = ic_stab.get("refined_count", 0)
            flag = "" if ms > 0.90 else "⚠ "
            print(f"  {flag}IC stability:  mean={ms:.4f} "
                  f"({rewritten}/{total_r} substantially rewritten)")
            # Show bottom 5 least stable
            per_ic = ic_stab.get("per_ic", [])
            for s in per_ic[:5]:
                stab = s.get("stability", 0)
                mark = "⚠ " if stab < 0.85 else "  "
                print(f"    {mark}{stab:.4f}  {s.get('ic_name', '?')}")

        # Orphaned ICs
        orphaned = l3.get("orphaned_ics", {})
        if orphaned and orphaned.get("orphaned_count", 0) > 0:
            oc = orphaned.get("orphaned_count", 0)
            total_a = orphaned.get("total_active_ics", 0)
            print(f"  ⚠ Orphaned ICs: {oc}/{total_a} not in any theme")
            for name in orphaned.get("orphaned_names", [])[:5]:
                print(f"    - {name}")

        # Thematic Coverage
        coverage = l3.get("thematic_coverage", {})
        if coverage and coverage.get("total_quotes", 0) > 0:
            cr = coverage.get("coverage_ratio", 0)
            flag = "" if cr >= 0.95 else "⚠ "
            print(f"  {flag}Thematic coverage: {cr:.1%} "
                  f"({coverage.get('covered_quotes', 0)}/{coverage.get('total_quotes', 0)} quotes)")

        # Cross-Review Convergence
        conv = l3.get("cross_review_convergence", {})
        if conv and conv.get("mean_docs_per_ic", 0) > 0:
            md = conv.get("mean_docs_per_ic", 0)
            conf = conv.get("confirmed_ratio", 0)
            strong = conv.get("strong_convergence_ratio", 0)
            print(f"  Convergence:  mean={md:.1f} docs/IC, "
                  f"confirmed={conf:.1%} (2+ docs), "
                  f"strong={strong:.1%} (3+ docs)")

        # Sentiment Purity
        sent_purity = l3.get("sentiment_purity", {})
        if sent_purity and sent_purity.get("per_theme"):
            avg_p = sent_purity.get("avg_purity", 0)
            flagged = sent_purity.get("flagged_count", 0)
            flag_str = f"  ⚠ " if flagged > 0 else "  "
            print(f"{flag_str}Sentiment purity: avg={avg_p:.2f} "
                  f"({flagged} themes flagged <0.70)")
            for tname, tdata in sent_purity.get("per_theme", {}).items():
                p = tdata.get("purity", 0)
                dom = tdata.get("dominant", "?")
                dist = tdata.get("distribution", {})
                total = tdata.get("total_with_sentiment", 0)
                mark = "⚠ " if tdata.get("flagged") else "  "
                if total > 0:
                    print(f"    {mark}{p:.2f} ({dom})  {tname}  "
                          f"[+{dist.get('positive', 0)} "
                          f"-{dist.get('negative', 0)} "
                          f"~{dist.get('neutral', 0)} "
                          f"±{dist.get('mixed', 0)}]")

    # Category summary
    cat_results = results.get("categories", {})
    if cat_results and cat_results.get("categories_created", 0) > 0:
        cat_names = cat_results.get("category_names", [])
        print(f"  Categories:   {cat_results['categories_created']} ({', '.join(cat_names)})")

    # Thematic structure summary
    structure = results.get("thematic_structure", [])
    if structure:
        # Detect if structure is hierarchical (categories) or flat (themes)
        first = structure[0] if structure else {}
        is_hierarchical = "themes" in first

        if is_hierarchical:
            total_themes = sum(c.get("theme_count", 0) for c in structure)
            print(f"\n  {'─'*56}")
            print(f"  THEMATIC STRUCTURE ({len(structure)} categories, {total_themes} themes)")
            print(f"  {'─'*56}")
            for cat in structure:
                cat_themes = cat.get("themes", [])
                cat_total_ics = sum(t.get("ic_count", 0) for t in cat_themes)
                print(f"\n  ▌ {cat['name']} ({len(cat_themes)} themes, {cat_total_ics} ICs)")
                print(f"    {cat.get('definition', '')[:100]}")
                for theme in cat_themes:
                    ic_count = theme.get("ic_count", 0)
                    total_quotes = sum(ic.get("quote_count", 0) for ic in theme.get("initial_codes", []))
                    print(f"\n    {theme['name']}")
                    print(f"      {theme.get('definition', '')[:100]}")
                    print(f"      ICs: {ic_count} | Quotes: {total_quotes}")
                    for ic in theme.get("initial_codes", []):
                        q_count = ic.get("quote_count", 0)
                        print(f"        - {ic['name']} ({q_count} quote{'s' if q_count != 1 else ''})")
        else:
            # Flat theme structure (no categories)
            print(f"\n  {'─'*56}")
            print(f"  THEMATIC STRUCTURE ({len(structure)} themes)")
            print(f"  {'─'*56}")
            for theme in structure:
                ic_count = theme.get("ic_count", 0)
                total_quotes = sum(ic.get("quote_count", 0) for ic in theme.get("initial_codes", []))
                print(f"\n  {theme['name']}")
                print(f"    {theme.get('definition', '')[:100]}")
                print(f"    ICs: {ic_count} | Quotes: {total_quotes}")
                for ic in theme.get("initial_codes", []):
                    q_count = ic.get("quote_count", 0)
                    print(f"      - {ic['name']} ({q_count} quote{'s' if q_count != 1 else ''})")

    print(f"\n  Database saved to: {db_path}")

    # Save results to JSON if requested
    if args.save_results:
        # Make results JSON-serializable (remove BatchITS objects)
        serializable = _make_serializable(results)
        with open(args.save_results, "w") as f:
            json.dump(serializable, f, indent=2, default=str)
        print(f"  Results saved to: {args.save_results}")

    print()


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
