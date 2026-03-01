"""
EQD-AI Layer 1: Human-in-the-Loop Terminal Interface.

Pure functions — no class, no state. The orchestrator manages flow.

Displays IC candidates with context, LLM reasoning, and collects
structured decisions from the human analyst.

Structured choices are the primary input:
  [N] New  [M] Merge  [R] Reject  [E] Edit  [Q] Quit

All decisions are logged with timestamp, LLM recommendation, and human notes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.embeddings import SimilarityResult
from src.models import BatchITS, ComparatorOutput, ICCandidate


# ── Display Constants ────────────────────────────────────────────────────────

SEPARATOR = "=" * 70
THIN_SEP = "-" * 70


def _sentence_context(text: str, start: int, end: int) -> tuple[str, str]:
    """
    Return the one sentence immediately before and after the span [start:end].

    Sentence boundary detection: scan backward from `start` for the nearest
    sentence-ending punctuation (.!?), then forward from `end` for the next one.
    Falls back to the full remaining text if no boundary is found.

    Returns (before, after) as strings, each stripped of leading/trailing
    whitespace. Either may be empty if the span is at the very start or end.
    """
    # ── Before: scan left from start for previous sentence end ──────────────
    sentence_endings = {'.', '!', '?'}
    before = ""
    if start > 0:
        # Find the sentence-end punctuation just before our span
        boundary = -1
        for i in range(start - 1, -1, -1):
            if text[i] in sentence_endings:
                boundary = i
                break
        # The "before" sentence starts after that punctuation (or at text[0])
        before_start = boundary + 1 if boundary >= 0 else 0
        before = text[before_start:start].strip()

    # ── After: scan right from end for next sentence end ────────────────────
    after = ""
    if end < len(text):
        boundary = len(text)
        for i in range(end, len(text)):
            if text[i] in sentence_endings:
                boundary = i + 1  # include the punctuation
                break
        after = text[end:boundary].strip()

    return before, after


# ── Display Functions ────────────────────────────────────────────────────────

def display_batch_header(
    batch_num: int,
    total_batches: int,
    codebook_size: int,
    new_candidates: int,
) -> None:
    """Print batch header with progress info."""
    print(f"\n{SEPARATOR}")
    print(f"  BATCH {batch_num}/{total_batches}  |  Codebook: {codebook_size} codes  |  New candidates: {new_candidates}")
    print(SEPARATOR)


def display_candidate_review(
    candidate: ICCandidate,
    comparator_output: ComparatorOutput,
    top_k: List[SimilarityResult],
    segment_text: str,
    candidate_num: int,
    total_candidates: int,
) -> None:
    """
    Display a candidate for human review.

    Shows: name, definition, verbatim quote in context,
    top-K similar codes, LLM recommendation + reasoning.
    """
    print(f"\n{THIN_SEP}")
    print(f"  NEW IC CANDIDATE [{candidate_num}/{total_candidates}]")
    print(THIN_SEP)

    # Candidate info
    print(f"  Name:       {candidate.ic_name}")
    print(f"  Definition: {candidate.definition}")
    print(f"  Confidence: {candidate.confidence:.0%}")

    # Verbatim quote with ±1 sentence context
    start = candidate.span_start
    end = candidate.span_end
    quote = segment_text[start:end]
    before, after = _sentence_context(segment_text, start, end)

    ellipsis_before = "..." if before else ""
    ellipsis_after  = "..." if after else ""

    print(f"\n  Quote: {ellipsis_before}{before}[{quote}]{after}{ellipsis_after}")
    print(f"         span [{start}:{end}]")

    # Top-K similar codes
    if top_k:
        print(f"\n  SIMILAR EXISTING CODES:")
        for i, sim_result in enumerate(top_k, 1):
            print(f"    [{i}] {sim_result.ic_name}  (sim: {sim_result.similarity:.3f})")
    else:
        print(f"\n  SIMILAR EXISTING CODES: (none)")

    # LLM recommendation
    print(f"\n  LLM RECOMMENDATION: {comparator_output.recommendation.value}")
    print(f"  Reasoning: {comparator_output.reasoning}")
    if comparator_output.merge_target_name:
        print(f"  Merge target: {comparator_output.merge_target_name}")


def display_its_status(batch_its: BatchITS) -> None:
    """Print ITS status for the current batch."""
    print(f"\n  ITS: {batch_its.its_value:.4f}  "
          f"(new: {batch_its.new_ics_created}, codebook: {batch_its.ics_before})")
    if batch_its.consecutive_low > 0:
        print(f"  Low-ITS streak: {batch_its.consecutive_low} batch(es)")
    if batch_its.is_checkpoint:
        print(f"  *** SATURATION CHECKPOINT — codebook may be stable ***")


def display_batch_summary(
    batch_num: int,
    new_created: int,
    merged: int,
    rejected: int,
) -> None:
    """Print summary after a batch is processed."""
    print(f"\n  Batch {batch_num} done: "
          f"+{new_created} new, {merged} merged, {rejected} rejected")


# ── Input Functions ──────────────────────────────────────────────────────────

def prompt_decision(
    top_k: List[SimilarityResult],
) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Prompt the human for a decision on a candidate.

    Returns: (action, merge_target_index, notes)
      - action: one of N, M, S, R, E, Q
      - merge_target_index: 1-based index into top_k (only for M/S actions)
      - notes: optional free-text notes

    Validates input in a loop until a valid choice is given.
    """
    # Build valid merge targets
    merge_targets = list(range(1, len(top_k) + 1)) if top_k else []

    print(f"\n  Choose action:")
    print(f"    [N] Accept as NEW code")
    if merge_targets:
        targets_str = ",".join(str(t) for t in merge_targets)
        print(f"    [M{targets_str}] MERGE with similar code (e.g., M1)")
    print(f"    [R] REJECT candidate")
    print(f"    [E] EDIT candidate then decide")
    print(f"    [Q] QUIT batch review")

    while True:
        raw = input("\n  > ").strip().upper()

        if raw == "N":
            notes = _prompt_notes()
            return "N", None, notes

        elif raw == "R":
            notes = _prompt_notes()
            return "R", None, notes

        elif raw == "E":
            return "E", None, None

        elif raw == "Q":
            return "Q", None, None

        elif raw.startswith("M") and len(raw) > 1:
            try:
                idx = int(raw[1:])
                if idx in merge_targets:
                    target_name = top_k[idx - 1].ic_name
                    confirm = input(f"\n  → Merging into: [{idx}] {target_name}\n  Confirm? [Y/N]: ").strip().upper()
                    if confirm in ("Y", "YES"):
                        notes = _prompt_notes()
                        return "M", idx, notes
                    # else: fall back to action prompt silently
                    continue
            except ValueError:
                pass
            print(f"  Invalid merge target. Valid: {merge_targets}")

        elif raw == "M" and merge_targets:
            # Default to M1
            target_name = top_k[0].ic_name
            confirm = input(f"\n  → Merging into: [1] {target_name}\n  Confirm? [Y/N]: ").strip().upper()
            if confirm in ("Y", "YES"):
                notes = _prompt_notes()
                return "M", 1, notes

        else:
            valid = "N, M, R, E, Q" if merge_targets else "N, R, E, Q"
            print(f"  Invalid input. Valid choices: {valid}")


def prompt_saturation_checkpoint() -> bool:
    """
    Ask the human whether to continue processing after saturation signal.

    Returns True to continue, False to stop.
    """
    print(f"\n{SEPARATOR}")
    print("  SATURATION CHECKPOINT")
    print("  The codebook has stabilised (few new codes in recent batches).")
    print("  You can continue processing or stop here for codebook sign-off.")
    print(f"{SEPARATOR}")

    while True:
        raw = input("\n  Continue processing? [Y/N]: ").strip().upper()
        if raw in ("Y", "YES"):
            return True
        elif raw in ("N", "NO"):
            return False
        print("  Please enter Y or N.")


def prompt_edit_candidate(candidate: ICCandidate) -> ICCandidate:
    """
    Let the human edit a candidate's name and definition.

    Returns a modified copy. If the user presses Enter, keeps original value.
    """
    print(f"\n  Edit candidate (press Enter to keep current value):")

    new_name = input(f"  Name [{candidate.ic_name}]: ").strip()
    if not new_name:
        new_name = candidate.ic_name

    new_def = input(f"  Definition [{candidate.definition}]: ").strip()
    if not new_def:
        new_def = candidate.definition

    return ICCandidate(
        ic_name=new_name,
        definition=new_def,
        quote_text=candidate.quote_text,
        span_start=candidate.span_start,
        span_end=candidate.span_end,
        confidence=candidate.confidence,
        existing_code_match=None,  # Reset — human is deciding
    )


def _prompt_notes() -> Optional[str]:
    """Prompt for optional notes."""
    notes = input("  Notes (Enter to skip): ").strip()
    return notes if notes else None


# ── Meta-IC Filtering Display ─────────────────────────────────────────────────

def display_meta_commentary_warning(candidate: ICCandidate, reason: str) -> None:
    """Display a warning when a candidate is detected as meta-commentary."""
    print(f"\n  ⚠ META-COMMENTARY DETECTED: {reason}")
    print(f"    '{candidate.ic_name}' may be a verdict/meta-comment rather")
    print(f"    than a specific product experience code. Consider rejecting.")


# ── Post-Synthesis Coherence Gate Display ─────────────────────────────────────

def display_flagged_theme(flagged_data: Dict[str, Any]) -> None:
    """Display a warning for a low-coherence theme."""
    print(f"\n  ⚠ LOW COHERENCE: '{flagged_data['theme_name']}'")
    print(f"    Normalized: {flagged_data['normalized']:.3f} (threshold: {flagged_data.get('threshold', 1.0)})")
    print(f"    Raw: {flagged_data['raw']:.3f}  |  ICs: {flagged_data['ic_count']}")
    print(f"    This theme's ICs are less similar than a random grouping.")


def prompt_theme_dissolve() -> bool:
    """Ask the human whether to dissolve a low-coherence theme."""
    while True:
        raw = input("    Dissolve this theme? [Y/N]: ").strip().upper()
        if raw in ("Y", "YES"):
            return True
        if raw in ("N", "NO"):
            return False
        print("    Please enter Y or N.")


# ── Category Agent Sign-Off ───────────────────────────────────────────────────

def prompt_category_signoff(
    proposals: List[Any],
    themes_data: List[Dict[str, Any]],
) -> bool:
    """
    Display proposed categories and ask the analyst to approve or skip.

    Called after CategoryAgent._validate_proposals() and before persist().
    If HIL is disabled, callers auto-approve without calling this function.

    Returns True to persist categories, False to skip (no categories stored
    this run — analyst must re-run category synthesis manually).

    Args:
        proposals: list of CategoryProposal objects (name, definition,
                   constituent_theme_names).
        themes_data: list of theme dicts used to show per-theme IC counts.
    """
    # Build a quick lookup: theme name → ic_count
    theme_ic_counts = {t["name"]: t.get("ic_count", 0) for t in themes_data}

    print(f"\n{SEPARATOR}")
    print("  CATEGORY SIGN-OFF")
    print(f"  {len(proposals)} categor{'y' if len(proposals) == 1 else 'ies'} proposed")
    print(f"{SEPARATOR}")

    for i, proposal in enumerate(proposals, 1):
        print(f"\n  [{i}] {proposal.name}")
        print(f"      {proposal.definition[:120]}")
        theme_names = proposal.constituent_theme_names
        total_ics = sum(theme_ic_counts.get(t, 0) for t in theme_names)
        print(f"      Themes ({len(theme_names)}, {total_ics} ICs total):")
        for t in theme_names:
            ic_n = theme_ic_counts.get(t, 0)
            print(f"        · {t} ({ic_n} IC{'s' if ic_n != 1 else ''})")

    print(f"\n{SEPARATOR}")
    print("  [A] Approve — persist these categories to the database")
    print("  [S] Skip    — do not persist; re-run later")
    print(f"{SEPARATOR}")

    while True:
        raw = input("\n  > ").strip().upper()
        if raw in ("A", "APPROVE", "Y", "YES"):
            return True
        if raw in ("S", "SKIP", "N", "NO"):
            print("  Categories skipped. Re-run pipeline to re-synthesise.")
            return False
        print("  Please enter A (approve) or S (skip).")
