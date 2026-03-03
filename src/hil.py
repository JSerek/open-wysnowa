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

REASONING_PREVIEW = 200   # chars shown before truncation hint
DEFINITION_PREVIEW = 85   # chars shown per top-K IC in candidate display
CONTEXT_WINDOW = 130      # chars of surrounding context shown before/after quote


# ── Display Constants ────────────────────────────────────────────────────────

SEPARATOR = "=" * 70
THIN_SEP = "-" * 70
QUOTE_SEP = "  " + "─" * 66


def _fixed_context(text: str, start: int, end: int, window: int = CONTEXT_WINDOW) -> tuple[str, str]:
    """
    Return up to `window` characters immediately before and after [start:end].

    Newlines and tabs are collapsed to single spaces so numbered lists,
    bullet points, and informal UGC don't bleed across display lines.

    Word-boundary snapping: if the window cuts mid-word, trim to the nearest
    space so the context reads cleanly.

    Pass window=len(text) (or any large int) to show the full segment text.

    Returns (before, after) as strings, stripped. Either may be empty.
    """
    import re

    def _collapse(s: str) -> str:
        return re.sub(r"[\r\n\t]+", " ", s).strip()

    before = ""
    if start > 0:
        raw_before = text[max(0, start - window):start]
        collapsed = _collapse(raw_before)
        # If we couldn't show from position 0, snap to first word boundary
        if start - window > 0 and " " in collapsed:
            collapsed = collapsed[collapsed.index(" ") + 1:]
        before = collapsed

    after = ""
    if end < len(text):
        raw_after = text[end:min(len(text), end + window)]
        collapsed = _collapse(raw_after)
        # If we couldn't show to end, snap to last word boundary
        if end + window < len(text) and " " in collapsed:
            collapsed = collapsed[:collapsed.rindex(" ")]
        after = collapsed

    return before, after


# ── Display Functions ────────────────────────────────────────────────────────

def display_batch_header(
    batch_num: int,
    total_batches: int,
    codebook_size: int,
    new_candidates: int,
    its_value: Optional[float] = None,
    session_new: int = 0,
    session_merged: int = 0,
    session_rejected: int = 0,
) -> None:
    """Print batch header with progress, codebook size, ITS, and session totals."""
    print(f"\n{SEPARATOR}")
    its_str = f"  |  ITS: {its_value:.3f}" if its_value is not None else ""
    print(f"  BATCH {batch_num}/{total_batches}  |  Codebook: {codebook_size} ICs{its_str}  |  Candidates: {new_candidates}")
    if batch_num > 1:
        print(f"  Session so far:  +{session_new} new  ↔ {session_merged} merged  ✗ {session_rejected} rejected")
    print(SEPARATOR)


def display_candidate_review(
    candidate: ICCandidate,
    comparator_output: ComparatorOutput,
    top_k: List[SimilarityResult],
    segment_text: str,
    candidate_num: int,
    total_candidates: int,
    segment_id: str = "",
    ic_definitions: Optional[Dict[str, str]] = None,
    context_window: int = CONTEXT_WINDOW,
) -> None:
    """
    Display a candidate for human review.

    Shows: name, definition, verbatim quote in context,
    top-K similar codes with truncated definitions,
    LLM recommendation + reasoning (truncated, expandable via ?).

    context_window controls how many chars of surrounding text are shown.
    Pass len(segment_text) to show the full segment. Analyst can expand
    interactively via the [C] / [C N] command in prompt_decision.
    """
    ic_definitions = ic_definitions or {}

    print(f"\n{THIN_SEP}")
    seg_label = f"  seg: {segment_id}" if segment_id else ""
    print(f"  NEW IC CANDIDATE [{candidate_num}/{total_candidates}]{seg_label}")
    print(THIN_SEP)

    # Candidate info
    print(f"  Name:       {candidate.ic_name}")
    print(f"  Definition: {candidate.definition}")
    print(f"  Confidence: {candidate.confidence:.0%}")

    # Verbatim quote with surrounding context + coverage
    start = candidate.span_start
    end = candidate.span_end
    seg_len = len(segment_text)
    quote = segment_text[start:end]
    quote_len = end - start
    coverage_pct = quote_len / seg_len * 100 if seg_len > 0 else 0.0
    coverage_flag = "  ⚠ high" if coverage_pct > 70 else ""
    before, after = _fixed_context(segment_text, start, end, window=context_window)

    ellipsis_before = "..." if (before and max(0, start - context_window) > 0) else ""
    ellipsis_after  = "..." if (after and end + context_window < seg_len) else ""
    window_label = "" if context_window == CONTEXT_WINDOW else f"  [ctx: {context_window} chars]"

    print(f"\n{QUOTE_SEP}")
    print(f"  {ellipsis_before}{before}[{quote}]{after}{ellipsis_after}")
    print(f"{QUOTE_SEP}")
    print(f"  Span:     [{start}:{end}]{window_label}")
    print(f"  Coverage: {coverage_pct:.0f}%  ({quote_len} of {seg_len} chars){coverage_flag}")

    # Top-K similar codes with truncated definitions
    if top_k:
        print(f"\n  SIMILAR EXISTING CODES:")
        for i, sim_result in enumerate(top_k, 1):
            print(f"    [{i}] {sim_result.ic_name}  (sim: {sim_result.similarity:.3f})")
            defn = ic_definitions.get(sim_result.ic_id, "")
            if defn:
                preview = defn[:DEFINITION_PREVIEW] + "…" if len(defn) > DEFINITION_PREVIEW else defn
                print(f"         {preview}")
    else:
        print(f"\n  SIMILAR EXISTING CODES: (none)")

    # LLM recommendation + truncated reasoning
    reasoning = comparator_output.reasoning or ""
    truncated = len(reasoning) > REASONING_PREVIEW
    reasoning_preview = reasoning[:REASONING_PREVIEW] + "…" if truncated else reasoning
    print(f"\n  LLM RECOMMENDATION: {comparator_output.recommendation.value}")
    print(f"  Reasoning: {reasoning_preview}")
    if truncated:
        print(f"  (type ? to expand reasoning + full IC definitions)")
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
    full_reasoning: str = "",
    ic_definitions: Optional[Dict[str, str]] = None,
    can_undo: bool = False,
    last_decision_desc: str = "",
    current_context_window: int = CONTEXT_WINDOW,
) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Prompt the human for a decision on a candidate.

    Returns: (action, merge_target_index_or_context_window, notes)
      - action: one of N, M, R, E, Q, U, C
      - merge_target_index: 1-based index into top_k (only for M actions)
      - For C action: second element is the requested context window (int),
        or None meaning "show full segment"
      - notes: optional free-text notes

    Validates input in a loop until a valid choice is given.
    """
    ic_definitions = ic_definitions or {}
    merge_targets = list(range(1, len(top_k) + 1)) if top_k else []

    ctx_hint = "full" if current_context_window >= 10_000 else f"{current_context_window} chars"
    print(f"\n  Choose action:")
    print(f"    [N] Accept as NEW code")
    if merge_targets:
        targets_str = ",".join(str(t) for t in merge_targets)
        print(f"    [M{targets_str}] MERGE with similar code (e.g., M1)")
    print(f"    [R] REJECT candidate")
    print(f"    [E] EDIT candidate then decide")
    if can_undo:
        print(f"    [U] UNDO last decision  ({last_decision_desc})")
    print(f"    [?] Expand: full reasoning + IC definitions")
    print(f"    [C] Expand context (currently: {ctx_hint})  e.g., C, C 300, C full")
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

        elif raw == "U":
            if can_undo:
                return "U", None, None
            print("  Nothing to undo.")

        elif raw == "C" or raw.startswith("C "):
            # Expand context window: C → full segment, C N → N chars
            parts = raw.split()
            if len(parts) == 1:
                # bare C → full segment (large sentinel)
                return "C", None, None
            token = parts[1]
            if token in ("FULL", "ALL"):
                return "C", None, None
            try:
                n = int(token)
                if n < 1:
                    raise ValueError
                return "C", n, None
            except ValueError:
                print(f"  Usage: C  (full segment)  or  C 300  (300 chars each side)")

        elif raw == "?":
            # Expand: show full reasoning + all top-K full definitions
            if full_reasoning:
                print(f"\n  FULL REASONING:\n  {full_reasoning}")
            if top_k and ic_definitions:
                print(f"\n  FULL IC DEFINITIONS:")
                for i, sim_result in enumerate(top_k, 1):
                    defn = ic_definitions.get(sim_result.ic_id, "(not found)")
                    print(f"    [{i}] {sim_result.ic_name}  (sim: {sim_result.similarity:.3f})")
                    print(f"         {defn}")
            # Re-print the action menu after expanding
            print(f"\n  Choose action:")
            print(f"    [N] Accept as NEW code")
            if merge_targets:
                targets_str = ",".join(str(t) for t in merge_targets)
                print(f"    [M{targets_str}] MERGE (e.g., M1)")
            print(f"    [R] REJECT  [E] EDIT  [Q] QUIT")
            if can_undo:
                print(f"    [U] UNDO  ({last_decision_desc})")

        elif raw.startswith("M") and len(raw) > 1:
            try:
                idx = int(raw[1:])
                if idx in merge_targets:
                    target_name = top_k[idx - 1].ic_name
                    confirm = input(f"\n  → Merging into: [{idx}] {target_name}\n  Confirm? [Y/N]: ").strip().upper()
                    if confirm in ("Y", "YES"):
                        notes = _prompt_notes()
                        return "M", idx, notes
                    continue
            except ValueError:
                pass
            print(f"  Invalid merge target. Valid: {merge_targets}")

        elif raw == "M" and merge_targets:
            target_name = top_k[0].ic_name
            confirm = input(f"\n  → Merging into: [1] {target_name}\n  Confirm? [Y/N]: ").strip().upper()
            if confirm in ("Y", "YES"):
                notes = _prompt_notes()
                return "M", 1, notes

        else:
            valid = "N, M, R, E, U, C, ?, Q" if merge_targets else "N, R, E, U, C, ?, Q"
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
