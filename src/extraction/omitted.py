"""
EQD-AI Layer 1 Pass 2 — omitted-text view builder.

After pass 1, each review has a set of accepted quote spans. To audit what the
first pass left behind, we re-present the *whole* review to the model with every
NOT-extracted fragment wrapped in `<omitted>...</omitted>` tags; the extracted
fragments are shown as plain text (the model sees exactly what it already took).

Design decisions (v2 contract / plan 2.2):
  - Boundaries are taken STRICTLY from the pass-1 spans. A tag may fall in the
    middle of a sentence — that is accepted (deterministic and faithful to the
    spans, no sentence re-segmentation).
  - The complement of the union of pass-1 spans is wrapped; overlapping/adjacent
    spans are merged first so no empty `<omitted></omitted>` tags are produced.
  - Pure function — no I/O, no model calls — so it is trivially testable.
"""

from __future__ import annotations

from typing import List, Tuple

OMITTED_OPEN = "<omitted>"
OMITTED_CLOSE = "</omitted>"


def _merge_spans(
    spans: List[Tuple[int, int]], text_len: int
) -> List[Tuple[int, int]]:
    """
    Clamp spans to [0, text_len], drop empty/invalid ones, and merge any
    overlapping or adjacent intervals into a minimal sorted list.

    Adjacent spans (start == prev_end) are merged too: there is no gap between
    them, so keeping them separate would only risk a zero-width omitted region.
    """
    cleaned: List[Tuple[int, int]] = []
    for start, end in spans:
        s = max(0, min(start, text_len))
        e = max(0, min(end, text_len))
        if e > s:
            cleaned.append((s, e))

    if not cleaned:
        return []

    cleaned.sort(key=lambda x: x[0])
    merged: List[Tuple[int, int]] = [cleaned[0]]
    for start, end in cleaned[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:  # overlap OR adjacency → extend
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def build_omitted_view(
    canonical_text: str, pass1_spans: List[Tuple[int, int]]
) -> str:
    """
    Build the pass-2 view of a review: extracted fragments as plain text, every
    un-extracted fragment wrapped in `<omitted>...</omitted>`.

    Args:
        canonical_text: the full review text (the segment's canonical_text).
        pass1_spans: accepted quote spans from pass 1 as (start, end) tuples
            (half-open, end exclusive), referencing canonical_text.

    Returns:
        A string view of the whole review. With no pass-1 spans the entire text
        is a single omitted block; with full coverage there are no omitted tags.
    """
    n = len(canonical_text)
    if n == 0:
        return ""

    merged = _merge_spans(pass1_spans, n)

    parts: List[str] = []
    cursor = 0
    for start, end in merged:
        if cursor < start:  # gap before this extracted span → omitted
            parts.append(OMITTED_OPEN + canonical_text[cursor:start] + OMITTED_CLOSE)
        parts.append(canonical_text[start:end])  # extracted → plain text
        cursor = end

    if cursor < n:  # trailing gap → omitted
        parts.append(OMITTED_OPEN + canonical_text[cursor:n] + OMITTED_CLOSE)

    return "".join(parts)
