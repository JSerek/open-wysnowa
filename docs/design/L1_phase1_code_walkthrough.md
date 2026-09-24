# Faza 1 — jak L1 działa krok po kroku (od strony kodu)

> Stan po commicie `feat(l1): Phase 1 — raw single-pass extraction + run registry`.
> Dokument opisuje **rzeczywisty przepływ kodu** v2 L1: jednoprzejściowa ekstrakcja
> evidence z surowym pomiarem, jeden tor decyzyjny i pełna śledzalność.
> Plan/kontrakt: `docs/planning/L1_v2_evidence_extraction_plan.md`.
>
> **Migawka historyczna.** Od P0 (2026-09-24, `v2-p0`) grounding działa przez
> `src.preprocessing.locate_quote` (zamiast `_ground_candidate` + `find()`),
> odrzuty mają klasy, a metryka `grounding_rate` nazywa się `span_integrity`.
> Aktualny opis: `docs/planning/P0_measurement_integrity_design.md`.

## Zasada nadrzędna Fazy 1

Trzy decyzje przenikają cały kod:

1. **LLM nie liczy offsetów.** Model zwraca tylko dosłowny `quote_text`; pozycję
   znakową wyznacza kod przez `str.find()`. (Empirycznie model myli offsety ~93%
   przypadków — patrz koniec dokumentu.)
2. **Jeden tor decyzyjny, bez progów.** Embedding tylko rankuje top‑k; każdą
   decyzję NEW/MERGE/REJECT podejmuje LLM‑sędzia.
3. **Surowy pomiar, pełna śledzalność.** Żadnych „protez" ratujących słabe modele;
   każda recenzja → osobna DB runu + rekord w centralnym rejestrze + log per kandydat.

---

## Przepływ danych (z lotu ptaka)

```
CSV ──load_reviews──▶ [Document] ──L0 preprocess──▶ [Segment]
   │
   └─▶ Layer1Orchestrator.run(segments)            (pętla po batchach)
         │
         for każdy batch:
           CoderAgent.process_batch ─▶ LLM (1 recenzja = 1 call)
              └─ RawICCandidate (tylko quote_text, BEZ offsetów)
              └─ _ground_candidate: canonical.find(quote) ─▶ ICCandidate (span policzony)
                                                          └─ brak dopasowania ⇒ DROP (halucynacja)
           dla każdego ICCandidate:
              CodebookComparator.evaluate ─▶ embedding top‑k (ranking) ─▶ LLM‑sędzia
              _apply_decision ─▶ NEW / MERGE / REJECT  (zapis IC + VerbatimQuote)
              reasoning_logger.log_candidate(...)        (ślad Appendix B)
         _refine_ic_definitions()                        (non‑destructive)
   │
   ├─▶ L1MetricsEngine.compute_all ─▶ metryki (grounding, density, quote_hallucination_rate, …)
   └─▶ RunRegistry: RunManifest + metryki ─▶ runs/leaderboard.db
```

---

## 1. Punkt wejścia — `scripts/run_pipeline.py`

CLI ładuje recenzje i konstruuje pipeline. Faza 1 dodała parametry runu
(`--seed`, `--k-index`, `--leaderboard-db`) przekazywane do manifestu:

```python
pipeline = EQDPipeline(
    config_path=config_path,
    db_path=db_path,
    seed=args.seed,
    k_repeat_index=args.k_index,
    leaderboard_db_path=args.leaderboard_db,
)
results = pipeline.run(docs, enable_hil=enable_hil, dataset_path=args.csv_path)
```

`dataset_path` jedzie do `run()`, bo manifest hashuje plik wejściowy.

---

## 2. `EQDPipeline` — wstrzykiwanie configu i orkiestracja

### 2a. Konstrukcja: gotowy `Config` albo ścieżka

Luka z handoffu (Faza 3 potrzebuje podmieniać id modeli programistycznie)
naprawiona w Fazie 1 — `__init__` przyjmuje **albo** gotowy obiekt `Config`,
**albo** `config_path`:

```python
# src/extraction/pipeline.py
def __init__(self, config_path=None, db_path="eqa_ai.db", config=None,
             seed=None, k_repeat_index=0, leaderboard_db_path="runs/leaderboard.db"):
    # Explicit config wins over path — harness can override agents.*.model in-memory
    self.config = config if config is not None else load_config(config_path)
    ...
```

Dzięki temu harness leaderboardu zbuduje `Config`, nadpisze
`agents.coder_agent.model` / `agents.embedding.model` i przekaże bez pisania
tymczasowych plików YAML.

### 2b. `run()` — L0 → L1 → metryki → rejestr

```python
segments = preprocess_documents(documents, self.db)            # L0
layer1_summary = self.layer1.run(segments, enable_hil=enable_hil)   # L1
...
quality_results = self.metrics_engine.compute_all(             # metryki
    its_history=its_history,
    batch_merge_rates=layer1_summary.get("batch_merge_rates", []),
    total_dropped=layer1_summary.get("total_dropped", 0),
    total_candidates=layer1_summary.get("total_candidates", 0),
    ...
)
self._register_run(documents, dataset_path, quality_results)   # manifest + rejestr
```

`run_id = "{study.name}_{UTC timestamp}"` → osobna DB runu (kontrakt #12). Rejestr
opakowany w `try/except`, bo księgowanie nigdy nie może wywrócić pipeline'u.

---

## 3. L0 — bez zmian

`preprocess_documents` robi 1 Document → 1 Segment (`canonical_text` = znormalizowany
tekst, niemutowalny — ground truth dla spanów). Faza 1 nie dotyka L0.

---

## 4. `Layer1Orchestrator.run()` — pętla po batchach

Batch (domyślnie 10 segmentów) to jednostka grupowania ITS/embeddingów; **decyzje
zapadają per kandydat**. Kroki w pętli:

### 4a. Coder: jedna recenzja = jeden call

```python
# src/extraction/coder_agent.py
def process_batch(self, segments):
    codebook = InitialCodeRepo(self.db).get_all_active()
    codebook_context = build_codebook_context(codebook)
    results, self.last_drop_counts = {}, {}
    for segment in segments:
        candidates, n_dropped = self._code_segment(segment, codebook_context)
        results[segment.id] = candidates
        self.last_drop_counts[segment.id] = n_dropped     # = liczba halucynacji
    return results
```

Tryb batchowy (`BatchCodingResult`, micro‑batche) **usunięty** — deterministycznie
jeden segment na wywołanie LLM.

### 4b. Model zwraca tekst, kod liczy offset

LLM‑owy schemat to `RawICCandidate` — **bez pól spanów**:

```python
# src/core/models.py
class RawICCandidate(BaseModel):       # to widzi instructor jako response_model
    ic_name: str
    definition: str
    quote_text: str          # "exact substring … do NOT provide character offsets"
    confidence: float
    sentiment: Optional[Sentiment] = None
    existing_code_match: Optional[str] = None
```

Po parsowaniu coder **gruntuje** każdy quote — to jedyna bramka jakości:

```python
# src/extraction/coder_agent.py
@staticmethod
def _ground_candidate(raw, segment) -> Optional[ICCandidate]:
    canonical = segment.canonical_text
    idx = canonical.find(raw.quote_text)
    if idx < 0:
        return None                      # nie‑dosłowny ⇒ halucynacja ⇒ DROP
    return ICCandidate(
        ic_name=raw.ic_name, definition=raw.definition, quote_text=raw.quote_text,
        span_start=idx, span_end=idx + len(raw.quote_text),   # span policzony przez kod
        confidence=raw.confidence, sentiment=raw.sentiment,
        existing_code_match=raw.existing_code_match,
    )
```

Niezmiennik `canonical[span_start:span_end] == quote_text` zachodzi **z konstrukcji**.
Brak realign/fuzzy (usunięte Tier 2/3). Odrzuty lecą do `last_drop_counts` →
`quote_hallucination_rate`.

### 4c. Spłaszczenie kandydatów — jeden tor

Brak ścieżki skrótu dla `existing_code_match`. **Wszyscy** kandydaci idą do sędziego;
`existing_code_match` jest tylko **logowanym sygnałem** (macierz `coder_reuse`):

```python
# src/extraction/orchestrator.py
for cand in candidates:
    if cand.existing_code_match is not None:
        summary["coder_flagged_match"] += 1     # sygnał, NIE routing
    all_candidates.append((cand, segment.id, segment.canonical_text))
```

### 4d. Pre‑embedding (1 batch call) + sędzia per kandydat

```python
precomputed_embeddings = self.embedding_service.embed_texts_batch(
    [f"{c.ic_name} | {c.definition}" for c, _, _ in all_candidates]
)
for idx, (cand, seg_id, seg_text) in enumerate(all_candidates, 1):
    comp_output, top_k, decision_meta = self.comparator.evaluate(
        cand, precomputed_embedding=precomputed_embeddings[idx - 1]
    )
```

`CodebookComparator.evaluate` realizuje **jeden tor bez progów**:

```python
# src/extraction/codebook_comparator.py
top_k_results = self.embedding_service.find_similar_ics(embedding, top_k=self.top_k)

if not top_k_results:                       # jedyny dozwolony skrót
    return NEW, [], {"decision_path": "empty_codebook", "max_sim": None, ...}

# codebook niepusty → ZAWSZE LLM‑sędzia (brak auto_new/auto_merge)
output = self._get_llm_recommendation(candidate, top_k_with_defs)
meta = {"decision_path": "llm", "max_sim": top_k_results[0].similarity,
        "llm_recommendation": output.recommendation.value}     # max_sim → AUC w Fazie 3
```

Embedding pełni wyłącznie rolę rankingu top‑k; `max_sim` jest zapisywany pod kątem
bezprogowego AUC w Fazie 3.

### 4e. Zastosowanie decyzji

W trybie headless (`--no-hil`) przyjmujemy rekomendację sędziego; `_apply_decision`
tworzy IC + `VerbatimQuote` (NEW), dokłada quote do istniejącego IC (MERGE) albo
loguje odrzut (REJECT). IC jest embedowany natychmiast, żeby kolejny kandydat
w batchu widział go w top‑k; quote embedowany zbiorczo na końcu batcha.

### 4f. Ślad per kandydat (Appendix B)

Po decyzji orchestrator zapisuje pełny rekord — to realizuje wymóg śledzalności:

```python
if self.reasoning_logger:
    self.reasoning_logger.log_candidate({
        "pass": 1, "segment_id": seg_id, "ic_name": cand.ic_name,
        "quote_text": cand.quote_text, "span_start": cand.span_start,
        "span_end": cand.span_end, "grounded": True,
        "coder_existing_code_match": cand.existing_code_match,
        "top_k": [{"ic_id": s.ic_id, "ic_name": s.ic_name, "sim": round(s.similarity, 4)}
                  for s in top_k],
        "decision_path": decision_path, "judge_verdict": comp_output.recommendation.value,
        "judge_reasoning": comp_output.reasoning, "final_action": result,
    })
```

`grounded` jest zawsze `True`, bo do sędziego docierają wyłącznie ugruntowane
kandydaty (niedosłowne odpadły w 4b).

### 4g. ITS i krzywa saturacji

`ITSTracker` liczy `new_ics / ics_before` per batch i kumulatywną krzywę odkrywania
ICs per segment — bez zmian względem v1.

### 4h. IC refinement — non‑destructive (kontrakt #15)

Na końcu definicje ICs z 2+ quotes są dopracowywane, ale oryginał jest **logowany
przed nadpisaniem** (DESIGN_PRINCIPLES #5):

```python
if self.reasoning_logger:
    self.reasoning_logger.log_record({
        "type": "ic_refinement", "ic_id": ic.id, "ic_name": ic.name,
        "original_definition": old_def,
        "refined_definition": refined_parsed.refined_definition,
        "change_summary": refined_parsed.change_summary, "quote_count": len(quotes),
    })
```

---

## 5. Metryki — `L1MetricsEngine.compute_all`

Sygnały referencyjne‑free, nigdy bramki. Faza 1:

- **`grounding`** — `canonical[span]==quote` (deterministyczne; teraz z konstrukcji 100%).
- **`extraction_density`** — pokrycie znakowe segmentu (union spanów) + `candidate_drop_rate`.
- **`quote_hallucination_rate`** (NOWA) — udział odrzutów bramki groundingu:

```python
# src/eval/l1_metrics.py
def compute_quote_hallucination_rate(self, total_dropped=0, total_valid_candidates=0):
    total_raw = total_valid_candidates + total_dropped
    rate = total_dropped / total_raw if total_raw else 0.0
    # MetricType.QUOTE_HALLUCINATION_RATE; kierunek: mniej = lepiej
    return {"quote_hallucination_rate": round(rate, 4),
            "hallucinated": total_dropped, "total_raw_candidates": total_raw}
```

`triage_efficiency` i `comparator_agreement` **usunięte** — były pochodnymi progów,
których już nie ma (ocena embeddingu wróci jako bezprogowe AUC w Fazie 3).

---

## 6. Manifest runu + centralny rejestr — `src/leaderboard/registry.py`

Każdy run zapisuje (a) własną DB runu oraz (b) jeden rekord w `runs/leaderboard.db`
= pełna parametryzacja (`RunManifest`) + metryki w formacie długim (łatwym do pivotu
w macierz w Fazie 3).

```python
# src/extraction/pipeline.py — budowa manifestu
manifest = RunManifest(
    run_id=self.run_id,
    generation_model_id=cfg.models[coder_agent.model].model_id,
    embedding_model_id=cfg.models[cfg.agents["embedding"].model].model_id,
    coder_prompt_hash=_sha256(build_coder_system_prompt("")),     # fingerprint promptu
    judge_prompt_hash=_sha256(build_comparator_system_prompt()),
    dataset_hash=..., dataset_size=len(documents),
    temperature=coder_agent.temperature, seed=self.seed,
    k_repeat_index=self.k_repeat_index,                            # architektura pod k=N
    config_snapshot={...}, run_db_path=self.db_path, git_sha=_git_sha(),
)
registry.register_run(manifest)
registry.record_metrics(self.run_id, metrics, directions)
```

`RunRegistry` to samodzielne SQLite z tabelami `runs` (kolumny = pola `RunManifest`)
i `run_metrics` (`run_id, metric_name, value, direction`). `load_matrix()` pivotuje
je w macierz metryka × (model_gen × model_embed) — fundament Fazy 3.

`_flatten_metrics` wyciąga skalary z zagnieżdżonych wyników i dokleja kierunki
(Appendix A): `grounding_rate` (więcej=lepiej), `quote_hallucination_rate`/
`candidate_drop_rate` (mniej=lepiej), reszta opisowa.

---

## 7. Co zostało usunięte (i dlaczego)

| Usunięte | Powód |
|---|---|
| Tryb batchowy codera (`BatchCodingResult`) | determinizm: 1 recenzja = 1 call |
| Offsety w schemacie LLM | model ich nie umie liczyć (~93% błędów) |
| Tier 2/3 auto‑korekta spanów | „proteza" ratująca słabe modele — zakłamuje pomiar |
| Meta‑filtr (`is_meta_commentary`, `meta_ic_filter`) | decyzję REJECT podejmuje wyłącznie sędzia |
| Progi `auto_new`/`auto_merge`/`merge_conflict` | jeden tor; embedding tylko rankuje |
| Ścieżka `existing_matches`/`_apply_existing_match` | wszyscy idą przez sędziego; match = sygnał |
| `triage_efficiency`, `comparator_agreement` | pochodne nieistniejących progów |

---

## 8. Najważniejszy wynik empiryczny

Ten sam smoke (`canonical_top10`, `google/gemini-3-flash-preview`, seed 42):

| | LLM liczy offsety | Kod liczy offset (`find`) |
|---|---|---|
| ICs utworzone | 4 | **38** |
| Odrzuty | 93.4% (57/61) | **0% (0/60)** |
| Extraction density | 7.5% | **49%** |
| Grounding | 100% | 100% |

Całe 93% strat było **artefaktem liczenia offsetów przez LLM** — tekst quote był
niemal zawsze dosłowny, model po prostu nie potrafił podać pozycji znakowej (błąd
rośnie z długością tekstu). Przeniesienie obliczania offsetu do kodu odblokowało
realną ekstrakcję przy zachowaniu twardej bramki „czy tekst dosłownie jest w danych".

> Następne fazy: **Faza 2** (drugie przejście / omitted‑text audit),
> **Faza 3** (leaderboard: macierz modeli + bezprogowe AUC embeddingu).
> Szczegóły: `docs/planning/L1_v2_evidence_extraction_plan.md`.
