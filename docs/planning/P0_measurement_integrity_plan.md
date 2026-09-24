# P0 Measurement Integrity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Naprawić trzy rekomendacje P0 (awaria sędziego i cel MERGE, niecyrkularny grounding z klasami odrzutów, wybór wystąpienia przy duplikatach), żeby kolejne runy leaderboardu dawały wiarygodne metryki i nie mieszały się ze starszymi.

**Architecture:** Deterministyczna logika groundingu trafia do czystej funkcji `locate_quote` w `src/preprocessing/grounding.py`, którą wołają pass-1 (`CoderAgent`) i pass-2 (orchestrator). Komparator jawnie oznacza awarię sędziego i nie tworzy z niej par AUC. Orchestrator rozwiązuje `merge_target_name` sędziego i weryfikuje każdy cytat przed insertem. Nowe liczniki z summary trafiają do `L1MetricsEngine`, a stamtąd do rejestru, który filtruje macierz po `pipeline_version`.

**Tech Stack:** Python 3, Pydantic v2, SQLite, pytest (`.venv/bin/python -m pytest`), instructor (mockowany w testach).

**Spec:** `docs/planning/P0_measurement_integrity_design.md`. Przeczytaj go przed pierwszym taskiem. Tło: `notes/2026-06-09-propozycje-zmian-po-recenzji.md` (P0-1…P0-3).

## Global Constraints

- Kontrakt #4 bez zmian: cytat jest akceptowany **tylko** jako dokładny podciąg `canonical_text`. Klasyfikacja odrzutu nigdy niczego nie przyjmuje.
- Bez zmian schematu SQLite (`src/core/db.py`) i bez zmian modelu `VerbatimQuote`.
- `attempt_realign()` i `verify_ic_quotes()` zostają nietknięte (wraz z testami).
- `PIPELINE_VERSION = "v2-p0"`.
- Nowe metryki rejestru mają kierunek `"less"`: `judge_failure_rate`, `merge_target_unresolved_rate`, `unmatched_quote_rate`, `ambiguous_occurrence_rate`. `span_integrity` ma kierunek `"more"`.
- Jedyne nowe `decision_path` to `"llm_failed"`. Nierozwiązany cel MERGE zachowuje `"llm"` (spec D6).
- Uruchamianie: zawsze `.venv/bin/python`. Stan wyjściowy to 224 testy green.
- W drzewie roboczym leżą cudze niezacommitowane zmiany (`eqd_config.yaml`, `src/core/config.py`, `tests/test_config.py`, `docs/research/`, `docs/testing/`, `notes/`). **Nigdy ich nie stage'uj.** Używaj `git add <konkretne pliki>`, nigdy `git add -A` ani `git add .`.
- Każdy commit kończy się linią: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`

## Review Focus

- Fraza występująca 3+ razy przy dwóch zajętych wystąpieniach ma trafić w trzecie. Test jest w Task 1 (`test_three_occurrences_two_claimed_picks_third`).
- Pusty albo składający się z samych białych znaków cytat od LLM ma być odrzutem `unmatched`, a nigdy spanem (0, 0). Test w Task 1 (`test_empty_quote_is_unmatched`).
- Polskie diakrytyki w postaci rozłożonej (litera + znak łączący) muszą dać odrzut klasy `normalized_ws` (NFKC je składa), a nie `unmatched`. Test w Task 1 (`test_decomposed_diacritics_is_normalized_ws`).
- Nazwa celu od sędziego z białymi znakami na brzegach albo inną wielkością liter ma się rozwiązać do właściwego IC. Test w Task 5 (`test_resolve_strips_and_ignores_case`).
- Istniejący `runs/leaderboard.db` ma runy z `pipeline_version` równym `"v2-phase2"` albo `""`. Domyślna macierz ma je pominąć i policzyć w `excluded_runs`. Test w Task 8 (`test_empty_version_rows_are_excluded`).

---

### Task 1: `locate_quote` — czysta funkcja groundingu

**Files:**
- Modify: `src/preprocessing/grounding.py` (nowa sekcja po `attempt_realign`, importy na górze)
- Modify: `src/preprocessing/__init__.py` (reeksport)
- Test: `tests/test_grounding.py` (nowa klasa na końcu pliku)

**Interfaces:**
- Consumes: —
- Produces:
  - `class DropClass(str, Enum)` z wartościami `"normalized_ws"`, `"case"`, `"ellipsis_stitch"`, `"unmatched"`
  - `@dataclass(frozen=True) class QuoteMatch: span: Optional[Tuple[int, int]]; n_occurrences: int; resolution: Optional[str]; drop_class: Optional[DropClass]`
  - `locate_quote(quote_text: str, canonical: str, claimed_spans: Sequence[Tuple[int, int]] = ()) -> QuoteMatch`
  - wartości `resolution`: `"unique"`, `"first_free"`, `"first_fallback"` albo `None` przy odrzucie
  - wszystkie trzy nazwy są importowalne z `src.preprocessing`

- [ ] **Step 1: Write the failing tests**

Dopisz na końcu `tests/test_grounding.py`:

```python
# ── locate_quote (P0: hard gate + drop diagnostics + occurrence selection) ────

from src.preprocessing import DropClass, QuoteMatch, locate_quote

REVIEW = "The combat is sluggish and clunky. The story was fine. Loading times are far too long."
DUP = "The combat is bad. The story was fine. The combat is bad. The combat is bad."


class TestLocateQuoteAcceptance:
    def test_unique_exact_match(self):
        m = locate_quote("The story was fine", REVIEW)
        s = REVIEW.index("The story was fine")
        assert m.span == (s, s + len("The story was fine"))
        assert m.n_occurrences == 1
        assert m.resolution == "unique"
        assert m.drop_class is None

    def test_span_invariant_holds(self):
        m = locate_quote("Loading times are far too long", REVIEW)
        s, e = m.span
        assert REVIEW[s:e] == "Loading times are far too long"

    def test_duplicate_first_free_skips_claimed(self):
        first = DUP.index("The combat is bad")
        second = DUP.index("The combat is bad", first + 1)
        m = locate_quote("The combat is bad", DUP, claimed_spans=[(first, first + 17)])
        assert m.span == (second, second + 17)
        assert m.n_occurrences == 3
        assert m.resolution == "first_free"

    def test_duplicate_unclaimed_takes_first_as_first_free(self):
        m = locate_quote("The combat is bad", DUP)
        assert m.span == (0, 17)
        assert m.resolution == "first_free"

    def test_three_occurrences_two_claimed_picks_third(self):
        idx = [0]
        while True:
            nxt = DUP.find("The combat is bad", idx[-1] + 1)
            if nxt < 0:
                break
            idx.append(nxt)
        assert len(idx) == 3
        claimed = [(idx[0], idx[0] + 17), (idx[1], idx[1] + 17)]
        m = locate_quote("The combat is bad", DUP, claimed_spans=claimed)
        assert m.span == (idx[2], idx[2] + 17)
        assert m.resolution == "first_free"

    def test_all_claimed_falls_back_to_first(self):
        claimed = [(0, len(DUP))]
        m = locate_quote("The combat is bad", DUP, claimed_spans=claimed)
        assert m.span == (0, 17)
        assert m.resolution == "first_fallback"

    def test_claimed_spans_irrelevant_for_unique(self):
        m = locate_quote("The story was fine", REVIEW, claimed_spans=[(0, len(REVIEW))])
        assert m.resolution == "unique"


class TestLocateQuoteDropClasses:
    def test_whitespace_difference_is_normalized_ws(self):
        m = locate_quote("The  combat is\nsluggish", REVIEW)
        assert m.span is None
        assert m.resolution is None
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_typographic_apostrophe_is_normalized_ws(self):
        canonical = "I don't like the ending at all."
        m = locate_quote("I don’t like the ending", canonical)
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_decomposed_diacritics_is_normalized_ws(self):
        canonical = "Produkt jest świetny, ale dostawa trwała zbyt długo."
        decomposed = "świetny"  # 's' + combining acute; NFKC → 'ś'
        m = locate_quote(f"Produkt jest {decomposed}", canonical)
        assert m.drop_class == DropClass.NORMALIZED_WS

    def test_case_difference_is_case(self):
        m = locate_quote("the combat is sluggish", REVIEW)
        assert m.drop_class == DropClass.CASE

    def test_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish... Loading times are far too long", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_unicode_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish… The story was fine", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_trailing_ellipsis_truncation_is_ellipsis_stitch(self):
        m = locate_quote("The combat is sluggish...", REVIEW)
        assert m.drop_class == DropClass.ELLIPSIS_STITCH

    def test_case_wins_over_ellipsis(self):
        canonical = "Wait... what? This ending is absurd."
        m = locate_quote("wait... What?", canonical)
        assert m.drop_class == DropClass.CASE

    def test_ellipsis_with_missing_fragment_is_unmatched(self):
        m = locate_quote("The combat is sluggish... the graphics are ugly", REVIEW)
        assert m.drop_class == DropClass.UNMATCHED

    def test_paraphrase_is_unmatched(self):
        m = locate_quote("loading is way too slow", REVIEW)
        assert m.drop_class == DropClass.UNMATCHED

    def test_empty_quote_is_unmatched(self):
        for q in ("", "   ", "\n"):
            m = locate_quote(q, REVIEW)
            assert m.span is None
            assert m.n_occurrences == 0
            assert m.drop_class == DropClass.UNMATCHED

    def test_quote_match_is_frozen(self):
        m = locate_quote("The story was fine", REVIEW)
        assert isinstance(m, QuoteMatch)
        with pytest.raises(Exception):
            m.span = None  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_grounding.py -v -k "LocateQuote"`
Expected: ERROR przy kolekcji, `ImportError: cannot import name 'DropClass' from 'src.preprocessing'`

- [ ] **Step 3: Implement `locate_quote`**

W `src/preprocessing/grounding.py` rozszerz importy na górze pliku:

```python
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Set, Tuple
```

Wstaw nową sekcję bezpośrednio po funkcji `attempt_realign` (przed `# ── Grounding Report`):

```python
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
```

W `src/preprocessing/__init__.py` dopisz do importu z `grounding` nazwy `DropClass`, `QuoteMatch`, `locate_quote` i dodaj je do `__all__`:

```python
from src.preprocessing.grounding import (
    verify_quote,
    attempt_realign,
    verify_ic_quotes,
    compute_coverage,
    compute_corpus_coverage,
    corpus_coverage_summary,
    GroundingReport,
    DropClass,
    QuoteMatch,
    locate_quote,
)
```

i w `__all__` po `"GroundingReport",`:

```python
    "DropClass",
    "QuoteMatch",
    "locate_quote",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_grounding.py -v`
Expected: PASS dla wszystkich testów (nowe + istniejące).

- [ ] **Step 5: Commit**

```bash
git add src/preprocessing/grounding.py src/preprocessing/__init__.py tests/test_grounding.py
git commit -m "feat(grounding): add locate_quote with drop classes and occurrence selection

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `CoderAgent` na `locate_quote` + `last_drops`

**Files:**
- Modify: `src/core/models.py:342-367` (`ICCandidate`: dwa nowe pola)
- Modify: `src/extraction/coder_agent.py` (docstring modułu, `__init__`, `process_batch`, `_code_segment`, usunięcie `_ground_candidate`, nowa funkcja modułowa `ground_candidate`, dataclass `GroundingDrop`)
- Test: `tests/test_coder_agent.py`

**Interfaces:**
- Consumes: `locate_quote`, `QuoteMatch`, `DropClass` z Task 1
- Produces:
  - `ICCandidate.n_occurrences: int = 1`, `ICCandidate.occurrence_resolution: Optional[str] = None`
  - `@dataclass(frozen=True) class GroundingDrop: ic_name: str; quote_text: str; drop_class: DropClass` w `src/extraction/coder_agent.py`
  - `ground_candidate(raw: RawICCandidate, canonical: str, claimed_spans: Sequence[Tuple[int, int]] = ()) -> Tuple[Optional[ICCandidate], QuoteMatch]` w `src/extraction/coder_agent.py`
  - `CoderAgent.last_drops: Dict[str, List[GroundingDrop]]` (resetowane w każdym `process_batch`)
  - `CoderAgent.last_drop_counts` bez zmian semantyki
  - `CoderAgent._ground_candidate` **nie istnieje**

- [ ] **Step 1: Write the failing tests**

W `tests/test_coder_agent.py` zmień import na górze:

```python
from src.extraction.coder_agent import CoderAgent, GroundingDrop, ground_candidate
from src.core.models import ICCandidate, RawICCandidate, Segment, SegmentCodingResult
from src.preprocessing import DropClass
```

Zastąp całą klasę `TestCoderAgentGrounding` tą wersją:

```python
class TestCoderAgentGrounding:
    """Test ground_candidate — the verbatim grounding gate (offsets are computed)."""

    def test_verbatim_quote_grounded_with_computed_span(self, test_segment):
        """A verbatim quote is grounded and its span is computed by the system."""
        raw = RawICCandidate(
            ic_name="slow_delivery",
            definition="Customer reports slow delivery",
            quote_text="dostawa trwała zbyt długo",
            confidence=0.9,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert isinstance(cand, ICCandidate)
        canonical = test_segment.canonical_text
        assert cand.span_start == canonical.index("dostawa trwała zbyt długo")
        assert canonical[cand.span_start:cand.span_end] == cand.quote_text
        assert cand.n_occurrences == 1
        assert cand.occurrence_resolution == "unique"
        assert match.drop_class is None

    def test_hallucinated_quote_dropped(self, test_segment):
        """Quote text not present verbatim → None + UNMATCHED."""
        raw = RawICCandidate(
            ic_name="hallucinated",
            definition="This text does not exist",
            quote_text="ten produkt jest okropny",
            confidence=0.8,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None
        assert match.drop_class == DropClass.UNMATCHED

    def test_partially_altered_quote_dropped(self, test_segment):
        """A near-miss with altered words is not verbatim → dropped."""
        raw = RawICCandidate(
            ic_name="altered",
            definition="Quote with a changed word",
            quote_text="dostawa trwała bardzo długo",  # 'zbyt' → 'bardzo'
            confidence=0.7,
        )
        cand, _ = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None

    def test_case_near_miss_dropped_with_class(self, test_segment):
        raw = RawICCandidate(
            ic_name="case_miss",
            definition="Quote differing only in letter case",
            quote_text="DOSTAWA trwała zbyt długo",
            confidence=0.7,
        )
        cand, match = ground_candidate(raw, test_segment.canonical_text)
        assert cand is None
        assert match.drop_class == DropClass.CASE
```

W klasie `TestCoderAgentProcessBatch`, w `test_returns_grounded_candidates_only`, dopisz na końcu testu:

```python
        # Full drop record (not just a count) is exposed for the reasoning log
        drops = agent.last_drops[test_segment.id]
        assert drops == [
            GroundingDrop(
                ic_name="invalid_code",
                quote_text="wrong text not in the segment",
                drop_class=DropClass.UNMATCHED,
            )
        ]
```

Dopisz nowy test w `TestCoderAgentProcessBatch`:

```python
    def test_repeated_phrase_gets_distinct_spans(self, mock_model_client, db):
        """Two candidates quoting a phrase that occurs twice get different occurrences."""
        mc, mock_client = mock_model_client
        agent = CoderAgent(mc, db, MagicMock())
        text = "The combat is bad. The story was fine. The combat is bad."
        seg = Segment(
            id="seg_dup", document_id="doc_test", canonical_text=text,
            original_text=text, char_count=len(text), content_hash="h",
        )
        mock_client.chat.completions.create_with_completion.return_value = (
            SegmentCodingResult(segment_id="seg_dup", candidates=[
                RawICCandidate(ic_name="combat_bad_a", definition="Combat criticised",
                               quote_text="The combat is bad", confidence=0.9),
                RawICCandidate(ic_name="combat_bad_b", definition="Combat criticised again",
                               quote_text="The combat is bad", confidence=0.9),
            ]),
            MagicMock(),
        )
        cands = agent.process_batch([seg])["seg_dup"]
        assert [c.span_start for c in cands] == [0, text.index("The combat is bad", 1)]
        assert all(c.occurrence_resolution == "first_free" for c in cands)
        assert all(c.n_occurrences == 2 for c in cands)
        assert agent.last_drops["seg_dup"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_coder_agent.py -v`
Expected: ERROR przy kolekcji, `ImportError: cannot import name 'GroundingDrop'`

- [ ] **Step 3: Add `ICCandidate` fields**

W `src/core/models.py`, w klasie `ICCandidate`, po linii `existing_code_match: Optional[str] = Field(default=None)` dodaj:

```python
    n_occurrences: int = Field(
        default=1,
        ge=1,
        description="Exact occurrences of quote_text in canonical_text (diagnostic)",
    )
    occurrence_resolution: Optional[str] = Field(
        default=None,
        description="How the span was chosen: unique | first_free | first_fallback",
    )
```

- [ ] **Step 4: Rewrite grounding in `coder_agent.py`**

1. W docstringu modułu zamień blok `Grounding gate (...)` na:

```
Grounding gate (v2 contract #4 — hard gate, no repair):
    the quote must be an EXACT verbatim substring of canonical_text. The span is
    located by `src.preprocessing.locate_quote` (first free occurrence when the
    phrase repeats). A non-verbatim quote is DROPPED; the drop is classified
    (normalized_ws / case / ellipsis_stitch / unmatched) and exposed in
    `last_drops` for the reasoning log. No realignment, no fuzzy acceptance.
```

2. Importy: zmień `from typing import Any, Dict, List, Optional, Tuple` na `from typing import Any, Dict, List, Optional, Sequence, Tuple`, dodaj `from dataclasses import dataclass`, a po `from src.core.models import ...` dodaj:

```python
from src.preprocessing.grounding import DropClass, QuoteMatch, locate_quote
```

3. Po `logger = logging.getLogger(__name__)` dodaj:

```python
@dataclass(frozen=True)
class GroundingDrop:
    """One candidate dropped by the grounding gate (full quote for the audit log)."""
    ic_name: str
    quote_text: str
    drop_class: DropClass


def ground_candidate(
    raw: RawICCandidate,
    canonical: str,
    claimed_spans: Sequence[Tuple[int, int]] = (),
) -> Tuple[Optional[ICCandidate], QuoteMatch]:
    """
    Ground a raw candidate against canonical text (shared by pass 1 and pass 2).

    Returns (candidate, match). candidate is None when the quote is not an exact
    substring; match.drop_class then says why. On success
    canonical[span_start:span_end] == quote_text holds by construction.
    """
    match = locate_quote(raw.quote_text, canonical, claimed_spans)
    if match.span is None:
        return None, match
    start, end = match.span
    return ICCandidate(
        ic_name=raw.ic_name,
        definition=raw.definition,
        quote_text=raw.quote_text,
        span_start=start,
        span_end=end,
        confidence=raw.confidence,
        sentiment=raw.sentiment,
        existing_code_match=raw.existing_code_match,
        n_occurrences=match.n_occurrences,
        occurrence_resolution=match.resolution,
    ), match
```

4. W `__init__`, po `self.last_drop_counts: Dict[str, int] = {}` dodaj:

```python
        # Full drop records from the most recent process_batch() call (for the
        # reasoning log + drop-class metrics). Keyed by segment_id.
        self.last_drops: Dict[str, List[GroundingDrop]] = {}
```

5. W `process_batch` zamień:

```python
        self.last_drop_counts = {}  # reset for this batch

        for idx, segment in enumerate(segments, 1):
            logger.info(f"[CODER] Segment {idx}/{len(segments)}: {segment.id}")
            candidates, n_dropped = self._code_segment(segment, codebook_context)
            results[segment.id] = candidates
            self.last_drop_counts[segment.id] = n_dropped
```

na:

```python
        self.last_drop_counts = {}  # reset for this batch
        self.last_drops = {}

        for idx, segment in enumerate(segments, 1):
            logger.info(f"[CODER] Segment {idx}/{len(segments)}: {segment.id}")
            candidates, drops = self._code_segment(segment, codebook_context)
            results[segment.id] = candidates
            self.last_drops[segment.id] = drops
            self.last_drop_counts[segment.id] = len(drops)
```

6. W `_code_segment` zmień adnotację zwrotną na `-> Tuple[List[ICCandidate], List[GroundingDrop]]`, a w docstringu `Returns (grounded_candidates, n_dropped).` na `Returns (grounded_candidates, drops).`. W bloku `except` zamień `return [], 0` na `return [], []`. Cały blok od `# Grounding gate — locate each quote verbatim; drop hallucinated ones` do `return grounded, n_dropped` zastąp:

```python
        # Grounding gate — locate each quote verbatim; drop (and classify) the rest.
        # Earlier accepted spans are "claimed" so a repeated phrase quoted by two
        # candidates lands on two different occurrences.
        grounded: List[ICCandidate] = []
        drops: List[GroundingDrop] = []
        claimed: List[Tuple[int, int]] = []
        for raw in result.candidates:
            candidate, match = ground_candidate(raw, segment.canonical_text, claimed)
            if candidate is None:
                drops.append(GroundingDrop(raw.ic_name, raw.quote_text, match.drop_class))
                logger.warning(
                    f"[HALLUCINATION] Dropped candidate '{raw.ic_name}' "
                    f"({match.drop_class.value}) — quote not found verbatim in "
                    f"segment {segment.id}. Quote: '{raw.quote_text[:60]}…'"
                )
                continue
            grounded.append(candidate)
            claimed.append((candidate.span_start, candidate.span_end))

        logger.info(
            f"Segment {segment.id}: {len(result.candidates)} candidates → "
            f"{len(grounded)} grounded ({len(drops)} hallucinated)"
        )
        return grounded, drops
```

7. Usuń całą metodę `_ground_candidate` (dekorator `@staticmethod` i ciało, do końca klasy).

- [ ] **Step 5: Temporarily point pass-2 at the new function**

`src/extraction/orchestrator.py` (≈ l. 512) nadal woła `CoderAgent._ground_candidate`. Zmień tę jedną linię (pełna obsługa pass-2 przyjdzie w Task 3):

```python
                cand, _match = ground_candidate(raw, segment.canonical_text, pass1_spans)
```

a import `from src.extraction.coder_agent import CoderAgent` zamień na:

```python
from src.extraction.coder_agent import CoderAgent, ground_candidate
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_coder_agent.py tests/test_second_pass.py tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/core/models.py src/extraction/coder_agent.py src/extraction/orchestrator.py tests/test_coder_agent.py
git commit -m "feat(coder): ground via locate_quote, expose classified drops

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Orchestrator — logowanie odrzutów, pass-2 i liczniki wystąpień

**Files:**
- Modify: `src/extraction/orchestrator.py` (inicjalizacja `summary` w `run()` ≈ l. 249-292; pass-1 w metodzie per-review ≈ l. 446-453; pass-2 ≈ l. 508-525; rekord w `_decide_and_apply` ≈ l. 685-705; nowy helper przy `_overlaps_any`)
- Test: `tests/test_second_pass.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `CoderAgent.last_drops`, `GroundingDrop`, `ground_candidate` (Task 2); `ICCandidate.occurrence_resolution`, `ICCandidate.n_occurrences`
- Produces (klucze `summary` zwracanego przez `Layer1Orchestrator.run`):
  - `summary["grounding_drop_classes"]: Dict[str, int]` (pass-1)
  - `summary["pass2_stats"]["drop_classes"]: Dict[str, int]`
  - `summary["ambiguous_occurrences"]: {"first_free": int, "first_fallback": int}`
  - `summary["accepted_quotes_total"]: int`
- Rekordy reasoning logu: `{"type": "grounding_drop", "pass": 1, ...}`; `pass2_grounding_drop` z `"drop_class"`; rekordy `candidate` z `"n_occurrences"` i `"occurrence_resolution"`.

- [ ] **Step 1: Write the failing tests**

W `tests/test_second_pass.py`, w fixture `orch` (klasa `TestPass2Integration`), po `o.coder_agent.last_drop_counts = {}` dodaj:

```python
        o.coder_agent.last_drops = {}
```

W `test_grounding_gate_drops_hallucinated_recovery` dopisz na końcu:

```python
        assert ps["drop_classes"] == {"unmatched": 1}
```

Dopisz na końcu klasy `TestPass2Integration`:

```python
    def test_pass2_hits_second_occurrence_instead_of_overlap_drop(self, db):
        """A repeated phrase recovered in pass 2 lands on the free occurrence."""
        text = "The combat is bad. The story was fine. The combat is bad."
        seg = Segment(
            id="seg_dup2", document_id="doc_dup2", canonical_text=text,
            original_text=text, char_count=len(text), segment_index=0,
            content_hash="hash_dup2",
        )
        DocumentRepo(db).insert(Document(id="doc_dup2", raw_text="x"))
        SegmentRepo(db).insert(seg)

        config = MagicMock()
        config.processing.batch_size = 15
        config.processing.its_saturation_threshold = 0.02
        config.processing.its_consecutive_batches = 3
        config.processing.similarity_prefilter_k = 5
        o = Layer1Orchestrator(MagicMock(), db, config)
        o.coder_agent = MagicMock()
        o.coder_agent.last_drop_counts = {}
        o.coder_agent.last_drops = {}
        o.comparator = MagicMock()
        o.second_pass_agent = MagicMock()
        o.embedding_service = MagicMock()
        o.embedding_service.embed_texts_batch.side_effect = (
            lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
        )

        def fake_embed_ic(ic):
            ic.embedding_json = [0.1, 0.2, 0.3]
            return ic
        o.embedding_service.embed_ic.side_effect = fake_embed_ic
        o.comparator.evaluate.return_value = (
            ComparatorOutput(recommendation=ComparatorRecommendation.NEW,
                             reasoning="Distinct concept."),
            [],
            {"decision_path": "empty_codebook", "max_sim": None, "llm_recommendation": None},
        )

        o.coder_agent.process_batch.return_value = {seg.id: [ICCandidate(
            ic_name="combat_bad", definition="Player criticises the combat",
            quote_text="The combat is bad", span_start=0, span_end=17,
            confidence=0.9, n_occurrences=2, occurrence_resolution="first_free",
        )]}
        o.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id=seg.id,
            fragments=[OmittedFragmentAssessment(
                omitted_text="The combat is bad.",
                reasoning="Repeated complaint at the end of the review.",
                omission_type=OmissionType.ACCIDENTAL,
                contains_evidence=True,
                recovered_evidence=[RawICCandidate(
                    ic_name="combat_bad_repeat",
                    definition="Player repeats the combat complaint",
                    quote_text="The combat is bad", confidence=0.8,
                )],
            )],
        )

        result = o.run([seg], enable_hil=False)

        ps = result["pass2_stats"]
        assert ps["overlap_drops"] == 0
        assert ps["recovered_accepted"] == 1
        assert result["ambiguous_occurrences"] == {"first_free": 2, "first_fallback": 0}
        assert result["accepted_quotes_total"] == 2
```

W `tests/test_orchestrator.py`, w fixture `mock_orchestrator`, po `orch.coder_agent = MagicMock()` dodaj:

```python
        orch.coder_agent.last_drop_counts = {}
        orch.coder_agent.last_drops = {}
```

Na górze `tests/test_orchestrator.py` dodaj importy:

```python
from src.extraction.coder_agent import GroundingDrop
from src.preprocessing import DropClass
```

Dopisz do klasy `TestLayer1Orchestrator`:

```python
    def test_pass1_drops_logged_and_classified(self, mock_orchestrator, test_segment):
        """Every pass-1 grounding drop becomes a full reasoning-log record + class count."""
        mock_orchestrator.coder_agent.process_batch.return_value = {test_segment.id: []}
        mock_orchestrator.coder_agent.last_drop_counts = {test_segment.id: 2}
        mock_orchestrator.coder_agent.last_drops = {test_segment.id: [
            GroundingDrop("a", "Produkt jest świetny... zbyt długo", DropClass.ELLIPSIS_STITCH),
            GroundingDrop("b", "zupełnie inny tekst", DropClass.UNMATCHED),
        ]}
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["grounding_drop_classes"] == {"ellipsis_stitch": 1, "unmatched": 1}
        assert result["total_dropped"] == 2
        records = [c.args[0] for c in mock_orchestrator.reasoning_logger.log_record.call_args_list]
        drops = [r for r in records if r.get("type") == "grounding_drop"]
        assert len(drops) == 2
        assert drops[0] == {
            "type": "grounding_drop", "pass": 1, "segment_id": test_segment.id,
            "ic_name": "a", "quote_text": "Produkt jest świetny... zbyt długo",
            "drop_class": "ellipsis_stitch", "grounded": False,
            "final_action": "grounding_drop",
        }

    def test_candidate_record_carries_occurrence_fields(self, mock_orchestrator, test_segment):
        canonical = test_segment.canonical_text
        quote_text = "Produkt jest świetny"
        start = canonical.index(quote_text)
        mock_orchestrator.coder_agent.process_batch.return_value = {test_segment.id: [
            ICCandidate(
                ic_name="product_praise", definition="Praise for the product",
                quote_text=quote_text, span_start=start,
                span_end=start + len(quote_text), confidence=0.8,
                n_occurrences=1, occurrence_resolution="unique",
            )
        ]}
        mock_orchestrator.comparator.evaluate.return_value = (
            ComparatorOutput(recommendation=ComparatorRecommendation.REJECT,
                             reasoning="Too vague."),
            [],
            {"decision_path": "llm", "max_sim": 0.6, "llm_recommendation": "REJECT"},
        )
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        rec = mock_orchestrator.reasoning_logger.log_candidate.call_args.args[0]
        assert rec["n_occurrences"] == 1
        assert rec["occurrence_resolution"] == "unique"
        assert result["accepted_quotes_total"] == 1
        assert result["ambiguous_occurrences"] == {"first_free": 0, "first_fallback": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_second_pass.py tests/test_orchestrator.py -v`
Expected: FAIL. Nowe testy dają `KeyError: 'grounding_drop_classes'`, `KeyError: 'drop_classes'`, `KeyError: 'ambiguous_occurrences'` albo `KeyError: 'n_occurrences'`.

- [ ] **Step 3: Extend `summary` initialisation**

W `run()`, w słowniku `summary`, po `"dropped_per_segment": {},  # {segment_id: n_dropped}` dodaj:

```python
            # Grounding diagnostics (P0): why pass-1 quotes failed the exact gate,
            # and how often a repeated phrase forced an occurrence choice.
            "grounding_drop_classes": {},   # {drop_class: n}
            "ambiguous_occurrences": {"first_free": 0, "first_fallback": 0},
            "accepted_quotes_total": 0,     # candidates passing the gate (pass 1 + 2)
```

a w `"pass2_stats": {...}` po `"overlap_drops": 0,` dodaj:

```python
                "drop_classes": {},          # {drop_class: n} for pass-2 grounding drops
```

- [ ] **Step 4: Add the ambiguity helper**

W sekcji `# ── Small span helpers`, po `_overlaps_any`, dodaj:

```python
    @staticmethod
    def _count_accepted_quote(cand: ICCandidate, summary: Dict[str, Any]) -> None:
        """Count a gate-passing quote and whether its occurrence was ambiguous."""
        summary["accepted_quotes_total"] += 1
        if cand.occurrence_resolution in ("first_free", "first_fallback"):
            summary["ambiguous_occurrences"][cand.occurrence_resolution] += 1
```

- [ ] **Step 5: Log pass-1 drops**

W metodzie per-review, bezpośrednio po `summary["total_candidates"] += len(pass1_cands)`, dodaj:

```python
        for drop in self.coder_agent.last_drops.get(seg_id, []):
            cls = drop.drop_class.value
            classes = summary["grounding_drop_classes"]
            classes[cls] = classes.get(cls, 0) + 1
            if self.reasoning_logger:
                self.reasoning_logger.log_record({
                    "type": "grounding_drop", "pass": 1, "segment_id": seg_id,
                    "ic_name": drop.ic_name, "quote_text": drop.quote_text,
                    "drop_class": cls, "grounded": False,
                    "final_action": "grounding_drop",
                })
        for cand in pass1_cands:
            self._count_accepted_quote(cand, summary)
```

- [ ] **Step 6: Classify pass-2 drops and count accepted quotes**

W pass-2 zastąp blok od `# Grounding gate (Tier 1) — span via find(); hallucination → drop.` do `continue` (włącznie, kończący gałąź `if cand is None:`):

```python
                # Grounding gate — exact match only; pass-1 spans are "claimed" so a
                # repeated phrase recovered here lands on its free occurrence.
                cand, match = ground_candidate(raw, segment.canonical_text, pass1_spans)
                if cand is None:
                    cls = match.drop_class.value
                    summary["pass2_stats"]["recovered_hallucinated"] += 1
                    p2_classes = summary["pass2_stats"]["drop_classes"]
                    p2_classes[cls] = p2_classes.get(cls, 0) + 1
                    if self.reasoning_logger:
                        self.reasoning_logger.log_record({
                            "type": "pass2_grounding_drop",
                            "pass": 2, "segment_id": seg_id,
                            "ic_name": raw.ic_name, "quote_text": raw.quote_text,
                            "omission_type": otype, "grounded": False,
                            "drop_class": cls,
                            "final_action": "grounding_drop",
                        })
                    continue
                self._count_accepted_quote(cand, summary)
```

(Blok `# DEDUP overlap gate` zostaje bez zmian bezpośrednio pod spodem.)

- [ ] **Step 7: Add occurrence fields to the candidate record**

W `_decide_and_apply`, w słowniku `record`, po `"span_end": cand.span_end,` dodaj:

```python
                "n_occurrences": cand.n_occurrences,
                "occurrence_resolution": cand.occurrence_resolution,
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_second_pass.py tests/test_orchestrator.py tests/test_coder_agent.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/extraction/orchestrator.py tests/test_second_pass.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): log classified grounding drops and occurrence choices

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Komparator — jawna awaria sędziego, bez par AUC

**Files:**
- Modify: `src/extraction/codebook_comparator.py:136-160` (`evaluate`) + docstring `evaluate` (opis `meta`)
- Test: `tests/test_codebook_comparator.py`

**Interfaces:**
- Consumes: —
- Produces: `meta` z `evaluate()` dla ścieżki sędziego ma klucze `decision_path` (`"llm"` | `"llm_failed"`), `judge_failed: bool`, `judge_error: Optional[str]`, `max_sim`, `llm_recommendation`. Ścieżka `empty_codebook` dostaje `judge_failed: False`, `judge_error: None`. `eval_pairs` nigdy nie zawiera pary z nieudanego wywołania.

- [ ] **Step 1: Write the failing tests**

W `tests/test_codebook_comparator.py`, w `test_llm_failure_defaults_to_new`, zamień `assert meta["decision_path"] == "llm"` na:

```python
        assert meta["decision_path"] == "llm_failed"
        assert meta["judge_failed"] is True
        assert "API timeout" in meta["judge_error"]
```

Dopisz do klasy `TestCodebookComparatorSingleTrack`:

```python
    def test_llm_failure_adds_no_auc_pair(self, mock_services, db, test_candidate, sample_ics):
        """Eval mode: a failed judge call is not a verdict → no (cosine, verdict) pair."""
        mc, mock_client, embedding_service = mock_services
        from src.core.db import InitialCodeRepo
        for ic in sample_ics:
            InitialCodeRepo(db).insert(ic)
        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.60),
        ]
        mock_client.chat.completions.create_with_completion.side_effect = Exception("boom")

        comparator = CodebookComparator(
            mc, embedding_service, db, self._make_config(), eval_mode=True,
        )
        output, _, meta = comparator.evaluate(test_candidate)

        assert output.recommendation == ComparatorRecommendation.NEW
        assert comparator.eval_pairs == []

    def test_successful_judge_meta_flags(self, mock_services, db, test_candidate, sample_ics):
        mc, mock_client, embedding_service = mock_services
        _, _, meta = self._seed_and_eval(
            mc, mock_client, embedding_service, db, test_candidate, sample_ics,
            similarity=0.5, verdict=ComparatorRecommendation.NEW,
        )
        assert meta["judge_failed"] is False
        assert meta["judge_error"] is None

    def test_successful_judge_records_auc_pair(self, mock_services, db, test_candidate, sample_ics):
        mc, mock_client, embedding_service = mock_services
        from src.core.db import InitialCodeRepo
        for ic in sample_ics:
            InitialCodeRepo(db).insert(ic)
        embedding_service.find_similar_ics.return_value = [
            SimilarityResult(ic_id="ic_001", ic_name="Delivery speed complaint", similarity=0.7),
        ]
        mock_client.chat.completions.create_with_completion.return_value = (
            ComparatorOutput(recommendation=ComparatorRecommendation.MERGE,
                             merge_target_name="Delivery speed complaint",
                             reasoning="Same phenomenon."),
            MagicMock(),
        )
        comparator = CodebookComparator(
            mc, embedding_service, db, self._make_config(), eval_mode=True,
        )
        comparator.evaluate(test_candidate)
        assert comparator.eval_pairs == [(pytest.approx(0.7), "MERGE")]
```

W `TestCodebookComparatorEmptyCodebook.test_empty_codebook_returns_new` zamień `output, top_k, _meta = ...` na `output, top_k, meta = ...` i dopisz:

```python
        assert meta["judge_failed"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_codebook_comparator.py -v`
Expected: FAIL (`KeyError: 'judge_failed'`, `assert 'llm' == 'llm_failed'`, `assert [(0.6, 'NEW')] == []`)

- [ ] **Step 3: Implement**

W `evaluate`, ścieżka pustego codebooka: zamień linię `meta = {"decision_path": "empty_codebook", ...}` na:

```python
            meta = {
                "decision_path": "empty_codebook", "max_sim": None,
                "llm_recommendation": None, "judge_failed": False, "judge_error": None,
            }
```

Zastąp blok od `try:` (wywołanie `_get_llm_recommendation`) do końcowego `return output, top_k_results, meta`:

```python
        judge_error: Optional[str] = None
        try:
            output = self._get_llm_recommendation(
                candidate=candidate,
                top_k_with_defs=top_k_with_defs,
            )
        except Exception as e:
            judge_error = str(e)
            logger.error(f"[ERROR] Comparator LLM failed for '{candidate.ic_name}': {e}")
            output = ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning=f"LLM comparison failed ({e}); defaulting to NEW for human review.",
            )
        judge_failed = judge_error is not None

        # Eval mode: record (top-1 cosine, verdict) for AUC — merge/new only, and
        # never from a failed judge call (a fallback NEW is not a verdict).
        if (
            self.eval_mode
            and not judge_failed
            and output.recommendation in (
                ComparatorRecommendation.MERGE,
                ComparatorRecommendation.NEW,
            )
        ):
            self.eval_pairs.append((max_sim, output.recommendation.value))

        meta = {
            "decision_path": "llm_failed" if judge_failed else "llm",
            "judge_failed": judge_failed,
            "judge_error": judge_error,
            "max_sim": max_sim,
            "llm_recommendation": output.recommendation.value,
        }
        return output, top_k_results, meta
```

Sprawdź, że `Optional` jest zaimportowane z `typing` na górze pliku. Jeśli nie, dodaj je do istniejącego importu. W docstringu `evaluate`, w opisie `meta`, dopisz linie:

```
                "decision_path": "empty_codebook" | "llm" | "llm_failed",
                "judge_failed": bool,
                "judge_error": str | None,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_codebook_comparator.py tests/test_leaderboard_phase3.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/codebook_comparator.py tests/test_codebook_comparator.py
git commit -m "fix(comparator): flag judge failures, keep them out of AUC pairs

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Orchestrator — rozwiązywanie celu MERGE i status sędziego

**Files:**
- Modify: `src/extraction/orchestrator.py` (`decision_paths` w `__init__` ≈ l. 220; `summary` w `run()`; gałąź bez HIL w `_decide_and_apply` ≈ l. 630-634; rekord ≈ l. 685-705; nowy `_resolve_merge_target`)
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `meta["judge_failed"]`, `meta["decision_path"] == "llm_failed"` (Task 4)
- Produces:
  - `Layer1Orchestrator._resolve_merge_target(name: Optional[str], top_k: List[SimilarityResult]) -> Optional[int]` (1-based)
  - `summary["decision_paths"]` zawiera klucz `"llm_failed"`
  - `summary["merge_target_unresolved"]: int`, `summary["judge_merge_verdicts"]: int`
  - rekord `candidate` z `"judge_failed"`, `"merge_target_name"`, `"merge_target_resolved"`

- [ ] **Step 1: Write the failing tests**

W `tests/test_orchestrator.py` dodaj importy:

```python
from src.core.db import InitialCodeRepo, VerbatimQuoteRepo
from src.core.embeddings import SimilarityResult
from src.core.models import ICStatus, InitialCode
```

**Najpierw przenieś fixture'y na poziom modułu.** Fixture'y `test_segment` i `mock_orchestrator` są dziś metodami klasy `TestLayer1Orchestrator`, więc nowe klasy ich nie widzą. Dziedziczenie po tej klasie odpaliłoby jej testy drugi raz. Wytnij obie funkcje z klasy i wklej je nad `class TestLayer1Orchestrator:` jako funkcje modułowe: usuń parametr `self` i jeden poziom wcięcia, a dekoratory `@pytest.fixture` i ciała zostaw bez zmian. Testy w `TestLayer1Orchestrator` dalej ich używają przez nazwę argumentu.

W fixture `mock_orchestrator`, przed `return orch`, dodaj (NEW potrzebuje prawdziwego IC do zapisu w DB):

```python
        def fake_embed_ic(ic):
            ic.embedding_json = [0.1, 0.2, 0.3]
            return ic
        orch.embedding_service.embed_ic.side_effect = fake_embed_ic
        orch.embedding_service.embed_quote.side_effect = lambda q: q
```

Dopisz nową klasę na końcu pliku:

```python
class TestMergeTargetResolution:
    TOP_K = [
        SimilarityResult(ic_id="ic_a", ic_name="delivery_speed", similarity=0.90),
        SimilarityResult(ic_id="ic_b", ic_name="Delivery_Delay", similarity=0.80),
    ]

    def test_resolve_exact(self):
        assert Layer1Orchestrator._resolve_merge_target("delivery_speed", self.TOP_K) == 1

    def test_resolve_second(self):
        assert Layer1Orchestrator._resolve_merge_target("Delivery_Delay", self.TOP_K) == 2

    def test_resolve_strips_and_ignores_case(self):
        assert Layer1Orchestrator._resolve_merge_target("  delivery_delay \n", self.TOP_K) == 2

    def test_resolve_outside_shortlist(self):
        assert Layer1Orchestrator._resolve_merge_target("price_complaint", self.TOP_K) is None

    def test_resolve_none_and_empty(self):
        assert Layer1Orchestrator._resolve_merge_target(None, self.TOP_K) is None
        assert Layer1Orchestrator._resolve_merge_target("", self.TOP_K) is None
        assert Layer1Orchestrator._resolve_merge_target("delivery_speed", []) is None


class TestAutoMergeTarget:
    """--no-hil: MERGE goes where the judge pointed, not to top-1."""

    def _seed_two_ics(self, db):
        repo = InitialCodeRepo(db)
        repo.insert(InitialCode(id="ic_a", name="delivery_speed",
                                definition="Complaints about delivery speed",
                                status=ICStatus.ACTIVE))
        repo.insert(InitialCode(id="ic_b", name="delivery_delay",
                                definition="Complaints about delivery delays",
                                status=ICStatus.ACTIVE))

    def _candidate(self, test_segment):
        q = "dostawa trwała zbyt długo"
        s = test_segment.canonical_text.index(q)
        return ICCandidate(ic_name="slow_delivery", definition="Delivery took too long",
                           quote_text=q, span_start=s, span_end=s + len(q), confidence=0.8)

    def _judge(self, orch, target_name, path="llm", failed=False):
        top_k = [
            SimilarityResult(ic_id="ic_a", ic_name="delivery_speed", similarity=0.9),
            SimilarityResult(ic_id="ic_b", ic_name="delivery_delay", similarity=0.8),
        ]
        rec = ComparatorRecommendation.NEW if failed else ComparatorRecommendation.MERGE
        orch.comparator.evaluate.return_value = (
            ComparatorOutput(recommendation=rec, merge_target_name=target_name,
                             reasoning="judge"),
            top_k,
            {"decision_path": path, "max_sim": 0.9,
             "llm_recommendation": rec.value, "judge_failed": failed,
             "judge_error": "boom" if failed else None},
        )

    def test_merge_goes_to_judge_named_target(self, mock_orchestrator, db, test_segment):
        self._seed_two_ics(db)
        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [self._candidate(test_segment)]}
        self._judge(mock_orchestrator, "delivery_delay")
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        vq = VerbatimQuoteRepo(db)
        assert len(vq.get_all_for_ic("ic_b")) == 1
        assert len(vq.get_all_for_ic("ic_a")) == 0
        assert result["merged"] == 1
        assert result["judge_merge_verdicts"] == 1
        assert result["merge_target_unresolved"] == 0
        rec = mock_orchestrator.reasoning_logger.log_candidate.call_args.args[0]
        assert rec["merge_target_name"] == "delivery_delay"
        assert rec["merge_target_resolved"] == "delivery_delay"
        assert rec["judge_failed"] is False

    def test_unresolved_target_falls_back_to_new(self, mock_orchestrator, db, test_segment):
        self._seed_two_ics(db)
        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [self._candidate(test_segment)]}
        self._judge(mock_orchestrator, "price_complaint")
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["merged"] == 0
        assert result["new_ics_created"] == 1
        assert result["merge_target_unresolved"] == 1
        assert result["judge_merge_verdicts"] == 1
        assert result["decision_paths"]["llm"] == 1
        rec = mock_orchestrator.reasoning_logger.log_candidate.call_args.args[0]
        assert rec["merge_target_name"] == "price_complaint"
        assert rec["merge_target_resolved"] is None
        assert rec["final_action"] == "new"

    def test_judge_failure_counted_as_llm_failed(self, mock_orchestrator, db, test_segment):
        self._seed_two_ics(db)
        mock_orchestrator.coder_agent.process_batch.return_value = {
            test_segment.id: [self._candidate(test_segment)]}
        self._judge(mock_orchestrator, None, path="llm_failed", failed=True)
        mock_orchestrator.reasoning_logger = MagicMock()

        result = mock_orchestrator.run([test_segment], enable_hil=False)

        assert result["decision_paths"]["llm_failed"] == 1
        assert result["decision_paths"]["llm"] == 0
        assert result["new_ics_created"] == 1
        assert result["judge_merge_verdicts"] == 0
        rec = mock_orchestrator.reasoning_logger.log_candidate.call_args.args[0]
        assert rec["judge_failed"] is True
        assert rec["decision_path"] == "llm_failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py -v -k "MergeTarget or AutoMerge"`
Expected: FAIL (`AttributeError: ... has no attribute '_resolve_merge_target'`, `KeyError: 'judge_merge_verdicts'`; w `test_merge_goes_to_judge_named_target` cytat ląduje w `ic_a`)

- [ ] **Step 3: Implement**

1. W `__init__` zamień inicjalizację `self.decision_paths` na:

```python
        self.decision_paths: Dict[str, int] = {
            "empty_codebook": 0,
            "llm": 0,
            "llm_failed": 0,   # judge call raised → fallback NEW (P0: judge_failure_rate)
        }
```

2. W słowniku `summary` w `run()`, po wpisie `"accepted_quotes_total": 0,` (Task 3), dodaj:

```python
            # Judge reliability (P0). merge_target_unresolved: --no-hil MERGE whose
            # merge_target_name is not on the shortlist → fallback NEW.
            "merge_target_unresolved": 0,
            "judge_merge_verdicts": 0,
```

3. Dodaj metodę statyczną w sekcji `# ── Small span helpers` (po `_count_accepted_quote`):

```python
    @staticmethod
    def _resolve_merge_target(
        merge_target_name: Optional[str],
        top_k: List[SimilarityResult],
    ) -> Optional[int]:
        """Map the judge's merge_target_name onto a 1-based top_k index.

        Exact match first, then stripped + case-insensitive. None when the name is
        missing or not on the shortlist (the judge may only merge into codes it
        was shown).
        """
        if not merge_target_name or not top_k:
            return None
        for i, sim in enumerate(top_k, 1):
            if sim.ic_name == merge_target_name:
                return i
        wanted = merge_target_name.strip().lower()
        for i, sim in enumerate(top_k, 1):
            if sim.ic_name.strip().lower() == wanted:
                return i
        return None
```

4. W `_decide_and_apply`, bezpośrednio po bloku aktualizującym `self.decision_paths`, dodaj:

```python
        if comp_output.recommendation == ComparatorRecommendation.MERGE:
            summary["judge_merge_verdicts"] += 1
```

Zweryfikuj, że `ComparatorRecommendation` jest importowane w `orchestrator.py` (`grep -n "ComparatorRecommendation" src/extraction/orchestrator.py`). Jeśli nie, dopisz je do istniejącego importu z `src.core.models`.

5. Zastąp gałąź `else:` (HIL wyłączony):

```python
        else:
            action = comp_output.recommendation.value[0]  # N, M, R → first char
            target_idx = None
            notes = "auto-accepted (HIL disabled)"
            if action == "M":
                target_idx = self._resolve_merge_target(
                    comp_output.merge_target_name, top_k
                )
                if target_idx is None:
                    # Judge named a target outside the shortlist (or none) — do not
                    # guess. Fall back to NEW and count it (P0).
                    action = "N"
                    notes = "auto-accepted; MERGE target unresolved → fallback NEW"
                    summary["merge_target_unresolved"] += 1
```

6. W słowniku `record` w `_decide_and_apply`, po `"judge_reasoning": comp_output.reasoning,` dodaj:

```python
                "judge_failed": decision_meta.get("judge_failed", False),
                "merge_target_name": comp_output.merge_target_name,
                "merge_target_resolved": (
                    top_k[target_idx - 1].ic_name
                    if result == "merge" and target_idx and top_k else None
                ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_second_pass.py -v`
Expected: PASS (także `test_existing_match_still_goes_through_judge`: MERGE z pustym `top_k` to teraz nierozwiązany cel → NEW, a fixture ma już `fake_embed_ic`).

- [ ] **Step 5: Commit**

```bash
git add src/extraction/orchestrator.py tests/test_orchestrator.py
git commit -m "fix(orchestrator): honour judge merge target in --no-hil, track judge failures

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Twarda weryfikacja cytatu przed insertem

**Files:**
- Modify: `src/extraction/orchestrator.py` (`_apply_new` ≈ l. 906-970, `_apply_merge` ≈ l. 973-1025; dwa nowe helpery)
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: —
- Produces:
  - `Layer1Orchestrator._build_verified_quote(candidate: ICCandidate, segment_id: str, ic_id: str) -> VerbatimQuote`, które przy brakującym segmencie albo niezgodnym spanie rzuca `RuntimeError`
  - `Layer1Orchestrator._insert_quote(quote: VerbatimQuote, defer_embed: bool) -> VerbatimQuote`

- [ ] **Step 1: Write the failing tests**

Dopisz na końcu `tests/test_orchestrator.py`:

```python
class TestHardQuoteVerification:
    """A quote whose span does not match canonical text must never be persisted."""

    def _bad_candidate(self):
        # quote_text is real, but the span points at the wrong place
        return ICCandidate(ic_name="bad_span", definition="Span does not match text",
                           quote_text="dostawa trwała zbyt długo",
                           span_start=0, span_end=25, confidence=0.8)

    def _comp(self):
        return ComparatorOutput(recommendation=ComparatorRecommendation.NEW,
                                reasoning="test")

    def test_apply_new_raises_and_persists_nothing(self, mock_orchestrator, db):
        with pytest.raises(RuntimeError, match="Span verification failed"):
            mock_orchestrator._apply_new(self._bad_candidate(), "seg_test",
                                         self._comp(), None)
        assert InitialCodeRepo(db).get_all_active() == []
        assert VerbatimQuoteRepo(db).get_all_for_segment("seg_test") == []
        mock_orchestrator.embedding_service.embed_ic.assert_not_called()

    def test_apply_new_missing_segment_raises(self, mock_orchestrator, db, test_segment):
        q = "dostawa trwała zbyt długo"
        s = test_segment.canonical_text.index(q)
        cand = ICCandidate(ic_name="orphan", definition="Segment does not exist",
                           quote_text=q, span_start=s, span_end=s + len(q), confidence=0.8)
        with pytest.raises(RuntimeError, match="not found"):
            mock_orchestrator._apply_new(cand, "seg_missing", self._comp(), None)
        assert InitialCodeRepo(db).get_all_active() == []

    def test_apply_merge_raises_and_persists_nothing(self, mock_orchestrator, db):
        InitialCodeRepo(db).insert(InitialCode(
            id="ic_t", name="delivery", definition="Delivery complaints",
            status=ICStatus.ACTIVE))
        with pytest.raises(RuntimeError, match="Span verification failed"):
            mock_orchestrator._apply_merge(self._bad_candidate(), "seg_test", "ic_t",
                                           self._comp(), None)
        assert VerbatimQuoteRepo(db).get_all_for_ic("ic_t") == []

    def test_valid_quote_is_verified_on_insert(self, mock_orchestrator, db, test_segment):
        q = "dostawa trwała zbyt długo"
        s = test_segment.canonical_text.index(q)
        cand = ICCandidate(ic_name="slow_delivery", definition="Delivery took too long",
                           quote_text=q, span_start=s, span_end=s + len(q), confidence=0.8)
        ic, quote = mock_orchestrator._apply_new(cand, "seg_test", self._comp(), None,
                                                 defer_quote_embed=True)
        assert quote.is_verified is True
        assert VerbatimQuoteRepo(db).get_all_for_ic(ic.id)[0].span_start == s
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py -v -k HardQuote`
Expected: FAIL (`DID NOT RAISE <class 'RuntimeError'>`)

- [ ] **Step 3: Implement**

Dodaj dwa helpery bezpośrednio przed `_apply_new` (w sekcji `# ── Decision Application`):

```python
    def _build_verified_quote(
        self,
        candidate: ICCandidate,
        segment_id: str,
        ic_id: str,
    ) -> VerbatimQuote:
        """Build the VerbatimQuote for a decision and hard-verify its span.

        Runs BEFORE any insert. After the grounding gate a mismatch is impossible
        without an upstream bug, so it fails loudly instead of persisting a
        silently unverified quote (P0-3).
        """
        quote = VerbatimQuote(
            ic_id=ic_id,
            segment_id=segment_id,
            quote_text=candidate.quote_text,
            span_start=candidate.span_start,
            span_end=candidate.span_end,
            sentiment=candidate.sentiment.value if candidate.sentiment else None,
        )
        segment = self.segment_repo.get_by_id(segment_id)
        if segment is None:
            raise RuntimeError(
                f"Segment {segment_id} not found while persisting quote for IC "
                f"'{candidate.ic_name}' — span cannot be verified."
            )
        if not quote.verify(segment.canonical_text):
            raise RuntimeError(
                f"Span verification failed for IC '{candidate.ic_name}' in segment "
                f"{segment_id}: canonical[{quote.span_start}:{quote.span_end}] != "
                f"quote_text. This indicates a grounding bug upstream."
            )
        return quote

    def _insert_quote(self, quote: VerbatimQuote, defer_embed: bool) -> VerbatimQuote:
        """Insert a verified quote, embedding it now unless the caller batches later."""
        if not defer_embed:
            quote = self.embedding_service.embed_quote(quote)
        self.quote_repo.insert(quote)
        return quote
```

W `_apply_new` zastąp wszystko od `# Embed IC (embed-on-write) — always immediate` do końca bloku `if defer_quote_embed: ... else: ...` (tuż przed `# Log decision`):

```python
        # Verify the quote BEFORE any insert — a failure leaves no orphan IC.
        quote = self._build_verified_quote(candidate, segment_id, ic.id)

        # Embed IC (embed-on-write) — always immediate
        ic = self.embedding_service.embed_ic(ic)

        # Persist IC, then its quote
        self.ic_repo.insert(ic)
        quote = self._insert_quote(quote, defer_quote_embed)
```

W `_apply_merge` zastąp wszystko od `# Create verbatim quote for the existing IC (propagate sentiment)` do końca bloku `if defer_quote_embed: ... else: ...` (tuż przed `# Log decision`):

```python
        quote = self._build_verified_quote(candidate, segment_id, target_ic.id)
        quote = self._insert_quote(quote, defer_quote_embed)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_second_pass.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/extraction/orchestrator.py tests/test_orchestrator.py
git commit -m "fix(orchestrator): hard-verify quote spans before any insert

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Metryki L1, spłaszczenie do rejestru i podsumowanie CLI

**Files:**
- Modify: `src/eval/l1_metrics.py` (docstring modułu, `compute_all`, `compute_grounding` → `compute_span_integrity`, `compute_quote_hallucination_rate`, dwie nowe metody)
- Modify: `src/extraction/pipeline.py` (`_METRIC_DIRECTIONS` ≈ l. 47, wywołanie `compute_all` ≈ l. 198, `_flatten_metrics` ≈ l. 318)
- Modify: `scripts/run_pipeline.py:161-165` i okolice (wydruk)
- Test: `tests/test_l1_metrics.py`, `tests/test_leaderboard_phase3.py`

**Interfaces:**
- Consumes (klucze summary z Task 3 i 5): `decision_paths`, `merge_target_unresolved`, `judge_merge_verdicts`, `grounding_drop_classes`, `pass2_stats["drop_classes"]`, `ambiguous_occurrences`, `accepted_quotes_total`
- Produces:
  - `L1MetricsEngine.compute_span_integrity() -> {"total_quotes", "verified", "failed", "span_integrity", "failures"}`
  - `L1MetricsEngine.compute_judge_reliability(decision_paths: Dict[str, int], merge_target_unresolved: int, judge_merge_verdicts: int) -> {"judge_failure_rate", "judge_failed", "judge_calls", "merge_target_unresolved", "merge_target_unresolved_rate", "judge_merge_verdicts"}`
  - `L1MetricsEngine.compute_ambiguous_occurrences(ambiguous_occurrences: Dict[str, int], accepted_quotes_total: int) -> {"ambiguous_occurrence_rate", "first_free", "first_fallback", "accepted_quotes_total"}`
  - `compute_quote_hallucination_rate(total_dropped, total_valid_candidates, drop_classes=None, pass2_drop_classes=None)` zwraca dodatkowo `"drop_classes"`, `"pass2_drop_classes"`, `"unmatched_quote_rate"`
  - klucze wyniku `compute_all`: `"span_integrity"` (zamiast `"grounding"`), `"judge_reliability"`, `"ambiguous_occurrences"`
  - klucze rejestru: `span_integrity`, `judge_failure_rate`, `merge_target_unresolved_rate`, `unmatched_quote_rate`, `ambiguous_occurrence_rate` (`grounding_rate` znika)

- [ ] **Step 1: Write the failing tests**

W `tests/test_l1_metrics.py` zastąp klasę `TestGrounding`:

```python
class TestSpanIntegrity:
    def test_all_quotes_verified(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_span_integrity()
        assert r["total_quotes"] == 2
        assert r["verified"] == 2
        assert r["span_integrity"] == 1.0
        assert r["failed"] == 0

    def test_empty_db_is_one(self, engine):
        assert engine.compute_span_integrity()["span_integrity"] == 1.0
```

W `TestQuoteHallucinationRate` dopisz:

```python
    def test_drop_class_breakdown(self, engine):
        r = engine.compute_quote_hallucination_rate(
            total_dropped=4, total_valid_candidates=6,
            drop_classes={"ellipsis_stitch": 3, "unmatched": 1},
            pass2_drop_classes={"case": 1},
        )
        assert r["quote_hallucination_rate"] == 0.4
        assert r["unmatched_quote_rate"] == 0.1          # 1 / (6+4)
        assert r["drop_classes"] == {"ellipsis_stitch": 3, "unmatched": 1}
        assert r["pass2_drop_classes"] == {"case": 1}

    def test_unmatched_rate_zero_without_candidates(self, engine):
        r = engine.compute_quote_hallucination_rate(0, 0, drop_classes={})
        assert r["unmatched_quote_rate"] == 0.0
```

Dopisz nowe klasy:

```python
class TestJudgeReliability:
    def test_rates(self, engine):
        r = engine.compute_judge_reliability(
            decision_paths={"empty_codebook": 1, "llm": 8, "llm_failed": 2},
            merge_target_unresolved=1,
            judge_merge_verdicts=4,
        )
        assert r["judge_failure_rate"] == 0.2            # 2 / (8+2)
        assert r["judge_failed"] == 2
        assert r["judge_calls"] == 10
        assert r["merge_target_unresolved_rate"] == 0.25 # 1 / 4

    def test_zero_denominators(self, engine):
        r = engine.compute_judge_reliability({"empty_codebook": 3}, 0, 0)
        assert r["judge_failure_rate"] == 0.0
        assert r["merge_target_unresolved_rate"] == 0.0


class TestAmbiguousOccurrences:
    def test_rate(self, engine):
        r = engine.compute_ambiguous_occurrences(
            {"first_free": 2, "first_fallback": 1}, accepted_quotes_total=10,
        )
        assert r["ambiguous_occurrence_rate"] == 0.3
        assert r["first_free"] == 2 and r["first_fallback"] == 1

    def test_zero_accepted(self, engine):
        r = engine.compute_ambiguous_occurrences({}, accepted_quotes_total=0)
        assert r["ambiguous_occurrence_rate"] == 0.0
```

W `TestComputeAll.test_returns_expected_keys` zamień `"grounding",` na `"span_integrity", "judge_reliability", "ambiguous_occurrences",` i dopisz na końcu testu:

```python
        assert "grounding" not in r
```

Dopisz test przepływu kwargs:

```python
    def test_compute_all_passes_p0_counters(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_all(
            its_history=[],
            total_dropped=1, total_candidates=3,
            decision_paths={"llm": 3, "llm_failed": 1},
            merge_target_unresolved=1, judge_merge_verdicts=2,
            grounding_drop_classes={"unmatched": 1},
            pass2_stats={"drop_classes": {"case": 1}},
            ambiguous_occurrences={"first_free": 1, "first_fallback": 0},
            accepted_quotes_total=4,
        )
        assert r["judge_reliability"]["judge_failure_rate"] == 0.25
        assert r["judge_reliability"]["merge_target_unresolved_rate"] == 0.5
        assert r["quote_hallucination_rate"]["unmatched_quote_rate"] == 0.25
        assert r["quote_hallucination_rate"]["pass2_drop_classes"] == {"case": 1}
        assert r["ambiguous_occurrences"]["ambiguous_occurrence_rate"] == 0.25
```

W `tests/test_leaderboard_phase3.py` dodaj import `from src.extraction.pipeline import EQDPipeline` i nową klasę:

```python
class TestFlattenMetrics:
    def test_p0_keys_and_rename(self):
        quality = {
            "span_integrity": {"span_integrity": 1.0},
            "judge_reliability": {"judge_failure_rate": 0.1,
                                  "merge_target_unresolved_rate": 0.2},
            "quote_hallucination_rate": {"quote_hallucination_rate": 0.3,
                                         "unmatched_quote_rate": 0.05},
            "ambiguous_occurrences": {"ambiguous_occurrence_rate": 0.0},
        }
        metrics, directions = EQDPipeline._flatten_metrics(quality)
        assert metrics["span_integrity"] == 1.0
        assert metrics["judge_failure_rate"] == 0.1
        assert metrics["merge_target_unresolved_rate"] == 0.2
        assert metrics["unmatched_quote_rate"] == 0.05
        assert metrics["ambiguous_occurrence_rate"] == 0.0
        assert "grounding_rate" not in metrics
        assert directions["span_integrity"] == "more"
        for k in ("judge_failure_rate", "merge_target_unresolved_rate",
                  "unmatched_quote_rate", "ambiguous_occurrence_rate"):
            assert directions[k] == "less"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_l1_metrics.py tests/test_leaderboard_phase3.py -v`
Expected: FAIL (`AttributeError: 'L1MetricsEngine' object has no attribute 'compute_span_integrity'`, `KeyError: 'span_integrity'`)

- [ ] **Step 3: Implement metrics**

W `src/eval/l1_metrics.py`:

1. W docstringu modułu zamień linię `  - Grounding — are all verbatim quotes verifiable against canonical text?` na:

```
  - Span Integrity — sanity check: every persisted quote still verifies against
    canonical text (1.0 expected; < 1.0 = bug, not a model property)
  - Quote Hallucination Rate — plus drop-class breakdown (normalized_ws / case /
    ellipsis_stitch / unmatched) and unmatched_quote_rate
  - Ambiguous Occurrence Rate — accepted quotes whose phrase repeats in the review
  - Judge Reliability — judge_failure_rate + merge_target_unresolved_rate
```

2. Zmień nazwę `compute_grounding` na `compute_span_integrity`. Zaktualizuj docstring (klucz `"span_integrity": float` zamiast `"grounding_rate": float` i zdanie „Sanity check — after the hard grounding gate this must be 1.0; anything lower indicates a bug.”). Końcówkę metody zamień na:

```python
        rate = verified / total if total > 0 else 1.0

        self.qm_repo.insert(QualityMetric(
            metric_type=MetricType.GROUNDING,
            value=rate,
        ))

        result = {
            "total_quotes": total,
            "verified": verified,
            "failed": len(failures),
            "span_integrity": rate,
            "failures": failures,
        }
        if failures:
            logger.error(
                f"Span integrity {verified}/{total} ({rate:.1%}) — persisted quotes "
                f"fail verification; this is a pipeline bug: {failures[:3]}"
            )
        else:
            logger.info(f"Span integrity: {verified}/{total} ({rate:.1%})")
        return result
```

3. Zastąp `compute_quote_hallucination_rate`:

```python
    def compute_quote_hallucination_rate(
        self,
        total_dropped: int = 0,
        total_valid_candidates: int = 0,
        drop_classes: Optional[Dict[str, int]] = None,
        pass2_drop_classes: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Quote Hallucination Rate (v2 Phase 1): raw faithfulness of the evidence.

        Formula: hallucinated / (grounded_candidates + hallucinated)   [pass 1]

        Spans are computed by the system (the model never emits offsets), so the
        only way a quote can fail is by not being a verbatim substring of the
        canonical text. Nothing is repaired, so this rate is not circular.

        P0 breakdown: drop_classes says HOW the failed quotes missed
        (normalized_ws / case / ellipsis_stitch = regeneration of real text;
        unmatched = paraphrase or fabrication). unmatched_quote_rate isolates the
        latter. pass2_drop_classes is reported alongside, outside the rate.

        Direction: less = better.
        """
        drop_classes = dict(drop_classes or {})
        pass2_drop_classes = dict(pass2_drop_classes or {})
        total_raw = total_valid_candidates + total_dropped
        rate = total_dropped / total_raw if total_raw > 0 else 0.0
        unmatched = drop_classes.get("unmatched", 0)
        unmatched_rate = unmatched / total_raw if total_raw > 0 else 0.0

        if total_raw > 0:
            self.qm_repo.insert(QualityMetric(
                metric_type=MetricType.QUOTE_HALLUCINATION_RATE,
                value=rate,
            ))

        logger.info(
            f"Quote hallucination rate: {rate:.1%} ({total_dropped}/{total_raw} candidates); "
            f"classes={drop_classes}"
        )
        return {
            "quote_hallucination_rate": round(rate, 4),
            "hallucinated": total_dropped,
            "total_raw_candidates": total_raw,
            "drop_classes": drop_classes,
            "pass2_drop_classes": pass2_drop_classes,
            "unmatched_quote_rate": round(unmatched_rate, 4),
        }

    def compute_judge_reliability(
        self,
        decision_paths: Dict[str, int],
        merge_target_unresolved: int = 0,
        judge_merge_verdicts: int = 0,
    ) -> Dict[str, Any]:
        """
        Judge reliability (P0). Never a gate — a run with failures is flagged, not
        stopped.

        judge_failure_rate = llm_failed / (llm + llm_failed): judge calls that raised
          after retries and fell back to NEW. Those calls produce no AUC pair.
        merge_target_unresolved_rate = unresolved / MERGE verdicts: --no-hil MERGEs
          whose merge_target_name was not on the shortlist (fallback NEW).

        Direction: less = better for both.
        """
        failed = int(decision_paths.get("llm_failed", 0))
        calls = int(decision_paths.get("llm", 0)) + failed
        failure_rate = failed / calls if calls > 0 else 0.0
        unresolved_rate = (
            merge_target_unresolved / judge_merge_verdicts
            if judge_merge_verdicts > 0 else 0.0
        )
        if failed:
            logger.warning(
                f"Judge failures: {failed}/{calls} ({failure_rate:.1%}) — run is unreliable"
            )
        return {
            "judge_failure_rate": round(failure_rate, 4),
            "judge_failed": failed,
            "judge_calls": calls,
            "merge_target_unresolved": int(merge_target_unresolved),
            "merge_target_unresolved_rate": round(unresolved_rate, 4),
            "judge_merge_verdicts": int(judge_merge_verdicts),
        }

    def compute_ambiguous_occurrences(
        self,
        ambiguous_occurrences: Dict[str, int],
        accepted_quotes_total: int = 0,
    ) -> Dict[str, Any]:
        """
        Share of gate-passing quotes whose phrase occurs 2+ times in the review, so
        the span had to be chosen (first_free / first_fallback). Direction: less.
        """
        first_free = int(ambiguous_occurrences.get("first_free", 0))
        first_fallback = int(ambiguous_occurrences.get("first_fallback", 0))
        n = first_free + first_fallback
        rate = n / accepted_quotes_total if accepted_quotes_total > 0 else 0.0
        return {
            "ambiguous_occurrence_rate": round(rate, 4),
            "first_free": first_free,
            "first_fallback": first_fallback,
            "accepted_quotes_total": int(accepted_quotes_total),
        }
```

4. W `compute_all`: w docstringu dopisz nowe kwargs (`decision_paths`, `merge_target_unresolved`, `judge_merge_verdicts`, `grounding_drop_classes`, `ambiguous_occurrences`, `accepted_quotes_total`). Zamień `results["grounding"] = self.compute_grounding()` na `results["span_integrity"] = self.compute_span_integrity()`. Wywołanie `compute_quote_hallucination_rate` zamień na:

```python
        results["quote_hallucination_rate"] = self.compute_quote_hallucination_rate(
            total_dropped=total_dropped,
            total_valid_candidates=total_candidates,
            drop_classes=kwargs.get("grounding_drop_classes", {}),
            pass2_drop_classes=kwargs.get("pass2_stats", {}).get("drop_classes", {}),
        )
        results["ambiguous_occurrences"] = self.compute_ambiguous_occurrences(
            kwargs.get("ambiguous_occurrences", {}),
            kwargs.get("accepted_quotes_total", 0),
        )
```

a przed blokiem `# ── EMBEDDING EVALUATION (Phase 3)` dodaj:

```python
        # ── JUDGE RELIABILITY (P0) ────────────────────────────────────────
        results["judge_reliability"] = self.compute_judge_reliability(
            kwargs.get("decision_paths", {}),
            kwargs.get("merge_target_unresolved", 0),
            kwargs.get("judge_merge_verdicts", 0),
        )
```

- [ ] **Step 4: Wire pipeline and flatten**

W `src/extraction/pipeline.py`:

1. W `_METRIC_DIRECTIONS` zamień `"grounding_rate": "more",` na:

```python
    "span_integrity": "more",
    # P0 — judge reliability + quote diagnostics
    "judge_failure_rate": "less",
    "merge_target_unresolved_rate": "less",
    "unmatched_quote_rate": "less",
    "ambiguous_occurrence_rate": "less",
```

2. W wywołaniu `self.metrics_engine.compute_all(...)`, po `auc_pairs=layer1_summary.get("auc_pairs", []),` dodaj:

```python
            # P0 — judge reliability + grounding diagnostics
            decision_paths=layer1_summary.get("decision_paths", {}),
            merge_target_unresolved=layer1_summary.get("merge_target_unresolved", 0),
            judge_merge_verdicts=layer1_summary.get("judge_merge_verdicts", 0),
            grounding_drop_classes=layer1_summary.get("grounding_drop_classes", {}),
            ambiguous_occurrences=layer1_summary.get("ambiguous_occurrences", {}),
            accepted_quotes_total=layer1_summary.get("accepted_quotes_total", 0),
```

3. W `_flatten_metrics` zamień `"grounding_rate": _get(["grounding", "grounding_rate"]),` na:

```python
            "span_integrity": _get(["span_integrity", "span_integrity"]),
            # P0 — judge reliability + quote diagnostics
            "judge_failure_rate": _get(["judge_reliability", "judge_failure_rate"]),
            "merge_target_unresolved_rate": _get(["judge_reliability", "merge_target_unresolved_rate"]),
            "unmatched_quote_rate": _get(["quote_hallucination_rate", "unmatched_quote_rate"]),
            "ambiguous_occurrence_rate": _get(["ambiguous_occurrences", "ambiguous_occurrence_rate"]),
```

- [ ] **Step 5: Update CLI summary**

W `scripts/run_pipeline.py` zastąp blok:

```python
    grounding = l3.get("grounding", {})
    if grounding:
        print(f"  Grounding:    {grounding.get('grounding_rate', 0):.1%} "
              f"({grounding.get('verified', 0)}/{grounding.get('total_quotes', 0)} quotes)")
```

na:

```python
    integrity = l3.get("span_integrity", {})
    if integrity:
        flag = "" if integrity.get("span_integrity", 1.0) == 1.0 else "⚠ BUG "
        print(f"  {flag}Span integrity: {integrity.get('span_integrity', 0):.1%} "
              f"({integrity.get('verified', 0)}/{integrity.get('total_quotes', 0)} quotes)")

    judge = l3.get("judge_reliability", {})
    if judge:
        flag = "⚠ " if judge.get("judge_failed", 0) else ""
        print(f"  {flag}Judge failures: {judge.get('judge_failure_rate', 0):.1%} "
              f"({judge.get('judge_failed', 0)}/{judge.get('judge_calls', 0)} calls); "
              f"merge target unresolved: {judge.get('merge_target_unresolved', 0)}"
              f"/{judge.get('judge_merge_verdicts', 0)}")
```

Po istniejącym wydruku `Quote hallucination rate` (wewnątrz tego samego `if hall:`) dodaj:

```python
        classes = hall.get("drop_classes", {})
        if classes:
            print(f"    drop classes: {classes}  "
                  f"(unmatched rate {hall.get('unmatched_quote_rate', 0):.1%})")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: wszystkie PASS. Jeśli `tests/test_db.py:308` (`repo.get_by_type("grounding")`) padnie: nie powinien, bo `MetricType.GROUNDING` jest nadal zapisywany. Zbadaj przyczynę, zanim cokolwiek zmienisz.

- [ ] **Step 7: Commit**

```bash
git add src/eval/l1_metrics.py src/extraction/pipeline.py scripts/run_pipeline.py tests/test_l1_metrics.py tests/test_leaderboard_phase3.py
git commit -m "feat(metrics): judge reliability, drop-class breakdown, span_integrity rename

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Rejestr i raport — oddzielenie wersji i znacznik awarii sędziego

**Files:**
- Modify: `src/leaderboard/registry.py:31` (`PIPELINE_VERSION`), `load_matrix` (≈ l. 184-226)
- Modify: `src/leaderboard/report.py` (`render_matrix_markdown`)
- Modify: `scripts/run_leaderboard.py:104-110` (bez zmian w logice; tylko sprawdź, że wywołanie domyślne działa)
- Test: `tests/test_leaderboard_registry.py`, `tests/test_leaderboard_phase3.py`

**Interfaces:**
- Consumes: metryka `judge_failure_rate` w `run_metrics` (Task 7)
- Produces:
  - `PIPELINE_VERSION = "v2-p0"`
  - `RunRegistry.load_matrix(pipeline_version: Optional[str] = PIPELINE_VERSION) -> {"columns", "directions", "cells", "pipeline_version", "excluded_runs"}`
  - `render_matrix_markdown` oznacza ` ⚠` kolumny, w których dowolna wartość `judge_failure_rate` > 0, dodaje przypis i (gdy matryca ma `pipeline_version`) linię nagłówka

- [ ] **Step 1: Write the failing tests**

Dopisz do `TestRunRegistry` w `tests/test_leaderboard_registry.py`:

```python
    def test_matrix_filters_to_current_version(self, registry):
        from src.leaderboard.registry import PIPELINE_VERSION
        old = _manifest(run_id="run_old", gen="gen-a")
        old.pipeline_version = "v2-phase2"
        registry.register_run(old)
        registry.register_run(_manifest(run_id="run_new", gen="gen-a"))
        registry.record_metrics("run_old", {"merge_rate": 0.9})
        registry.record_metrics("run_new", {"merge_rate": 0.1})

        matrix = registry.load_matrix()
        assert PIPELINE_VERSION == "v2-p0"
        assert matrix["pipeline_version"] == "v2-p0"
        assert matrix["cells"]["merge_rate"]["gen-a×emb-a"] == [0.1]
        assert matrix["excluded_runs"] == 1

        everything = registry.load_matrix(pipeline_version=None)
        assert sorted(everything["cells"]["merge_rate"]["gen-a×emb-a"]) == [0.1, 0.9]
        assert everything["excluded_runs"] == 0
        assert everything["pipeline_version"] is None

    def test_empty_version_rows_are_excluded(self, registry):
        legacy = _manifest(run_id="run_legacy")
        legacy.pipeline_version = ""
        registry.register_run(legacy)
        registry.record_metrics("run_legacy", {"merge_rate": 0.5})
        matrix = registry.load_matrix()
        assert matrix["cells"] == {}
        assert matrix["excluded_runs"] == 1
```

Dopisz do `TestReport` w `tests/test_leaderboard_phase3.py`:

```python
    def test_markdown_flags_judge_failures(self):
        matrix = {
            "columns": ["A×X", "B×X"],
            "directions": {"judge_failure_rate": "less", "merge_rate": ""},
            "cells": {
                "judge_failure_rate": {"A×X": [0.0], "B×X": [0.0, 0.05]},
                "merge_rate": {"A×X": [0.2], "B×X": [0.3]},
            },
            "pipeline_version": "v2-p0",
            "excluded_runs": 3,
        }
        md = render_matrix_markdown(matrix)
        header = md.splitlines()[2]
        assert "B×X ⚠" in header
        assert "A×X ⚠" not in header
        assert "v2-p0" in md and "3" in md.splitlines()[0]
        assert "judge_failure_rate > 0" in md

    def test_markdown_without_version_has_no_header_line(self):
        matrix = {
            "columns": ["A×X"],
            "directions": {"merge_rate": ""},
            "cells": {"merge_rate": {"A×X": [0.2]}},
        }
        md = render_matrix_markdown(matrix)
        assert md.startswith("| Metric")
        assert "⚠" not in md
```

(Uwaga: w `test_markdown_flags_judge_failures` indeks `[2]` wynika z układu: linia 0 to nagłówek wersji, linia 1 jest pusta, linia 2 to nagłówek tabeli.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_leaderboard_registry.py tests/test_leaderboard_phase3.py -v`
Expected: FAIL (`KeyError: 'pipeline_version'`, `assert 'v2-phase2' == 'v2-p0'`, brak `⚠`)

- [ ] **Step 3: Implement registry filter**

W `src/leaderboard/registry.py` zamień `PIPELINE_VERSION = "v2-phase2"` na:

```python
# Bumped for the P0 measurement-integrity fixes: runs before this version carry
# merge-to-top-1 and silent judge-failure NEWs, so they are not averaged with
# newer runs (load_matrix filters on this by default).
PIPELINE_VERSION = "v2-p0"
```

Zastąp `load_matrix`:

```python
    def load_matrix(
        self, pipeline_version: Optional[str] = PIPELINE_VERSION
    ) -> Dict[str, Any]:
        """
        Pivot run_metrics into a metric × (gen_model × embed_model) matrix.

        Only runs of `pipeline_version` are included (default: the current one), so
        runs from older, differently-behaving pipelines are never averaged into the
        same cell. pipeline_version=None includes every run.

        Returns:
            {
                "columns": [ "<gen>×<embed>", ... ],
                "directions": { metric_name: direction },
                "cells": { metric_name: { column: [values across runs/k] } },
                "pipeline_version": str | None,
                "excluded_runs": int,   # runs of other versions left out
            }
        """
        query = """
            SELECT r.generation_model_id AS gen,
                   r.embedding_model_id  AS emb,
                   m.metric_name         AS metric,
                   m.value               AS value,
                   m.direction           AS direction
            FROM run_metrics m
            JOIN runs r ON r.run_id = m.run_id
        """
        params: tuple = ()
        if pipeline_version is not None:
            query += " WHERE r.pipeline_version = ?"
            params = (pipeline_version,)

        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
            if pipeline_version is None:
                excluded = 0
            else:
                excluded = conn.execute(
                    "SELECT COUNT(*) FROM runs WHERE pipeline_version IS NOT ?",
                    (pipeline_version,),
                ).fetchone()[0]
        finally:
            conn.close()

        columns: List[str] = []
        directions: Dict[str, str] = {}
        cells: Dict[str, Dict[str, List[float]]] = {}

        for row in rows:
            col = f"{row['gen']}×{row['emb']}"
            if col not in columns:
                columns.append(col)
            metric = row["metric"]
            directions.setdefault(metric, row["direction"] or "")
            cells.setdefault(metric, {}).setdefault(col, []).append(row["value"])

        return {
            "columns": columns,
            "directions": directions,
            "cells": cells,
            "pipeline_version": pipeline_version,
            "excluded_runs": int(excluded),
        }
```

- [ ] **Step 4: Implement report flag**

W `src/leaderboard/report.py` zastąp `render_matrix_markdown`:

```python
_JUDGE_FAILURE_METRIC = "judge_failure_rate"


def _judge_failure_columns(matrix: Dict[str, Any]) -> set:
    """Columns where any run reported judge failures (results unreliable)."""
    per_col = matrix.get("cells", {}).get(_JUDGE_FAILURE_METRIC, {})
    return {col for col, values in per_col.items() if any(v > 0 for v in values)}


def render_matrix_markdown(matrix: Dict[str, Any]) -> str:
    """
    Render the pivot as a GitHub-flavoured Markdown table.

    matrix is the dict returned by `RunRegistry.load_matrix()`:
        {"columns": [...], "directions": {metric: dir}, "cells": {metric: {col: [v]}},
         "pipeline_version": str | None, "excluded_runs": int}
    Columns with judge_failure_rate > 0 in any run are marked ⚠ (P0).
    """
    metrics, columns = _ordered(matrix)
    directions = matrix.get("directions", {})
    cells = matrix.get("cells", {})

    if not metrics:
        return "_(no metrics recorded)_"

    flagged = _judge_failure_columns(matrix)
    header = ["Metric", *[f"{c} ⚠" if c in flagged else c for c in columns]]
    lines: List[str] = []
    if matrix.get("pipeline_version"):
        lines.append(
            f"_pipeline_version: {matrix['pipeline_version']} — "
            f"{matrix.get('excluded_runs', 0)} run(s) of other versions excluded_"
        )
        lines.append("")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for metric in metrics:
        row = [_metric_label(metric, directions.get(metric, ""))]
        col_cells = cells.get(metric, {})
        for col in columns:
            row.append(_fmt_cell(aggregate_cell(col_cells.get(col, []))))
        lines.append("| " + " | ".join(row) + " |")
    if flagged:
        lines.append("")
        lines.append(
            "⚠ judge_failure_rate > 0 in at least one run of this column — "
            "judge fell back to NEW; results are unreliable."
        )
    return "\n".join(lines)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_leaderboard_registry.py tests/test_leaderboard_phase3.py -v`
Expected: PASS (także istniejące `test_record_metrics_and_matrix`, `test_matrix_collects_across_models` i `TestHarnessMatrix`, bo `_manifest` i `_StubPipeline` używają domyślnego `PIPELINE_VERSION`).

- [ ] **Step 6: Commit**

```bash
git add src/leaderboard/registry.py src/leaderboard/report.py tests/test_leaderboard_registry.py tests/test_leaderboard_phase3.py
git commit -m "feat(leaderboard): version-split matrix (v2-p0) and judge-failure flag

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Dokumentacja, pełna suita i smoke

**Files:**
- Modify: `CLAUDE.md` (sekcja `## L1 metrics`)
- Modify: `docs/planning/IDEAS.md` (wpis o P0)
- Modify: `docs/planning/P0_measurement_integrity_design.md` (linia statusu)

**Interfaces:**
- Consumes: wszystko z Task 1–8
- Produces: —

- [ ] **Step 1: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: wszystko PASS, liczba testów > 224. Zanotuj dokładną liczbę do commita i wpisu w `IDEAS.md`.

- [ ] **Step 2: Grep for leftovers**

Run: `grep -rn "_ground_candidate\|compute_grounding\|\"grounding_rate\"\|v2-phase2" src/ scripts/ tests/`
Expected: jedyne trafienie to komentarz przy `PIPELINE_VERSION` w `registry.py` (i ewentualnie `test_matrix_filters_to_current_version` z `"v2-phase2"`). `GroundingReport.grounding_rate` w `grounding.py` to property, a nie klucz słownika, więc zostaje.

- [ ] **Step 3: Smoke run (live API — requires `.env` keys)**

Run: `.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv --db runs/p0_smoke.db --no-hil`

Jeśli `runs/p0_smoke.db` istnieje, skrypt zapyta o nadpisanie. Odpowiedz `O`. Expected w podsumowaniu:
- `Span integrity: 100.0%` (bez `⚠ BUG`);
- linia `Judge failures: …` (przy zdrowym API `0.0%`);
- przy odrzutach: linia `drop classes: {...}`.

Następnie: `grep -c '"type": "grounding_drop"' runs/*p0_smoke*_reasoning.jsonl || true`. Liczba powinna być równa sumie odrzutów pass-1 z logu (`candidate_drop_rate` × kandydaci). Wynik 0 jest poprawny, jeśli model nie miał odrzutów.

Jeśli brakuje kluczy API, **nie udawaj smoke'a**. Zapisz w raporcie końcowym, że krok pominięto i dlaczego.

- [ ] **Step 4: Update CLAUDE.md**

W sekcji `## L1 metrics (src/eval/l1_metrics.py — L1MetricsEngine)` zastąp linię
`- **grounding** — quotes where \`canonical_text[span]==quote_text\` (deterministic)`
na:

```markdown
- **span_integrity** — sanity check: persisted quotes still satisfy `canonical_text[span]==quote_text`; 1.0 expected, < 1.0 = bug (renamed from `grounding`, which was 1.0 by construction)
- **quote_hallucination_rate** + drop classes (`normalized_ws` / `case` / `ellipsis_stitch` / `unmatched`) and **unmatched_quote_rate** — raw, non-circular quote fidelity (hard gate, nothing repaired)
- **judge_failure_rate**, **merge_target_unresolved_rate** — judge reliability; failed judge calls produce no AUC pair
- **ambiguous_occurrence_rate** — accepted quotes whose phrase repeats in the review (span = first free occurrence)
```

Pod listą metryk dodaj akapit:

```markdown
Leaderboard runs are tagged `pipeline_version`; `RunRegistry.load_matrix()` shows only
the current version (`v2-p0`) by default. Runs before `v2-p0` are biased (merge to
top-1 in `--no-hil`, judge failures counted as NEW + AUC pairs) — see
`docs/planning/P0_measurement_integrity_design.md`.
```

- [ ] **Step 5: Update IDEAS.md and spec status**

W `docs/planning/IDEAS.md` dodaj na górze aktywnego backlogu (zachowaj konwencję pliku, przeczytaj go najpierw):

```markdown
- ✅ **P0 measurement integrity** (2026-09-24, `v2-p0`) — judge failure status + `judge_failure_rate` (no AUC pairs), `--no-hil` honours `merge_target_name`, hard-gate grounding with drop classes, first-free occurrence for repeated phrases, hard `verify()` before insert, version-split leaderboard matrix. Runs `v2-phase2` and older are biased — re-run before comparing. Spec/plan: `docs/planning/P0_measurement_integrity_{design,plan}.md`.
```

Zaktualizuj też stopkę `Last updated` w `IDEAS.md`, jeśli istnieje.

W `docs/planning/P0_measurement_integrity_design.md` zamień linię statusu na:

```markdown
> **Status:** ✅ zrealizowane (2026-09-24, `PIPELINE_VERSION = "v2-p0"`). Plan:
> `docs/planning/P0_measurement_integrity_plan.md`.
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md docs/planning/IDEAS.md docs/planning/P0_measurement_integrity_design.md
git commit -m "docs: record P0 measurement-integrity metrics and v2-p0 version split

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: Final report**

Zgłoś:
- liczbę testów przed i po;
- wynik smoke'a (albo informację, że został pominięty, i dlaczego);
- wartości `span_integrity`, `judge_failure_rate` i klasy odrzutów ze smoke'a;
- listę commitów (`git log --oneline <start>..HEAD`).
