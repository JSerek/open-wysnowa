# EQD-AI v2 — P0: integralność pomiaru (spec projektowy)

> **Status:** ✅ zrealizowane (2026-09-24, `PIPELINE_VERSION = "v2-p0"`). Plan:
> `docs/planning/P0_measurement_integrity_plan.md`.
> **Źródła:** rekomendacje P0 #1–#3 z `docs/research/2026-09-llm-qda-landscape.md`
> (§ rekomendacje), specyfikacje P0-1…P0-3 z
> `notes/2026-06-09-propozycje-zmian-po-recenzji.md`.

## 1. Cel i kryterium sukcesu

Rekomendacje P0 mają zostać zrobione **przed kolejnymi pomiarami**. Chodzi o to,
żeby kolejne runy leaderboardu dawały wiarygodne `embedding_separation_auc`,
`merge_rate` i sygnały wierności cytatów, a runy sprzed poprawki były jawnie
oddzielone.

Sukces oznacza, że:
- awaria sędziego LLM nie tworzy pary AUC i jest widoczna jako `judge_failure_rate`
  w summary, rejestrze i raporcie;
- w trybie `--no-hil` MERGE trafia do IC wskazanego przez sędziego, a nie do top-1;
- każdy odrzucony cytat jest zalogowany w całości z klasą odrzutu, a raportowana
  wierność cytatów nie jest cyrkularna;
- przy frazie występującej w segmencie wielokrotnie wybór wystąpienia jest
  świadomy i policzony;
- macierz leaderboardu nie uśrednia runów `v2-p0` ze starszymi.

**Poza zakresem:** przeliczanie starych baz, zmiany promptów (P1), permutacje i k
powtórzeń (P1), usuwanie `attempt_realign()` / `verify_ic_quotes` (celowo
zostają), migracje schematu SQLite.

## 2. Ustalenia empiryczne, które ukształtowały zakres

- **v2 nie ma etapu naprawy cytatów.** Bramka jest twarda (`find()` albo odrzut).
  Cyrkularność „grounding po naprawie” z v1 w v2 wraca w innej postaci: metryka
  `grounding` sprawdza cytaty już zapisane w bazie, czyli takie, które przeszły
  bramkę, więc daje 1.0 z definicji.
- **Duplikaty fraz:** w 6 runach (≈400 cytatów) żaden cytat nie występuje w swoim
  segmencie więcej niż raz. Efekt +30–50 pp z [73] dotyczy krótkich, powtarzalnych
  spanów. U nas poprawka P0 #3 jest defensywna, a licznik ma pokazać, czy problem
  kiedykolwiek się pojawi.
- **Odrzuty:** w `top10_ollama_qwen.log` 9 z 13 odrzutów to cytaty sklejone przez
  „...”, a nie zmyślenia. Pass-1 nie zapisuje dziś odrzutów w reasoning logu (w logu
  tekstowym jest tylko pierwsze 60 znaków).
- **Rejestr:** `RunManifest.pipeline_version` istnieje (`"v2-phase2"`), ale
  `RunRegistry.load_matrix()` uśrednia wszystkie runy w jednej komórce,
  niezależnie od wersji.

## 3. Decyzje (kontrakt)

| # | Decyzja | Alternatywy odrzucone |
|---|---------|------------------------|
| D1 | **Twarda bramka + diagnostyka.** Kontrakt #4 bez zmian: przyjmujemy tylko dokładne dopasowanie. Klasyfikacja odrzutu działa wyłącznie po odrzucie i nigdy niczego nie przyjmuje. | Poziomy tolerancji z akceptacją; strict + normalized. |
| D2 | **Duplikaty: tania poprawka + licznik.** Pierwsze wystąpienie, które nie nachodzi na zajęte spany; bez zmian w prompcie i w `RawICCandidate`. | Pełne indeksowanie wystąpień w prompcie; sam licznik. |
| D3 | **Fallback sędziego: NEW z jawnym statusem.** Awaria sędziego oraz MERGE do celu spoza top-k kończą się NEW; oba przypadki są policzone i zalogowane. | Pominięcie kandydata; przerwanie runu powyżej progu. |
| D4 | **Zakres przyległy:** twardy `verify()` (helper `_persist_quote`), oznaczenie i oddzielenie starych runów w rejestrze, `judge_failure_rate` w raporcie. **Bez** usuwania `attempt_realign()`. | Tylko rdzeń P0; rdzeń + sprzątanie. |
| D5 | **Logika groundingu jako czysta funkcja w `src/preprocessing/grounding.py`**, wspólna dla pass-1 i pass-2. | Rozbudowa `CoderAgent._ground_candidate`; klasyfikacja post-hoc w metrykach. |
| D6 | **Nierozwiązany cel MERGE zachowuje `decision_path="llm"`**, a jego para AUC (werdykt MERGE) zostaje. Jedyne nowe `decision_path` to `"llm_failed"`. | Osobne `decision_path="merge_target_unresolved"`. |
| D7 | **Bez zmian w schemacie SQLite.** Diagnostyka trafia do reasoning logu, summary i rejestru. | Kolumna `match_level` w `verbatim_quotes`. |

## 4. Projekt

### 4.1. Grounding (P0 #2 + P0 #3) — `src/preprocessing/grounding.py`

Nowa jednostka reeksportowana z `src.preprocessing`:

```python
class DropClass(str, Enum):
    NORMALIZED_WS   = "normalized_ws"    # found after whitespace/typographic normalization
    CASE            = "case"             # ...and after lowercasing
    ELLIPSIS_STITCH = "ellipsis_stitch"  # split on "..."/"…", every fragment found
    UNMATCHED       = "unmatched"        # paraphrase or fabrication — not distinguished

@dataclass(frozen=True)
class QuoteMatch:
    span: Optional[Tuple[int, int]]      # None → dropped
    n_occurrences: int                   # exact occurrences in canonical
    resolution: Optional[str]            # "unique" | "first_free" | "first_fallback"
    drop_class: Optional[DropClass]      # set only when span is None

def locate_quote(
    quote_text: str,
    canonical: str,
    claimed_spans: Sequence[Tuple[int, int]] = (),
) -> QuoteMatch
```

**Reguły:**
- **Akceptacja** wymaga dokładnego dopasowania podciągu. Niezmiennik: przy
  `span is not None` zawsze `canonical[s:e] == quote_text`.
- **Wystąpienia** są liczone z nakładaniem (szukanie od `idx + 1`).
- **Wybór wystąpienia:**
  - 1 wystąpienie → `resolution="unique"`;
  - więcej → pierwsze, które nie nachodzi na żaden z `claimed_spans` (`"first_free"`);
  - wszystkie nachodzą → pierwsze (`"first_fallback"`).
  - Nachodzenie oznacza niepuste przecięcie przedziałów półotwartych.
- **Klasyfikacja odrzutu** jest liczona tylko przy braku dokładnego dopasowania.
  Klasy są sprawdzane po kolei, wygrywa pierwsza pasująca:
  1. `normalized_ws`: po NFKC, zamianie typograficznych cudzysłowów, apostrofów i
     myślników na ASCII oraz zwinięciu białych znaków (w cytacie i w tekście
     kanonicznym) cytat jest podciągiem;
  2. `case`: jak wyżej, dodatkowo po `lower()`;
  3. `ellipsis_stitch`: cytat zawiera „...” lub „…”, a każdy niepusty fragment
     po podziale (znormalizowany, lowercase, bez brzegowych kropek i spacji) jest
     podciągiem;
  4. `unmatched`: wszystko pozostałe.

**`claimed_spans`:**
- **pass-1:** spany kandydatów z tej samej odpowiedzi LLM, które przeszły bramkę
  wcześniej (w kolejności zwróconej przez model);
- **pass-2:** zaakceptowane spany z pass-1 danego segmentu. Jeśli fraza występuje
  ponownie w pominiętym fragmencie, pass-2 trafia w to wystąpienie i nie jest
  odrzucany przez bramkę overlap.

**Przepływ:**
- `CoderAgent._ground_candidate` zostaje usunięte. Pass-1 (`CoderAgent`) i pass-2
  (orchestrator, `orchestrator.py` ≈ l. 512) wołają `locate_quote` i budują
  `ICCandidate` ze spanu.
- `CoderAgent` zachowuje `last_drop_counts` (bez zmian) i dodaje
  `last_drops: Dict[str, List[GroundingDrop]]`, gdzie
  `GroundingDrop = (ic_name, quote_text, drop_class)`.
- Orchestrator loguje każdy odrzut z pass-1 jako rekord reasoning logu:
  `{"type": "grounding_drop", "pass": 1, "segment_id", "ic_name", "quote_text"
  (pełny), "drop_class", "grounded": false, "final_action": "grounding_drop"}`.
  Istniejący rekord `pass2_grounding_drop` dostaje pole `drop_class`.
- Rekordy `candidate` (pass-1 i pass-2) dostają pola `n_occurrences` i
  `occurrence_resolution`.
  Pełni to rolę per-cytatowego „poziomu dopasowania” z rekomendacji, dostosowanego
  do D1. `ICCandidate` dostaje dwa opcjonalne pola (`n_occurrences: int = 1`,
  `occurrence_resolution: Optional[str] = None`), z których korzysta rekord.
  Model `VerbatimQuote` i schemat DB się nie zmieniają.

**Summary (`Layer1Orchestrator.run`):**
- `grounding_drop_classes: Dict[str, int]` (pass-1);
- `pass2_stats["drop_classes"]: Dict[str, int]`;
- `ambiguous_occurrences: {"first_free": int, "first_fallback": int}` (oba przejścia);
- `accepted_quotes_total: int`: liczba kandydatów, którzy przeszli bramkę (pass-1 +
  pass-2), jako mianownik dla `ambiguous_occurrence_rate`.

### 4.2. Sędzia i merge target (P0 #1) + twardy `verify()`

**`codebook_comparator.py::evaluate`:**
- wyjątek z `_get_llm_recommendation` (po retry) ustawia `judge_failed = True`, a
  rekomendacja nadal brzmi NEW (reasoning jak dotąd);
- `eval_pairs.append(...)` tylko gdy `eval_mode and not judge_failed` i werdykt ∈
  {MERGE, NEW};
- `meta = {"decision_path": "llm_failed" | "llm", "judge_failed": bool,
  "judge_error": Optional[str], "max_sim", "llm_recommendation"}`.

**`orchestrator.py`:**
- `self.decision_paths` inicjalizowane z kluczem `"llm_failed": 0`;
- nowy `@staticmethod _resolve_merge_target(name, top_k) -> Optional[int]`
  (1-based) szuka najpierw dokładnego dopasowania `ic_name`, potem po `strip().lower()`.
  `None` albo brak na shortliście zwraca `None`;
- gałąź bez HIL w `_decide_and_apply`:
  - `action == "M"` z rozwiązanym celem → `target_idx` wskazany przez sędziego;
  - nierozwiązany cel → `action = "N"`, notatka `"auto-accepted; MERGE target
    unresolved → fallback NEW"`, `summary["merge_target_unresolved"] += 1`.
    `decision_path` zostaje `"llm"` (D6);
- `summary["judge_merge_verdicts"] += 1` przy każdym werdykcie MERGE sędziego
  (także nierozwiązanym, także w HIL);
- rekord `candidate` w reasoning logu dostaje `judge_failed`, `merge_target_name`
  (wskazanie sędziego) i `merge_target_resolved` (nazwa IC, do którego faktycznie
  trafił cytat, albo `None`);
- tryb HIL się nie zmienia (cel wybiera człowiek).

**Helper `_persist_quote(candidate, segment_id, ic_id, defer_embed) -> VerbatimQuote`**
(wspólny dla `_apply_new` i `_apply_merge`; to minimalny wycinek P2-1):
- buduje `VerbatimQuote` i **weryfikuje go przed jakimkolwiek insertem**, także
  przed utworzeniem IC w `_apply_new`. Weryfikacja jest więc rozdzielona od insertu:
  najpierw `_build_verified_quote(...)`, potem inserty;
- `segment is None` → `RuntimeError`; `verify() is False` → `RuntimeError`
  z nazwą IC, `segment_id` i spanem. Po błędzie w bazie nie ma ani IC, ani cytatu.

### 4.3. Metryki i leaderboard

**`L1MetricsEngine` (`src/eval/l1_metrics.py`):**
- **nowa `compute_judge_reliability(decision_paths, merge_target_unresolved,
  judge_merge_verdicts)`** zwraca `judge_failure_rate = llm_failed / (llm +
  llm_failed)` (0.0 przy mianowniku 0), `merge_target_unresolved_rate =
  unresolved / judge_merge_verdicts` (0.0 przy mianowniku 0) oraz surowe liczniki;
- **`compute_quote_hallucination_rate`** dostaje `drop_classes` i
  `pass2_drop_classes` oraz zwraca dodatkowo rozbicie i `unmatched_quote_rate =
  drop_classes["unmatched"] / (grounded + dropped)` dla pass-1.
  `quote_hallucination_rate` bez zmian;
- **nowa `compute_ambiguous_occurrences(ambiguous_occurrences,
  accepted_quotes_total)`** zwraca `ambiguous_occurrence_rate` oraz podział
  `first_free` / `first_fallback`;
- **`compute_grounding` → `compute_span_integrity`**, klucz wyniku `"span_integrity"`
  (logika bez zmian). Semantyka: sanity check, 1.0 oczekiwane, a wartość <1.0
  oznacza bug i jest logowana na poziomie ERROR. `MetricType.GROUNDING` zostaje
  (bez migracji enuma w DB);
- `compute_all` przyjmuje nowe kwargs z summary.

**`src/extraction/pipeline.py`:**
- `_flatten_metrics`: `grounding_rate` → `span_integrity`; nowe klucze:
  `judge_failure_rate`, `merge_target_unresolved_rate`, `unmatched_quote_rate`,
  `ambiguous_occurrence_rate`;
- `_METRIC_DIRECTIONS`: `span_integrity: "more"`, cztery nowe: `"less"`.

**`src/leaderboard/registry.py`:**
- `PIPELINE_VERSION = "v2-p0"`;
- `load_matrix(pipeline_version: Optional[str] = PIPELINE_VERSION)` filtruje
  `runs.pipeline_version`, a `None` oznacza wszystkie wersje. Wynik zawiera
  dodatkowo `"pipeline_version"` oraz `"excluded_runs": int` (runy innych wersji).

**`src/leaderboard/report.py`:**
- nagłówek raportu podaje wersję i liczbę pominiętych runów;
- kolumny, w których któryś run ma `judge_failure_rate > 0`, dostają znacznik ⚠
  i przypis „awarie sędziego — wynik niewiarygodny”.

**`scripts/run_pipeline.py`:** podsumowanie CLI wypisuje `judge_failure_rate`,
`merge_target_unresolved` i rozbicie klas odrzutów.

## 5. Testy i weryfikacja

Stan wyjściowy: **224 testy green** (2026-09-24). TDD: testy powstają przed kodem.

- **`tests/test_grounding.py` (`locate_quote`):**
  - `unique`, `first_free`, `first_fallback`;
  - po jednym przypadku na każdą klasę odrzutu;
  - pierwszeństwo klas (przypadek spełniający `case` i `ellipsis_stitch` → `case`);
  - niezmiennik spanu;
  - pusty cytat / pusty tekst.
- **`tests/test_coder_agent.py`:** `last_drops` z pełnym cytatem i klasą;
  `last_drop_counts` bez zmian; dwa kandydaty z tą samą, powtórzoną frazą dostają
  różne spany.
- **`tests/test_codebook_comparator.py`:** wyjątek sędziego → NEW,
  `decision_path == "llm_failed"`, `judge_failed is True`, puste `eval_pairs`
  w eval mode.
- **`tests/test_orchestrator.py`:**
  - `_resolve_merge_target`: exact, case-insensitive, nazwa spoza listy → `None`,
    `None` → `None`;
  - MERGE na top-2 kończy się cytatem przy top-2;
  - MERGE na nazwę spoza listy tworzy nowy IC, `merge_target_unresolved == 1`, a
    para AUC zostaje;
  - `_persist_quote` z niezgodnym spanem rzuca `RuntimeError` i nie zostawia w bazie
    ani IC, ani cytatu;
  - pass-2 trafia w drugie wystąpienie frazy zamiast w bramkę overlap;
  - rekordy `grounding_drop` lądują w reasoning logu.
- **`tests/test_l1_metrics.py`:** `judge_failure_rate`,
  `merge_target_unresolved_rate`, `unmatched_quote_rate`,
  `ambiguous_occurrence_rate`, `span_integrity` (także przy mianowniku 0).
- **`tests/test_leaderboard_registry.py` / `test_leaderboard_phase3.py`:**
  filtr wersji w `load_matrix` (domyślny i `None`), `excluded_runs`, ⚠ w raporcie,
  nowe klucze w `_flatten_metrics`.

**Weryfikacja końcowa:**
1. `.venv/bin/python -m pytest tests/ -v`: wszystko green, liczba testów > 224.
2. Smoke: `.venv/bin/python scripts/run_pipeline.py data/canonical_top10.csv --db
   runs/p0_smoke.db --no-hil`. Sprawdzam `span_integrity == 1.0`, obecność nowych
   metryk w summary i rekordy `grounding_drop` w reasoning logu (jeśli były odrzuty).
3. Opcjonalnie (płatne API): jeden run leaderboardu, który potwierdza, że matryca
   `v2-p0` jest oddzielona od starszych runów.

**Dokumentacja po implementacji:** `CLAUDE.md` (sekcja L1 metrics: `span_integrity`
+ cztery nowe metryki, wersja `v2-p0`), `docs/planning/IDEAS.md` (P0 zrobione,
runy `v2-phase2` obciążone).

## 6. Ryzyka

- **Rename `grounding_rate` → `span_integrity`** zmienia nazwę wiersza w rejestrze.
  Stare runy mają stary klucz, ale filtr wersji i tak je oddziela, więc nie jest
  potrzebna migracja.
- **`first_free` w pass-1** zależy od kolejności kandydatów zwróconej przez model.
  Przy duplikatach i dwóch kodach przypisanie wystąpień może być zamienione.
  Akceptujemy to, bo na obecnych danych nie ma duplikatów, a przypadek jest
  policzony w `ambiguous_occurrences`.
- **Fallback NEW** nadal lekko zawyża liczbę IC przy awariach. Jest to widoczne
  w `judge_failure_rate` i `merge_target_unresolved_rate` (D3).
