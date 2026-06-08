# EQD-AI v2 — L1 Evidence Extraction: szczegółowy plan (3 fazy)

> **Status:** zatwierdzony plan implementacyjny (sesja projektowa 2026-06-07).
> Realizacja faza po fazie w osobnych sesjach / czystych oknach kontekstowych.
> **Każda faza musi zaczynać się od wczytania:** tej sekcji Context +
> „DECYZJE PROJEKTOWE (kontrakt)" + „Handoff: środowisko i założenia
> implementacyjne". Reszta jest specyficzna dla danej fazy.
>
> **Postęp realizacji:**
> - ✅ **FAZA 1 — UKOŃCZONA** (commit `c65b9c4`, 2026-06-07): surowy jednoprzejściowy
>   fundament, jeden tor decyzyjny, manifest runu + rejestr.
> - ✅ **FAZA 2 — UKOŃCZONA** (2026-06-08): drugie przejście (omitted-text audit),
>   dwupunktowa density + metryki diagnostyczne pass2. 205 testów green; smoke
>   `canonical_top10` zweryfikowany (komplet metryk pass2 w rejestrze).
> - ⏳ **FAZA 3 — DO ZROBIENIA:** leaderboard (macierz modeli) + bezprogowe AUC.

## Context — po co to robimy

v2 skupia się wyłącznie na L1: ekstrakcji dowodów (evidence/quotes) z pojedynczych
recenzji/transkrypcji metodą bottom-up + budowie codebooka ICs. MVP pracuje na
recenzjach *Dying Light: The Beast* ze Steam (`data/canonical_top{10,30,50,100}.csv`),
docelowo różne formy tekstu. L0 (segmentacja/normalizacja) zostaje bez zmian.

Trzy braki obecnego L1, które ten plan naprawia:

1. **Nie wiemy, co dzieje się z nie-wyciągniętym tekstem.** Jeśli model wyciąga 40%
   recenzji (Extraction Density = 0.4), nie wiemy, czy pozostałe 60% pominięto
   **celowo** (filler) czy **przez pomyłkę** (lost-in-the-middle). → wprowadzamy
   **drugie przejście** per recenzja: model dostaje pełną recenzję z programistycznie
   oznaczonymi fragmentami nie-wyciągniętymi, klasyfikuje każdy (deliberate/accidental)
   i może odzyskać dowody.
2. **Pipeline po cichu „ratuje" słabe modele** (auto-korekta spanów Tier 2/3,
   meta-filtr, progi triage zależne od modelu+datasetu). To zakłamuje porównanie
   modeli. → przechodzimy na **surowy pomiar**: jeden tor decyzyjny, twarda bramka
   grounding bez naprawiania, bez progów operacyjnych.
3. **Nie da się empirycznie porównać modeli LLM/embeddingów.** → budujemy
   **leaderboard** = macierz metryk L1 per (model generacyjny × model embeddingowy),
   z bezprogową oceną embeddingu (AUC) i rejestrem runów dla pełnej śledzalności.

Cel końcowy: jak najwyższej jakości ekstrakcja evidence w eksploracyjnej analizie
jakościowej, z możliwością empirycznego porównania modeli wg ustalonych metryk.

---

## DECYZJE PROJEKTOWE (kontrakt — obowiązuje we wszystkich fazach)

Wszystkie poniższe są zatwierdzone przez użytkownika w dyskusji projektowej:

1. **Jednostka analizy = jedna recenzja = jeden segment = jeden API call.** L0 robi
   1 Document → 1 Segment (`src/preprocessing/segmentation.py:75-113`, 1:1). W v2
   coder przetwarza **jedną recenzję na wywołanie** — `segments_per_coder_call`
   ustawiamy na `1`, tryb batchowy codera (`BatchCodingResult`) wyłączamy.
2. **Dwa przejścia per recenzja, sekwencyjnie:** dla recenzji N robimy
   `pass1 → przetworzenie kandydatów → pass2 → przetworzenie odzyskanych → dopiero
   recenzja N+1`. pass2 recenzji N widzi codebook ze stanem po jej własnym pass1.
3. **pass2 robi TEN SAM model co pass1** (opcja A — mierzymy zachowanie modelu jako
   całościowego two-pass pipeline'u). Do empirycznego sprawdzenia później.
4. **Wyrzucamy „protezy", mierzymy surowo. LLM NIE liczy offsetów** (decyzja
   2026-06-07 — empirycznie ~93% błędnych offsetów, drift rosnący z długością;
   patrz memory `phase1-span-error-finding`):
   - Model zwraca **tylko dosłowny `quote_text`** (model LLM = `RawICCandidate`,
     bez pól spanów). **Tier 2/3 span auto-korekta — USUNIĘTA.**
   - **Offset liczy kod** deterministycznie: `span = canonical.find(quote_text)`
     (`CoderAgent._ground_candidate` → `ICCandidate` z policzonym spanem).
   - **Bramka groundingu (twarda, bez naprawy):** czy IDENTYCZNY tekst występuje
     w danych. Jeśli `find == -1` (model zhalucynował znaki/słowa/zdania) →
     kandydat odrzucony i odrzut liczy się na niekorzyść modelu
     (`quote_hallucination_rate` / `candidate_drop_rate`).
   - **meta_ic_filter** (`is_meta_commentary`, config `processing.meta_ic_filter`) —
     USUWAMY.
5. **Jeden tor decyzyjny dla wszystkich kandydatów (opcja A).** Coder produkuje
   tylko evidence (quote + propozycja IC). KAŻDĄ decyzję merge/new/reject podejmuje
   `embedding-retrieval (top-k) + LLM-sędzia`. `existing_code_match` zostaje tylko
   jako **logowany sygnał** („czy model rozpoznał własny codebook?"), NIE steruje
   przepływem. Ścieżka skrótu `existing_matches` w orchestratorze znika.
6. **Bez progów operacyjnych w fazie pomiarowej.** `auto_new_threshold` /
   `auto_merge_threshold` / triage shortcut — USUWAMY. Embedding pełni jedynie rolę
   **wyszukiwania top-k** (rankingowo, bezprogowo). LLM-sędzia ocenia każdego
   kandydata. (Próg operacyjny może wrócić w przyszłości tylko jako knob kosztu przy
   dużej skali, kalibrowany per wdrożenie — poza zakresem MVP.)
7. **Ocena embeddingu = bezprogowe AUC** separacji: dla par `(cosine_sim do top-1 IC,
   werdykt LLM-sędziego ∈ {merge, new})` liczymy AUC (prawdopodobieństwo, że para
   „merge" ma wyższy cosinus niż para „new"). Sędzia w trybie eval musi być
   **ślepy na cosinus** (osobny prompt — orzeka wyłącznie z tekstów), inaczej pomiar
   jest cyrkularny. Na małych zbiorach sędzia ocenia WSZYSTKIE pary (pełny zakres
   podobieństwa).
8. **Leaderboard = macierz metryk per (model generacyjny × model embeddingowy).**
   NIE jeden composite score. Człowiek czyta macierz. Metryki dzielimy na
   „wewnętrznie-referencyjne" (mają naturalny kierunek) i „opisowe" (bez kierunku).
9. **Jeden slot generacyjny × jeden slot embeddingowy** (na start). Model
   generacyjny = coder + pass2-judge + grey-zone/merge-judge + IC-refinement (te
   same id modelu). Konfigurowalność per rola = odroczona.
10. **Runy benchmarkowe są headless** (`--no-hil`), w pełni automatyczne.
11. **k=1 na start, architektura pod k=N** (powtórzenia runu → wariancja). Store i
    rejestr muszą od początku przyjmować `k_repeat_index`.
12. **Persystencja: osobna DB per run + centralny rejestr runów.** Manifest runu =
    pełna parametryzacja (modele, prompt_hash, dataset_hash, seed, temperatura,
    k_repeat_index) + finalne metryki + wskaźnik do DB runu.
13. **density mierzona dwupunktowo per recenzja** (po pass1 i po pass2), agregowana
    na końcu. Przestaje być czysto „end-of-run aggregate".
14. **MVP = recenzje + krótkie formy.** Transkrypcje (długie → ponowny podział na
    segmenty, „omitted względem czego") — odroczone. Ale model danych pass2 zakłada
    `segment_id` jako jednostkę (dziś = recenzja); klucz dokumentu nie blokuje
    przyszłego rozszerzenia.
15. **IC definition refinement na końcu zostaje** (`_refine_ic_definitions`,
    ICs z 3+ quotes) — ale **non-destructive** (DESIGN_PRINCIPLES #5): refinement
    musi zalogować definicję sprzed zmiany (`original_definition` → `refined` +
    powód) do reasoning_log, zamiast cicho nadpisać oryginał. Quotes (ground truth)
    nietknięte (#1).

---

## Handoff: środowisko i założenia implementacyjne

Informacje wspólne, potrzebne do wdrożenia każdej fazy w czystym oknie:

- **Uruchamianie:** zawsze `.venv/bin/python`. Klucze w `.env`:
  `OPENROUTER_API_KEY` (modele generacyjne) + `OPENAI_API_KEY` (embeddingi —
  OpenRouter nie ma API embeddingów).
- **Konfiguracja modeli** (`eqd_config.yaml`): słownik `models:` definiuje nazwane
  modele (`or_smart` = `google/gemini-3-flash-preview`, `or_fast` =
  `openai/gpt-5-nano`, `embed_openai` = `text-embedding-3-small`). `agents:` mapuje
  rolę → nazwany model (`coder_agent.model`, `codebook_comparator.model`,
  `embedding.model`). `ModelClient` (`src/core/config.py`) rozwiązuje
  agent → provider/model i robi wywołania (instructor). „Slot generacyjny"
  (kontrakt #9) = ten sam nazwany model w `coder_agent` i `codebook_comparator`
  (oraz używany przez agenta pass2 i refinement).
- **Wejście pipeline'u:** `EQDPipeline` (`src/extraction/pipeline.py`) →
  L0 (`preprocess_documents`) → L1 (`Layer1Orchestrator.run`) → opcjonalny
  HIL sign-off → metryki (`L1MetricsEngine.compute_all`). `run_id` =
  `{study.name}_{UTC timestamp}`. `ReasoningLogger` pisze do katalogu rodzica
  `db_path`. CSV→Document: `scripts/load_steam_reviews.py`. CLI: `scripts/run_pipeline.py`.
- **DB:** SQLite (`src/core/db.py`). Repos: `InitialCodeRepo`, `VerbatimQuoteRepo`,
  `SegmentRepo`, `QualityMetricRepo`. Tabele L2–L4 istnieją, ale w v2 nieużywane.
  Embeddingi cache'owane w DB runu → przy osobnej DB per run cache jest
  automatycznie izolowany per run (ważne przy podmianie modelu embeddingowego).
- **Embedding API** (`src/core/embeddings.py`): `embed_text`, `embed_texts_batch`,
  `find_similar_ics(embedding, top_k, exclude_ids)` (zwraca `SimilarityResult`
  posortowane malejąco), `cosine_similarity`.
- **Determinizm:** `temperature` ustawiana per agent; `seed` jest *best-effort*
  (nie wszystkie providery OpenRouter go honorują). Dlatego architektura pod k=N
  (powtórzenia → wariancja) jest konieczna mimo ustawienia seed/temperatury.
- **Luka implementacyjna do naprawienia w Fazie 1 (potrzebna w Fazie 3):**
  `EQDPipeline.__init__` przyjmuje dziś tylko `config_path` i ładuje config ze
  ścieżki (`load_config`). Harness leaderboardu musi **podmieniać id modeli
  programistycznie**. → w Fazie 1 zrefaktoruj `EQDPipeline`, by przyjmował także
  gotowy obiekt `Config` (np. `config: Optional[Config] = None` obok
  `config_path`), tak by harness mógł zbudować config, nadpisać
  `agents.*.model` i przekazać bez pisania tymczasowych plików YAML.
- **Standardy repo:** weryfikuj składnię, uruchamiaj `pytest tests/ -v`,
  staguj selektywnie, commit message wg konwencji repo (skill `eqa-repo-standards`).
  v1 do odzyskania z taga `v1-full-pipeline` (`git show v1-full-pipeline:src/<file>`).
- **Open source (Apache-2.0) — twarde reguły higieny dla wszystkich faz:**
  - Projekt zmierza do publikacji jako open source (LICENSE = Apache-2.0).
  - **Nigdy nie commituj danych** (recenzje Steam = treści użytkowników + znak
    towarowy; nieredystrybuowalne). `*.csv`/`*.db`/`runs/`/`linkedin/` pozostają
    w `.gitignore`. Reasoning_log i DB runów zawierają tekst recenzji + outputy
    modelu → nigdy do repo.
  - **Fixture'y testowe Faz 1–3 MUSZĄ być syntetyczne** (zmyślony tekst), nie
    wycinki z `data/canonical_top*.csv`. Wzór: istniejące `tests/conftest.py`
    (zmyślone recenzje) i `tests/test_load_steam_reviews.py` (zmyślony CSV w
    `tmp_path`).
  - **Brak sekretów w kodzie/testach** — klucze tylko przez `.env` (jest w
    `.gitignore`; `.env.example` śledzony).
  - **Publikowanie wyników leaderboardu**: kod jest OK pod Apache-2.0, ale publiczne
    publikowanie porównań komercyjnych modeli sprawdź względem ToS dostawców
    (klauzule benchmarkingu). Kod ≠ wyniki.

---

## Stan obecny (punkt wyjścia) — najważniejsze pliki

- `src/preprocessing/segmentation.py` — L0, 1 Document → 1 Segment. **Bez zmian.**
- `src/core/models.py` — wszystkie modele Pydantic. `ICCandidate` (274-342),
  `VerbatimQuote` (96-128), `InitialCode` (130-159), `MetricType` enum (40-57),
  `ComparatorOutput`/`ComparatorRecommendation` (365-393), `Sentiment` (266-271),
  `SegmentCodingResult`/`BatchCodingResult` (344-362), `RefinedICOutput` (638-654).
- `src/extraction/coder_agent.py` — pass1; `_validate_span` 3-tier (332-409),
  drop tracking (`last_drop_counts`), tryb batch (`_code_segments_batch`,
  `_call_llm_batch`).
- `src/extraction/codebook_comparator.py` — `evaluate()` (62-175): triage progowy +
  LLM grey-zone; `_get_llm_recommendation` (177-240).
- `src/extraction/orchestrator.py` — `Layer1Orchestrator.run()` (254-601):
  per-batch flow, ścieżka `existing_matches`/`_apply_existing_match`, triage stats,
  embedding coordination, `_hil_loop`, `_apply_decision`, `_refine_ic_definitions`.
- `src/extraction/prompts.py` — coder (40-192), comparator (198-308; **zawiera
  similarity scores jako „primary signal"**), IC refinement (314-348).
- `src/eval/l1_metrics.py` — `L1MetricsEngine.compute_all` + metryki (density
  253-378 agregatowo z DB via `_merge_spans` 381-400, grounding 204-251,
  candidate_drop_rate, ic_concentration, merge_rate, triage_efficiency,
  comparator_agreement, coder_confidence, quote_coverage, cross_review_convergence).
- `src/extraction/pipeline.py` — `EQDPipeline` spina L0→L1→metryki; tworzy `run_id`,
  `ReasoningLogger`, `ModelClient`, `EmbeddingService`.
- `src/core/reasoning_log.py` — `ReasoningLogger` (już istnieje, do rozszerzenia).
- `src/core/db.py` — schema SQLite; tabele `verbatim_quotes`, `initial_codes`,
  `segments`, `quality_metrics`.
- `eqd_config.yaml` — `models`, `agents`, `processing` (progi, meta_filter,
  segments_per_coder_call, reasoning_log_mode).
- `src/leaderboard/` — placeholder, do zabudowania w Fazie 3.
- `scripts/run_pipeline.py`, `scripts/load_steam_reviews.py`, `scripts/init_db.py`.

---

## FAZA 1 — surowy, jednoprzejściowy fundament  ✅ UKOŃCZONA (commit `c65b9c4`)

**Cel:** oczyścić L1 z protez i skrótów; jeden tor decyzyjny; pełna śledzalność.
Po tej fazie pipeline robi jednoprzejściową ekstrakcję z surowym pomiarem i pełnym
manifestem runu. (Drugie przejście dochodzi w Fazie 2.)

### 1.1 Wyłącz tryb batchowy codera (1 recenzja = 1 call)
- `eqd_config.yaml`: `processing.segments_per_coder_call: 1`.
- `coder_agent.py`: ścieżka batchowa (`_code_segments_batch`, `_call_llm_batch`,
  użycie `BatchCodingResult`) — usuń lub martwo-wyłącz; zostaw tylko
  `_code_segment` (single). Cel: deterministyczny, jeden segment na wywołanie.

### 1.2 LLM nie liczy offsetów — offset programistyczny + bramka groundingu
- Model LLM zwraca tylko `quote_text` (`RawICCandidate`, bez spanów).
- `coder_agent._ground_candidate(raw, segment)`: `idx = canonical.find(quote)`;
  jeśli `idx < 0` → kandydat odrzucony (halucynacja, brak naprawy); w przeciwnym
  razie buduje `ICCandidate` ze spanem `[idx, idx+len(quote)]` (pierwsze
  wystąpienie). Spany powstają deterministycznie w kodzie.
- Kandydaci niedosłowni → zliczeni w `last_drop_counts` jako **halucynacja**
  (patrz 1.6 `quote_hallucination_rate`).

### 1.3 Usuń meta-filtr
- `orchestrator.py`: usuń wywołanie `is_meta_commentary` i gałąź
  `_apply_reject(..., "meta-filtered")`.
- `eqd_config.yaml`: usuń blok `processing.meta_ic_filter`.
- Usuń funkcję `is_meta_commentary` i powiązane (znajdź przez grep). Decyzję
  REJECT podejmuje wyłącznie LLM-sędzia (1.4).

### 1.4 Jeden tor decyzyjny — bez progów, bez skrótu coder-merge
- `codebook_comparator.py:evaluate()` (62-175): usuń triage progowy
  (`auto_new_threshold`, `auto_merge_threshold`, gałęzie `auto_new`/`auto_merge`).
  Nowy przepływ dla KAŻDEGO kandydata:
  1. embedding kandydata (lub precomputed),
  2. `find_similar_ics(top_k)` — wyłącznie wyszukiwanie (rankingowo),
  3. **zawsze** `_get_llm_recommendation` (NEW/MERGE/REJECT) — z top-k + definicjami.
  - Pusty codebook → zwróć NEW bez wywołania LLM (jedyny dozwolony skrót — nie ma
    z czym porównać).
  - Zwracaj nadal `top_k_results` + meta z `max_sim` (potrzebne do AUC w Fazie 3).
- `orchestrator.py`: usuń ścieżkę `existing_matches` / `_apply_existing_match`.
  WSZYSTKIE kandydaty (z `existing_code_match` ustawionym i nie) idą przez
  `comparator.evaluate()`. `existing_code_match` zapisuj tylko do reasoning_log
  jako sygnał (do macierzy `coder_reuse`), nie używaj do routingu.
- `eqd_config.yaml`: usuń `auto_new_threshold`, `auto_merge_threshold`,
  `merge_conflict_similarity_threshold` z `processing`.

### 1.5 Refactor EQDPipeline + manifest runu + osobna DB per run + centralny rejestr
- **Refactor** `EQDPipeline.__init__` → przyjmuje opcjonalny gotowy `Config`
  (obok `config_path`), by harness mógł podmieniać id modeli programistycznie
  (patrz Handoff: luka implementacyjna).
- **Nowy moduł** `src/leaderboard/registry.py`:
  - `RunManifest` (Pydantic): `run_id`, `generation_model_id`, `embedding_model_id`,
    `coder_prompt_hash`, `judge_prompt_hash`, `dataset_path`, `dataset_hash`,
    `dataset_size`, `temperature`, `seed`, `k_repeat_index`, `config_snapshot`
    (dict istotnych parametrów `processing`), `created_at`, `run_db_path`,
    `pipeline_version`/`git_sha`.
  - Centralny rejestr = osobna SQLite (`runs/leaderboard.db`) z tabelami:
    - `runs` (kolumny = pola `RunManifest`),
    - `run_metrics` (`run_id`, `metric_name`, `value`, `direction`) — długi format,
      łatwy do pivotu w macierz.
  - API: `register_run(manifest)`, `record_metrics(run_id, metrics: dict)`,
    `load_matrix() -> pivot` (do Fazy 3).
- `pipeline.py`: po obliczeniu metryk zbuduj `RunManifest` (model id z configu,
  hashe promptów przez `hashlib.sha256` na treści promptu, `dataset_hash` z pliku
  wejściowego) i zapisz do rejestru. DB runu = obecna `db_path` (już osobna per run
  przez timestamp w `run_id`).
- Parametry CLI (`scripts/run_pipeline.py`): dodaj `--seed`, `--k-index`
  (domyślnie 0), `--leaderboard-db` (domyślnie `runs/leaderboard.db`).

### 1.6 Rozszerz reasoning_log do pełnej śledzalności
- `src/core/reasoning_log.py`: zapewnij, że per kandydat logujemy:
  `{pass: 1, segment_id, quote_text, span_start, span_end, grounded: bool,
  coder_existing_code_match, top_k: [(ic_id, ic_name, sim)], judge_verdict,
  judge_reasoning, final_action}`. To realizuje wymóg pełnej parametryzacji procesu.
- (`pass` pole już teraz = 1; Faza 2 dołoży `pass: 2`.)

### 1.7 Nowa metryka surowa: `quote_hallucination_rate`
- `src/core/models.py:MetricType`: dodaj `QUOTE_HALLUCINATION_RATE = "quote_hallucination_rate"`.
- `l1_metrics.py`: `quote_hallucination_rate = hallucinated / (grounded + hallucinated)`
  liczone z odrzutów bramki groundingu (z orchestratora). Kierunek: **mniej = lepiej**.
  (Pierwotnie planowane jako `span_error_rate`; po decyzji „LLM nie liczy offsetów"
  błąd spanu nie istnieje — spany liczy kod — więc metryka mierzy niedosłowność/halucynację.)
- `candidate_drop_rate` zostaje, ale teraz oznacza wyłącznie odrzuty przez bramkę
  grounding (bo innych „cichych" odrzutów już nie ma) — w Fazie 1 równe
  `quote_hallucination_rate`. Doprecyzuj docstring.

### 1.8 Testy Fazy 1
- Zaktualizuj `tests/` pod usunięty batch/triage/meta. Dodaj testy:
  - kandydat z błędnym spanem → odrzucony (nie naprawiony), zliczony w
    `span_error_rate`;
  - każdy kandydat trafia do `comparator.evaluate()` (brak ścieżki skrótu);
  - `RunManifest` zapisany do rejestru z kompletem pól;
  - `EQDPipeline` przyjmuje gotowy `Config` i honoruje nadpisane id modeli.

### Weryfikacja Fazy 1
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv \
  --db runs/phase1_smoke.db --no-hil --seed 42
.venv/bin/python -m pytest tests/ -v
```
- Sprawdź `runs/leaderboard.db` → tabela `runs` ma 1 rekord z kompletnym manifestem.
- Sprawdź reasoning_log → każdy kandydat ma top_k + judge_verdict + grounded.
- Potwierdź brak progów/meta/batch w configu i kodzie (grep — Appendix C).

---

## FAZA 2 — drugie przejście (omitted-text audit)  ✅ UKOŃCZONA (2026-06-08)

**Cel:** po pass1 każdej recenzji uruchom pass2 — model dostaje pełną recenzję z
oznaczonymi fragmentami nie-wyciągniętymi, klasyfikuje je (deliberate/accidental) i
może odzyskać dowody. Mierzymy density w dwóch punktach + nowe metryki diagnostyczne.

**Wymaga wczytania:** Context + „DECYZJE PROJEKTOWE (kontrakt)" + „Handoff" +
wynik Fazy 1.

> **Notatka realizacyjna (2026-06-08):** jednostka two-pass = recenzja; pass1
> codera wołany per-recenzję (`coder.process_batch([segment])`), więc recenzja N+1
> widzi ICs z recenzji N (świeży codebook — wierne kontraktowi #2). Tor decyzyjny
> wydzielony do `Layer1Orchestrator._decide_and_apply` (DRY pass1/pass2). Bramki
> pass2: grounding gate (`recovered_hallucinated`) → DEDUP overlap
> (`overlap_drops`, log `overlap_drop`). `recovery_rate` = udział recenzji z ≥1
> zaakceptowanym odzyskiem (komplementarny do `density_delta`, który łapie
> magnitudę znakową). Nagłówek HIL: „Candidates" → „Reviews" (jednostka per-recenzja).
> Nowe pliki: `src/extraction/omitted.py`, `src/extraction/second_pass_agent.py`,
> `tests/test_second_pass.py` (14 testów, fixture'y syntetyczne).

### 2.1 ✅ Nowe modele Pydantic (pass2)
W `src/core/models.py`:
```python
class OmissionType(str, Enum):
    DELIBERATE = "deliberate"   # filler/meta/off-topic — pominięty słusznie
    ACCIDENTAL = "accidental"   # przeoczony (np. lost-in-the-middle)

class OmittedFragmentAssessment(BaseModel):
    omitted_text: str                     # dokładny tekst fragmentu omitted
    reasoning: str                        # CoT — PIERWSZE pole (model myśli przed decyzją)
    omission_type: OmissionType           # dlaczego pominięty
    contains_evidence: bool               # czy fragment zawiera nie-wyciągnięty dowód
    recovered_evidence: Optional[List[RawICCandidate]] = None  # odzyskane dowody (bez offsetów — kod je liczy)

class SecondPassResult(BaseModel):       # agregat — łapie wszystkie fragmenty
    segment_id: str
    fragments: List[OmittedFragmentAssessment] = Field(default_factory=list)
```
- `recovered_evidence` reużywa `RawICCandidate` (bez offsetów) → grounding przez
  `find()` na `canonical_text` całej recenzji (= segment) liczy span, tak jak w
  pass1 → dalej istniejący tor (embedding → sędzia → merge).
- **Kolejność pól w `OmittedFragmentAssessment` jest istotna**: `reasoning` przed
  polami decyzyjnymi (poprawny CoT).

### ✅ 2.2 Programistyczne oznaczanie fragmentów omitted
- **Nowy moduł** `src/extraction/omitted.py`:
  `build_omitted_view(canonical_text, pass1_spans) -> str`.
  - Z `pass1_spans` (lista `(start,end)` zaakceptowanych quotes pass1 dla tej
    recenzji) policz **dopełnienie** spanów (fragmenty przed/między/po evidence).
  - Owiń każdy nie-wyciągnięty fragment w `<omitted>...</omitted>`; fragmenty
    wyciągnięte zostaw jako czysty tekst (model widzi, co już wziął).
  - **Granice brane surowo po spanach** (akceptujemy tag w połowie zdania —
    decyzja użytkownika; deterministyczne i wierne).
  - Zwróć string-widok recenzji do promptu pass2.

### ✅ 2.3 Agent pass2 (ten sam model)
- **Nowy moduł** `src/extraction/second_pass_agent.py` (wzór: `coder_agent.py`):
  - `assess_omitted(segment, pass1_spans, codebook_context) -> SecondPassResult`.
  - Buduje prompt z `build_omitted_view`; jeden API call per recenzja; instructor
    z `response_model=SecondPassResult`.
  - Model = ten sam slot generacyjny co coder (kontrakt #3/#9).
- **Nowe prompty** w `prompts.py`:
  `build_second_pass_system_prompt()` + `build_second_pass_user_prompt(view)`.
  Zadanie: „dla każdego `<omitted>` fragmentu: najpierw `reasoning` (CoT, czy
  zawiera nie-wyciągnięty dowód), potem `omission_type` (deliberate/accidental),
  `contains_evidence`, i jeśli tak — `recovered_evidence` jako pełne ICCandidate
  (quote = dokładny podciąg, span względem całej recenzji)".

### ✅ 2.4 Integracja w orchestratorze — per recenzja two-pass
- `orchestrator.py`: zrestrukturyzuj tak, by jednostką two-pass była **recenzja**:
  ```
  dla każdej recenzji (segmentu):
    pass1: coder.extract → kandydaci → tor decyzyjny (embedding+sędzia+merge)
    snapshot density_pass1 (union spanów zaakceptowanych quotes pass1 tej recenzji)
    zbuduj omitted-view z pass1_spans
    pass2: second_pass_agent.assess_omitted → SecondPassResult
      dla każdego recovered ICCandidate:
        grounding gate (Tier 1) → jeśli przejdzie:
          DEDUP: odrzuć, jeśli span nakłada się na którykolwiek span pass1 tej recenzji
          → embedding + sędzia + merge (ten sam tor)
    snapshot density_pass2 (union spanów pass1 ∪ zaakceptowane pass2)
    zapisz density_pass1, density_pass2, fragmenty omitted do agregacji
  ITS/saturation tracking pozostaje per batch (grupowanie recenzji).
  ```
- **DEDUP overlap** (kontrakt): odzyskany quote pass2 odrzucamy, jeśli jego span
  `(s,e)` nakłada się na dowolny span zaakceptowany w pass1 tej recenzji
  (`max(s,s1) < min(e,e1)`). Nowy, jawny krok — loguj jako `pass2_overlap_drop`.
- reasoning_log: rekordy pass2 z `pass: 2`, `omission_type`, `contains_evidence`,
  `reasoning`, oraz dla recovered — pełny ślad jak w pass1.

### ✅ 2.5 Nowe metryki (dwupunktowa density + diagnostyka pass2)
- `MetricType` (dodaj): `DENSITY_PASS1`, `DENSITY_PASS2`, `DENSITY_DELTA`,
  `RECOVERY_RATE`, `ACCIDENTAL_OMISSION_RATIO`, `DELIBERATE_OMISSION_RATIO`.
- `l1_metrics.py` — przebuduj pomiar density na **dwupunktowy per recenzja**
  (kontrakt #13): zbieraj snapshoty z orchestratora (in-memory), nie tylko
  agregat z DB. Nowe metryki:
  - `density_pass1`, `density_pass2` — średnie po recenzjach (opisowe).
  - `density_delta = density_pass2 − density_pass1` — **wewn.-referencyjna**;
    duży delta = pass1 dużo zgubił (gorzej skalibrowany). Kierunek: mniej = lepiej.
  - `recovery_rate` — udział recenzji/znaków odzyskanych w pass2. Wewn.-referencyjna.
  - `accidental_omission_ratio = accidental / (accidental + deliberate)` po
    fragmentach omitted — **kluczowy dyskryminator uwagi modelu**. Mniej = lepiej.
  - (opcjonalnie macierz 2×2 `omission_type × contains_evidence` jako sygnał
    spójności modelu — komórki „dziwne", np. accidental ∧ ¬contains_evidence.)
- `pipeline.py`: przekaż snapshoty density + statystyki pass2 z `layer1_summary`
  do `metrics_engine.compute_all`.

### ✅ 2.6 Testy Fazy 2
- `build_omitted_view`: poprawne dopełnienie spanów (przed/między/po), surowe
  granice, brak nakładania tagów.
- DEDUP: recovered quote nakładający się na pass1 → odrzucony.
- Recovered evidence przechodzi pełny tor (grounding → sędzia → merge).
- density_pass1 ≤ density_pass2 (pass2 tylko dokłada); poprawne `density_delta`.
- Parsowanie `SecondPassResult` z `reasoning` przed polami decyzyjnymi.

### Weryfikacja Fazy 2
```bash
.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv \
  --db runs/phase2_smoke.db --no-hil --seed 42
.venv/bin/python -m pytest tests/ -v
```
- Reasoning_log: rekordy `pass:2` z `omission_type`/`contains_evidence`/`reasoning`.
- Metryki: `density_pass1`, `density_pass2`, `density_delta`, `recovery_rate`,
  `accidental_omission_ratio` obecne i sensowne.
- Rejestr runów (`run_metrics`) zawiera nowe metryki.

---

## FAZA 3 — leaderboard (macierz modeli)  ⏳ DO ZROBIENIA

**Cel:** uruchamiać L1 dla wielu (model generacyjny × model embeddingowy),
zbierać metryki do macierzy, oceniać embedding bezprogowym AUC. k=1 teraz,
architektura pod k=N.

**Wymaga wczytania:** Context + „DECYZJE PROJEKTOWE (kontrakt)" + „Handoff" +
wyniki Faz 1–2 (rejestr runów, jeden tor decyzyjny, metryki).

### 3.1 Sędzia ślepy na cosinus (do AUC)
- `prompts.py`: nowy `build_comparator_system_prompt_simblind()` +
  `build_comparator_user_prompt_simblind()` — orzeka merge/new/reject **wyłącznie z
  tekstów** (quote+definicja kandydata vs definicje top-k ICs), BEZ podawania
  wartości podobieństwa (kontrast: obecny prompt 267-308 podaje sim jako „primary
  signal" → cyrkularne dla oceny embeddingu).
- `codebook_comparator.py`: tryb `eval_mode` (flaga) → używa promptu sim-blind i
  zapisuje parę `(max_sim, judge_verdict)` dla każdego kandydata (pełny zakres
  podobieństwa, bo sędzia ocenia wszystkich — kontrakt #6/#7).

### 3.2 Metryka `embedding_separation_auc`
- `MetricType`: dodaj `EMBEDDING_SEPARATION_AUC`.
- `l1_metrics.py`: zbierz pary `(cosine_sim_top1, judge ∈ {merge, new})` (REJECT
  pomiń lub potraktuj jak „new" — do ustalenia w implementacji), policz **AUC**
  (np. statystyka U Manna-Whitneya / ranking; bez zewn. zależności — własna
  implementacja na rankach). Kierunek: **więcej = lepiej**. To kolumna oceny osi
  embeddingowej w macierzy.

### 3.3 Harness leaderboardu
- **Nowy moduł** `src/leaderboard/harness.py`:
  - Wejście: lista `generation_model_id`, lista `embedding_model_id`, dataset,
    `k` (powtórzenia), seed bazowy.
  - Dla każdej kombinacji × `k_repeat_index`: zbuduj `Config` z override
    (podmień `agents.coder_agent.model`, `agents.codebook_comparator.model`,
    `agents.embedding.model`; agent pass2 i refinement dziedziczą slot generacyjny),
    przekaż gotowy `Config` do `EQDPipeline(config=...)` (refaktor z Fazy 1.5),
    odpal `EQDPipeline.run(..., enable_hil=False)` do osobnej DB runu,
    zarejestruj `RunManifest` + metryki (Faza 1.5).
  - **Headless** zawsze (kontrakt #10).
- **Nowy skrypt** `scripts/run_leaderboard.py` — CLI nad harnessem
  (`--gen-models`, `--embed-models`, `--dataset`, `-k`, `--seed`).

### 3.4 Agregacja i prezentacja macierzy
- `src/leaderboard/registry.py:load_matrix()` → pivot `run_metrics`:
  wiersze = metryki, kolumny = (gen_model × embed_model), komórki = wartość
  (przy k>1: średnia ± odchylenie po `k_repeat_index`).
- **Nowy moduł** `src/leaderboard/report.py`: render macierzy (Markdown/CSV; HTML
  opcjonalnie). Oznacz **kierunek** metryk (patrz Appendix A).
- Wariancja (k>1): raportuj odchylenie jako sygnał stabilności modelu.

### 3.5 Testy Fazy 3
- AUC: syntetyczne pary (idealna separacja → ~1.0; przeplot → ~0.5).
- Sędzia sim-blind: prompt nie zawiera wartości podobieństwa.
- Harness: 2 modele gen × 1 embedding × k=1 → 2 rekordy w rejestrze; `load_matrix`
  zwraca poprawny pivot.
- k=2 → agregacja średnia ± odchylenie.

### Weryfikacja Fazy 3
```bash
.venv/bin/python scripts/run_leaderboard.py \
  --gen-models or_smart,or_fast --embed-models embed_openai \
  --dataset data/canonical_top10.csv -k 1 --seed 42
.venv/bin/python -m pytest tests/ -v
```
- `runs/leaderboard.db` → po jednym rekordzie na kombinację.
- `report.py` renderuje macierz z kierunkami i (przy k>1) wariancją.

---

## Zgodność z DESIGN_PRINCIPLES.md

Plan sprawdzony względem `docs/reference/DESIGN_PRINCIPLES.md`:

- **#1 Raw data immutable** ✅ — pass2 tylko dodaje evidence; nigdy nie modyfikuje
  quotes pass1. Dedup odrzuca nowe nakładające się, nie zmienia istniejących.
- **#2 Traceable** ✅ wzmacnia — run manifest + reasoning_log (Appendix B) + osobna
  DB per run = pełny audit trail. `existing_code_match` logowany, nie ukrywany.
- **#3 Bottom-up first** ✅ — brak seed themes/predefiniowanych kategorii; pass2 to
  nadal indukcja nad surowym tekstem.
- **#4 HIL gdzie dodaje sygnał** ✅ — runy benchmarkowe headless (kontrakt #10),
  ale interaktywna ścieżka `CodebookSignoff` (HIL) pozostaje dla normalnych runów.
- **#5 Non-destructive / versioning** ⚠️→✅ — osobna DB per run = immutable artifacts
  per run. **Jedyna luka:** IC refinement nadpisuje definicję w miejscu →
  naprawione w kontrakcie #15 (logować `original_definition` przed zmianą).
- **#6 Provider agnosticism** ✅ wzmacnia — leaderboard = czysto config-driven
  podmiana modeli (`agents.*.model`); żadnej logiki provider-specific w warstwach
  (quirki w `config.py`). Harness override przez `Config`, nie przez kod warstw.
- **#7 Transparent, nie black-box** ✅ wzmacnia — usunięcie protez (auto-korekta
  spanów, meta-filtr, ciche progi) eliminuje „ciche ratowanie" słabych modeli; każdy
  odrzut (grounding gate, dedup overlap) jest logowany i zliczany w metryce
  (`span_error_rate`, `pass2_overlap_drop`). Silent failures = bugs.

## Appendix A — finalny spis metryk macierzy

| Metryka | Faza | Kierunek | Typ |
|---|---|---|---|
| grounding | istn. | więcej=lepiej | opisowa/jakość |
| quote_hallucination_rate | 1 | mniej=lepiej | wewn.-ref. |
| candidate_drop_rate | istn./1 | mniej=lepiej | wewn.-ref. |
| ic_concentration (singleton_ratio) | istn. | — | opisowa |
| merge_rate | istn. | — | opisowa |
| coder_confidence | istn. | — | opisowa |
| coder_reuse (2×2) | istn. | — | opisowa (z `existing_code_match` jako sygnał) |
| ITS / saturation_curve | istn. | — | opisowa |
| cross_review_convergence | istn. | więcej=lepiej | judgment-call |
| density_pass1 | 2 | — | opisowa |
| density_pass2 | 2 | — | opisowa |
| density_delta | 2 | mniej=lepiej | wewn.-ref. |
| recovery_rate | 2 | (z density_delta) | wewn.-ref. |
| accidental_omission_ratio | 2 | mniej=lepiej | wewn.-ref. |
| embedding_separation_auc | 3 | więcej=lepiej | ocena embeddingu |

Usunięte w v2: `triage_efficiency`, `comparator_agreement` (zastąpione przez AUC),
meta-filtr.

## Appendix B — zakres reasoning_log per kandydat (śledzalność)
`{run_id, pass (1|2), segment_id, quote_text, span_start, span_end, grounded,
coder_existing_code_match, top_k:[(ic_id,ic_name,sim)], judge_verdict,
judge_reasoning, final_action}`; dla pass2 dodatkowo
`{omission_type, contains_evidence, reasoning, pass2_overlap_drop}`.

## Appendix C — usunięcia (sanity-check po Fazie 1, grep)
`segments_per_coder_call>1`/BatchCodingResult, Tier 2/3 span fix, **offsety w
schemacie LLM** (LLM zwraca tylko `quote_text`; offset liczy kod), `is_meta_commentary`,
`meta_ic_filter`, `auto_new_threshold`, `auto_merge_threshold`,
`merge_conflict_similarity_threshold`, ścieżka `existing_matches`/`_apply_existing_match`.
