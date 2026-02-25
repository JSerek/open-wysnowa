"""
Stabilization run comparator.

Reads multiple results JSON files and prints a side-by-side metrics table.
Useful for tracking how metrics evolve across different configs/segment counts.

Usage (run from project root):
    python scripts/compare_runs.py runs/results_stab_30.json runs/results_stab_50.json
    python scripts/compare_runs.py runs/results_*.json
    python scripts/compare_runs.py runs/results_*.json --csv > comparison.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

# ── Metric extraction ─────────────────────────────────────────────────────────

def _safe(val, fmt=None):
    """Format a value safely — returns '—' if missing/None."""
    if val is None:
        return "—"
    if fmt:
        try:
            return fmt.format(val)
        except (TypeError, ValueError):
            return str(val)
    return str(val)


def extract_metrics(path: Path) -> dict:
    """Pull all comparable metrics from a results JSON."""
    with open(path) as f:
        r = json.load(f)

    l3   = r.get("layer3", {})
    l0   = r.get("layer0", {})
    l1   = r.get("layer1", {})
    l2   = r.get("layer2", {})

    # ── Pipeline summary ──
    docs   = l0.get("documents", "?")
    segs   = l0.get("segments",  "?")
    ics    = l1.get("new_ics_created", "?")
    merged = l1.get("merged", "?")

    ts = r.get("thematic_structure", [])
    cats   = len(ts)
    themes = sum(len(c.get("themes", [])) for c in ts)

    # ── Drop rate (layer1: dropped candidates / total candidates) ──
    total_cand = l1.get("total_candidates", 0)
    dropped    = l1.get("total_dropped", 0)
    drop_r     = (dropped / total_cand) if total_cand else None

    # ── Grounding ──
    grounding   = l3.get("grounding", {})
    grounding_r = grounding.get("grounding_rate")

    # ── Extraction density ──
    density_dist = l3.get("extraction_density", {}).get("distribution", {})
    density_m    = density_dist.get("mean")

    # ── IC concentration ──
    ic_conc     = l3.get("ic_concentration", {})
    singleton_r = ic_conc.get("singleton_ratio")

    # ── Merge rate ──
    merge_r = l3.get("merge_rate", {}).get("overall_rate")

    # ── Triage efficiency ──
    triage_r = l3.get("triage_efficiency", {}).get("efficiency")

    # ── Theme coherence (flat {name: float}) ──
    coh_map     = l3.get("theme_coherence", {})
    vals        = [v for v in coh_map.values() if isinstance(v, (int, float))]
    coh_avg     = (sum(vals) / len(vals)) if vals else None

    # ── Coherence normalised ──
    coh_norm_avg = l3.get("coherence_normalized", {}).get("avg_normalized")

    # ── Theme distinctness (list of [a, b, sim]) ──
    dist_list   = l3.get("theme_distinctness", [])
    if dist_list and isinstance(dist_list[0], (list, tuple)):
        sims      = [row[2] for row in dist_list if len(row) >= 3]
        dist_avg  = (sum(sims) / len(sims)) if sims else None
        OVERLAP_T = 0.70
        overlap_n = sum(1 for s in sims if s > OVERLAP_T)
    else:
        dist_avg, overlap_n = None, None

    # ── Sentiment purity ──
    sent      = l3.get("sentiment_purity", {})
    sent_avg  = sent.get("avg_purity")
    sent_flag = sent.get("flagged_count")

    # ── Thematic coverage ──
    cov_r = l3.get("thematic_coverage", {}).get("coverage_ratio")

    # ── Cross-review convergence ──
    conv_conf = l3.get("cross_review_convergence", {}).get("confirmed_ratio")

    # ── Meaning saturation (per-theme → average breadth & spread) ──
    ms      = l3.get("meaning_saturation_per_theme", {})
    ms_vals = [v for v in ms.values() if isinstance(v, dict)]
    ms_breadth = (sum(v.get("breadth", 0) for v in ms_vals) / len(ms_vals)) if ms_vals else None
    ms_spread  = (sum(v.get("spread",  0) for v in ms_vals) / len(ms_vals)) if ms_vals else None

    # ── IC stability ──
    ic_stab_m = l3.get("ic_stability", {}).get("mean_stability")

    # ── File metadata ──
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    return {
        "file":         path.name,
        "modified":     mtime,
        # Pipeline
        "docs":         docs,
        "segs":         segs,
        "ics":          ics,
        "merged":       merged,
        "themes":       themes,
        "cats":         cats,
        # Quality
        "grounding":    grounding_r,
        "drop_rate":    drop_r,
        "density_mean": density_m,
        "singleton_r":  singleton_r,
        "merge_rate":   merge_r,
        "triage_auto":  triage_r,
        "coh_avg":      coh_avg,
        "coh_norm_avg": coh_norm_avg,
        "distinctness": dist_avg,
        "overlaps":     overlap_n,
        "sent_purity":  sent_avg,
        "sent_flagged": sent_flag,
        "coverage":     cov_r,
        "convergence":  conv_conf,
        "ms_breadth":   ms_breadth,
        "ms_spread":    ms_spread,
        "ic_stability": ic_stab_m,
    }


# ── Display ───────────────────────────────────────────────────────────────────

ROWS = [
    # (label, key, format)
    ("── PIPELINE SUMMARY ──", None, None),
    ("Documents",         "docs",         "{}"),
    ("Segments",          "segs",         "{}"),
    ("ICs created",       "ics",          "{}"),
    ("ICs merged",        "merged",       "{}"),
    ("Themes",            "themes",       "{}"),
    ("Categories",        "cats",         "{}"),
    ("── EXTRACTION ─────", None, None),
    ("Grounding rate",    "grounding",    "{:.1%}"),
    ("Drop rate",         "drop_rate",    "{:.1%}"),
    ("Density mean",      "density_mean", "{:.1%}"),
    ("Singleton ratio",   "singleton_r",  "{:.1%}"),
    ("── CODEBOOK ───────", None, None),
    ("Merge rate",        "merge_rate",   "{:.1%}"),
    ("Triage auto",       "triage_auto",  "{:.1%}"),
    ("IC stability",      "ic_stability", "{:.3f}"),
    ("── THEMATIC ───────", None, None),
    ("Coherence avg",     "coh_avg",      "{:.3f}"),
    ("Coh norm avg",      "coh_norm_avg", "{:.2f}x"),
    ("Distinctness avg",  "distinctness", "{:.3f}"),
    ("Overlap pairs",     "overlaps",     "{}"),
    ("Sent purity avg",   "sent_purity",  "{:.3f}"),
    ("Sent flagged",      "sent_flagged", "{}"),
    ("── COVERAGE ───────", None, None),
    ("Thematic coverage", "coverage",     "{:.1%}"),
    ("Convergence conf",  "convergence",  "{:.1%}"),
    ("MS breadth",        "ms_breadth",   "{:.3f}"),
    ("MS spread",         "ms_spread",    "{:.3f}"),
]

COL_W = 22  # width of each data column
LABEL_W = 20


def print_table(runs: list[dict]) -> None:
    sep = "─" * (LABEL_W + 2 + COL_W * len(runs) + (len(runs) - 1) * 3)

    # Header
    header = f"{'':>{LABEL_W}}  " + "   ".join(r["file"][:COL_W].ljust(COL_W) for r in runs)
    date_r = f"{'modified':>{LABEL_W}}  " + "   ".join(r["modified"][:COL_W].ljust(COL_W) for r in runs)
    print()
    print(sep)
    print(header)
    print(date_r)
    print(sep)

    for label, key, fmt in ROWS:
        if key is None:
            # Section header
            print(f"\n  {label}")
            continue
        values = []
        for r in runs:
            raw = r.get(key)
            values.append(_safe(raw, fmt))
        row = f"  {label:>{LABEL_W - 2}}  " + "   ".join(v.rjust(COL_W) for v in values)
        print(row)

    print()
    print(sep)
    print()


def write_csv(runs: list[dict], writer) -> None:
    keys = [row[1] for row in ROWS if row[1] is not None]
    labels = {row[1]: row[0] for row in ROWS if row[1] is not None}
    fmts   = {row[1]: row[2] for row in ROWS if row[1] is not None}

    header = ["metric"] + [r["file"] for r in runs]
    writer.writerow(header)
    writer.writerow(["modified"] + [r["modified"] for r in runs])

    for key in keys:
        row_vals = [labels.get(key, key)]
        for r in runs:
            raw = r.get(key)
            row_vals.append(_safe(raw, fmts.get(key)))
        writer.writerow(row_vals)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare EQD-AI stabilization run metrics")
    parser.add_argument("files", nargs="+", help="Results JSON files to compare")
    parser.add_argument("--csv", action="store_true", help="Output as CSV (pipe to file)")
    args = parser.parse_args()

    paths = [Path(f) for f in args.files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"Error: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    runs = []
    for p in paths:
        try:
            runs.append(extract_metrics(p))
        except Exception as e:
            print(f"Warning: could not parse {p.name}: {e}", file=sys.stderr)

    if not runs:
        print("No valid run files found.", file=sys.stderr)
        sys.exit(1)

    if args.csv:
        writer = csv.writer(sys.stdout)
        write_csv(runs, writer)
    else:
        print_table(runs)


if __name__ == "__main__":
    main()
