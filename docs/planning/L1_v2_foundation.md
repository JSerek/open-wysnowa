# L1 v2 — Harvested v1 Baseline

> **Co to jest.** Krótka notatka z wiedzą przeniesioną z v1 do v2, która nadal jest
> prawdziwa. **To NIE jest opis bieżącego stanu implementacji** — ten żyje w
> [`L1_v2_evidence_extraction_plan.md`](L1_v2_evidence_extraction_plan.md)
> (autorytatywny plan, wszystkie 3 fazy ukończone). Tu zostają tylko dwie rzeczy,
> których nie ma nigdzie indziej: **kontrakt data-modelu** i **empiryczne ustalenia
> z runów stabilizacyjnych v1**.
>
> Pełny pipeline v1 (L0–L4) jest zachowany w tagu `v1-full-pipeline` i gałęzi
> `archive/full-pipeline` (`git show v1-full-pipeline:src/<file>`).

---

## 1. Data-model kontrakt (evidence)

Z `src/core/models.py`. Load-bearing typy dla L1 — przeniesione z v1 zasadniczo
nienaruszone:

- **`Segment`** — preprocessowana jednostka analizy.
  - `canonical_text` jest **IMMUTABLE** po utworzeniu; każdy span się do niego odnosi.
  - `content_hash` = SHA-256 z `canonical_text`; `verify_integrity()` to sprawdza.
  - `original_text` zachowany sprzed normalizacji; `char_count`, `segment_index`.
- **`VerbatimQuote`** — dokładny podciąg `canonical_text` ze spanem char-level.
  - Ground-truth check (bez LLM): `canonical_text[span_start:span_end] == quote_text`
    przez `verify(canonical_text)` → ustawia `is_verified`.
  - `span_end > span_start` wymuszane przez validator. Opcjonalne `sentiment`,
    `quote_embedding_json`.
- **`InitialCode` (IC)** — wpis codebooka / najniższa jednostka analityczna.
  - `name` (1–120 znaków), `definition` (5–600 znaków), `status` (active/…),
    `confidence` (*novelty* confidence codera 0–1 przy utworzeniu, potem zamrożone).
  - **Embed-on-write**: `embedding_input_text()` zwraca `f"{name} | {definition}"`
    — to tekst używany do całej pracy similarity/consistency nad IC.

Łańcuch: `Document → Segment → VerbatimQuote → InitialCode`. Quotes to immutable
evidence; ICs to abstrakcja nad nimi.

Datasety kanoniczne (negatywne recenzje *Dying Light: The Beast*, `canonical_top{10,
30,50,100}.csv`) opisane w `CLAUDE.md`.

---

## 2. Empirical learnings z runów stabilizacyjnych v1

> ⚠️ **Kontekst historyczny.** Poniższe liczby (zwłaszcza comparator↔embedding
> agreement i historia progów) odnoszą się do **architektury v1** — progowego
> triage z dwoma torami decyzyjnymi. v2 (Faza 1) usunął progi i przeszedł na jeden
> tor (embedding top-k + LLM-sędzia bezprogowo), więc te wartości nie są
> obowiązującymi parametrami, tylko obserwacjami z poprzedniej architektury.

Distilled z `archived/v1/docs/testing/TEST_RUN_SUMMARY_*` i
`archived/v1/docs/planning/STABILIZATION_TESTING_PLAN.md`:

- **Saturacja osiągnięta** przy N=100 (ITS_final 0.029 🟢); N=50 jeszcze nienasycone
  (0.154 🔴). Baza evidence rośnie, potem plateau — zgodnie z oczekiwaniem.
- **Comparator↔embedding agreement maleje ze skalą**: N=30 ≈79% → N=50 ≈62% →
  N=100 ≈56%. Warto obserwować w v2 (więcej kandydatów ⇒ gęstsza przestrzeń
  similarity ⇒ więcej autentycznych sporów w grey-zone). Próg działania v1 był <50%.
- **Coherence gate nieaktywny przy małym N** (relative 0.5×baseline floor nigdy nie
  odpala) — problem L2, ale przypomnienie, że *relative* progi mogą cicho no-opować.
- **Rekalibracja progów (2026-03-04)** przesunęła auto_new 0.50→0.55, auto_merge
  0.72→0.65, distinctness 0.70→0.80, by poszerzyć/dostroić grey-zone.

Pełne run summaries i oryginalny `STABILIZATION_TESTING_PLAN.md` — w tagu
`v1-full-pipeline`.
