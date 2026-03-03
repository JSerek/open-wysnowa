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

    # Coder Confidence
    conf = metrics.get("coder_confidence", {})
    if conf and conf.get("mean_confidence") is not None:
        print(f"\n  {SECTION_SEP}")
        print(f"  CODER CONFIDENCE")
        mean_c = conf["mean_confidence"]
        sd_c   = conf.get("sd_confidence", 0.0)
        q1_c   = conf.get("q1_confidence")
        q2_c   = conf.get("q2_confidence")
        q3_c   = conf.get("q3_confidence")
        iqr_c  = conf.get("iqr_confidence", 0.0)
        low_n  = conf.get("low_confidence_count", 0)
        total_n = conf.get("total_new_ics", 0)
        low_ratio = conf.get("low_confidence_ratio", 0.0)
        label = "high" if mean_c >= 0.8 else "moderate" if mean_c >= 0.6 else "LOW ⚠"
        print(f"    mean={mean_c:.2f} ({label})  sd={sd_c:.2f}")
        if q1_c is not None:
            print(f"    Q1={q1_c:.2f}  Q2={q2_c:.2f}  Q3={q3_c:.2f}  IQR={iqr_c:.2f}")
        print(f"    range=[{conf.get('min_confidence', 0):.2f}, {conf.get('max_confidence', 0):.2f}]  n={total_n}")
        if low_n:
            flag = " ⚠ review these ICs" if low_ratio > 0.20 else ""
            print(f"    low-confidence (<0.6): {low_n}/{total_n} ({low_ratio:.0%}){flag}")
        else:
            print(f"    low-confidence (<0.6): none")

    # Coder Reuse Rate (2×2 matrix)
    reuse = metrics.get("coder_reuse", {})
    if reuse:
        flagged  = reuse.get("flagged_match", 0)
        new_new  = reuse.get("new_comp_new", 0)
        new_mrg  = reuse.get("new_comp_merge", 0)
        new_rej  = reuse.get("new_comp_reject", 0)
        total_new_path = new_new + new_mrg + new_rej
        total = flagged + total_new_path
        if total > 0:
            print(f"\n  {SECTION_SEP}")
            print(f"  CODER REUSE RATE")
            print(f"    Coder flagged existing (bypass comparator):  {flagged:4d}  ({flagged/total:.0%})")
            print(f"    Coder said NEW → comparator NEW:             {new_new:4d}  ({new_new/total:.0%})")
            print(f"    Coder said NEW → comparator MERGE:           {new_mrg:4d}  ({new_mrg/total:.0%})")
            print(f"    Coder said NEW → comparator REJECT:          {new_rej:4d}  ({new_rej/total:.0%})")
            if total_new_path > 0:
                flip_rate = (new_mrg + new_rej) / total_new_path
                flag = " ⚠ coder over-generates" if flip_rate > 0.40 else ""
                print(f"    Comparator flip rate (merge+reject / new-path): {flip_rate:.0%}{flag}")

    # Quote Coverage Per IC
    qcov = metrics.get("quote_coverage", {})
    per_ic_cov = qcov.get("per_ic", [])
    if per_ic_cov:
        print(f"\n  {SECTION_SEP}")
        print(f"  QUOTE COVERAGE PER IC")
        overall_mean = qcov.get("overall_mean_pct", qcov.get("overall_mean", 0.0))
        overall_max  = qcov.get("overall_max_pct",  qcov.get("overall_max",  0.0))
        high_count   = qcov.get("high_coverage_count", 0)
        total_pairs  = qcov.get("total_ic_segment_pairs", 0)
        flag_summary = f"  ⚠ {high_count} pairs >70%" if high_count > 0 else ""
        print(f"    overall: mean={overall_mean:.1f}%  max={overall_max:.1f}%  "
              f"pairs={total_pairs}{flag_summary}")
        # Show only ICs with at least one high-coverage segment, or top-5 by max
        flagged_ics = [ic for ic in per_ic_cov if ic["high_coverage_segments"] > 0]
        show_ics = flagged_ics if flagged_ics else per_ic_cov[:5]
        if flagged_ics:
            print(f"    ICs with high-coverage evidence (>70% of segment):")
        else:
            print(f"    Top ICs by max coverage:")
        for ic in show_ics:
            high_flag = f"  ⚠ {ic['high_coverage_segments']} seg >70%" if ic["high_coverage_segments"] > 0 else ""
            name = ic["ic_name"][:42].ljust(42)
            print(f"      {name}  mean={ic['mean_coverage']:.0%}  max={ic['max_coverage']:.0%}{high_flag}")

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

# ── Layer 4: Analytical Brief ──────────────────────────────────────────────

def display_analytical_brief(brief: Dict[str, Any]) -> None:
    """
    Display the Layer 4 analytical interpretation in the terminal.

    Args:
        brief: AnalyticalBrief.model_dump() dict with metrics, structure, synthesis.
    """
    print(f"\n{SEPARATOR}")
    print(f"  LAYER 4: ANALYTICAL INTERPRETATION")
    print(SEPARATOR)

    # ── Metrics Assessment ──
    metrics = brief.get("metrics", {})
    assessments = metrics.get("assessments", [])
    if assessments:
        print(f"\n  {SECTION_SEP}")
        print(f"  METRICS ASSESSMENT")
        status_emoji = {"healthy": "🟢", "monitor": "🟡", "investigate": "🔴"}
        for a in assessments:
            status = a.get("status", "?")
            emoji = status_emoji.get(status, "⚪")
            print(f"\n    {emoji} {a.get('metric_name', '?')}: {a.get('observed_value', '?')}")
            print(f"      {a.get('interpretation', '')}")
            ctx = a.get("context_factors")
            if ctx:
                print(f"      Context: {ctx}")

    # ── Data Quality Summary ──
    dqs = metrics.get("data_quality_summary", "")
    if dqs:
        print(f"\n  {SECTION_SEP}")
        print(f"  DATA QUALITY SUMMARY")
        _print_wrapped(dqs, indent=4)

    # ── Saturation ──
    sat = metrics.get("saturation_assessment", "")
    if sat:
        print(f"\n  {SECTION_SEP}")
        print(f"  SATURATION ASSESSMENT")
        _print_wrapped(sat, indent=4)

    # ── Thematic Structure ──
    structure = brief.get("structure", {})
    strongest = structure.get("strongest_themes", [])
    weakest = structure.get("weakest_themes", [])
    if strongest or weakest:
        print(f"\n  {SECTION_SEP}")
        print(f"  THEMATIC STRUCTURE")
        if strongest:
            print(f"    Strongest: {', '.join(strongest)}")
        if weakest:
            print(f"    Weakest:   {', '.join(weakest)}")

    # Per-theme diagnostics
    theme_diags = structure.get("theme_diagnostics", [])
    if theme_diags:
        print()
        for td in theme_diags:
            issue = td.get("issue_type", "healthy")
            label = f" [{issue.upper()}]" if issue != "healthy" else ""
            print(f"    {td.get('theme_name', '?')} ({td.get('ic_count', 0)} ICs){label}")
            print(f"      {td.get('assessment', '')}")
            action = td.get("suggested_action")
            if action:
                print(f"      Action: {action}")

    # Structural summary
    ss = structure.get("structural_summary", "")
    if ss:
        print(f"\n    Summary: {ss}")

    # ── Overall Assessment ──
    synthesis = brief.get("synthesis", {})
    overall = synthesis.get("overall_assessment", "")
    if overall:
        print(f"\n  {SECTION_SEP}")
        print(f"  OVERALL ASSESSMENT")
        _print_wrapped(overall, indent=4)

    # ── Key Findings ──
    findings = synthesis.get("key_findings", [])
    if findings:
        print(f"\n  {SECTION_SEP}")
        print(f"  KEY FINDINGS")
        for i, f in enumerate(findings, 1):
            print(f"    {i}. {f}")

    # ── Recommendations ──
    config_recs = synthesis.get("config_recommendations", [])
    if config_recs:
        print(f"\n  {SECTION_SEP}")
        print(f"  CONFIG RECOMMENDATIONS")
        for rec in config_recs:
            print(
                f"    {rec.get('parameter', '?')}: "
                f"{rec.get('current_value', '?')} -> {rec.get('suggested_value', '?')}"
            )
            print(f"      {rec.get('rationale', '')}")

    next_steps = synthesis.get("next_steps", [])
    if next_steps:
        print(f"\n  NEXT STEPS")
        for i, step in enumerate(next_steps, 1):
            print(f"    {i}. {step}")

    # ── Confidence Note ──
    confidence = synthesis.get("confidence_note", "")
    if confidence:
        print(f"\n  {SECTION_SEP}")
        print(f"  CONFIDENCE NOTE")
        _print_wrapped(confidence, indent=4)

    print(f"\n{SEPARATOR}")


def _print_wrapped(text: str, indent: int = 4, width: int = 80) -> None:
    """Print text with indentation, wrapping long lines."""
    prefix = " " * indent
    words = text.split()
    line = prefix
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(line)
            line = prefix + word
        else:
            if line == prefix:
                line += word
            else:
                line += " " + word
    if line.strip():
        print(line)


def _mini_bar(value: float, max_val: float = 1.0, width: int = 15) -> str:
    """Generate a mini ASCII bar chart."""
    if max_val <= 0:
        return " " * width
    ratio = min(value / max_val, 1.0)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)
