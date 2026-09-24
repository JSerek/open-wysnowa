"""
EQD-AI Ground Truth Verification.

Deterministic checks — no LLM involved. Every verbatim quote must be
an exact substring of its segment's canonical_text at the claimed span.

This is the core quality gate: if canonical_text[span_start:span_end] != quote_text,
the quote is hallucinated or misaligned.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.core.db import Database, InitialCodeRepo, SegmentRepo, VerbatimQuoteRepo
from src.core.models import InitialCode, Segment, VerbatimQuote


# ── Single Quote Verification ────────────────────────────────────────────────

def verify_quote(quote: VerbatimQuote, canonical_text: str) -> bool:
    """
    Deterministic ground truth check for a single quote.

    Verifies: canonical_text[span_start:span_end] == quote_text

    Updates quote.is_verified in place.
    Returns True if verified, False if hallucinated/misaligned.
    """
    return quote.verify(canonical_text)


def attempt_realign(quote: VerbatimQuote, canonical_text: str) -> Optional[Tuple[int, int]]:
    """
    If span is wrong but quote_text exists in canonical_text, find correct span.

    This handles cases where the LLM got the text right but the offsets wrong.
    Returns (new_start, new_end) if found, None if quote_text not in canonical_text.
    """
    idx = canonical_text.find(quote.quote_text)
    if idx >= 0:
        return (idx, idx + len(quote.quote_text))
    return None


# ── Quote Location (v2 hard gate + drop diagnostics) ─────────────────────────

class DropClass(str, Enum):
    """Why a quote failed the exact-match gate. Diagnostic only — never accepts."""
    NORMALIZED_WS = "normalized_ws"      # found after whitespace/typographic normalization
    CASE = "case"                        # ...and after lowercasing
    ELLIPSIS_STITCH = "ellipsis_stitch"  # split on "..."/"…", every fragment found
    UNMATCHED = "unmatched"              # paraphrase or fabrication — not distinguished


@dataclass(frozen=True)
class QuoteMatch:
    """Result of locating one quote in a canonical text."""
    span: Optional[Tuple[int, int]]      # None → dropped
    n_occurrences: int                   # exact occurrences in canonical
    resolution: Optional[str]            # "unique" | "first_free" | "first_fallback"
    drop_class: Optional[DropClass]      # set only when span is None


_TYPOGRAPHIC = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "–": "-", "—": "-", "−": "-",
})
_WS = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\.{3,}")  # "…" becomes "..." under NFKC


def _loose(text: str) -> str:
    """NFKC + ASCII typography + collapsed whitespace (diagnostic comparison only)."""
    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHIC)
    return _WS.sub(" ", text).strip()


def _occurrences(needle: str, haystack: str) -> List[int]:
    """All start offsets of needle in haystack, overlapping occurrences included."""
    out: List[int] = []
    i = haystack.find(needle)
    while i >= 0:
        out.append(i)
        i = haystack.find(needle, i + 1)
    return out


def _classify_drop(quote_text: str, canonical: str) -> DropClass:
    """First matching class wins: normalized_ws → case → ellipsis_stitch → unmatched."""
    q, c = _loose(quote_text), _loose(canonical)
    if not q:
        return DropClass.UNMATCHED
    if q in c:
        return DropClass.NORMALIZED_WS
    ql, cl = q.lower(), c.lower()
    if ql in cl:
        return DropClass.CASE
    if _ELLIPSIS.search(q):
        fragments = [f.strip(" .") for f in _ELLIPSIS.split(ql)]
        fragments = [f for f in fragments if f]
        if fragments and all(f in cl for f in fragments):
            return DropClass.ELLIPSIS_STITCH
    return DropClass.UNMATCHED


def locate_quote(
    quote_text: str,
    canonical: str,
    claimed_spans: Sequence[Tuple[int, int]] = (),
) -> QuoteMatch:
    """
    Locate a quote in canonical text under the v2 hard gate (contract #4).

    Only an EXACT substring is accepted; the span is computed here, never by the
    LLM. With several exact occurrences the first one not overlapping any
    `claimed_spans` interval wins ("first_free"); if all overlap, the first one
    ("first_fallback"). A non-matching quote gets a DropClass explaining the near
    miss — the classification is diagnostic and never turns a drop into a match.
    """
    if not quote_text.strip():
        return QuoteMatch(None, 0, None, DropClass.UNMATCHED)

    starts = _occurrences(quote_text, canonical)
    if not starts:
        return QuoteMatch(None, 0, None, _classify_drop(quote_text, canonical))

    length = len(quote_text)
    if len(starts) == 1:
        return QuoteMatch((starts[0], starts[0] + length), 1, "unique", None)

    for s in starts:
        e = s + length
        if not any(max(s, cs) < min(e, ce) for cs, ce in claimed_spans):
            return QuoteMatch((s, e), len(starts), "first_free", None)
    return QuoteMatch((starts[0], starts[0] + length), len(starts), "first_fallback", None)


# ── Grounding Report ─────────────────────────────────────────────────────────

@dataclass
class GroundingReport:
    """Summary of grounding verification for a set of quotes."""
    total_quotes: int = 0
    verified_count: int = 0
    failed_count: int = 0
    realigned_count: int = 0
    not_found_count: int = 0
    failed_quotes: List[VerbatimQuote] = field(default_factory=list)
    realigned_quotes: List[Tuple[VerbatimQuote, int, int]] = field(default_factory=list)

    @property
    def grounding_rate(self) -> float:
        """Fraction of quotes that are verified (including realigned)."""
        if self.total_quotes == 0:
            return 1.0
        return (self.verified_count + self.realigned_count) / self.total_quotes

    @property
    def is_acceptable(self) -> bool:
        """Grounding rate >= 95% is acceptable per architecture doc."""
        return self.grounding_rate >= 0.95


# ── IC-level Verification ────────────────────────────────────────────────────

def verify_ic_quotes(
    ic: InitialCode,
    db: Database,
    auto_realign: bool = True,
) -> GroundingReport:
    """
    Verify all verbatim quotes for a given Initial Code.

    If auto_realign=True, attempts to fix wrong spans when the quote_text
    exists in canonical_text but at a different offset.
    """
    vq_repo = VerbatimQuoteRepo(db)
    seg_repo = SegmentRepo(db)

    quotes = vq_repo.get_all_for_ic(ic.id)
    report = GroundingReport(total_quotes=len(quotes))

    for quote in quotes:
        canonical = seg_repo.get_canonical_text(quote.segment_id)
        if canonical is None:
            report.failed_count += 1
            report.not_found_count += 1
            report.failed_quotes.append(quote)
            continue

        if verify_quote(quote, canonical):
            report.verified_count += 1
        elif auto_realign:
            new_span = attempt_realign(quote, canonical)
            if new_span:
                report.realigned_count += 1
                report.realigned_quotes.append((quote, new_span[0], new_span[1]))
            else:
                report.failed_count += 1
                report.failed_quotes.append(quote)
        else:
            report.failed_count += 1
            report.failed_quotes.append(quote)

    return report


# ── Coverage Computation ─────────────────────────────────────────────────────

def compute_coverage(segment_id: str, db: Database) -> float:
    """
    Compute what fraction of a segment's canonical_text is covered by
    verified verbatim quotes.

    Coverage = (total unique characters covered by IC spans) / char_count.

    Uses a set of character indices to handle overlapping spans correctly.
    """
    seg_repo = SegmentRepo(db)
    vq_repo = VerbatimQuoteRepo(db)

    segment = seg_repo.get_by_id(segment_id)
    if segment is None or segment.char_count == 0:
        return 0.0

    quotes = vq_repo.get_all_for_segment(segment_id)

    # Collect all character positions covered by verified quotes
    covered: Set[int] = set()
    for quote in quotes:
        if quote.is_verified:
            for i in range(quote.span_start, quote.span_end):
                covered.add(i)

    return len(covered) / segment.char_count


def compute_corpus_coverage(db: Database) -> Dict[str, float]:
    """
    Compute coverage for all segments in the database.

    Returns {segment_id: coverage_fraction}.
    """
    seg_repo = SegmentRepo(db)
    # Get all documents first, then their segments
    from src.core.db import DocumentRepo
    doc_repo = DocumentRepo(db)
    docs = doc_repo.get_all()

    coverage: Dict[str, float] = {}
    for doc in docs:
        segments = seg_repo.get_all_for_document(doc.id)
        for seg in segments:
            coverage[seg.id] = compute_coverage(seg.id, db)

    return coverage


def corpus_coverage_summary(db: Database) -> Tuple[float, int, int]:
    """
    Summary stats for corpus coverage.

    Returns: (mean_coverage, segments_with_any_coverage, total_segments)
    """
    coverages = compute_corpus_coverage(db)

    if not coverages:
        return 0.0, 0, 0

    values = list(coverages.values())
    mean_cov = sum(values) / len(values)
    covered_count = sum(1 for v in values if v > 0)

    return mean_cov, covered_count, len(values)
