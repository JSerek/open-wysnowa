"""
EQD-AI Layer 3: Quality Report — Terminal Dashboard.

Display functions for all quality metrics.
Three report types:
1. Codebook report — after Layer 1 (grounding, coverage, ITS, meaning saturation)
2. Theme report — after Layer 2 (coherence, distinctness)
3. Final report — complete summary of all 6 metrics + audit trail

Pure display functions — no state, no DB access.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.models import BatchITS

# ── Display Constants ────────────────────────────────────────────────────────

SEPARATOR = "=" * 70
THIN_SEP = "-" * 70
SECTION_SEP = "─" * 50


# ── Codebook Quality Report ─────────────────────────────────────────────────

def display_codebook_report(metrics: Dict[str, Any]) -> None:
    """
    Display quality report after codebook sign-off.

    Shows: grounding rate, coverage, ITS curve, meaning saturation.
    """
    print(f"\n{SEPARATOR}")
    print(f"  CODEBOOK QUALITY REPORT")
    print(SEPARATOR)

    # Grounding
    grounding = metrics.get("grounding", {})
    if grounding:
        print(f"\n  {SECTION_SEP}")
        print(f"  GROUNDING")
        total = grounding.get("total_quotes", 0)
        verified = grounding.get("verified", 0)
        rate = grounding.get("grounding_rate", 0.0)
        print(f"    Verified: {verified}/{total} ({rate:.1%})")
        failures = grounding.get("failures", [])
        if failures:
            print(f"    ⚠ {len(failures)} verification failure(s)")

    # Coverage
    coverage = metrics.get("coverage", {})
    if coverage:
        print(f"\n  {SECTION_SEP}")
        print(f"  COVERAGE")
        total_seg = coverage.get("total_segments", 0)
        coded_seg = coverage.get("coded_segments", 0)
        rate = coverage.get("coverage_rate", 0.0)
        print(f"    Coded segments: {coded_seg}/{total_seg} ({rate:.1%})")

    # ITS curve
    its_history: List[BatchITS] = metrics.get("its_history", [])
    if its_history:
        print(f"\n  {SECTION_SEP}")
        print(f"  INCREMENTAL TYPE SATURATION (ITS)")
        print(f"    Batch   ITS     New  Codebook  Low-streak")
        for batch in its_history:
            bar = _mini_bar(batch.its_value, max_val=1.0, width=15)
            checkpoint = " ★" if batch.is_checkpoint else ""
            print(
                f"    {batch.batch_number:5d}   {batch.its_value:.4f}  "
                f"{batch.new_ics_created:4d}  {batch.ics_before:8d}  "
                f"{batch.consecutive_low:10d} {bar}{checkpoint}"
            )

    # Meaning saturation
    saturation: List[Dict] = metrics.get("meaning_saturation", [])
    if saturation:
        print(f"\n  {SECTION_SEP}")
        print(f"  MEANING SATURATION (per IC)")
        print(f"    IC Name                              Quotes  Clusters  Diversity")

        # Sort by diversity (ascending — thin evidence first)
        sorted_sat = sorted(saturation, key=lambda x: x["diversity_score"])
        for entry in sorted_sat:
            name = entry["ic_name"][:40].ljust(40)
            flag = " ⚠" if entry["diversity_score"] < 0.3 and entry["evidence_count"] >= 3 else ""
            print(
                f"    {name}  {entry['evidence_count']:6d}  "
                f"{entry['clusters']:8d}  {entry['diversity_score']:.3f}{flag}"
            )


# ── Theme Quality Report ────────────────────────────────────────────────────

def display_theme_report(metrics: Dict[str, Any]) -> None:
    """
    Display quality report for themes.

    Shows: coherence per theme, distinctness pairs with warnings.
    """
    print(f"\n{SEPARATOR}")
    print(f"  THEME QUALITY REPORT")
    print(SEPARATOR)

    # Coherence
    coherence: Dict[str, float] = metrics.get("theme_coherence", {})
    if coherence:
        print(f"\n  {SECTION_SEP}")
        print(f"  THEME COHERENCE (intra-theme IC similarity)")
        print(f"    Theme                                    Coherence")

        for name, score in sorted(coherence.items(), key=lambda x: x[1]):
            display_name = name[:44].ljust(44)
            label = "high" if score > 0.7 else "moderate" if score > 0.4 else "LOW ⚠"
            print(f"    {display_name}  {score:.3f}  ({label})")

    # Distinctness
    distinctness: List[Tuple[str, str, float]] = metrics.get("theme_distinctness", [])
    if distinctness:
        print(f"\n  {SECTION_SEP}")
        print(f"  THEME DISTINCTNESS (inter-theme similarity)")
        print(f"    Theme A                     Theme B                     Similarity")

        for name_a, name_b, sim in sorted(distinctness, key=lambda x: -x[2]):
            a_display = name_a[:28].ljust(28)
            b_display = name_b[:28].ljust(28)
            flag = " ⚠ OVERLAP" if sim > 0.70 else ""
            print(f"    {a_display}  {b_display}  {sim:.3f}{flag}")


# ── Final Report ────────────────────────────────────────────────────────────

def display_final_report(
    metrics: Dict[str, Any],
    decision_log_summary: Optional[Dict[str, int]] = None,
) -> None:
    """
    Display the complete final analysis report.

    Combines all 6 metrics + audit trail summary.
    """
    print(f"\n{'#' * 70}")
    print(f"  EQD-AI FINAL ANALYSIS REPORT")
    print(f"{'#' * 70}")

    # Overview
    grounding = metrics.get("grounding", {})
    coverage = metrics.get("coverage", {})
    coherence = metrics.get("theme_coherence", {})
    distinctness = metrics.get("theme_distinctness", [])

    print(f"\n  SUMMARY")
    print(f"  {SECTION_SEP}")

    if grounding:
        print(f"  Grounding rate:     {grounding.get('grounding_rate', 0):.1%}")
    if coverage:
        print(f"  Segment coverage:   {coverage.get('coverage_rate', 0):.1%}")

    its_history = metrics.get("its_history", [])
    if its_history:
        final_its = its_history[-1]
        print(f"  Final ITS:          {final_its.its_value:.4f} (batch {final_its.batch_number})")
        print(f"  Final codebook:     {final_its.ics_before + final_its.new_ics_created} ICs")

    if coherence:
        avg_coh = sum(coherence.values()) / len(coherence) if coherence else 0
        print(f"  Avg theme coherence: {avg_coh:.3f} ({len(coherence)} themes)")

    if distinctness:
        overlapping = [(a, b, s) for a, b, s in distinctness if s > 0.70]
        print(f"  Theme pairs:        {len(distinctness)} total, {len(overlapping)} overlapping")

    # Detailed reports
    display_codebook_report(metrics)
    display_theme_report(metrics)

    # Decision log summary
    if decision_log_summary:
        print(f"\n  {SECTION_SEP}")
        print(f"  AUDIT TRAIL SUMMARY")
        for action, count in sorted(decision_log_summary.items()):
            print(f"    {action}: {count}")

    print(f"\n{'#' * 70}")
    print(f"  END OF REPORT")
    print(f"{'#' * 70}\n")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mini_bar(value: float, max_val: float = 1.0, width: int = 15) -> str:
    """Generate a mini ASCII bar chart."""
    if max_val <= 0:
        return " " * width
    ratio = min(value / max_val, 1.0)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)
