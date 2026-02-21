"""
EQD-AI Layer 2: Theme Human-in-the-Loop (HIL Level 3).

Structured theme feedback interface with 7 options.
Pure functions — the pipeline manages the iteration loop (max 3 rounds).

Feedback options:
  1=SPLIT  2=MERGE  3=IC_MISASSIGNED  4=RENAME
  5=REDEFINE  6=OVERLAP_CONFLICT  7=FREETEXT
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.models import ThemeFeedback, ThemeFeedbackOption, ThemeProposal

# ── Display Constants ────────────────────────────────────────────────────────

SEPARATOR = "=" * 70
THIN_SEP = "-" * 70


# ── Display Functions ────────────────────────────────────────────────────────

def display_theme_proposal(
    theme: ThemeProposal,
    theme_num: int,
    total_themes: int,
    ic_quote_counts: Dict[str, int],
    coherence_score: Optional[float] = None,
) -> None:
    """
    Display a single theme proposal for review.

    Args:
        theme: the ThemeProposal to display
        theme_num: 1-indexed position
        total_themes: total number of themes
        ic_quote_counts: {ic_name: quote_count} for evidence display
        coherence_score: optional pre-computed coherence (from quality metrics)
    """
    print(f"\n{THIN_SEP}")
    print(f"  THEME [{theme_num}/{total_themes}]: {theme.name}")
    print(THIN_SEP)

    print(f"  Definition: {theme.definition}")
    print(f"  Rationale:  {theme.rationale}")

    if coherence_score is not None:
        label = "high" if coherence_score > 0.7 else "moderate" if coherence_score > 0.4 else "low"
        print(f"  Coherence:  {coherence_score:.3f} ({label})")

    print(f"\n  Constituent ICs ({len(theme.constituent_ic_names)}):")
    for i, ic_name in enumerate(theme.constituent_ic_names, 1):
        qcount = ic_quote_counts.get(ic_name, 0)
        print(f"    [{i}] {ic_name}  ({qcount} quotes)")


def display_all_themes(
    themes: List[ThemeProposal],
    ic_quote_counts: Dict[str, int],
    coherence_scores: Optional[Dict[str, float]] = None,
    distinctness_warnings: Optional[List[Tuple[str, str, float]]] = None,
) -> None:
    """
    Display overview of all themes with optional quality signals.

    Args:
        themes: all current theme proposals
        ic_quote_counts: {ic_name: quote_count}
        coherence_scores: {theme_name: coherence} optional
        distinctness_warnings: list of (theme_a, theme_b, similarity) for overlapping pairs
    """
    print(f"\n{SEPARATOR}")
    print(f"  THEME REVIEW — {len(themes)} theme(s) proposed")
    print(SEPARATOR)

    for i, theme in enumerate(themes, 1):
        coh = coherence_scores.get(theme.name) if coherence_scores else None
        total_quotes = sum(
            ic_quote_counts.get(ic_name, 0)
            for ic_name in theme.constituent_ic_names
        )
        coh_str = f"  coh={coh:.2f}" if coh is not None else ""
        print(
            f"  [{i}] {theme.name}  "
            f"({len(theme.constituent_ic_names)} ICs, {total_quotes} quotes{coh_str})"
        )

    # Check for unassigned ICs
    all_assigned = set()
    for theme in themes:
        all_assigned.update(theme.constituent_ic_names)
    unassigned = [
        name for name in ic_quote_counts.keys()
        if name not in all_assigned
    ]
    if unassigned:
        print(f"\n  ⚠ {len(unassigned)} IC(s) not assigned to any theme:")
        for name in unassigned:
            print(f"    - {name}")

    # Distinctness warnings
    if distinctness_warnings:
        print(f"\n  ⚠ Overlapping theme pairs (similarity > 0.70):")
        for t_a, t_b, sim in distinctness_warnings:
            print(f"    - \"{t_a}\" ↔ \"{t_b}\" (sim={sim:.3f})")


def display_revision_diff(
    old_themes: List[ThemeProposal],
    new_themes: List[ThemeProposal],
) -> None:
    """Show what changed between revision rounds."""
    old_names = {t.name for t in old_themes}
    new_names = {t.name for t in new_themes}

    added = new_names - old_names
    removed = old_names - new_names
    kept = old_names & new_names

    print(f"\n{THIN_SEP}")
    print(f"  REVISION DIFF")
    print(THIN_SEP)

    if added:
        print(f"  + Added: {', '.join(added)}")
    if removed:
        print(f"  - Removed: {', '.join(removed)}")
    if kept:
        # Check for IC changes in kept themes
        old_map = {t.name: set(t.constituent_ic_names) for t in old_themes}
        new_map = {t.name: set(t.constituent_ic_names) for t in new_themes}
        for name in kept:
            ics_added = new_map.get(name, set()) - old_map.get(name, set())
            ics_removed = old_map.get(name, set()) - new_map.get(name, set())
            if ics_added or ics_removed:
                print(f"  ~ \"{name}\": ", end="")
                parts = []
                if ics_added:
                    parts.append(f"+{len(ics_added)} ICs")
                if ics_removed:
                    parts.append(f"-{len(ics_removed)} ICs")
                print(", ".join(parts))

    if not added and not removed:
        print("  No structural changes (names may have been updated)")

    print(f"  Total: {len(old_themes)} → {len(new_themes)} themes")


# ── Input Functions ──────────────────────────────────────────────────────────

def prompt_theme_feedback(
    theme: ThemeProposal,
    theme_num: int,
    all_theme_names: List[str],
) -> Optional[ThemeFeedback]:
    """
    Collect structured feedback for a single theme.

    Returns ThemeFeedback or None if no feedback (skip).
    """
    print(f"\n  Feedback for theme [{theme_num}] \"{theme.name}\":")
    print(f"    [1] SPLIT — too broad, split into sub-themes")
    print(f"    [2] MERGE — too narrow, merge with another theme")
    print(f"    [3] IC_MISASSIGNED — move an IC to a different theme")
    print(f"    [4] RENAME — suggest a new name")
    print(f"    [5] REDEFINE — suggest a revised definition")
    print(f"    [6] OVERLAP_CONFLICT — flag overlap with another theme")
    print(f"    [7] FREETEXT — other feedback")
    print(f"    [Enter] Skip — no feedback for this theme")

    while True:
        raw = input("\n  > ").strip()

        if not raw:
            return None  # Skip

        if raw not in ("1", "2", "3", "4", "5", "6", "7"):
            print("  Enter 1-7 or press Enter to skip.")
            continue

        option = ThemeFeedbackOption(raw)
        details = _collect_feedback_details(option, theme, all_theme_names)

        return ThemeFeedback(
            theme_name=theme.name,
            option=option,
            details=details,
        )


def _collect_feedback_details(
    option: ThemeFeedbackOption,
    theme: ThemeProposal,
    all_theme_names: List[str],
) -> Optional[str]:
    """Collect option-specific details for the feedback."""

    if option == ThemeFeedbackOption.SPLIT:
        names = input("  Provisional sub-theme names (comma-separated, or Enter to skip): ").strip()
        return names if names else None

    elif option == ThemeFeedbackOption.MERGE:
        print("  Available themes to merge with:")
        others = [n for n in all_theme_names if n != theme.name]
        for i, name in enumerate(others, 1):
            print(f"    [{i}] {name}")
        raw = input("  Target theme number: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(others):
                return others[idx]
        except (ValueError, IndexError):
            pass
        return input("  Target theme name: ").strip() or None

    elif option == ThemeFeedbackOption.IC_MISASSIGNED:
        print(f"  ICs in this theme:")
        for i, ic_name in enumerate(theme.constituent_ic_names, 1):
            print(f"    [{i}] {ic_name}")
        ic_raw = input("  IC to move (number): ").strip()
        target = input("  Move to which theme: ").strip()
        try:
            ic_idx = int(ic_raw) - 1
            if 0 <= ic_idx < len(theme.constituent_ic_names):
                return f"{theme.constituent_ic_names[ic_idx]} -> {target}"
        except (ValueError, IndexError):
            pass
        return None

    elif option == ThemeFeedbackOption.RENAME:
        new_name = input("  New name: ").strip()
        return new_name if new_name else None

    elif option == ThemeFeedbackOption.REDEFINE:
        new_def = input("  New definition: ").strip()
        return new_def if new_def else None

    elif option == ThemeFeedbackOption.OVERLAP_CONFLICT:
        print("  Which theme overlaps?")
        others = [n for n in all_theme_names if n != theme.name]
        for i, name in enumerate(others, 1):
            print(f"    [{i}] {name}")
        raw = input("  Theme number: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(others):
                return others[idx]
        except (ValueError, IndexError):
            pass
        return input("  Theme name: ").strip() or None

    elif option == ThemeFeedbackOption.FREETEXT:
        text = input("  Your feedback: ").strip()
        return text if text else None

    return None


def collect_all_feedback(
    themes: List[ThemeProposal],
    ic_quote_counts: Dict[str, int],
    coherence_scores: Optional[Dict[str, float]] = None,
) -> List[ThemeFeedback]:
    """
    Iterate over all themes and collect feedback from the analyst.

    Displays each theme in detail, then prompts for feedback.
    Returns list of ThemeFeedback (may be empty if all skipped).
    """
    all_theme_names = [t.name for t in themes]
    feedback_list: List[ThemeFeedback] = []

    for i, theme in enumerate(themes, 1):
        display_theme_proposal(
            theme, i, len(themes), ic_quote_counts,
            coherence_scores.get(theme.name) if coherence_scores else None,
        )

        fb = prompt_theme_feedback(theme, i, all_theme_names)
        if fb:
            feedback_list.append(fb)

    return feedback_list


def prompt_signoff_themes() -> bool:
    """
    Ask whether to sign off on themes or continue iterating.

    Returns True if signed off, False to provide more feedback.
    """
    print(f"\n{SEPARATOR}")
    print("  THEME SIGN-OFF")
    print("  Accept these themes as final, or provide another round of feedback?")
    print(SEPARATOR)

    while True:
        raw = input("\n  [A] Accept themes  [F] More feedback: ").strip().upper()
        if raw in ("A", "ACCEPT"):
            return True
        elif raw in ("F", "FEEDBACK"):
            return False
        print("  Enter A or F.")
