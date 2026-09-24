# Local-model leaderboard — feasibility test

**Status:** feasibility done (2026-09-23/24) — wyniki w sekcji 8 · **Dataset:** `data/canonical_top10.csv` · **Registry:** `runs/leaderboard_local.db` (smoke, 3 recenzje), `runs/leaderboard_local_top10.db` (top10)

## 1. Cel

Sprawdzić, czy lokalne modele generatywne (Ollama na Macu) jako `coder_agent` +
`codebook_comparator` dają sensowną ekstrakcję dowodów w leaderboardzie L1 —
grounding, brak halucynacji cytatów, rozsądne metryki — względem dotychczasowych
runów chmurowych (OpenRouter/Gemini). Iteracja 1 to **feasibility na dwóch modelach**
(qwen + gemma), zanim dołożymy trzeci.

Constraint sprzętowy: Mac nie udźwignie dwóch lokalnych modeli naraz. Ollama trzyma
model w RAM przez `keep_alive` (~5 min), więc modele uruchamiamy **osobnymi
wywołaniami z jawnym `ollama stop` pomiędzy** — nigdy jednym wywołaniem z listą.

Embedding pozostaje chmurowy (`embed_openai` / `text-embedding-3-small`) — wariant z
lokalnym embeddingiem opisany w sekcji 6.

Modele (tagi z `ollama list`):

| Klucz w configu | Tag Ollama | Rozmiar | Uwagi |
|---|---|---|---|
| `ollama_qwen` | `qwen3.6:35b-a3b` | 23 GB | MoE (~3B aktywnych), thinking domyślnie ON |
| `ollama_qwen38` | `qwen3.8:27b` | 17 GB | dense 27B, thinking domyślnie ON; ~14% offload na CPU |
| `ollama_gemma` | `gemma4:26b-a4b-it-q8_0` | 28 GB | MoE (~4B aktywnych), thinking domyślnie ON |
| `ollama_gptoss` | `gpt-oss:20b` | 13 GB | reasoner — faza 2 (nie uruchamiany) |

## 2. Konfiguracja (`eqd_config.yaml`)

```yaml
providers:
  ollama:
    type: openai_compatible
    api_key_env: OLLAMA_API_KEY
    base_url: http://localhost:11434/v1
    instructor_mode: json

models:
  ollama_qwen:   { provider: ollama, model_id: qwen3.6:35b-a3b,        reasoning: false, extra_body: {reasoning_effort: none} }
  ollama_qwen38: { provider: ollama, model_id: qwen3.8:27b,            reasoning: false, extra_body: {reasoning_effort: none} }
  ollama_gemma:  { provider: ollama, model_id: gemma4:26b-a4b-it-q8_0, reasoning: false, extra_body: {reasoning_effort: none} }
  ollama_gptoss: { provider: ollama, model_id: gpt-oss:20b,            reasoning: false }
```

**Thinking trzeba wyłączyć jawnie.** Samo `reasoning: false` tylko *nie wysyła*
parametru — a qwen3.6, qwen3.8 i gemma4 w Ollamie myślą domyślnie. Dlatego
`NamedModel.extra_body` (`614ec8a`): statyczny `extra_body` doklejany do każdego
wywołania (coder, second pass, sędzia, refinement), wygrywający z translacją
`reasoning_effort` agenta. W endpointcie OpenAI-compat Ollamy
`reasoning_effort: "none"` wyłącza thinking całkowicie (test: 253 → 16 tokenów
completion dla gemmy, 83 → 17 dla qwen3.8; pole `reasoning` puste). Harness nadpisuje
`model` agentów per-run, więc bloki `agents:` zostają nietknięte.

## 3. Pre-flight (read-only)

```bash
ollama ps                                   # co jest w RAM
curl -s http://localhost:11434/v1/models    # endpoint OpenAI-compat odpowiada
ollama stop --all 2>/dev/null || true       # czysty start
```

## 4. Smoke test — bramka zgodności (jeden model, szybko)

Cel: potwierdzić, że structured output przez instructor JSON działa lokalnie
(parsuje się JSON, nie wycieka „thinking", ICs powstają). Najpierw trudniejszy
reasoner — qwen.

```bash
.venv/bin/python scripts/run_leaderboard.py \
  --gen-models ollama_qwen \
  --embed-models embed_openai \
  --dataset data/canonical_top10.csv \
  --limit 3 \
  --leaderboard-db runs/leaderboard_local.db \
  --log-level INFO
```

**Pass:** brak wyjątków parsowania, niezerowa liczba ICs, `grounding_rate` > 0,
`quote_hallucination_rate` niskie. Fail → patrz Ryzyka.

## 5. Feasibility: dwa modele sekwencyjnie (qwen → gemma)

```bash
# --- Model 1: qwen ---
.venv/bin/python scripts/run_leaderboard.py \
  --gen-models ollama_qwen \
  --embed-models embed_openai \
  --dataset data/canonical_top10.csv \
  --leaderboard-db runs/leaderboard_local.db \
  --seed 42 --csv-out runs/leaderboard_local.csv

ollama stop qwen3.6:35b-a3b        # zwolnij RAM

# --- Model 2: gemma ---
.venv/bin/python scripts/run_leaderboard.py \
  --gen-models ollama_gemma \
  --embed-models embed_openai \
  --dataset data/canonical_top10.csv \
  --leaderboard-db runs/leaderboard_local.db \
  --seed 42 --csv-out runs/leaderboard_local.csv

ollama stop gemma4:26b-a4b-it-q8_0
```

Drugie wywołanie renderuje macierz z **całego** rejestru, więc na końcu widać obie
kolumny obok siebie (qwen × embed_openai, gemma × embed_openai). `--seed 42` dla
powtarzalności; `k=1` (domyślnie) wystarcza na feasibility.

## 6. Faza 2: trzeci model

Ten sam wzorzec, jedno wywołanie + `ollama stop`:

```bash
.venv/bin/python scripts/run_leaderboard.py \
  --gen-models ollama_gptoss \
  --embed-models embed_openai \
  --dataset data/canonical_top10.csv \
  --leaderboard-db runs/leaderboard_local.db \
  --seed 42 --csv-out runs/leaderboard_local.csv
ollama stop gpt-oss:20b
```

## 7. Przyszły wariant: lokalny embedding (osobna seria)

- `ollama pull nomic-embed-text` (lub inny lokalny embed).
- Dodać `embed_ollama` w `models:` (`provider: ollama`, `model_id: nomic-embed-text`).
- Uruchomić z `--embed-models embed_ollama`.
- **Uwaga:** inny model embeddingu ⇒ `embedding_separation_auc` **nie jest
  porównywalne** z runami na `embed_openai`; traktować jako osobną serię (osobna baza
  rejestru zalecana).

## 8. Wyniki (2026-09-23/24)

Wszystkie runy: thinking OFF (poza pierwszym smoke qwen3.6), `embed_openai`,
`--seed 42`, k=1 na wywołanie. **Uwaga na wersję kodu:** poprawki P0 weszły 2026-09-24
~11:30 (`v2-p0`); runy oznaczone `v2-phase2` mają stary bias (MERGE → top-1 w
`--no-hil`, awarie sędziego → NEW + para AUC). `RunRegistry.load_matrix()` domyślnie
pokazuje tylko `v2-p0`, więc CSV z harnessu nie zawiera starszych kolumn — tabele
niżej złożone ręcznie z `run_metrics`.

### 8.1 Smoke (3 recenzje, `runs/leaderboard_local.db`)

| | qwen3.6 (thinking ON) | gemma4 (thinking OFF) |
|---|---|---|
| Czas | ~41 min | ~8,5 min |
| IC refinement fail | **10/10** (`finish_reason=length` — thinking zjadł `max_tokens=800`) | 0/9 |
| quote_hallucination_rate | 0.00 | 0.00 |
| ICs | 12 | 18 |

→ Potwierdzone ryzyko „thinking psuje structured output"; naprawione przez
`extra_body: {reasoning_effort: none}`.

### 8.2 top10, cztery modele/runy (`runs/leaderboard_local_top10.db`)

| Metryka | qwen3.6 | qwen3.8 | gemma #1 | Gemini 3 Flash¹ | GPT-5-nano¹ |
|---|---|---|---|---|---|
| Wersja kodu | v2-phase2 | v2-phase2 | v2-phase2 | v2-phase2 | v2-phase2 |
| Czas | 16 min | **97 min** | 19 min | — | — |
| ICs / cytaty | 30 / 66 | 41 / 53 | 37 / 93 | — | — |
| Śr. długość cytatu | — | **202 zn.** (max 1855) | 78 zn.² | — | — |
| quote_hallucination_rate ↓ | **0.217** | 0.136 | 0.000 | 0.000 | 0.077 |
| extraction_density_mean | 0.476 | 0.513 | 0.459 | 0.545 | 0.610 |
| accidental_omission_ratio ↓ | 0.554 | 0.213 | 0.395 | 0.366 | 0.790 |
| merge_rate | 0.50 | **0.17** | 0.60 | 0.45 | 0.54 |
| singleton_ratio | 0.43 | **0.78** | 0.32 | 0.59 | 0.44 |
| cross_review_convergence ↑ | 0.47 | 0.17 | 0.51 | 0.33 | 0.26 |
| embedding_separation_auc ↑ | 0.998 | 0.973 (12 M / 40 N) | 0.976 | 0.938 | 0.907 |

¹ Runy chmurowe z `runs/leaderboard_phase3_smoke.db` (2026-06, kod Phase 3).
² Z runu gemma #4 (v2-p0); rząd wielkości ten sam we wszystkich runach gemmy.

### 8.3 Powtarzalność gemma4 — 3 runy na `v2-p0`

| Metryka | run 2 | run 3 | run 4 | średnia ± sd |
|---|---|---|---|---|
| ICs | 37 | 34 | 40 | 37 ± 3 |
| quote_hallucination_rate | 0 | 0 | 0 | **0 ± 0** |
| span_integrity / judge_failure_rate / merge_target_unresolved_rate | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 | — |
| extraction_density_mean | 0.472 | 0.467 | 0.468 | **0.469 ± 0.003** |
| cross_review_convergence | 0.405 | 0.412 | 0.425 | 0.414 ± 0.010 |
| embedding_separation_auc | 0.970 | 0.963 | 0.951 | 0.962 ± 0.010 |
| merge_rate | 0.56 | 0.59 | 0.59 | 0.58 ± 0.02 |
| singleton_ratio | 0.49 | 0.50 | 0.45 | 0.48 ± 0.03 |
| density_pass1 | 0.443 | 0.423 | 0.404 | 0.423 ± 0.019 |
| accidental_omission_ratio | 0.29 | 0.34 | 0.39 | 0.34 ± 0.05 |
| recovery_rate | 0.4 | 0.5 | 0.7 | 0.53 ± 0.15 |

(run 1 = gemma #1 z 8.2, `v2-phase2`, nieporównywalny.)

### 8.4 Wnioski

1. **gemma4 = najlepszy model lokalny i kandydat na referencję.** 0 odrzuconych
   kandydatów w 4 runach (~280), krótkie jednowątkowe cytaty, sensowny merge,
   najwyższa zbieżność między recenzjami; ~17–19 min na top10.
2. **Wynik końcowy gemmy jest stabilny, podział pass1/pass2 — nie.** Gęstość po
   obu przejściach 0.469 ± 0.003, ale pass 1 waha się 0.40–0.44 i second pass to
   wyrównuje. `accidental_omission_ratio` i `recovery_rate` są przy top10 za
   zaszumione (kilka fragmentów/run) do porównań między modelami — potrzeba k≥3
   albo większego datasetu.
3. **qwen3.6 skleja cytaty.** 22% kandydatów odpada na twardej bramce — skleja
   fragmenty recenzji wielokropkiem (`'The good: ... Secondly this game is
   spooky...'`); drop skupiony w 4/10 recenzji. Kandydat do poprawki promptu
   codera (P1-4: „nie łącz fragmentów, zwróć osobne cytaty").
4. **qwen3.8 odwrotnie niż gemma: długie cytaty, brak mergowania.** Wyższa
   gęstość to w dużej mierze artefakt cytatów 2,5× dłuższych (akapity mieszające
   wątki); sędzia prawie nie merguje → 78% singletonów, tylko 3 kody z ≥3 recenzji
   (gemma: 7). Niski merge_rate nie wynika z biasu P0-1 (ten zmieniał *cel* MERGE,
   nie jego częstość). Tematycznie oba modele widzą to samo. Do tego ~6× wolniejszy
   (dense 27B + offload na CPU). Klasy dropów nieznane (run sprzed `v2-p0`).
5. **AUC nie rozróżnia tu modeli.** Wszystkie ≥0.95, a rozrzut gemmy (±0.01) jest
   porównywalny z różnicami między modelami; AUC qwen3.8 opiera się na 12 parach
   MERGE.
6. **Zawieszenie (gemma run 4):** jedno wywołanie second pass wpadło w pętlę
   powtórzeń i wygenerowało pełne `max_tokens: 16000`; retry instructora zadziałał.
   Mac w tym czasie zasnął (generacja spadła do ~2 tok/s) → run trwał 2 h 40 min
   zamiast ~26 min.

### 8.5 Następne kroki

- qwen3.6 i Gemini (chmura) po k=3 na `v2-p0` — czy różnice między modelami
  przekraczają rozrzut wewnątrz modelu.
- Opcjonalnie qwen3.8 raz na `v2-p0` (klasy dropów), jeśli ~1,5 h jest akceptowalne.
- gpt-oss (sekcja 6) wciąż nieuruchomiony.

## Ryzyka i mitygacje

- **Thinking psuje structured output.** Potwierdzone (8.1). Rozwiązane:
  `extra_body: {reasoning_effort: none}` per model (sekcja 2).
- **Pętla powtórzeń do `max_tokens`.** Lokalny model potrafi raz na kilka runów
  wygenerować 16k tokenów śmieci; nie ma timeoutu klienta. Mitygacja: rozważyć
  niższe `max_tokens` dla modeli lokalnych (np. 4000) — pętla kończy się szybciej,
  retry i tak ją naprawia.
- **Uśpienie Maca w trakcie długiego runu.** Uruchamiać przez `caffeinate -i
  .venv/bin/python scripts/run_leaderboard.py ...`.
- **Wolne generowanie.** Lokalne 23–28 GB modele są dużo wolniejsze niż chmura;
  top10 może iść kilkanaście–kilkadziesiąt minut na model. Oczekiwane.
- **Nakładanie modeli w RAM.** Wyeliminowane przez osobne wywołania + `ollama stop`.
- **Mieszanie z chmurowymi danymi.** Wyeliminowane przez dedykowane
  `runs/leaderboard_local.db`.

## Weryfikacja (end-to-end)

1. Smoke test (sekcja 4) kończy się bez błędu i tworzy ICs.
2. Po sekcji 5: macierz markdown ma dwie kolumny (qwen, gemma);
   `runs/leaderboard_local.csv` istnieje.
3. Sanity metryk: `grounding_rate` ≳ poziom chmurowy, `quote_hallucination_rate`
   niskie, `embedding_separation_auc` ≠ None (eval mode).
4. Przegląd `runs/*reasoning.jsonl` dla qwen — brak wycieku thinking do pól wyjściowych.
5. Rejestr `runs/leaderboard_local.db` zawiera wpisy `runs` + `run_metrics` dla obu modeli.
