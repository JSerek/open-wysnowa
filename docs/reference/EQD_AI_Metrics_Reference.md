# EQD-AI — Referencja metryk jakości

*Warstwa ekstrakcji dowodów (L0 + L1)*

v3.0 | wrzesień 2026 | stan kodu: pipeline v2-p0 | 20 metryk w 6 grupach

> Plik generowany przez `scripts/build_metrics_reference.js` (razem z wersją .docx) — nie edytuj go ręcznie.

Dokument opisuje wszystkie metryki, które pipeline EQD-AI liczy po każdym runie. Dla każdej metryki podaje: definicję prostym językiem, wzór, kierunek interpretacji, moment i miejsce obliczania, zastosowanie, wskazówki do czytania wyników oraz przykład liczbowy. Tam, gdzie to możliwe, podajemy też wartość z runu referencyjnego.

Run referencyjny: gemma4 26B × text-embedding-3-small, canonical_top10, v2-p0, średnia z 3 runów.

*Poprzednia wersja (v2.0, luty 2026, 17 metryk pipeline’u v1) jest dostępna w historii gita; metryki wycofane w v2 wymienia Aneks A.*

---

## Spis treści

- [Wprowadzenie](#wprowadzenie)
  - [Co mierzymy i dlaczego](#co-mierzymy-i-dlaczego)
  - [Zasady wspólne dla wszystkich metryk](#zasady-wspólne-dla-wszystkich-metryk)
  - [Kiedy metryki są liczone](#kiedy-metryki-są-liczone)
  - [Słowniczek](#słowniczek)
  - [Szybka ściąga](#szybka-ściąga)
- [1. Integralność danych](#1-integralność-danych)
- [2. Niezawodność sędziego](#2-niezawodność-sędziego)
- [3. Pokrycie tekstu](#3-pokrycie-tekstu)
- [4. Zdrowie codebooka](#4-zdrowie-codebooka)
- [5. Nasycenie](#5-nasycenie)
- [6. Koder i embeddingi](#6-koder-i-embeddingi)
- [7. Jak czytać wyniki razem](#7-jak-czytać-wyniki-razem)
  - [Zasady porównywania runów](#zasady-porównywania-runów)
- [Aneks A. Metryki wycofane w v2](#aneks-a-metryki-wycofane-w-v2)
- [Aneks B. Gdzie znaleźć wartości](#aneks-b-gdzie-znaleźć-wartości)

---

## Wprowadzenie

### Co mierzymy i dlaczego

W v2 projekt koncentruje się na warstwie dowodów: zamianie surowych recenzji na codebook złożony z dosłownych cytatów (dowodów) i kodów wstępnych (IC — krótkich podsumowań tego, o czym mówi cytat). Jakość tej warstwy przenosi się na wszystko, co później zbudujemy na jej podstawie, dlatego mierzymy ją dokładnie.

Metryki odpowiadają na sześć pytań:

- **Integralność danych** — czy dowody są prawdziwymi, dosłownymi fragmentami recenzji?
- **Niezawodność sędziego** — czy decyzje NEW / MERGE / REJECT zostały faktycznie podjęte, a nie zastąpione awaryjnym NEW?
- **Pokrycie tekstu** — ile treści zamieniliśmy w dowody i ile przeoczyliśmy?
- **Zdrowie codebooka** — czy kody konsolidują się, czy rozdrabniają?
- **Nasycenie** — czy nowe dane jeszcze przynoszą nowe kody?
- **Koder i embeddingi** — jak zachowują się poszczególne komponenty pipeline’u?

### Zasady wspólne dla wszystkich metryk

- **Żadna metryka nie jest bramką.** Wszystkie są sygnałami dla analityka i nie zatrzymują pipeline’u. Jedyną twardą bramką jest sama bramka groundingu: cytat, który nie jest dosłownym fragmentem tekstu, jest odrzucany.
- **Metryki bez wzorca (reference-free).** Nie mamy „złotego” zbioru z poprawnymi odpowiedziami. Metryki opisują wewnętrzną spójność i wierność wyników, a nie zgodność z wzorcem.
- **Surowy pomiar, bez progów.** W v2 usunęliśmy progi decyzyjne z triage’u. Zakresy podane w sekcjach „Jak czytać” są orientacyjne i pomagają w interpretacji, ale nie są kryteriami zaliczenia.
- **Kierunek:** ↑ — więcej znaczy lepiej; ↓ — mniej znaczy lepiej; opisowa — ani więcej, ani mniej nie jest samo w sobie lepsze, wartość charakteryzuje zachowanie modelu i porównuje się ją między modelami na tych samych danych; diagnostyczna — służy do znajdowania konkretnych przypadków do przeglądu.

### Kiedy metryki są liczone

| Moment | Co się dzieje | Metryki |
| --- | --- | --- |
| Po każdym batchu (w trakcie runu) | `ITSTracker` zapisuje, ile nowych kodów powstało. | ITS |
| W trakcie przetwarzania każdej recenzji | Pomiar gęstości po pass 1 i pass 2; ocena pominiętych fragmentów. | density_pass1/2, density_delta, recovery_rate, omission |
| Na koniec każdego runu | `L1MetricsEngine.compute_all()` liczy wszystkie metryki. Pojedyncze liczby zapisuje w tabeli `quality_metrics` bazy runu i w rejestrze leaderboardu (`run_metrics`). | wszystkie pozostałe |
| Tylko w eval mode (harness leaderboardu) | Sędzia pracuje na prompcie sim-blind, a system zbiera pary (cosinus, werdykt). | embedding_separation_auc |

### Słowniczek

| Pojęcie | Znaczenie |
| --- | --- |
| Recenzja / segment | Jednostka tekstu źródłowego. Po preprocessingu (L0) każda recenzja ma znormalizowany tekst kanoniczny (`canonical_text`), względem którego sprawdzane są cytaty. |
| Kandydat | Propozycja modelu kodującego: cytat + nazwa i definicja kodu. Kandydat może zostać odrzucony, dołączony do istniejącego kodu albo stać się nowym kodem. |
| IC (initial code) | Kod wstępny: krótkie podsumowanie tego, o czym mówi cytat. Codebook to zbiór IC wraz z ich cytatami. |
| Cytat / dowód | Dosłowny fragment recenzji przypięty do IC. |
| Span | Pozycja cytatu w tekście: znak początkowy i końcowy. Liczy ją kod (wyszukiwanie w tekście), nigdy model. |
| Bramka groundingu | Sprawdzenie, czy cytat jest dosłownym fragmentem tekstu. Jeśli nie — kandydat jest odrzucany; nic nie jest naprawiane. |
| Sędzia (codebook comparator) | Model LLM, który dla każdego kandydata decyduje: NEW (nowy kod), MERGE (dołącz do istniejącego kodu) lub REJECT (odrzuć). Widzi shortlistę najbardziej podobnych kodów (top-k z embeddingu). |
| Pass 1 / pass 2 | Pass 1 — główna ekstrakcja. Pass 2 — audyt pominiętego tekstu: model ocenia fragmenty, z których nic nie zacytowano, i może odzyskać z nich dowody. |
| HIL / --no-hil | HIL — człowiek zatwierdza codebook. `--no-hil` — tryb w pełni automatyczny. |
| Eval mode / sim-blind | Tryb pomiarowy leaderboardu: sędzia nie widzi wartości podobieństwa, żeby jego werdykt był niezależny od embeddingu. |
| Run / leaderboard | Run to jedno uruchomienie pipeline’u na zbiorze danych. Leaderboard zestawia metryki runów w macierzy modeli (średnia ± sd z powtórzeń k). |

### Szybka ściąga

Wszystkie metryki w jednej tabeli. Kolumna „Run ref.” to wartość z runu referencyjnego (gemma4 26B × text-embedding-3-small, canonical_top10, v2-p0, średnia z 3 runów).

| Metryka | Co mierzy | Kierunek | Run ref. |
| --- | --- | --- | --- |
| *1. Integralność danych* |  |  |  |
| **span_integrity** | Czy zapisane cytaty zgadzają się z tekstem (test kodu) | ↑ (=1.0) | 1.0 |
| **quote_hallucination_rate** | Odsetek cytatów niebędących dosłownym fragmentem tekstu | ↓ | 0.0 |
| **drop_classes** | Dlaczego cytat został odrzucony | diagn. | — |
| **unmatched_quote_rate** | Parafrazy i zmyślenia | ↓ | 0.0 |
| **candidate_drop_rate** | Kandydaci odrzuceni przez bramkę (= 1.2) | ↓ | 0.0 |
| **ambiguous_occurrence_rate** | Cytaty z frazą powtarzającą się w recenzji | ↓ | 0.0 |
| *2. Niezawodność sędziego* |  |  |  |
| **judge_failure_rate** | Wywołania sędziego zakończone błędem | ↓ | 0.0 |
| **merge_target_unresolved_rate** | MERGE do kodu spoza shortlisty | ↓ | 0.0 |
| *3. Pokrycie tekstu* |  |  |  |
| **extraction_density** | Jaka część recenzji stała się dowodami | opis. | 0.469 |
| **density_pass1 / pass2** | Gęstość przed audytem i po nim | opis. | 0.424 / 0.469 |
| **density_delta** | Ile tekstu z dowodami przeoczył pass 1 | ↓ | 0.046 |
| **recovery_rate** | Recenzje, w których pass 2 coś odzyskał | opis. | 0.533 |
| **accidental_omission_ratio** | Pominięcia będące przeoczeniem | ↓ | 0.340 |
| **quote_coverage_per_ic** | Czy jeden kod „zjada” całą recenzję | diagn. | — |
| *4. Zdrowie codebooka* |  |  |  |
| **singleton_ratio** | Kody z jednym dowodem | opis. | 0.479 |
| **merge_rate** | Kandydaci dołączeni do istniejących kodów | opis. | 0.580 |
| **cross_review_convergence** | Kody potwierdzone przez ≥ 2 recenzje | ↑ | 0.414 |
| *5. Nasycenie* |  |  |  |
| **ITS** | Tempo pojawiania się nowych kodów per batch | krzywa | — |
| *6. Koder i embeddingi* |  |  |  |
| **coder_confidence** | Samoocena pewności kodera | opis. | 0.935 |
| **coder_reuse** | Koder vs sędzia: kto wyłapał duplikat | diagn. | — |
| **embedding_separation_auc** | Zgodność embeddingu z werdyktami sędziego | ↑ | 0.962 |

---

## 1. Integralność danych

Czy dowody są prawdziwe? Te metryki sprawdzają, czy każdy cytat jest dosłownym fragmentem recenzji i jak model radzi sobie z wiernym przepisywaniem tekstu.

#### 1.1 span_integrity — integralność spanów

Kontrola poprawności samego systemu: czy każdy zapisany cytat nadal wskazuje dokładnie ten tekst, który cytuje.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek zapisanych w bazie cytatów, dla których wycinek tekstu źródłowego wskazany przez span (`canonical_text[span_start:span_end]`) jest identyczny z `quote_text`. |
| **Wzór** | span_integrity = cytaty_zweryfikowane / wszystkie_cytaty |
| **Zakres** | 0.0–1.0; oczekiwana wartość to zawsze 1.0 |
| **Kierunek** | ↑ (więcej = lepiej), ale praktycznie jest to test zero-jedynkowy |
| **Kiedy liczona** | Na koniec każdego runu, po zbudowaniu codebooka |
| **Gdzie w kodzie** | `L1MetricsEngine.compute_span_integrity()` |
| **Klucz** | leaderboard: `span_integrity`; tabela `quality_metrics`: typ `grounding` (nazwa historyczna) |

**Do czego służy**

- Test regresji dla kodu: potwierdza, że nic po drodze (zapis do bazy, normalizacja, merge) nie rozjechało cytatów z tekstem.
- To **nie** jest cecha modelu. Model nigdy nie podaje offsetów; liczy je kod, a cytaty niepasujące odpadają wcześniej na bramce groundingu.

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| 1.0 | Wszystko w porządku. Tak ma być zawsze. |
| < 1.0 | Błąd w kodzie pipeline’u. Sprawdź listę `failures` (id cytatu, id IC, powód: „segment not found” lub „span mismatch”). |

> **Przykład**
>
> Codebook zawiera 212 cytatów. Wszystkie 212 po ponownym sprawdzeniu pasują do tekstu → span_integrity = 212/212 = **1.0**.
>
> Gdyby po zmianie w normalizacji tekstu 3 cytaty przestały pasować, wynik wyniósłby 209/212 = 0.986 i należałoby szukać błędu w kodzie, a nie w modelu.

**W runie referencyjnym:** 1.0 (sd 0.0).

#### 1.2 quote_hallucination_rate — odsetek halucynowanych cytatów

Najważniejsza miara wierności dowodów: jak często model „cytuje” coś, czego w recenzji dosłownie nie ma.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek kandydatów z pierwszego przebiegu (pass 1), których cytat nie jest dosłownym fragmentem tekstu recenzji i dlatego zostaje odrzucony przez bramkę groundingu. Nic nie jest naprawiane ani dopasowywane w przybliżeniu. |
| **Wzór** | quote_hallucination_rate = odrzucone / (przyjęte + odrzucone)   [pass 1] |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu, z liczników zebranych przy bramce groundingu |
| **Gdzie w kodzie** | `compute_quote_hallucination_rate()`; bramka: `locate_quote()` w `src/preprocessing/grounding.py` |
| **Klucz** | leaderboard: `quote_hallucination_rate` |

**Do czego służy**

- Główna oś porównania modeli na leaderboardzie: który model wiernie przepisuje tekst, a który go parafrazuje.
- Metryka nie jest cykliczna (nie ocenia wyniku własnej naprawy): skoro nic nie jest naprawiane, każdy błąd modelu jest widoczny.
- Zawsze czytaj ją razem z rozbiciem na klasy odrzuceń (1.3) i z `unmatched_quote_rate` (1.4).

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| ≈ 0 | Model cytuje dosłownie. Stan docelowy. |
| kilka % | Sprawdź klasy odrzuceń: czy to drobne różnice w przepisaniu, czy parafrazy. |
| kilkadziesiąt % | Model nie nadaje się do ekstrakcji dowodów bez zmian w promptach (przed poprawką offsetów w Phase 1 obserwowaliśmy 93%). |

> **Przykład**
>
> Model zaproponował 50 kandydatów. 47 cytatów znaleziono w tekście dosłownie, 3 nie → rate = 3 / (47 + 3) = **0.06** (6%).

**W runie referencyjnym:** 0.0 (sd 0.0) — żaden kandydat nie został odrzucony.

#### 1.3 drop_classes — klasy odrzuconych cytatów

Diagnostyka do metryki 1.2. Każdy odrzucony cytat dostaje jedną klasę, która mówi, **dlaczego** nie pasował. Klasy sprawdza się po kolei; wygrywa pierwsza pasująca. Klasyfikacja służy wyłącznie diagnozie — nigdy nie zamienia odrzucenia w przyjęcie.

| Klasa | Co się stało | Przykład (tekst recenzji: „The game crashes every hour. The story is boring.”) |
| --- | --- | --- |
| normalized_ws | Cytat pasuje dopiero po ujednoliceniu białych znaków i typografii (spacje, cudzysłowy, myślniki). | Model zwrócił „The  story is boring” (podwójna spacja). |
| case | Cytat pasuje dopiero po zignorowaniu wielkości liter. | Model zwrócił „the story is boring”. |
| ellipsis_stitch | Model skleił kilka fragmentów wielokropkiem; każdy z nich z osobna jest w tekście. | „The game crashes … is boring”. |
| unmatched | Nie pasuje w żaden z powyższych sposobów: parafraza albo zmyślenie (tych dwóch nie rozróżniamy). | „The game crashes all the time”. |

**Jak czytać:** pierwsze trzy klasy to niedokładne przepisanie prawdziwego tekstu — sygnał, że prompt lub model „poprawia” tekst. `unmatched` to prawdziwa halucynacja. Klasy odrzuceń z pass 2 raportujemy osobno (`pass2_drop_classes`); nie wliczają się do metryki 1.2.

**Gdzie:** wynik `quote_hallucination_rate.drop_classes`; logika w `_classify_drop()` w `src/preprocessing/grounding.py`.

#### 1.4 unmatched_quote_rate — odsetek cytatów niepasujących

Wyodrębnia z metryki 1.2 tylko najpoważniejsze błędy: parafrazy i zmyślenia.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek wszystkich kandydatów z pass 1, których cytat trafił do klasy `unmatched`. |
| **Wzór** | unmatched_quote_rate = unmatched / (przyjęte + odrzucone) |
| **Zakres** | 0.0–1.0; zawsze ≤ quote_hallucination_rate |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_quote_hallucination_rate()` |
| **Klucz** | leaderboard: `unmatched_quote_rate` |

**Do czego służy**

- Oddziela model, który cytuje niechlujnie (błędy białych znaków lub wielkości liter), od modelu, który wymyśla treść.

**Jak czytać**

- Duża różnica między 1.2 a 1.4 → model przepisuje prawdziwy tekst, tylko niedokładnie; zwykle wystarczy poprawić prompt.
- 1.4 ≈ 1.2 → prawie wszystkie odrzucenia to parafrazy albo zmyślenia; to poważniejszy problem z wiernością.

> **Przykład**
>
> Z 50 kandydatów 3 odrzucono: 1 × `case`, 2 × `unmatched`. quote_hallucination_rate = 3/50 = 0.06, a unmatched_quote_rate = 2/50 = **0.04**.

**W runie referencyjnym:** 0.0 (sd 0.0).

#### 1.5 candidate_drop_rate — odsetek odrzuconych kandydatów

Metryka zachowana dla ciągłości z v1. W v2 liczbowo równa quote_hallucination_rate.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek kandydatów odrzuconych przez bramkę groundingu. W v2 bramka jest jedyną ścieżką odrzucenia (nie ma naprawy spanów), dlatego wartość jest identyczna z 1.2. Dodatkowo raportujemy, w których segmentach było najwięcej odrzuceń. |
| **Wzór** | candidate_drop_rate = odrzucone / (przyjęte + odrzucone) |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_extraction_density()` → pole `drop_rate` |
| **Klucz** | leaderboard: `candidate_drop_rate` |

**Do czego służy**

- Lista `top_drop_segments` wskazuje recenzje, na których model najczęściej się myli — dobry punkt startu do ręcznego przeglądu.

**Jak czytać**

- Czytaj jak 1.2. Gdyby kiedyś te dwie wartości się rozjechały, pojawiła się nowa ścieżka odrzucania kandydatów i trzeba to wyjaśnić.

> **Przykład**
>
> 3 odrzucenia na 50 kandydatów → 0.06, w tym 2 w jednej recenzji. Ta recenzja trafia na początek listy `top_drop_segments`.

**W runie referencyjnym:** 0.0 (sd 0.0).

#### 1.6 ambiguous_occurrence_rate — odsetek cytatów niejednoznacznych

Jak często pozycja cytatu w tekście musiała zostać wybrana, bo ta sama fraza występuje w recenzji kilka razy.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek przyjętych cytatów (pass 1 i pass 2), których fraza występuje w recenzji dwa lub więcej razy. Wtedy system przypisuje span do pierwszego wystąpienia, które nie jest jeszcze zajęte przez inny cytat (`first_free`), a jeśli wszystkie są zajęte — do pierwszego wystąpienia (`first_fallback`). |
| **Wzór** | ambiguous_occurrence_rate = (first_free + first_fallback) / wszystkie_przyjęte_cytaty |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_ambiguous_occurrences()`; wybór spanu w `locate_quote()` |
| **Klucz** | leaderboard: `ambiguous_occurrence_rate` |

**Do czego służy**

- Mówi, na ile można ufać pozycji cytatu (a więc density i coverage), gdy fraza się powtarza.
- Wysoka wartość zwykle oznacza, że model cytuje zbyt krótkie, generyczne frazy („great game”, „fix it”).

**Jak czytać**

- `first_fallback` > 0 → dwa cytaty wskazują ten sam fragment tekstu; to może oznaczać zdublowany dowód.

> **Przykład**
>
> Recenzja: „Great parkour, but it crashes. Great parkour though.” Model cytuje „Great parkour” → fraza występuje 2 razy, więc span trafia do pierwszego wolnego wystąpienia (`first_free`).
>
> Jeśli takich cytatów było 4 na 80 przyjętych → rate = 4/80 = **0.05**.

**W runie referencyjnym:** 0.0 (sd 0.0).

---

## 2. Niezawodność sędziego

Czy decyzje o losie kandydatów zostały faktycznie podjęte? Awaria sędziego po cichu zamienia się w NEW i zaburza metryki codebooka, dlatego mierzymy ją osobno. Metryki wprowadzone w ramach P0 (measurement integrity).

#### 2.1 judge_failure_rate — odsetek awarii sędziego

Jak często wywołanie sędziego (LLM decydującego NEW / MERGE / REJECT) zakończyło się błędem.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek wywołań sędziego, które mimo ponowień (retry) zakończyły się wyjątkiem. Kandydat trafia wtedy awaryjnie do NEW (`decision_path = "llm_failed"`), a takie wywołanie nie daje pary do AUC (5.3). |
| **Wzór** | judge_failure_rate = llm_failed / (llm + llm_failed) |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu. Liczone są tylko rzeczywiste wywołania — przy pustym codebooku kandydat dostaje NEW bez pytania sędziego. |
| **Gdzie w kodzie** | `compute_judge_reliability()` |
| **Klucz** | leaderboard: `judge_failure_rate` |

**Do czego służy**

- Flaga wiarygodności runu. Awaryjne NEW sztucznie zawyżają liczbę kodów i singletonów oraz zaniżają merge_rate.
- Porównanie niezawodności modeli (np. lokalne modele częściej zwracają niepoprawny JSON).

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| 0 | Run wiarygodny. |
| > 0 | Log ostrzega „run is unreliable”. Metryki codebooka (rozdział 4) są zaburzone; porównuj je ostrożnie albo powtórz run. |

> **Przykład**
>
> Sędzia był wołany 120 razy, 3 wywołania się nie powiodły → 3 / (117 + 3) = **0.025**. 3 kandydaci trafili do NEW „z automatu”, a AUC policzono na 117 werdyktach.

**W runie referencyjnym:** 0.0 (sd 0.0).

#### 2.2 merge_target_unresolved_rate — odsetek nierozwiązanych celów MERGE

Jak często sędzia każe połączyć kandydata z kodem, którego nie ma na liście kodów, którą mu pokazano.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek werdyktów MERGE, w których nazwa kodu docelowego (`merge_target_name`) nie pasuje do żadnej pozycji na shortliście. W trybie `--no-hil` taki kandydat trafia do NEW. |
| **Wzór** | merge_target_unresolved_rate = nierozwiązane / werdykty_MERGE |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu; istotne w trybie automatycznym (`--no-hil`) |
| **Gdzie w kodzie** | `compute_judge_reliability()` |
| **Klucz** | leaderboard: `merge_target_unresolved_rate` |

**Do czego służy**

- Wykrywa sędziego, który „wymyśla” nazwy kodów zamiast wybrać z listy.
- Pokazuje, ile MERGE zamieniło się w NEW — ma to bezpośredni wpływ na singleton_ratio i merge_rate.

**Jak czytać**

- Wartość > 0 → przejrzyj reasoning log: czy nazwa była literówką istniejącego kodu, czy zupełnie nowym tworem.

> **Przykład**
>
> Sędzia wydał 40 werdyktów MERGE. W jednym wskazał „Poor performance”, a na shortliście był „Performance issues” → 1/40 = **0.025**; ten kandydat został zapisany jako NEW.

**W runie referencyjnym:** 0.0 (sd 0.0).

---

## 3. Pokrycie tekstu

Ile treści recenzji zamieniliśmy w dowody i ile przeoczyliśmy? Gęstość mówi, ile tekstu pokrywają cytaty; metryki pass 2 mówią, czy luki to świadoma selekcja, czy przeoczenia.

#### 3.1 extraction_density — gęstość ekstrakcji

Jaka część tekstu recenzji została zamieniona w cytaty-dowody.

| Pole | Opis |
| --- | --- |
| **Definicja** | Dla każdego segmentu: liczba znaków pokrytych przez cytaty (po połączeniu nakładających się spanów, żeby nie liczyć ich podwójnie) podzielona przez długość segmentu. Raportowany jest rozkład: mean, median, p25, p75, min, max, oraz segmenty skrajne (> 0.80 i < 0.20). |
| **Wzór** | density(segment) = znaki_pokryte / znaki_segmentu |
| **Zakres** | 0.0–1.0 na segment |
| **Kierunek** | opisowa (bez „lepszego” kierunku) |
| **Kiedy liczona** | Na koniec każdego runu, na stanie bazy (po obu przebiegach) |
| **Gdzie w kodzie** | `compute_extraction_density()` |
| **Klucz** | leaderboard: `extraction_density_mean`; `quality_metrics`: typ `coverage` |

**Do czego służy**

- Charakteryzuje „styl” modelu: czy cytuje wybiórczo krótkie frazy, czy długie fragmenty.
- Wskazuje recenzje do ręcznego przeglądu: bardzo niska gęstość może oznaczać przeoczenia, bardzo wysoka — cytowanie wszystkiego jak leci.

**Jak czytać**

- To metryka opisowa: nie wiemy, jaka część recenzji „powinna” być zacytowana. Porównuj modele na tym samym zbiorze danych.
- Patrz na kształt rozkładu, nie tylko na średnią: wysoka średnia przy niskim p25 oznacza kilka słabo pokrytych recenzji.
- Czy luki to przeoczenia, rozstrzyga dopiero pass 2 (3.3–3.5).

> **Przykład**
>
> Recenzja ma 400 znaków. Cytaty mają spany [0–60], [40–100] i [300–340]. Po połączeniu: [0–100] + [300–340] = 140 znaków → density = 140/400 = **0.35**.

**W runie referencyjnym:** 0.469 (sd 0.003) — około połowy tekstu recenzji to dowody.

#### 3.2 density_pass1 / density_pass2 — gęstość po każdym przebiegu

Ta sama gęstość, ale zmierzona dwa razy: po pierwszym przebiegu ekstrakcji i po przebiegu naprawczym.

| Pole | Opis |
| --- | --- |
| **Definicja** | Pass 1 to zwykła ekstrakcja. Pass 2 to audyt pominiętego tekstu: model dostaje recenzję z zaznaczonymi fragmentami, z których nic nie zacytowano (`<omitted>`), ocenia każdy z nich i może odzyskać z niego dowody. Gęstość liczymy per recenzja po każdym przebiegu, a potem uśredniamy. Z konstrukcji pass2 ≥ pass1. |
| **Wzór** | density_passN = średnia po recenzjach z (znaki_pokryte_po_passN / znaki_recenzji) |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | opisowe |
| **Kiedy liczona** | W każdym runie; pomiar w pamięci, per recenzja, w trakcie przetwarzania |
| **Gdzie w kodzie** | `compute_density_passes()` |
| **Klucz** | leaderboard: `density_pass1`, `density_pass2` |

**Do czego służy**

- Punkt wyjścia do density_delta (3.3). Same wartości opisują, ile tekstu pokrywa model przed audytem i po nim.

**Jak czytać**

- `density_pass2` powinno być bardzo bliskie `extraction_density_mean` (oba opisują stan końcowy); duża rozbieżność oznacza błąd pomiaru.

> **Przykład**
>
> Recenzja 400 znaków: pass 1 pokrył 160 znaków (0.40), pass 2 odzyskał dodatkowe 40 znaków → 200/400 = 0.50.

**W runie referencyjnym:** pass1 = 0.424, pass2 = 0.469.

#### 3.3 density_delta — przyrost gęstości w pass 2

Ile tekstu z dowodami pierwszy przebieg przeoczył.

| Pole | Opis |
| --- | --- |
| **Definicja** | Średni po recenzjach przyrost gęstości między pass 1 a pass 2. |
| **Wzór** | density_delta = średnia(density_pass2 − density_pass1) |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↓ (mniej = lepiej) |
| **Kiedy liczona** | W każdym runie |
| **Gdzie w kodzie** | `compute_density_passes()` |
| **Klucz** | leaderboard: `density_delta` |

**Do czego służy**

- Miara uwagi modelu, odniesiona do jego własnego drugiego przebiegu (bez zewnętrznego wzorca): mała delta = pass 1 wyłapał prawie wszystko, duża = uwaga modelu „ucieka” (np. efekt lost-in-the-middle w dłuższych recenzjach).

**Jak czytać**

- Czytaj razem z recovery_rate (3.4): ta sama delta może oznaczać drobne odzyski w wielu recenzjach albo duży odzysk w jednej.

> **Przykład**
>
> Trzy recenzje z przyrostami 0.10, 0.00 i 0.05 → density_delta = 0.15/3 = **0.05**.

**W runie referencyjnym:** 0.046 (sd 0.018) — pass 2 dokłada średnio ~4.6 punktu procentowego pokrycia.

#### 3.4 recovery_rate — odsetek recenzji z odzyskanym dowodem

W ilu recenzjach drugi przebieg znalazł cokolwiek, co pierwszy przeoczył.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek recenzji, w których pass 2 odzyskał co najmniej jeden dowód, który przeszedł bramki (grounding i brak nakładania się na cytaty z pass 1). |
| **Wzór** | recovery_rate = recenzje_z_odzyskiem / wszystkie_recenzje |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | opisowa |
| **Kiedy liczona** | W każdym runie |
| **Gdzie w kodzie** | `compute_density_passes()` |
| **Klucz** | leaderboard: `recovery_rate` |

**Do czego służy**

- Pokazuje, czy przeoczenia pass 1 są rozproszone (wysoki recovery_rate), czy skupione w kilku recenzjach (niski).

**Jak czytać**

- Wysoki recovery_rate + mała delta → wiele drobnych przeoczeń. Niski recovery_rate + duża delta → kilka recenzji z dużymi lukami; warto je obejrzeć.

> **Przykład**
>
> Z 10 recenzji pass 2 coś odzyskał w 5 → recovery_rate = **0.50**.

**W runie referencyjnym:** 0.533 (sd 0.153) — duży rozrzut między runami przy 10 recenzjach.

#### 3.5 accidental_omission_ratio — odsetek przypadkowych pominięć

Gdy model czegoś nie zacytował: czy zrobił to świadomie, czy przeoczył?

| Pole | Opis |
| --- | --- |
| **Definicja** | W pass 2 model ocenia każdy pominięty fragment jako `deliberate` (słusznie pominięty: wypełniacz, meta-komentarz, treść nie na temat) albo `accidental` (prawdziwe przeoczenie — fragment zawierał treść do zakodowania). Metryka to udział przeoczeń. `deliberate_omission_ratio` jest jej dopełnieniem do 1. |
| **Wzór** | accidental_omission_ratio = accidental / (accidental + deliberate) |
| **Zakres** | 0.0–1.0; brak wartości, gdy nie było pominiętych fragmentów |
| **Kierunek** | ↓ (mniej = lepiej); deliberate_omission_ratio — opisowa |
| **Kiedy liczona** | W każdym runie |
| **Gdzie w kodzie** | `compute_omission_stats()` |
| **Klucz** | leaderboard: `accidental_omission_ratio`, `deliberate_omission_ratio` |

**Do czego służy**

- Najlepszy dostępny wskaźnik uwagi modelu: oddziela świadomą selekcję od przeoczeń.
- Dodatkowe liczniki (`recovered_candidates`, `recovered_accepted`, `recovered_hallucinated`, `overlap_drops`) pokazują, co stało się z dowodami odzyskanymi w pass 2 i ile odpadło na bramkach.

**Jak czytać**

- To samoocena modelu — ten sam model ocenia własne pominięcia. Traktuj ją jako sygnał, nie jako prawdę.
- Wysoki accidental przy niskiej density_delta → model deklaruje przeoczenia, ale niewiele z nich odzyskuje (lub odzyskane dowody odpadają na bramkach).

> **Przykład**
>
> W recenzji jest 5 pominiętych fragmentów: „Bought it on sale.” (deliberate), „10/10 would buy again” (deliberate), „GG” (deliberate), „Refunded after 2h” (deliberate), „the co-op keeps desyncing” (accidental — to realny problem).
>
> accidental_omission_ratio = 1/5 = **0.20**; deliberate_omission_ratio = 0.80.

**W runie referencyjnym:** accidental = 0.340 (sd 0.046), deliberate = 0.660.

#### 3.6 quote_coverage_per_ic — pokrycie recenzji przez jeden kod

Czy któryś kod „zjada” prawie całą recenzję jednym dowodem.

| Pole | Opis |
| --- | --- |
| **Definicja** | Dla każdej pary (IC, segment): jaką część segmentu pokrywają cytaty tego jednego IC (z połączeniem nakładających się spanów). Raportowane per IC (średnie i maksymalne pokrycie) oraz łącznie; pary z pokryciem > 0.70 są liczone osobno. |
| **Wzór** | coverage(IC, segment) = znaki_pokryte_przez_cytaty_IC / znaki_segmentu |
| **Zakres** | 0.0–1.0 na parę (w raporcie łącznym podawane w %) |
| **Kierunek** | diagnostyczna (nie trafia na leaderboard) |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_quote_coverage_per_ic()` |
| **Klucz** | wynik `quote_coverage` (tylko raport runu) |

**Do czego służy**

- Wyszukuje zbyt szerokie cytaty: dowód powinien być konkretnym fragmentem, a nie całą recenzją przypiętą do jednego kodu.

**Jak czytać**

- Pary > 0.70 obejrzyj ręcznie: czy recenzja faktycznie mówi tylko o jednej rzeczy (wtedy OK), czy cytat obejmuje kilka różnych wątków (wtedy kod jest zbyt ogólny).

> **Przykład**
>
> Recenzja ma 300 znaków. IC „Częste crashe” ma z niej cytat długości 240 znaków → coverage = 240/300 = **0.80** > 0.70 → para trafia do `high_coverage_count`.

---

## 4. Zdrowie codebooka

Czy codebook się konsoliduje, czy rozdrabnia? Te metryki opisują strukturę zbioru kodów po zakończeniu runu.

#### 4.1 singleton_ratio (ic_concentration) — odsetek kodów z jednym dowodem

Na ile dowody rozkładają się na kody: ile kodów ma tylko jeden cytat.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek aktywnych IC, które mają dokładnie jeden cytat. Raportowane też: średnia liczba cytatów na IC i rozkład (min, p25, p50, p75, max). |
| **Wzór** | singleton_ratio = IC_z_1_cytatem / wszystkie_aktywne_IC |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | opisowa |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_ic_concentration()` |
| **Klucz** | leaderboard: `singleton_ratio`; `quality_metrics`: typ `ic_concentration` |

**Do czego służy**

- Ocenia, czy codebook konsoliduje się w kody poparte wieloma dowodami, czy rozdrabnia się na pojedyncze obserwacje.

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| < 0.30 | Dowody dobrze skonsolidowane — większość kodów ma kilka cytatów. |
| 0.30–0.60 | Typowe dla małych zbiorów (np. 10 recenzji). Obserwuj trend przy większych danych. |
| > 0.60 przy dużym zbiorze | Codebook się rozdrabnia: sprawdź, czy sędzia za często wybiera NEW i czy nie ma awarii sędziego (2.1). |

- Na małym zbiorze wysoki singleton_ratio jest naturalny — wiele wątków pojawia się tylko w jednej recenzji. Metryka opisowa, bo prawdziwie unikalne obserwacje też są wartościowe.

> **Przykład**
>
> Codebook ma 10 kodów: 5 ma po jednym cytacie, pozostałe po 2–6 → singleton_ratio = 5/10 = **0.50**.

**W runie referencyjnym:** 0.479 (sd 0.026).

#### 4.2 merge_rate — odsetek scaleń

Jak często nowy kandydat okazuje się czymś, co już jest w codebooku.

| Pole | Opis |
| --- | --- |
| **Definicja** | Odsetek kandydatów, dla których sędzia zdecydował MERGE (dołączenie cytatu do istniejącego IC). Liczony łącznie i osobno dla każdego batcha. |
| **Wzór** | merge_rate = MERGE / kandydaci   (łącznie oraz per batch) |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | opisowa |
| **Kiedy liczona** | Na koniec każdego runu, z liczników per batch |
| **Gdzie w kodzie** | `compute_merge_rate()` |
| **Klucz** | leaderboard: `merge_rate`; `quality_metrics`: typ `merge_rate` |

**Do czego służy**

- Pokazuje przejście codebooka od fazy odkrywania (głównie NEW) do fazy konsolidacji (głównie MERGE).
- Porównanie modeli: jak chętnie dany sędzia łączy kody.

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| Rośnie z batcha na batch | Codebook dojrzewa — nowe recenzje potwierdzają istniejące kody. |
| Stale ≈ 0 | Każdy kandydat jest nowy: początek badania albo rozdrobniony codebook. |
| Bardzo wysoki od początku | Kody mogą być zbyt ogólne i „wchłaniać” różne wątki; sprawdź definicje najpopularniejszych IC. |

- Runy sprzed v2-p0 mają zawyżony merge_rate (w `--no-hil` MERGE zawsze trafiał do kodu top-1); nie porównuj ich z nowszymi.

> **Przykład**
>
> Batch 1: 1 MERGE / 10 kandydatów = 0.10; batch 2: 5/12 = 0.42; batch 3: 7/11 = 0.64. Łącznie 13/33 = **0.39** — rosnący trend świadczy o dojrzewaniu codebooka.

**W runie referencyjnym:** 0.580 (sd 0.018).

#### 4.3 cross_review_convergence — zbieżność między recenzjami

Ile kodów zostało potwierdzonych przez więcej niż jedną, niezależną recenzję.

| Pole | Opis |
| --- | --- |
| **Definicja** | Dla każdego IC liczymy, z ilu różnych recenzji (dokumentów) pochodzą jego cytaty. Metryka główna to odsetek IC z dowodami z co najmniej 2 recenzji (`confirmed_ratio`). Dodatkowo: `strong_convergence_ratio` (≥ 3 recenzje) i średnia liczba recenzji na IC. |
| **Wzór** | cross_review_convergence = IC_z_≥2_recenzjami / wszystkie_aktywne_IC |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | ↑ (więcej = lepiej) |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_cross_review_convergence()` |
| **Klucz** | leaderboard: `cross_review_convergence` |

**Do czego służy**

- Namiastka zgodności między koderami: niezależne źródła prowadzą do tego samego pojęcia.
- Odróżnia wątki powtarzalne od jednostkowych obserwacji.

**Jak czytać**

- Rośnie naturalnie z liczbą recenzji — porównuj tylko runy na tym samym zbiorze.
- Uwaga: metryka leży na granicy L1 i L2 (mówi o tematach, a nie tylko o dowodach). Zostaje w zestawie, ale jej zakres jest do przemyślenia.

> **Przykład**
>
> IC „Częste crashe”: cytaty z recenzji A, B, C → 3 recenzje (strong). IC „Nudna fabuła”: 2 cytaty, oba z recenzji A → 1 recenzja.
>
> Z 4 kodów 2 mają dowody z ≥ 2 recenzji → cross_review_convergence = 2/4 = **0.50**.

**W runie referencyjnym:** 0.414 (sd 0.010).

---

## 5. Nasycenie

Czy dokładanie danych jeszcze coś zmienia? Nasycenie to klasyczne kryterium z badań jakościowych.

#### 5.1 ITS — Incremental Type Saturation (nasycenie typów kodów)

Czy kolejne porcje danych jeszcze przynoszą nowe kody — czyli czy osiągnęliśmy nasycenie.

| Pole | Opis |
| --- | --- |
| **Definicja** | Dla każdego batcha: liczba nowo utworzonych IC podzielona przez liczbę IC, które istniały przed batchem. Dla pierwszego batcha (pusty codebook) ITS = 1.0, jeśli powstał jakikolwiek kod. Nasycenie (checkpoint) następuje, gdy ITS jest poniżej progu przez N kolejnych batchy. |
| **Wzór** | ITS(batch) = nowe_IC / IC_przed_batchem<br>nasycenie: ITS < 0.02 przez 3 kolejne batche |
| **Zakres** | ≥ 0.0 (może przekraczać 1.0 we wczesnych batchach) |
| **Kierunek** | opisowa — krzywa, a nie pojedyncza liczba |
| **Kiedy liczona** | Na bieżąco, po każdym batchu (batch_size = 10 recenzji) |
| **Gdzie w kodzie** | `ITSTracker` w `src/extraction/orchestrator.py`; model `BatchITS` |
| **Klucz** | wynik `its_history`; parametry w `eqd_config.yaml`: `its_saturation_threshold`, `its_consecutive_batches` (nie trafia na leaderboard) |

**Do czego służy**

- Klasyczne kryterium nasycenia z badań jakościowych: kiedy można przestać dokładać dane.
- W trybie HIL checkpoint nasycenia to naturalny moment na przegląd codebooka.

**Jak czytać**

- Przy 10 recenzjach jest tylko 1 batch — ITS nie ma wtedy wartości informacyjnej. Sensowna od kilkudziesięciu recenzji (np. canonical_top50/100).
- Brak nasycenia po dużej liczbie recenzji → dane są bardzo różnorodne albo codebook się rozdrabnia (sprawdź singleton_ratio).

> **Przykład**
>
> Batch 1: 0 → 14 kodów, ITS = 1.0. Batch 2: 14 przed, +6 nowych, ITS = 0.43. Batch 3: 20 przed, +2, ITS = 0.10.
>
> Batche 4–6: 22 kody przed każdym, 0 nowych → ITS = 0.0 trzy razy z rzędu → **checkpoint nasycenia** po batchu 6.

---

## 6. Koder i embeddingi

Jak zachowują się poszczególne komponenty: model kodujący i model embeddingowy?

#### 6.1 coder_confidence — pewność kodera

Jak pewny siebie jest model kodujący, gdy tworzy nowy kod.

| Pole | Opis |
| --- | --- |
| **Definicja** | Rozkład samooceny kodera (0–1) zapisanej przy tworzeniu IC. Liczone są tylko przyjęte kody NEW (bez MERGE i REJECT). Raportowane: średnia, odchylenie standardowe, kwartyle, min/max oraz liczba i odsetek kodów poniżej 0.6. |
| **Wzór** | mean_confidence = średnia pewności nowych IC<br>low_confidence_ratio = IC_z_pewnością_< 0.6 / nowe_IC |
| **Zakres** | 0.0–1.0 |
| **Kierunek** | opisowa |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_coder_confidence()` |
| **Klucz** | leaderboard: `mean_coder_confidence` |

**Do czego służy**

- Wskazuje kody do przeglądu w HIL: kody z niską pewnością warto sprawdzić w pierwszej kolejności.

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| średnia > 0.8 | Model jest bardzo pewny siebie (dane wyraźne lub model przesadnie pewny). |
| średnia 0.6–0.8 | Zdrowa niepewność, typowa dla eksploracji. |
| średnia < 0.6 lub > 20% kodów < 0.6 | Model często niepewny — przejrzyj oznaczone kody. |

- LLM-y mają skłonność do zawyżania pewności, dlatego metryka jest opisowa. Bardziej przydatna do wskazania pojedynczych kodów do przeglądu niż do porównywania modeli.

> **Przykład**
>
> 4 nowe kody z pewnością 0.95, 0.90, 0.85 i 0.55 → średnia = **0.81**; 1 kod poniżej 0.6 → low_confidence_ratio = 0.25 (> 20%, warto przejrzeć ten kod).

**W runie referencyjnym:** 0.935 (sd 0.018).

#### 6.2 coder_reuse — macierz: koder vs sędzia

Czy koder sam rozpoznaje istniejące kody, zanim zrobi to sędzia.

| Pole | Opis |
| --- | --- |
| **Definicja** | Tabela liczników porównująca deklarację kodera z decyzją sędziego: `flagged_match` — koder sam wskazał istniejący kod; `new_comp_new` — koder uznał kandydata za nowy, sędzia potwierdził NEW; `new_comp_merge` — koder uznał za nowy, sędzia zmienił na MERGE; `new_comp_reject` — koder uznał za nowy, sędzia odrzucił. |
| **Wzór** | cztery liczniki (bez jednej liczby zbiorczej) |
| **Zakres** | liczby całkowite ≥ 0 |
| **Kierunek** | opisowa |
| **Kiedy liczona** | Na koniec każdego runu |
| **Gdzie w kodzie** | `compute_all()` → `coder_reuse`; liczniki w orchestratorze |
| **Klucz** | wynik `coder_reuse` (tylko raport runu) |

**Do czego służy**

- Ocenia, ile pracy deduplikacyjnej wykonuje sędzia za kodera. Duże `new_comp_merge` = koder nie korzysta z kontekstu codebooka.

**Jak czytać**

- Dużo `new_comp_reject` → koder proponuje kandydatów, których sędzia nie uznaje za kody (np. zbyt ogólne lub bez treści).

> **Przykład**
>
> Na 50 kandydatów: flagged_match = 8, new_comp_new = 20, new_comp_merge = 20, new_comp_reject = 2. W 20 przypadkach sędzia „złapał” duplikat, którego koder nie zauważył.

#### 6.3 embedding_separation_auc — rozdzielczość embeddingu

Na ile podobieństwo z embeddingu zgadza się z decyzjami sędziego — bez ustalania żadnego progu.

| Pole | Opis |
| --- | --- |
| **Definicja** | Dla każdego kandydata ocenionego względem niepustego codebooka zapisujemy parę: (cosinus do najbliższego istniejącego kodu, werdykt sędziego). MERGE to klasa pozytywna (embedding powinien dawać wysokie podobieństwo), NEW — negatywna (niskie). AUC to prawdopodobieństwo, że losowa para MERGE ma wyższy cosinus niż losowa para NEW. Pomijamy REJECT, NEW przy pustym codebooku i nieudane wywołania sędziego. |
| **Wzór** | AUC = P(cos_MERGE > cos_NEW)<br>obliczane jako U Manna-Whitneya / (n_MERGE × n_NEW); remisy dostają średnią rangę |
| **Zakres** | 0.0–1.0; brak wartości, gdy jedna z klas jest pusta |
| **Kierunek** | ↑ (więcej = lepiej) |
| **Kiedy liczona** | Tylko w eval mode (harness leaderboardu). Sędzia dostaje wtedy prompt sim-blind — nie widzi wartości cosinusów, więc jego werdykt jest od nich niezależny. |
| **Gdzie w kodzie** | `compute_embedding_separation_auc()`; pary zbiera `codebook_comparator.py` |
| **Klucz** | leaderboard: `embedding_separation_auc`; w wyniku także `n_merge`, `n_new` |

**Do czego służy**

- Ocena modelu embeddingowego bez progów: czy jego ranking podobieństw odpowiada temu, co sędzia uznaje za ten sam kod.
- Podstawa przyszłego porównania kilku modeli embeddingowych na leaderboardzie.

**Jak czytać**

| Obserwacja | Co to znaczy |
| --- | --- |
| ≈ 1.0 | Embedding czysto oddziela duplikaty od nowych kodów. |
| 0.7–0.9 | Dobry, ale nieidealny ranking; na shortliście mogą pojawiać się mylące kandydatury. |
| ≈ 0.5 | Brak sygnału — embedding nie pomaga sędziemu. |

- Zawsze sprawdź `n_merge` i `n_new`: przy kilku parach w jednej z klas wynik jest niestabilny.
- AUC mierzy zgodność embeddingu z sędzią, a nie z „prawdą”. Słaby sędzia zaniży AUC nawet dobrego embeddingu.

> **Przykład**
>
> Cosinusy dla MERGE: 0.82, 0.74, 0.61. Dla NEW: 0.70, 0.55, 0.40. Porównujemy wszystkie 3 × 3 = 9 par: 0.82 wygrywa z 3, 0.74 z 3, 0.61 z 2 (przegrywa z 0.70).
>
> AUC = 8/9 = **0.89**.

**W runie referencyjnym:** 0.962 (sd 0.010).

---

## 7. Jak czytać wyniki razem

Pojedyncza metryka rzadko wystarcza. Poniższe pary i zestawy warto czytać łącznie:

| Zestaw | Na co patrzeć |
| --- | --- |
| quote_hallucination_rate + drop_classes + unmatched_quote_rate | Czy odrzucenia to niechlujne przepisanie (poprawialne promptem), czy parafrazy i zmyślenia (problem modelu). |
| density_delta + recovery_rate | Czy przeoczenia są drobne i rozproszone, czy duże i skupione w kilku recenzjach. |
| accidental_omission_ratio + density_delta | Czy model, deklarując przeoczenia, faktycznie je odzyskuje. |
| judge_failure_rate + singleton_ratio + merge_rate | Awarie sędziego zawyżają singletony i zaniżają merge_rate — najpierw sprawdź awarie, potem interpretuj codebook. |
| embedding_separation_auc + n_merge / n_new | AUC na kilku parach jest niestabilne; sprawdź liczebność obu klas. |
| extraction_density + quote_coverage_per_ic | Wysoka gęstość może wynikać z kilku zbyt szerokich cytatów. |

### Zasady porównywania runów

- Porównuj runy wyłącznie na tym samym zbiorze danych (np. `canonical_top10`) — wiele metryk zależy od liczby i długości recenzji.
- Leaderboard domyślnie pokazuje tylko runy z bieżącą wersją pipeline’u (`v2-p0`). Runy wcześniejsze są obciążone: w `--no-hil` MERGE zawsze trafiał do kodu top-1, a awarie sędziego liczyły się jako NEW i jako pary do AUC.
- Przy powtórzeniach (k > 1) patrz na odchylenie standardowe: duże sd (np. recovery_rate na 10 recenzjach) oznacza, że różnice między modelami mogą być przypadkowe.

---

## Aneks A. Metryki wycofane w v2

Poniższe metryki były w wersji v2.0 tego dokumentu (luty 2026). Kod metryk L2+ jest dostępny w tagu `v1-full-pipeline` (np. `git show v1-full-pipeline:src/<plik>`).

| Metryka v1 | Powód wycofania |
| --- | --- |
| Grounding Rate | Zmieniona nazwa na span_integrity (1.1). Stara metryka z konstrukcji zawsze wynosiła 1.0, bo mierzyła cytaty po naprawie spanów; wierność mierzy teraz quote_hallucination_rate. |
| Triage Efficiency | Usunięta w Phase 1: nie ma już progów automatycznych decyzji, każdy kandydat trafia do sędziego. |
| Comparator Agreement | Usunięta w Phase 1 z tego samego powodu; jakość embeddingu mierzy teraz AUC (6.3). |
| IC Stability | Poza zakresem v2. |
| Saturation Curve, Meaning Saturation | Metryki nasycenia na poziomie tematów (L2) — odłożone razem z pipeline’em v1. W v2 zostaje ITS (5.1). |
| Theme Coherence, Theme Distinctness, Cross-Theme IC Sharing, Sentiment Purity | Metryki tematów (L2) — odłożone. |
| Thematic Coverage, Orphaned IC Count | Metryki pokrycia strukturalnego (L2/L3) — odłożone. |

## Aneks B. Gdzie znaleźć wartości

| Miejsce | Co zawiera |
| --- | --- |
| Wynik `compute_all()` / raport runu | Pełne słowniki wszystkich metryk, w tym rozkłady, listy segmentów i liczniki diagnostyczne. |
| Tabela `quality_metrics` w bazie runu | Pojedyncze liczby per run (typy z `MetricType` w `src/core/models.py`). |
| Rejestr leaderboardu, tabela `run_metrics` | Skalarne metryki runu z kierunkiem (mapa `_METRIC_DIRECTIONS` w `src/extraction/pipeline.py`). |
| `RunRegistry.load_matrix()` / raport leaderboardu | Macierz metryka × (model generujący × model embeddingowy), średnia ± sd. |
| Reasoning log (`runs/*_reasoning.jsonl`) | Uzasadnienia decyzji kodera i sędziego — do ręcznej analizy przypadków wskazanych przez metryki. |
