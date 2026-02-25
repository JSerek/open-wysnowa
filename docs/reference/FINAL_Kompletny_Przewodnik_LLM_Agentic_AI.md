# KOMPLETNY PRZEWODNIK: Od Podstaw LLM do Zaawansowanych Systemów Agentowych

## Szczegółowa Esencja Wiedzy z Kursów Inżynierskich

**Źródła wiedzy:**
- Praktyczny LLM DataWorkshop (Kurs podstawowy - fundamenty)
- Software 3.0 Agentic AI (Kurs zaawansowany - systemy agentowe)

---

## O tym Przewodniku

Ten dokument zawiera **szczegółową esencję wiedzy** wyekstrahowaną z dwóch inżynierskich kursów o LLM i systemach agentowych. To nie jest "streszczenie" - to **kompletny przewodnik** zawierający:

✅ **Pełną wiedzę teoretyczną** - wszystkie kluczowe koncepty wyjaśnione szczegółowo
✅ **Gotowe do użycia code templates** - praktyczne przykłady dla każdej techniki
✅ **Boilerplates i patterns** - sprawdzone wzorce projektowe
✅ **Best practices i anti-patterns** - czego unikać i dlaczego
✅ **Ścieżkę uczenia** - od podstaw do zaawansowanych systemów
✅ **Real-world examples** - case studies i praktyczne implementacje

**Wielkość:**
- **~14,000 słów** szczegółowych wyjaśnień
- **~4,400 linii** kodu i przykładów
- **4 główne części** pokrywające całe spektrum wiedzy

---

## Dla Kogo Jest Ten Przewodnik?

**✅ Idealny dla:**
- Product Managers z background w research i analytics
- Data Scientists przechodzących na GenAI/LLM
- Software Engineers budujących aplikacje z AI
- AI Enthusiasts chcących zrozumieć jak to działa "pod maską"
- Każdego kto chce **robić rzeczy** z LLM, nie tylko "bawić się"

**💡 Podejście:**
- **Pragmatyczne** - skupione na tym co działa w praktyce
- **Edukacyjne** - wyjaśnia "dlaczego", nie tylko "jak"
- **Sceptyczne** - oddziela hype od rzeczywistości
- **Code-first** - każda koncepcja = working example

---

## Struktura Dokumentu

### **CZĘŚĆ I: FUNDAMENTY** (Podstawy)
Wprowadzenie do LLM, tokeny, API, Prompt Engineering, strukturyzacja outputów, Pydantic, Instructor.

**Nauczysz się:**
- Jak działają LLM i dlaczego przewidują "następny token"
- Jak skutecznie promptować (CoT, Few-Shot, Templates)
- Dlaczego walidacja outputów jest kluczowa
- Jak używać Pydantic jako "quality gateway"
- Instructor - połączenie Pydantic + OpenAI

### **CZĘŚĆ II: RAG I CONTEXT ENGINEERING** (Średniozaawansowane)
Retrieval-Augmented Generation, dlaczego naive chunking to anti-pattern, proper architecture, context engineering.

**Nauczysz się:**
- Czym RAG NAPRAWDĘ jest (hint: nie tylko chunking + vector DB)
- Dlaczego naive chunking niszczy semantykę
- Jak prawidłowo zaprojektować RAG system
- Context Engineering - jak dostarczać wiedzę do LLM
- Complete financial assistant implementation

### **CZĘŚĆ III: SOFTWARE 3.0 I AI AGENTS** (Zaawansowane)
Paradygmat Software 3.0, spektrum autonomii L1-L7, AI Agents, ReAct Pattern.

**Nauczysz się:**
- Ewolucja: Software 1.0 → 2.0 → 3.0
- 7 poziomów autonomii i RED LINE at L4
- Typy agentów: Reflex, Model-Based, Goal-Based, Utility, Learning
- ReAct Pattern - fundamentalny wzorzec dla agentów
- Kiedy LLM vs klasyczny ML

### **CZĘŚĆ IV: MEMORY ENGINEERING** (Bardzo Zaawansowane)
7-warstwowa architektura pamięci, biomimetyka, memory trilemma, stateful systems.

**Nauczysz się:**
- Biomimetyka - uczenie od neurobiologii
- 7 warstw pamięci: Constitutional → Working → Workflow → Episodic → Semantic → Procedural → Resource
- Memory Trilemma: Cost vs Latency vs Recall
- Stateless vs Stateful - kiedy którego używać
- Context Engineering z Jinja2

---

## Kluczowe Zasady Tego Przewodnika

### 1. **Jakość pod Kontrolą = Strukturyzacja + Walidacja**
Produkcyjne systemy AI wymagają structured outputs i validation. To odróżnia "zabawki" od real solutions.

### 2. **RAG ≠ Chunking + Vector DB**
Naive chunking niszczy semantykę. Proper RAG = przemyślana architektura z zachowaniem struktury danych.

### 3. **Red Line at Level 4**
Przejście do stateful systems (L4+) wymaga szczególnej uwagi. Nie wszystko potrzebuje pamięci długoterminowej.

### 4. **Memory Architecture Matters**
Jakość decyzji agenta jest wprost proporcjonalna do jakości jego architektury pamięci.

### 5. **Start Simple, Scale Thoughtfully**
Zacznij od L1/L2 (stateless). Dodawaj complexity tylko gdy konieczne.

---

## Jak Korzystać z Tego Przewodnika?

### **📖 Czytanie Liniowe (Recommended dla początkujących)**
Przejdź przez dokument część po części:
1. Część I (tydzień 1-2) - Fundamenty
2. Część II (tydzień 3-4) - RAG i Context Engineering
3. Część III (tydzień 5-7) - Software 3.0 i Agents
4. Część IV (tydzień 8-10) - Memory Engineering

### **🔍 Reference Lookup (Dla doświadczonych)**
Użyj jako reference gdy pracujesz nad konkretnym problemem:
- Potrzebujesz structured output? → Część I, Section 3
- Budujesz RAG system? → Część II, Section 4-5
- Implementujesz agenta? → Część III, Section 7
- Projektujesz memory? → Część IV, Section 8

### **💻 Code Templates (Dla praktyków)**
Wszystkie przykłady kodu to:
- ✅ Working implementations
- ✅ Production-ready patterns
- ✅ Commented dla clarity
- ✅ Reusable boilerplates

Możesz je bezpośrednio używać i adaptować do swoich projektów.

---

## Przed Rozpoczęciem

**Wymagania:**
- Python 3.8+
- OpenAI API key (lub dostęp do compatible API)
- Podstawowa znajomość Pythona

**Instalacja potrzebnych bibliotek:**
```bash
pip install openai pydantic instructor jinja2 python-dotenv
```

**Optional (dla pełnych przykładów):**
```bash
pip install numpy scikit-learn rank-bm25 tenacity
```

---

## Konwencje w Dokumencie

**💡 Ikona żarówki** - kluczowa idea/zasada
**✅ Checkmark** - best practice
**❌ X mark** - anti-pattern, czego unikać
**⚠️ Warning** - ważne ostrzeżenie

**Code blocks:**
```python
# Working example code
# Możesz go bezpośrednio użyć
```

**Comparisons:**
```python
# ❌ ZŁE - pokazuje anti-pattern
bad_example()

# ✅ DOBRE - pokazuje proper approach
good_example()
```

---

## Licencja i Użycie

Ten dokument powstał jako prywatna synteza wiedzy z kursów edukacyjnych.
- ✅ Możesz używać do nauki
- ✅ Możesz adaptować code examples do swoich projektów
- ✅ Możesz dzielić się wiedzą z zespołem

---

**Autor Syntezy:** Jakub (serekkuba@gmail.com)
**Data:** 2026-02-14
**Źródła:** Kursy DataWorkshop i Software 3.0 Agentic AI

---

# Zaczynajmy! 🚀

Poniżej znajdziesz kompletną wiedzę - od pierwszych kroków z LLM po zaawansowane systemy z memory engineering. Każda sekcja buduje na poprzedniej, tworząc spójną ścieżkę uczenia.

**Powodzenia w Twojej podróży z LLM i Agentic AI!**

---

# CZĘŚĆ I: FUNDAMENTY

## 1. Wprowadzenie do Large Language Models

### 💡 Kluczowa Idea
LLM to pre-trained modele przewidujące następny token w sekwencji.

### 1.1 Czym są LLM

Large Language Models to modele językowe wytrenowane na ogromnych zbiorach danych tekstowych. Ich główną cechą jest zdolność do przewidywania następnego tokenu w sekwencji, co pozwala im:
- Generować spójny tekst
- Odpowiadać na pytania
- Wykonywać różnorodne zadania językowe
- Tłumaczyć, podsumowywać, analizować

**Ewolucja:**
- Software 1.0: Ręcznie pisany kod (if/else, reguły)
- Software 2.0: Uczenie maszynowe (trenowanie na danych specyficznych)
- **Software 3.0: Pre-trained models (LLM) + fine-tuning/prompting**

### 1.2 Tokeny i Embeddingi

**Token** to podstawowa jednostka przetwarzania tekstu przez LLM.

**Kluczowe fakty:**
- 1 token ≈ 0.75 słowa (średnio dla języka angielskiego)
- Token NIE zawsze = słowo
- Może być: część słowa, całe słowo, znak przestankowy
- Tokenizacja używa algorytmów jak BPE (Byte Pair Encoding)

**Przykłady tokenizacji:**
```
"Hello world!" → ["Hello", " world", "!"]  # 3 tokeny
"ChatGPT" → ["Chat", "GPT"]  # 2 tokeny
"wonderful" → ["wonder", "ful"]  # 2 tokeny
```

**Embeddingi:**
- Numeryczne reprezentacje tokenów w przestrzeni wektorowej
- Każdy token = wektor liczb (np. 1536 wymiarów dla text-embedding-3-small)
- Podobieństwo semantyczne = bliskość w przestrzeni embeddingów
- Umożliwiają operacje matematyczne na znaczeniach

### 1.3 API OpenAI - Podstawy

**Podstawowe wywołanie:**

```python
from openai import OpenAI

client = OpenAI()  # Wymaga OPENAI_API_KEY w zmiennych środowiskowych

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Jesteś pomocnym asystentem."},
        {"role": "user", "content": "Co to jest LLM?"}
    ],
    temperature=0.7,
    max_tokens=500
)

# Dostęp do odpowiedzi
answer = response.choices[0].message.content
print(answer)
```

**Role w messages:**
- `system`: Instrukcje długoterminowe, definicja roli
- `user`: Zapytanie użytkownika
- `assistant`: Odpowiedź modelu (w historii konwersacji)

### 1.4 Parametry Modelu

**temperature** (0.0 - 2.0)
- `0.0`: Deterministyczny, zawsze ten sam output dla tego samego inputu
- `0.3-0.7`: Balans między kreatywnością a spójnością (recommended dla większości)
- `1.0`: Domyślna wartość
- `1.5-2.0`: Bardzo kreatywny, może być chaotyczny

**max_tokens**
- Maksymalna długość odpowiedzi w tokenach
- Input + output nie może przekroczyć limitu kontekstu modelu
- gpt-4o-mini: 128k kontekstu
- gpt-4o: 128k kontekstu

**top_p** (0.0 - 1.0) - nucleus sampling
- Alternatywa dla temperature
- `0.1`: Wybiera tylko top 10% najbardziej prawdopodobnych tokenów
- `1.0`: Rozważa wszystkie tokeny
- **Nie używaj jednocześnie z temperature** - wybierz jedno

**presence_penalty** / **frequency_penalty** (-2.0 - 2.0)
- Zmniejszają powtarzanie
- Wartości dodatnie: penalizują powtórzenia
- Wartości ujemne: zachęcają do powtórzeń
- `presence_penalty`: Karze za pojawienie się tokenu (niezależnie ile razy)
- `frequency_penalty`: Karze proporcjonalnie do częstości występowania

### 1.5 System Prompts vs User Prompts

**💡 System prompt = instrukcje długoterminowe, User prompt = konkretne zadanie**

**System Prompt:**
- Definiuje rolę i zachowanie modelu
- Zawiera długoterminowe instrukcje
- Pozostaje stały przez całą konwersację
- Przykład: "Jesteś ekspertem od analizy finansowej. Zawsze podajesz źródła i liczysz wszystko dokładnie."

**User Prompt:**
- Konkretne pytanie lub zadanie
- Zmienia się z każdym zapytaniem
- Zawiera specyficzny kontekst dla danego zadania
- Przykład: "Ile wyniosła przychody firmy XYZ w Q3 2024?"

**Dobre praktyki:**
```python
# ✅ DOBRZE - Separacja roli i zadania
messages = [
    {
        "role": "system",
        "content": "Jesteś asystentem programisty. Zawsze pokazujesz kod z komentarzami i wyjaśniasz krok po kroku."
    },
    {
        "role": "user",
        "content": "Napisz funkcję sortującą listę liczb metodą quick sort"
    }
]

# ❌ ŹLE - Wszystko w user prompt
messages = [
    {
        "role": "user",
        "content": "Jesteś asystentem programisty. Napisz funkcję sortującą..."
    }
]
```

---

## 2. Prompt Engineering

### 💡 Kluczowa Idea
Jakość outputu zależy od jakości promptu - struktura i jasność mają znaczenie.

### 2.1 Podstawowe Techniki Promptowania

**1. Bądź Konkretny i Jasny**

```python
# ❌ ŹLE - zbyt ogólne
"Napisz o kotach"

# ✅ DOBRZE - konkretne
"Napisz 3-akapitowy artykuł o zachowaniach socjalnych kotów domowych, skupiając się na komunikacji i hierarchii. Użyj przykładów z badań naukowych."
```

**2. Określ Format Outputu**

```python
# ❌ ŹLE
"Jakie są zalety i wady Python?"

# ✅ DOBRZE
"Wypisz 5 zalet i 5 wad języka Python jako wypunktowaną listę. Każdy punkt powinien mieć 1-2 zdania wyjaśnienia."
```

**3. Użyj Delimiters (Separatorów)**

```python
system_prompt = """
Analizujesz sentiment tekstu.

Tekst do analizy znajduje się między tagami <text> i </text>.
Zwróć tylko: POSITIVE, NEGATIVE lub NEUTRAL.
"""

user_prompt = """
<text>
Ten produkt jest okropny! Nie polecam nikomu.
</text>
"""
```

**4. Podaj Przykłady (Few-Shot Learning)**

```python
prompt = """
Klasyfikuj email jako SPAM lub HAM.

Przykłady:
Email: "Congratulations! You won $1000000!"
Klasa: SPAM

Email: "Meeting scheduled for tomorrow at 3pm"
Klasa: HAM

Email: "Click here for free iPhone!"
Klasa: SPAM

Teraz sklasyfikuj:
Email: "Your invoice for January is ready"
Klasa:
"""
```

### 2.2 Chain-of-Thought (CoT)

**💡 Zasada: Pozwól modelowi "myśleć na głos" krok po kroku**

**Bez CoT:**
```python
prompt = "Ile to 15% z 240?"
# Output: "36"
```

**Z CoT:**
```python
prompt = """
Ile to 15% z 240?
Rozwiąż krok po kroku, pokazując swoje rozumowanie.
"""

# Output:
# "Krok 1: 15% to 15/100 = 0.15
#  Krok 2: 0.15 × 240 = 36
#  Odpowiedź: 36"
```

**CoT dla złożonych problemów:**

```python
prompt = """
Firma ma 150 pracowników. W tym roku zatrudniła 20% więcej osób, ale 15 osób odeszło.
Ile teraz ma pracowników?

Pomyśl krok po kroku:
1. Ile osób firma zatrudniła?
2. Jaki był całkowity wzrost po zatrudnieniu?
3. Ile zostało po odejściach?
"""
```

**Przykład z kod

u:**
```python
from openai import OpenAI

client = OpenAI()

def solve_with_cot(problem: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Jesteś pomocnym asystentem. Zawsze rozwiązuj problemy krok po kroku, pokazując swoje rozumowanie."
            },
            {
                "role": "user",
                "content": problem
            }
        ],
        temperature=0
    )
    return response.choices[0].message.content
```

### 2.3 Few-Shot Learning

**Zero-Shot (bez przykładów):**
```python
"Przetłumacz na język techniczny: 'komputer nie działa'"
```

**One-Shot (1 przykład):**
```python
"""
Przykład:
Input: "komputer nie działa"
Output: "Brak responsywności systemu operacyjnego"

Teraz Ty:
Input: "internet jest wolny"
Output:
"""
```

**Few-Shot (kilka przykładów):**
```python
"""
Przekształć potoczne opisy na medyczną terminologię:

Input: "boli mnie głowa"
Output: "ból głowy (cephalgia)"

Input: "mam gorączkę"
Output: "stan podgorączkowy (febris)"

Input: "kręci mi się w głowie"
Output: "zawroty głowy (vertigo)"

Teraz Ty:
Input: "boli mnie gardło"
Output:
"""
```

**Code Template - Few-Shot System:**

```python
from typing import List, Dict

def create_few_shot_prompt(
    examples: List[Dict[str, str]],
    task_description: str,
    new_input: str
) -> str:
    """
    Tworzy few-shot prompt z przykładami.

    Args:
        examples: Lista słowników z 'input' i 'output'
        task_description: Opis zadania
        new_input: Nowy input do przetworzenia
    """
    prompt = f"{task_description}\n\n"

    for ex in examples:
        prompt += f"Input: {ex['input']}\n"
        prompt += f"Output: {ex['output']}\n\n"

    prompt += f"Teraz Ty:\nInput: {new_input}\nOutput:"

    return prompt

# Użycie
examples = [
    {"input": "boli mnie głowa", "output": "ból głowy (cephalgia)"},
    {"input": "mam gorączkę", "output": "stan podgorączkowy (febris)"}
]

prompt = create_few_shot_prompt(
    examples=examples,
    task_description="Przekształć potoczne opisy na terminologię medyczną:",
    new_input="boli mnie gardło"
)
```

### 2.4 Prompt Templates

**Używanie Jinja2 do dynamicznych promptów:**

```python
from jinja2 import Template

# Template definition
template_str = """
You are a {{ role }}.

Your task: {{ task }}

{% if context %}
Context:
{{ context }}
{% endif %}

{% if examples %}
Examples:
{% for ex in examples %}
Input: {{ ex.input }}
Output: {{ ex.output }}
{% endfor %}
{% endif %}

Now process:
{{ user_input }}
"""

template = Template(template_str)

# Usage
prompt = template.render(
    role="financial analyst",
    task="Extract key financial metrics",
    context="Q3 2024 earnings report",
    examples=[
        {"input": "Revenue: $500M", "output": "{'revenue': 500000000}"},
    ],
    user_input="Profit margin increased to 23%"
)
```

**Reusable Prompt Class:**

```python
from typing import Optional, List, Dict
from openai import OpenAI

class PromptTemplate:
    def __init__(self, system_template: str, user_template: str):
        self.system_template = Template(system_template)
        self.user_template = Template(user_template)
        self.client = OpenAI()

    def execute(self, model: str = "gpt-4o-mini", **kwargs) -> str:
        """Execute prompt with variables."""
        messages = [
            {
                "role": "system",
                "content": self.system_template.render(**kwargs)
            },
            {
                "role": "user",
                "content": self.user_template.render(**kwargs)
            }
        ]

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get('temperature', 0.7)
        )

        return response.choices[0].message.content

# Użycie
extraction_template = PromptTemplate(
    system_template="You are a {{ role }}. Extract {{ data_type }} from text.",
    user_template="Text: {{ text }}"
)

result = extraction_template.execute(
    role="data analyst",
    data_type="email addresses",
    text="Contact john@example.com or mary@company.org"
)
```

---

## 3. Ustrukturyzowane Outputy

### 💡 Fundamentalna Zasada
**Jakość pod kontrolą = Strukturyzacja + Walidacja**

To odróżnia "zabawki eksperymentalne" od produkcyjnych rozwiązań.

### 3.1 Problem z Plaintext Responses

**Typowe problemy z niesturukturyzowanym tekstem:**

1. **Trudność w parsowaniu**
   - Gdzie kończy się jedna informacja, a zaczyna druga?
   - Czy odpowiedź zawiera wszystkie wymagane dane?

2. **Brak gwarancji kompletności**
   - Model może pominąć pole
   - Brak mechanizmu wymuszającego kompletność

3. **Niespójny format**
   - Raz lista, raz akapity, raz punkty
   - Uniemożliwia automatyczne przetwarzanie

4. **Niemożność walidacji typu**
   - Czy cena jest liczbą czy tekstem?
   - Czy data ma właściwy format?

**Przykład problemu:**

```python
# ❌ Niesturukturyzowana odpowiedź
response = """
Produkt: iPhone 15
Cena to około 4000-5000 złotych
Dostępność: tak, w większości sklepów
Ocena klientów: bardzo dobra (4.5/5)
"""

# Jak to sparsować? Jak wyciągnąć cenę jako liczbę?
# Jak zagwarantować, że zawsze dostaniemy wszystkie pola?
```

### 3.2 JSON Schema

**JSON Schema definiuje strukturę oczekiwanych danych:**

```json
{
  "type": "object",
  "properties": {
    "product_name": {"type": "string"},
    "price": {"type": "number"},
    "in_stock": {"type": "boolean"},
    "rating": {"type": "number", "minimum": 0, "maximum": 5}
  },
  "required": ["product_name", "price", "in_stock"]
}
```

**Użycie w prompt:**

```python
schema = {
    "type": "object",
    "properties": {
        "dish": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["dish", "ingredients", "steps"]
}

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Generujesz przepisy w JSON zgodnym ze schematem."},
        {"role": "user", "content": f"Przepis na naleśniki. Schema: {schema}"}
    ]
)
```

**Problemy z czystym JSON Schema:**
- Trzeba ręcznie pisać duży JSON
- Brak automatycznej walidacji w Pythonie
- Trudne utrzymanie i modyfikacja
- Nie gwarantuje 100% zgodności (model może zwrócić niepoprawny JSON)

### 3.3 Function Calling

**Function Calling wymusza JSON output:**

```python
schema = {
    "type": "object",
    "properties": {
        "dish": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["dish", "ingredients", "steps"]
}

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Przygotuj naleśniki"}
    ],
    functions=[{"name": "create_recipe", "parameters": schema}],
    function_call="auto"  # lub {"name": "create_recipe"} aby wymusić
)

# Dostęp do wyniku
result = response.choices[0].message.function_call.arguments
print(result)  # JSON string
```

**Ścieżka do danych:**
- Response: `response.choices[0].message`
- W przypadku function call: `.function_call.arguments` (zamiast `.content`)
- Arguments to string JSON, trzeba sparsować: `json.loads(arguments)`

**Czy Function Calling gwarantuje poprawność?**
- ✅ Zawsze zwraca JSON (parsow alny)
- ⚠️ JSON może nie być zgodny ze schematem (rzadkie przypadki)
- ❌ Wartości mogą być niepoprawne (np. cena ujemna)

### 3.4 Pydantic Models

**💡 Pydantic = quality gateway dla LLM outputs**

**Podstawowa definicja:**

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Product(BaseModel):
    product_id: int = Field(description="Unique product identifier")
    name: str = Field(description="Product name")
    price: float = Field(gt=0, description="Price must be positive")
    in_stock: bool = Field(description="Availability status")
    tags: List[str] = Field(description="Product categories")
    description: Optional[str] = Field(None, description="Optional description")
```

**Kluczowe cechy Pydantic:**

1. **Automatyczna walidacja typów**
   ```python
   product = Product(product_id=1, name="iPhone", price=999.99, in_stock=True, tags=["electronics"])
   # ✅ OK

   product = Product(product_id=1, name="iPhone", price=-10, in_stock=True, tags=[])
   # ❌ ValidationError: price must be > 0
   ```

2. **Konwersja typów gdzie możliwe**
   ```python
   product = Product(product_id="123", name="iPhone", price="999.99", in_stock="yes", tags=["phones"])
   # ✅ OK - automatycznie konwertuje:
   # "123" → 123
   # "999.99" → 999.99
   # "yes" → True (jeśli Field ma coercion)
   ```

3. **Field validators**
   ```python
   class Email(BaseModel):
       address: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
       verified: bool = Field(default=False)

   class User(BaseModel):
       username: str = Field(min_length=3, max_length=20)
       age: int = Field(ge=18, le=120)  # ge = greater or equal, le = less or equal
       email: Email
   ```

4. **Nested structures**
   ```python
   class Address(BaseModel):
       street: str
       city: str
       country: str
       postal_code: str

   class User(BaseModel):
       name: str
       email: str
       addresses: List[Address]  # Lista zagnieżdżonych obiektów
   ```

5. **Automatic JSON schema generation**
   ```python
   print(Product.model_json_schema())
   # Zwraca pełny JSON schema zgodny ze standardem
   ```

**Przykład walidacji:**

```python
from pydantic import BaseModel, Field, ValidationError

class Recipe(BaseModel):
    dish: str = Field(min_length=1)
    ingredients: List[str] = Field(min_length=1)
    steps: List[str] = Field(min_length=1)
    servings: int = Field(gt=0)

# ✅ Poprawne dane
try:
    recipe = Recipe(
        dish="Pancakes",
        ingredients=["flour", "milk", "eggs"],
        steps=["Mix ingredients", "Cook on pan"],
        servings=4
    )
    print("Valid!")
except ValidationError as e:
    print(f"Error: {e}")

# ❌ Niepoprawne dane
try:
    recipe = Recipe(
        dish="",  # Za krótkie
        ingredients=[],  # Pusta lista
        steps=["Mix"],
        servings=0  # Musi być > 0
    )
except ValidationError as e:
    print(f"Validation errors: {e}")
    # Wypisuje wszystkie błędy walidacji
```

### 3.5 Instructor Library

**💡 Instructor = Pydantic + OpenAI w jednym**

**Instalacja:**
```bash
pip install instructor
```

**Podstawowe użycie:**

```python
from openai import OpenAI
import instructor
from pydantic import BaseModel, Field
from typing import List

# Patch OpenAI client
client = OpenAI()
client = instructor.patch(client, mode=instructor.Mode.MD_JSON)

# Define Pydantic model
class Recipe(BaseModel):
    dish: str = Field(description="Name of the dish")
    ingredients: List[str] = Field(description="List of ingredients")
    steps: List[str] = Field(description="Preparation steps")

# Make API call with response_model
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You generate recipes."},
        {"role": "user", "content": "Create a pancake recipe"}
    ],
    response_model=Recipe  # Instructor magic happens here
)

# Response is already a validated Pydantic object!
print(response.dish)  # Direct attribute access
print(response.ingredients)
print(response.steps)
```

**Kluczowe różnice z Function Calling:**

| Aspekt | Function Calling | Instructor |
|--------|------------------|------------|
| Definicja schematu | Ręczny JSON dict | Pydantic model |
| Walidacja | Manualna | Automatyczna |
| Typ wyniku | JSON string | Pydantic object |
| Ścieżka danych | `.function_call.arguments` | Bezpośredni dostęp do atrybutów |
| Retry przy błędach | Ręczna implementacja | Wbudowana |

**Tryby Instructor:**

```python
# MD_JSON - najlepszy dla większości przypadków
client = instructor.patch(client, mode=instructor.Mode.MD_JSON)

# JSON - czysty JSON bez markdown
client = instructor.patch(client, mode=instructor.Mode.JSON)

# FUNCTIONS - używa function calling pod spodem
client = instructor.patch(client, mode=instructor.Mode.FUNCTIONS)
```

**Zaawansowany przykład:**

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum

class PizzaSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

class Topping(BaseModel):
    name: str
    extra: bool = False

class PizzaOrder(BaseModel):
    size: PizzaSize
    toppings: List[Topping]
    quantity: int = Field(ge=1, le=10)
    special_instructions: Optional[str] = None

    @validator('toppings')
    def check_toppings_limit(cls, v):
        if len(v) > 8:
            raise ValueError('Maximum 8 toppings allowed')
        return v

# Usage with Instructor
order = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "I want a large pizza with pepperoni, mushrooms, and extra cheese"}
    ],
    response_model=PizzaOrder
)

print(f"Size: {order.size}")
print(f"Toppings: {[t.name for t in order.toppings]}")
print(f"Quantity: {order.quantity}")
```

**Obsługa błędów:**

```python
from pydantic import ValidationError

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Extract data"}],
        response_model=MyModel,
        max_retries=3  # Instructor automatycznie retry przy ValidationError
    )
except ValidationError as e:
    print(f"Nie udało się po 3 próbach: {e}")
except Exception as e:
    print(f"Inny błąd: {e}")
```

### 3.6 Response Format vs Function Calling

**Kiedy użyć którego?**

**Function Calling:**
- Gdy chcesz, aby model wywoływał konkretne akcje
- Gdy potrzebujesz sekwencji działań
- Gdy integrujesz z istniejącymi funkcjami

**Response Format (z Pydantic + Instructor):**
- Gdy potrzebujesz tylko danych w określonym formacie
- Prostsze, bardziej bezpośrednie
- Lepsza walidacja
- Mniej tokenów (bardziej ekonomiczne)

**Porównanie:**

```python
# ===== FUNCTION CALLING =====
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    }
}

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "John is 25"}],
    functions=[{"name": "extract_person", "parameters": schema}],
    function_call="auto"
)

# Trzeba sparsować i zwalidować
import json
data = json.loads(response.choices[0].message.function_call.arguments)
person = Person(**data)  # Manual validation


# ===== INSTRUCTOR (Lepsze) =====
class Person(BaseModel):
    name: str
    age: int = Field(ge=0, le=150)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "John is 25"}],
    response_model=Person
)

# Już zwalidowany Pydantic object!
print(response.name)
print(response.age)
```

### 3.7 Praktyczne Wzorce

**Pattern 1: Extraction Pipeline**

```python
class ExtractedData(BaseModel):
    entities: List[str] = Field(description="Named entities found")
    sentiment: str = Field(description="POSITIVE, NEGATIVE, or NEUTRAL")
    key_points: List[str] = Field(description="Main points from text")
    language: str = Field(description="Detected language code")

def extract_from_text(text: str) -> ExtractedData:
    """Extract structured data from unstructured text."""
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Extract structured information from text."},
            {"role": "user", "content": text}
        ],
        response_model=ExtractedData
    )

# Usage
data = extract_from_text("Apple announced new iPhone. Customers are excited!")
print(data.entities)  # ["Apple", "iPhone"]
print(data.sentiment)  # "POSITIVE"
```

**Pattern 2: Data Validation & Cleaning**

```python
class CleanedAddress(BaseModel):
    street: str = Field(description="Street name and number")
    city: str
    postal_code: str = Field(pattern=r"^\d{2}-\d{3}$")  # Format: 00-000
    country: str = Field(default="Poland")

    @validator('city')
    def capitalize_city(cls, v):
        return v.title()

def clean_address(raw_address: str) -> CleanedAddress:
    """Clean and structure raw address string."""
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Clean and structure Polish addresses."},
            {"role": "user", "content": f"Address: {raw_address}"}
        ],
        response_model=CleanedAddress
    )

# Usage
address = clean_address("ul. marszałkowska 123, warszawa, 00-123")
print(address.city)  # "Warszawa" (auto-capitalized)
```

**Pattern 3: Multi-Step Reasoning**

```python
class ReasoningStep(BaseModel):
    step_number: int
    thought: str = Field(description="What are you thinking?")
    action: str = Field(description="What action to take?")
    confidence: float = Field(ge=0, le=1)

class Solution(BaseModel):
    problem_understanding: str
    reasoning_steps: List[ReasoningStep]
    final_answer: str
    confidence_score: float = Field(ge=0, le=1)

def solve_with_reasoning(problem: str) -> Solution:
    """Solve problem with explicit reasoning chain."""
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Solve problems step-by-step with explicit reasoning."
            },
            {
                "role": "user",
                "content": problem
            }
        ],
        response_model=Solution
    )
```

**Pattern 4: Retry with Improvement**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def extract_with_retry(text: str, model_class: type[BaseModel]):
    """Extract with automatic retry on validation errors."""
    try:
        return client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Extract data according to schema: {model_class.model_json_schema()}"},
                {"role": "user", "content": text}
            ],
            response_model=model_class
        )
    except ValidationError as e:
        # Instructor automatically retries and improves prompt
        raise

# Usage
data = extract_with_retry("Some text...", MyDataModel)
```

---

## Podsumowanie Części I

W tej części nauczyłeś się:

✅ **Podstaw LLM**: Tokenów, embeddingów, API
✅ **Parametrów modelu**: temperature, max_tokens, top_p
✅ **Prompt Engineering**: CoT, Few-Shot, Templates
✅ **Strukturyzacji outputów**: JSON Schema, Function Calling
✅ **Pydantic**: Definicji modeli, walidacji, nested structures
✅ **Instructor**: Integracji Pydantic z OpenAI

**Kluczowe zasady:**
1. Zawsze waliduj outputy z LLM
2. Używaj Pydantic jako quality gateway
3. Strukturyzacja > plaintext dla produkcji
4. Instructor ułatwia życie

**Następne kroki:**
W Części II przejdziemy do RAG (Retrieval-Augmented Generation), gdzie nauczysz się jak łączyć LLM z zewnętrznymi źródłami wiedzy - i dlaczego naive chunking to anti-pattern!
# CZĘŚĆ II: RAG I CONTEXT ENGINEERING

## 4. Retrieval-Augmented Generation (RAG)

### 💡 Kluczowa Idea
**RAG ≠ Chunking + Vector Database**
**RAG = Retriever (pobieranie wiedzy) + Generator (LLM)**

### 4.1 Czym jest RAG (i czym NIE jest)

**Definicja:**
RAG to architektura łącząca:
1. **Retriever**: System pobierający relevantną wiedzę z zewnętrznego źródła
2. **Generator**: LLM generujący odpowiedź na podstawie pobranej wiedzy

**Główny cel:**
- Oddzielenie wiedzy od modelu
- Umożliwienie aktualizacji wiedzy bez retrainingu modelu
- Zmniejszenie halucynacji poprzez grounding w faktach

**❌ Częsty błąd - co RAG NIE JEST:**

```
Naive RAG = "Podziel dokument na chunki → Embeddingi → Vector DB → Wyszukaj → LLM"
```

To jest **anti-pattern**, który:
- Niszczy semantyczną strukturę danych
- Traci kontekst (szczególnie w tabelach)
- Daje gorsze wyniki niż przemyślana architektura

### 4.2 Anti-Pattern: Naive Chunking

**Problem z automatycznym chunkingiem:**

```python
# ❌ ANTI-PATTERN - Naive chunking
def naive_chunk(text: str, chunk_size: int = 500):
    """Dzieli tekst na chunki o stałym rozmiarze - ZŁA PRAKTYKA"""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

# Co jest nie tak?
# 1. Może rozdzielić tabelę w połowie
# 2. Może rozerwać powiązane informacje
# 3. Traci strukturę (nagłówki, sekcje)
# 4. Ignoruje semantykę
```

**Przykład zniszczenia semantyki - Tabela finansowa:**

```
Oryginalna tabela:
+------------------+----------+----------+
| Kategoria        | 2023     | 2024     |
+------------------+----------+----------+
| Przychody        | 1500 mln | 1800 mln |
| Koszty           | 1000 mln | 1200 mln |
| Zysk             | 500 mln  | 600 mln  |
+------------------+----------+----------+

Po naiwnym chunkingu (chunk_size=50 słów):
Chunk 1: "Kategoria 2023 2024 Przychody 1500 mln 1800 mln"
Chunk 2: "Koszty 1000 mln 1200 mln Zysk 500"
Chunk 3: "mln 600 mln"

❌ Struktura zniszczona - niemożliwe odczytanie!
```

**Dlaczego to jest problem:**

1. **Utrata kontekstu tabelarycznego**
   - Nie wiadomo, która liczba do czego się odnosi
   - Powiązania między kolumnami zerwane

2. **Semantyczna niespójność**
   - Fragmenty zdań w różnych chunkach
   - Kontekst zagubiony

3. **Niemożność odpowiedzi na pytania**
   ```
   Q: "Jaki był zysk w 2024?"
   Chunk 2: "Koszty 1000 mln 1200 mln Zysk 500"
   Chunk 3: "mln 600 mln"
   → Model nie wie, że "600 mln" to zysk w 2024!
   ```

### 4.3 Właściwa Architektura RAG

**💡 Zasada: Zachowaj strukturę semantyczną danych**

**Proper RAG Architecture:**

```
┌─────────────────────────────────────────────┐
│         KNOWLEDGE BASE                       │
│  (Structured, semantically coherent units)  │
│                                              │
│  • Całe tabele z kontekstem                 │
│  • Sekcje dokumentów z nagłówkami           │
│  • Powiązane informacje razem              │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │   RETRIEVER    │
         │                │
         │ • Semantic     │
         │   Search       │
         │ • Metadata     │
         │   Filtering    │
         │ • Hybrid       │
         │   Search       │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │   CONTEXT      │
         │   BUILDER      │
         │                │
         │ Formatuje      │
         │ retrieved      │
         │ knowledge      │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │   GENERATOR    │
         │     (LLM)      │
         │                │
         │ Odpowiada na   │
         │ podstawie      │
         │ kontekstu      │
         └────────────────┘
```

**Kluczowe komponenty:**

1. **Knowledge Base Design**
   - Przechowuj dane w semantycznie spójnych jednostkach
   - Dodaj metadata (typ dokumentu, data, źródło)
   - Zachowaj strukturę (tabele jako całość, sekcje razem)

2. **Retriever**
   - Semantic search (embeddings)
   - Keyword search (BM25)
   - Hybrid approach (najlepsze z obu)
   - Metadata filtering

3. **Context Builder**
   - Formatuje retrieved content dla LLM
   - Dodaje strukturę (XML tags, markdown)
   - Priorytetyzuje najbardziej relevantne fragmenty

4. **Generator (LLM)**
   - Otrzymuje structured context
   - Generuje odpowiedź based on context
   - Może cytować źródła

### 4.4 Context Engineering - Structured Context Delivery

**💡 Jak dostarczać kontekst do LLM:**

**Pattern 1: XML Tags dla struktury**

```python
from typing import List
from pydantic import BaseModel, Field

class FinancialContext(BaseModel):
    source: str = Field(description="Nazwa dokumentu źródłowego")
    year: int
    revenues: float
    costs: float
    profit: float

def format_context(data: List[FinancialContext]) -> str:
    """Formatuje dane finansowe jako structured context."""
    context = "<context>\n"

    for item in data:
        context += f"""
<financial_data>
    <source>{item.source}</source>
    <year>{item.year}</year>
    <revenues>{item.revenues} mln USD</revenues>
    <costs>{item.costs} mln USD</costs>
    <profit>{item.profit} mln USD</profit>
</financial_data>
"""

    context += "</context>"
    return context

# System prompt z instrukcjami
system_prompt = """
Jesteś ekspertem finansowym i analitykiem.

Dane znajdują się w tagu <context></context>.
Każdy wpis jest w <financial_data></financial_data>.

<guidelines>
1. Wartości są w milionach USD
2. Bazuj odpowiedzi TYLKO na dostarczonych danych
3. Jeśli danych nie ma, powiedz "Nie mam tej informacji"
4. Zawsze podawaj źródło (tag <source>)
</guidelines>
"""

# User query
user_query = "Jaki był zysk w 2024 roku?"

# Context data
context_data = [
    FinancialContext(source="Q4 2023 Report", year=2023, revenues=1500, costs=1000, profit=500),
    FinancialContext(source="Q4 2024 Report", year=2024, revenues=1800, costs=1200, profit=600)
]

# Formatuj kontekst
formatted_context = format_context(context_data)

# API call
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{formatted_context}\n\nPytanie: {user_query}"}
    ]
)

print(response.choices[0].message.content)
# Output: "Zysk w 2024 roku wyniósł 600 mln USD (źródło: Q4 2024 Report)"
```

**Pattern 2: Markdown Tables dla tabelarycznych danych**

```python
def format_as_markdown_table(data: List[dict]) -> str:
    """Formatuje dane jako Markdown table - LLM świetnie je rozumie."""

    # Header
    table = "| Rok | Przychody (mln) | Koszty (mln) | Zysk (mln) |\n"
    table += "|-----|-----------------|--------------|------------|\n"

    # Rows
    for row in data:
        table += f"| {row['year']} | {row['revenues']} | {row['costs']} | {row['profit']} |\n"

    return table

context = f"""
<context>
# Dane finansowe PKO SA 2023-2024

{format_as_markdown_table([
    {'year': 2023, 'revenues': 1500, 'costs': 1000, 'profit': 500},
    {'year': 2024, 'revenues': 1800, 'costs': 1200, 'profit': 600}
])}

Źródło: Raporty roczne PKO SA
</context>
"""
```

**Pattern 3: JSON dla złożonych struktur**

```python
import json
from typing import Dict, Any

def format_as_json_context(data: Dict[str, Any]) -> str:
    """Formatuje złożone dane jako JSON w kontekście."""
    return f"""
<context>
<format>JSON</format>
<data>
{json.dumps(data, indent=2, ensure_ascii=False)}
</data>
</context>
"""

# Przykład - złożona struktura
company_data = {
    "company": "PKO SA",
    "financials": {
        "2023": {
            "Q1": {"revenue": 350, "profit": 120},
            "Q2": {"revenue": 380, "profit": 130},
            "Q3": {"revenue": 370, "profit": 125},
            "Q4": {"revenue": 400, "profit": 125}
        },
        "2024": {
            "Q1": {"revenue": 420, "profit": 145},
            "Q2": {"revenue": 450, "profit": 155},
            "Q3": {"revenue": 440, "profit": 150},
            "Q4": {"revenue": 490, "profit": 150}
        }
    },
    "employees": 25000,
    "headquarters": "Warsaw, Poland"
}

context = format_as_json_context(company_data)
```

### 4.5 Practical RAG Implementation

**Complete RAG System Example:**

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
import instructor

# ===== MODELS =====

class Document(BaseModel):
    """Dokument w knowledge base."""
    id: str
    content: str
    metadata: dict
    embedding: Optional[List[float]] = None

class RetrievedDoc(BaseModel):
    """Dokument po retrieval z score."""
    document: Document
    relevance_score: float

class Answer(BaseModel):
    """Structured answer z RAG."""
    answer: str = Field(description="Odpowiedź na pytanie")
    confidence: float = Field(ge=0, le=1, description="Pewność odpowiedzi")
    sources: List[str] = Field(description="ID dokumentów źródłowych")
    reasoning: str = Field(description="Uzasadnienie odpowiedzi")

# ===== RETRIEVER =====

class SimpleRetriever:
    """Prosty retriever z semantic search."""

    def __init__(self, documents: List[Document]):
        self.documents = documents
        self.client = OpenAI()

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding dla tekstu."""
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Oblicz cosine similarity."""
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def retrieve(self, query: str, top_k: int = 3) -> List[RetrievedDoc]:
        """Retrieve top-k najbardziej relevantnych dokumentów."""
        query_embedding = self._get_embedding(query)

        scored_docs = []
        for doc in self.documents:
            if doc.embedding is None:
                doc.embedding = self._get_embedding(doc.content)

            score = self._cosine_similarity(query_embedding, doc.embedding)
            scored_docs.append(RetrievedDoc(document=doc, relevance_score=score))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x.relevance_score, reverse=True)

        return scored_docs[:top_k]

# ===== CONTEXT BUILDER =====

class ContextBuilder:
    """Buduje structured context z retrieved documents."""

    @staticmethod
    def build(retrieved_docs: List[RetrievedDoc]) -> str:
        """Format retrieved documents jako structured context."""
        context = "<context>\n"

        for i, ret_doc in enumerate(retrieved_docs, 1):
            doc = ret_doc.document
            context += f"""
<document id="{doc.id}" relevance="{ret_doc.relevance_score:.2f}">
<metadata>
{doc.metadata}
</metadata>
<content>
{doc.content}
</content>
</document>
"""

        context += "</context>"
        return context

# ===== RAG SYSTEM =====

class RAGSystem:
    """Complete RAG system."""

    def __init__(self, documents: List[Document]):
        self.retriever = SimpleRetriever(documents)
        self.context_builder = ContextBuilder()
        self.client = OpenAI()
        self.client = instructor.patch(self.client, mode=instructor.Mode.MD_JSON)

    def answer(self, query: str, top_k: int = 3) -> Answer:
        """Answer query using RAG."""

        # 1. Retrieve relevant documents
        retrieved_docs = self.retriever.retrieve(query, top_k=top_k)

        # 2. Build context
        context = self.context_builder.build(retrieved_docs)

        # 3. Generate answer with LLM
        system_prompt = """
Jesteś pomocnym asystentem odpowiadającym na pytania na podstawie dostarczonych dokumentów.

<guidelines>
1. Bazuj odpowiedzi TYLKO na informacjach z <context>
2. Jeśli nie ma informacji, powiedz: "Nie znalazłem tej informacji w dostępnych dokumentach"
3. Zawsze cytuj ID dokumentów źródłowych
4. Bądź precyzyjny i konkretny
5. Oceń swoją pewność odpowiedzi (0-1)
</guidelines>
"""

        user_prompt = f"""
{context}

Pytanie: {query}
"""

        answer = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_model=Answer
        )

        return answer

# ===== USAGE EXAMPLE =====

# Create knowledge base
documents = [
    Document(
        id="doc1",
        content="PKO SA w 2023 roku osiągnęło przychody 1500 mln PLN i zysk 500 mln PLN.",
        metadata={"source": "Raport roczny 2023", "year": 2023}
    ),
    Document(
        id="doc2",
        content="W 2024 roku PKO SA zwiększyło przychody do 1800 mln PLN, a zysk wzrósł do 600 mln PLN.",
        metadata={"source": "Raport roczny 2024", "year": 2024}
    ),
    Document(
        id="doc3",
        content="PKO SA zatrudnia 25 000 pracowników i ma siedzibę w Warszawie.",
        metadata={"source": "Profil firmy", "year": 2024}
    )
]

# Initialize RAG system
rag = RAGSystem(documents)

# Ask question
answer = rag.answer("Jaki był zysk PKO SA w 2024?")

print(f"Odpowiedź: {answer.answer}")
print(f"Pewność: {answer.confidence}")
print(f"Źródła: {answer.sources}")
print(f"Uzasadnienie: {answer.reasoning}")

# Output example:
# Odpowiedź: Zysk PKO SA w 2024 roku wyniósł 600 mln PLN.
# Pewność: 0.95
# Źródła: ['doc2']
# Uzasadnienie: Informacja pochodzi bezpośrednio z dokumentu doc2 (Raport roczny 2024), który explicite podaje wartość zysku.
```

### 4.6 Advanced RAG Patterns

**Pattern 1: Hybrid Search (Semantic + Keyword)**

```python
from rank_bm25 import BM25Okapi
import numpy as np

class HybridRetriever:
    """Łączy semantic search z keyword search (BM25)."""

    def __init__(self, documents: List[Document], alpha: float = 0.5):
        self.documents = documents
        self.alpha = alpha  # Waga dla semantic vs keyword (0.5 = równe)
        self.client = OpenAI()

        # Prepare BM25
        tokenized_docs = [doc.content.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized_docs)

    def retrieve(self, query: str, top_k: int = 3) -> List[RetrievedDoc]:
        """Hybrid retrieval."""
        # 1. Semantic scores
        query_embedding = self._get_embedding(query)
        semantic_scores = []

        for doc in self.documents:
            if doc.embedding is None:
                doc.embedding = self._get_embedding(doc.content)
            score = self._cosine_similarity(query_embedding, doc.embedding)
            semantic_scores.append(score)

        # Normalize to 0-1
        semantic_scores = np.array(semantic_scores)
        if semantic_scores.max() > 0:
            semantic_scores = semantic_scores / semantic_scores.max()

        # 2. Keyword scores (BM25)
        tokenized_query = query.lower().split()
        keyword_scores = self.bm25.get_scores(tokenized_query)

        # Normalize to 0-1
        if keyword_scores.max() > 0:
            keyword_scores = keyword_scores / keyword_scores.max()

        # 3. Combine scores
        combined_scores = (
            self.alpha * semantic_scores +
            (1 - self.alpha) * keyword_scores
        )

        # 4. Rank and return top-k
        scored_docs = [
            RetrievedDoc(document=doc, relevance_score=float(score))
            for doc, score in zip(self.documents, combined_scores)
        ]

        scored_docs.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_docs[:top_k]
```

**Pattern 2: Metadata Filtering**

```python
class FilteredRetriever:
    """Retriever z filtrowaniem po metadata."""

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        metadata_filters: Optional[dict] = None
    ) -> List[RetrievedDoc]:
        """
        Retrieve z opcjonalnym filtrowaniem.

        Args:
            query: Zapytanie
            top_k: Ile dokumentów zwrócić
            metadata_filters: Filtry, np. {"year": 2024, "source": "annual_report"}
        """
        # Filter documents by metadata
        filtered_docs = self.documents

        if metadata_filters:
            filtered_docs = [
                doc for doc in self.documents
                if all(
                    doc.metadata.get(key) == value
                    for key, value in metadata_filters.items()
                )
            ]

        if not filtered_docs:
            return []

        # Semantic search on filtered documents
        query_embedding = self._get_embedding(query)
        scored_docs = []

        for doc in filtered_docs:
            if doc.embedding is None:
                doc.embedding = self._get_embedding(doc.content)

            score = self._cosine_similarity(query_embedding, doc.embedding)
            scored_docs.append(RetrievedDoc(document=doc, relevance_score=score))

        scored_docs.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_docs[:top_k]

# Usage
answer = rag.answer(
    "Jaki był zysk?",
    metadata_filters={"year": 2024}  # Tylko dokumenty z 2024
)
```

**Pattern 3: Re-ranking**

```python
class ReRankingRAG:
    """RAG z re-rankingiem dla lepszej precyzji."""

    def retrieve_and_rerank(
        self,
        query: str,
        initial_k: int = 10,
        final_k: int = 3
    ) -> List[RetrievedDoc]:
        """
        1. Retrieve więcej dokumentów (initial_k)
        2. Re-rank używając LLM do oceny relevance
        3. Zwróć top final_k
        """
        # 1. Initial retrieval
        candidates = self.retriever.retrieve(query, top_k=initial_k)

        # 2. Re-rank with LLM
        reranked = []

        for candidate in candidates:
            # Ask LLM to score relevance
            prompt = f"""
Na skali 0-10, jak relevantny jest ten dokument dla pytania?

Pytanie: {query}

Dokument: {candidate.document.content}

Zwróć tylko liczbę 0-10.
"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            try:
                llm_score = float(response.choices[0].message.content.strip()) / 10.0
                candidate.relevance_score = llm_score
            except:
                pass  # Keep original score if parsing fails

            reranked.append(candidate)

        # 3. Sort and return top final_k
        reranked.sort(key=lambda x: x.relevance_score, reverse=True)
        return reranked[:final_k]
```

### 4.7 RAG Best Practices

**✅ DO:**

1. **Zachowaj semantyczną spójność chunks**
   ```python
   # ✅ Chunk by semantic units
   - Całe sekcje z nagłówkami
   - Kompletne tabele
   - Powiązane paragrafy razem
   ```

2. **Dodaj metadata**
   ```python
   document = Document(
       content="...",
       metadata={
           "source": "annual_report_2024.pdf",
           "section": "Financial Results",
           "page": 15,
           "date": "2024-12-31",
           "company": "PKO SA"
       }
   )
   ```

3. **Use structured context formatting**
   ```python
   # XML tags, Markdown tables, JSON - cokolwiek co dodaje strukturę
   ```

4. **Validate retrieved content**
   ```python
   # Sprawdź czy retrieved docs są rzeczywiście relevantne
   # Ustaw threshold dla relevance_score
   if max_score < 0.7:
       return "Nie znalazłem wystarczająco relevantnych informacji"
   ```

5. **Cite sources**
   ```python
   # Zawsze podawaj źródła w odpowiedzi
   answer.sources = [doc.id for doc in used_docs]
   ```

**❌ DON'T:**

1. **Nie używaj naive fixed-size chunking**
   ```python
   # ❌ Nie rób tego
   chunks = [text[i:i+500] for i in range(0, len(text), 500)]
   ```

2. **Nie ignoruj struktury dokumentu**
   ```python
   # ❌ Nie traktuj PDF/Word jako plain text
   # ✅ Parsuj strukturę (nagłówki, tabele, listy)
   ```

3. **Nie polegaj tylko na semantic search**
   ```python
   # ✅ Użyj hybrid search (semantic + keyword)
   ```

4. **Nie zwracaj zbyt dużo context**
   ```python
   # Model ma limit kontekstu
   # Priorytetyzuj najważniejsze fragmenty
   # Ogranicz top_k do 3-5 dokumentów
   ```

5. **Nie zakładaj, że retrieved content jest prawdziwy**
   ```python
   # Zawsze waliduj i cross-reference
   # Oceń confidence
   ```

### 4.8 Case Study: Financial Assistant

**Kompletny przykład RAG dla asystenta finansowego:**

```python
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# ===== MODELS =====

class FinancialMetric(BaseModel):
    """Metryka finansowa."""
    metric_name: str
    value: float
    unit: str  # e.g., "mln PLN", "USD", "%"
    period: str  # e.g., "Q1 2024", "2024"

class FinancialAnswer(BaseModel):
    """Odpowiedź asystenta finansowego."""
    answer: str
    metrics: List[FinancialMetric]
    confidence: float = Field(ge=0, le=1)
    sources: List[str]
    caveats: Optional[str] = Field(None, description="Zastrzeżenia lub uwagi")

# ===== FINANCIAL RAG SYSTEM =====

class FinancialRAG:
    """RAG system dla analiz finansowych."""

    def __init__(self, documents: List[Document]):
        self.rag = RAGSystem(documents)

    def analyze(self, query: str) -> FinancialAnswer:
        """Analyze financial query."""

        system_prompt = """
Jesteś ekspertem finansowym i analitykiem. Analizujesz dane finansowe firm.

<guidelines>
1. Wszystkie wartości w dokumentach są w milionach (mln)
2. Bazuj TYLKO na dostarczonych danych
3. Wyciągnij konkretne metryki finansowe
4. Podaj źródła i okres
5. Dodaj caveats jeśli dane mogą być niepełne lub nieaktualne
6. Oceń swoją pewność
</guidelines>

<output_format>
Zwróć strukturalną odpowiedź z:
- Tekstową odpowiedzią
- Listą metryk (nazwa, wartość, jednostka, okres)
- Confidence score
- Źródłami
- Caveats (jeśli applicable)
</output_format>
"""

        retrieved_docs = self.rag.retriever.retrieve(query, top_k=5)
        context = self.rag.context_builder.build(retrieved_docs)

        user_prompt = f"""
{context}

Pytanie analityczne: {query}
"""

        response = self.rag.client.chat.completions.create(
            model="gpt-4o",  # Use better model for financial analysis
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_model=FinancialAnswer,
            temperature=0  # Deterministic for financial data
        )

        return response

# ===== USAGE =====

# Create financial knowledge base
fin_documents = [
    Document(
        id="pko_2023_q4",
        content="""
PKO SA - Raport kwartalny Q4 2023

Przychody: 1500 mln PLN (+12% YoY)
Koszty operacyjne: 1000 mln PLN
EBITDA: 700 mln PLN
Zysk netto: 500 mln PLN

Marża zysku: 33.3%
ROE: 15.2%
""",
        metadata={"company": "PKO SA", "period": "Q4 2023", "type": "quarterly_report"}
    ),
    Document(
        id="pko_2024_q4",
        content="""
PKO SA - Raport kwartalny Q4 2024

Przychody: 1800 mln PLN (+20% YoY)
Koszty operacyjne: 1200 mln PLN
EBITDA: 850 mln PLN
Zysk netto: 600 mln PLN

Marża zysku: 33.3%
ROE: 16.8%
""",
        metadata={"company": "PKO SA", "period": "Q4 2024", "type": "quarterly_report"}
    )
]

# Initialize
fin_rag = FinancialRAG(fin_documents)

# Analyze
analysis = fin_rag.analyze("""
Jaka była dynamika wzrostu przychodów i zysku PKO SA między 2023 a 2024?
Porównaj też rentowność.
""")

print(f"Odpowiedź: {analysis.answer}")
print(f"\nMetryki:")
for metric in analysis.metrics:
    print(f"  - {metric.metric_name}: {metric.value} {metric.unit} ({metric.period})")
print(f"\nPewność: {analysis.confidence}")
print(f"Źródła: {analysis.sources}")
if analysis.caveats:
    print(f"Uwagi: {analysis.caveats}")

# Expected output:
# Odpowiedź: PKO SA wykazało silny wzrost między 2023 a 2024. Przychody wzrosły
# z 1500 mln do 1800 mln PLN (+20%), a zysk netto z 500 mln do 600 mln PLN (+20%).
# Rentowność pozostała stabilna na poziomie 33.3% marży zysku, podczas gdy ROE
# poprawiło się z 15.2% do 16.8%.
#
# Metryki:
#   - Przychody: 1500.0 mln PLN (Q4 2023)
#   - Przychody: 1800.0 mln PLN (Q4 2024)
#   - Wzrost przychodów: 20.0 % (2023-2024)
#   - Zysk netto: 500.0 mln PLN (Q4 2023)
#   - Zysk netto: 600.0 mln PLN (Q4 2024)
#   - Wzrost zysku: 20.0 % (2023-2024)
#   - Marża zysku: 33.3 % (stała)
#   - ROE: 15.2 % (Q4 2023)
#   - ROE: 16.8 % (Q4 2024)
#
# Pewność: 0.95
# Źródła: ['pko_2023_q4', 'pko_2024_q4']
# Uwagi: Dane dotyczą tylko Q4 poszczególnych lat. Dla pełnego obrazu roku
# zalecana analiza wszystkich kwartałów.
```

---

## Podsumowanie Części II

W tej części nauczyłeś się:

✅ **Czym jest RAG** i czym NIE jest (nie tylko chunking + vector DB)
✅ **Dlaczego naive chunking** niszczy semantyczną strukturę danych
✅ **Właściwą architekturę RAG**: Retriever + Context Builder + Generator
✅ **Context Engineering**: Jak strukturalnie dostarczać wiedzę do LLM
✅ **Praktyczne implementacje**: Semantic search, hybrid search, re-ranking
✅ **Best practices**: Metadata, source citation, validation

**Kluczowe zasady:**
1. **Zachowaj semantyczną spójność** - nie dziel arbitralnie
2. **Struktura jest kluczowa** - XML tags, Markdown, JSON
3. **Hybrid search > tylko semantic** - łącz embeddings z keyword search
4. **Zawsze cytuj źródła** - transparency i traceability
5. **Waliduj confidence** - nie każda odpowiedź jest pewna

**Następne kroki:**
W Części III przejdziemy do paradygmatu Software 3.0, spektrum autonomii (L1-L7) i fundamentów AI Agents - w tym kluczowego wzorca ReAct!
# CZĘŚĆ III: SOFTWARE 3.0 I AI AGENTS

## 5. Paradygmat Software 3.0

### 💡 Kluczowa Idea
**Software 3.0 = Pre-trained Models + Prompting/Fine-tuning (zamiast trenowania od zera)**

### 5.1 Ewolucja Paradygmatów

**Software 1.0: Explicit Programming**
```python
# Ręcznie pisany kod z regułami
def categorize_email(email_text):
    if "viagra" in email_text.lower() or "lottery" in email_text.lower():
        return "SPAM"
    elif "meeting" in email_text.lower() or "invoice" in email_text.lower():
        return "WORK"
    else:
        return "PERSONAL"

# Problemy:
# - Nieskalowalność (tysiące reguł)
# - Brak adaptacji do nowych przypadków
# - Maintainance nightmare
```

**Software 2.0: Machine Learning**
```python
# Trenujemy model od zera na naszych danych
from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import TfidfVectorizer

# 1. Zbierz dane treningowe (potrzeba tysięcy przykładów!)
X_train = ["meeting tomorrow at 3pm", "you won the lottery!", ...]
y_train = ["WORK", "SPAM", ...]

# 2. Feature engineering
vectorizer = TfidfVectorizer()
X_features = vectorizer.fit_transform(X_train)

# 3. Trenuj model
model = MultinomialNB()
model.fit(X_features, y_train)

# 4. Użyj
new_email = "Check out this amazing offer!!!"
prediction = model.predict(vectorizer.transform([new_email]))

# Problemy:
# - Potrzeba dużo danych treningowych
# - Długi czas treningu
# - Wymaga ekspertów ML
# - Model specyficzny dla jednego zadania
```

**Software 3.0: Pre-trained Models + Prompting**
```python
# Używamy gotowego, pre-trained LLM
from openai import OpenAI

client = OpenAI()

def categorize_email(email_text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Pre-trained model!
        messages=[
            {
                "role": "system",
                "content": "Kategoryzuj emaile jako: SPAM, WORK, lub PERSONAL"
            },
            {
                "role": "user",
                "content": f"Email: {email_text}"
            }
        ]
    )
    return response.choices[0].message.content

# Zalety:
# ✅ Działa od razu (zero-shot)
# ✅ Nie potrzeba danych treningowych
# ✅ Jeden model = wiele zadań
# ✅ Łatwa adaptacja (zmiana promptu)
# ✅ Dostępne dla każdego (nie tylko ML experts)
```

**Porównanie:**

| Aspekt | Software 1.0 | Software 2.0 | Software 3.0 |
|--------|--------------|--------------|--------------|
| **Approach** | Ręczne reguły | Trenowanie od zera | Pre-trained + prompting |
| **Dane** | Nie potrzeba | Tysiące przykładów | Opcjonalne (few-shot) |
| **Czas dev** | Tygodnie | Tygodnie-miesiące | Godziny-dni |
| **Adaptacja** | Nowy kod | Nowy trening | Nowy prompt |
| **Expertise** | Programista | ML Engineer | Prompt Engineer |
| **Skalowalność** | Niska | Średnia | Wysoka |
| **Koszt** | Czas dev | GPU + czas | API calls |

### 5.2 Kiedy używać LLM, a kiedy klasycznego ML?

**💡 Nie wszystko wymaga LLM - wybierz właściwe narzędzie**

**Używaj LLM gdy:**

1. **Zadania związane z językiem naturalnym**
   - Generowanie tekstu
   - Sentiment analysis
   - Tłumaczenia
   - Podsumowania
   - Q&A

2. **Brak lub mało danych treningowych**
   - Zero-shot lub few-shot learning
   - Nowe domeny

3. **Złożone rozumowanie**
   - Multi-step reasoning
   - Chain-of-thought
   - Kontekstowe zrozumienie

4. **Potrzeba elastyczności**
   - Szybka adaptacja do nowych zadań
   - Zmienne requirements

**Używaj klasycznego ML gdy:**

1. **Dane tabelaryczne / strukturalne**
   ```python
   # Przykład: Przewidywanie churn klientów
   Features: wiek, liczba_transakcji, średnia_wartość, dni_od_ostatniej_aktywności
   Target: czy_odszedł (0/1)

   # ✅ Użyj XGBoost/Random Forest - będzie lepsze niż LLM
   ```

2. **Precyzja > interpretacja**
   - Klasyczny ML często daje lepszą metryczną precyzję
   - Szczególnie dla zadań numerycznych

3. **Koszty i latencja**
   - Klasyczny ML: inference w milisekundach
   - LLM: sekundy + koszt API

4. **Compliance i regulacje**
   - Finanse, medycyna wymagają explainability
   - Klasyczny ML łatwiej interpretować

5. **Offline / edge deployment**
   - Małe modele klasycznego ML działają offline
   - LLM zazwyczaj wymaga cloud API

**Hybrid Approach - najlepsze z obu światów:**

```python
# Przykład: LLM ekstrakcja + ML predykcja

# 1. LLM ekstrahuje features z nieustrukturyzowanego tekstu
class CustomerReview(BaseModel):
    sentiment: str
    product_quality_score: int
    service_quality_score: int
    mentions_price: bool
    mentions_delivery: bool

def extract_features(review_text: str) -> CustomerReview:
    """LLM strukturyzuje tekst."""
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Extract features: {review_text}"}],
        response_model=CustomerReview
    )

# 2. Klasyczny ML przewiduje na podstawie structured features
import xgboost as xgb

def predict_churn(customer_features: CustomerReview, other_features: dict) -> float:
    """XGBoost przewiduje prawdopodobieństwo churn."""
    # Combine LLM-extracted features with other data
    X = {
        'sentiment_score': 1 if customer_features.sentiment == 'POSITIVE' else 0,
        'product_score': customer_features.product_quality_score,
        'service_score': customer_features.service_quality_score,
        **other_features  # Age, transactions, etc.
    }

    return xgb_model.predict_proba(X)[:, 1]  # Probability of churn

# Best of both worlds:
# - LLM handles unstructured text
# - ML handles structured prediction
```

### 5.3 Transfer Learning w kontekście LLM

**Transfer Learning = wykorzystanie wiedzy z jednego zadania w innym**

**W klasycznym ML:**
```python
# Trenujemy na ImageNet (1M obrazków)
# Potem fine-tunujemy na naszych 1000 obrazkach psów/kotów
base_model = ResNet50(weights='imagenet')  # Pre-trained
model = fine_tune(base_model, my_dog_cat_data)
```

**W LLM - transfer learning jest wbudowany:**

```python
# Model już zna:
# - Składnię języków programowania
# - Struktury danych
# - Wzorce problemowe
# - Kontekst biznesowy

# Wystarczy pokazać przykłady (few-shot):
prompt = """
Convert business logic to SQL:

Example 1:
Input: "customers who bought more than $1000 last month"
Output: SELECT * FROM customers WHERE total_spent_last_month > 1000

Example 2:
Input: "products with low stock that sold well"
Output: SELECT * FROM products WHERE stock < 10 AND sales_last_month > 100

Now you:
Input: "users who signed up this year but never made a purchase"
Output:
"""

# LLM wykorzystuje swoją pre-trained knowledge + few-shot examples
```

**Fine-tuning LLM (advanced):**
```python
# Gdy few-shot nie wystarcza, można fine-tunować
from openai import OpenAI

client = OpenAI()

# 1. Przygotuj training data
training_data = [
    {
        "messages": [
            {"role": "system", "content": "You are a financial analyst"},
            {"role": "user", "content": "Analyze Q3 results"},
            {"role": "assistant", "content": "Q3 shows 15% revenue growth..."}
        ]
    },
    # ... więcej przykładów
]

# 2. Fine-tune model
fine_tune_job = client.fine_tuning.jobs.create(
    training_file="file-abc123",
    model="gpt-4o-mini-2024-07-18"
)

# 3. Użyj fine-tuned model
response = client.chat.completions.create(
    model=fine_tune_job.fine_tuned_model,
    messages=[{"role": "user", "content": "Analyze Q4"}]
)

# Fine-tuning używaj gdy:
# - Masz setki/tysiące przykładów specyficznego stylu
# - Potrzebujesz konsystentnego outputu
# - Few-shot nie daje wystarczającej jakości
```

---

## 6. Spektrum Autonomii (L1-L7)

### 💡 Kluczowa Idea
**Autonomia systemów AI ma poziomy - czerwona linia przy L4 (stateful systems)**

### 6.1 7 Poziomów Autonomii

**Poziomy autonomii opisują jak bardzo system może działać niezależnie:**

```
L1 ────────────► L7
Stateless        Stateful         Full Autonomy
Reactive         Proactive        Self-Learning
Zero Memory      Managed Memory   Adaptive

RED LINE at L4 ←─────────────────
(Managed Memory + State)
```

### 6.2 L1: Stateless, Reactive

**Charakterystyka:**
- Każde wywołanie jest niezależne
- Brak pamięci między wywołaniami
- Czyste funkcje: Input → Output
- Najprostszy i najbezpieczniejszy poziom

**Przykład - Calculator Bot:**
```python
def calculate(expression: str) -> float:
    """L1: Stateless calculator."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a calculator. Return only the numeric result."},
            {"role": "user", "content": f"Calculate: {expression}"}
        ]
    )
    return float(response.choices[0].message.content)

# Każde wywołanie jest niezależne
result1 = calculate("15 + 27")  # 42
result2 = calculate("100 - 30")  # 70
result3 = calculate("multiply previous result by 2")  # ❌ Nie wie co to "previous result"
```

**Use cases:**
- Proste konwersje i transformacje
- Klasyfikacja tekstu
- Ekstrakcja danych
- Walidacja

**Zalety:**
- Łatwe testowanie
- Przewidywalne
- Skalowalne (można równolegle)
- Brak state corruption

**Wady:**
- Brak kontekstu między wywołaniami
- Nie może "pamiętać" poprzednich interakcji

### 6.3 L2: Stateless z Context

**Charakterystyka:**
- Wciąż stateless, ale dostaje kontekst
- Kontekst jest przekazywany explicite
- System nie przechowuje nic między wywołaniami

**Przykład - Conversation with context:**
```python
def chat_with_context(user_message: str, conversation_history: List[dict]) -> str:
    """L2: Stateless but receives context."""

    messages = conversation_history + [
        {"role": "user", "content": user_message}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    return response.choices[0].message.content

# Usage
history = []

# Turn 1
response1 = chat_with_context("My name is John", history)
history.append({"role": "user", "content": "My name is John"})
history.append({"role": "assistant", "content": response1})

# Turn 2
response2 = chat_with_context("What's my name?", history)  # ✅ Zna - bo dostał history
# Ale sam system nic nie przechowuje!
```

**Use cases:**
- Chatboty z session management po stronie aplikacji
- Multi-turn conversations
- Context-aware processing

**Zalety:**
- Kontrola nad contextem (aplikacja decyduje co przekazać)
- Wciąż deterministyczne
- Można limitować context size

**Wady:**
- Aplikacja musi zarządzać state
- Context rośnie (token costs)

### 6.4 L3: Stateless z Tools

**Charakterystyka:**
- Może wywoływać external tools/functions
- Ale wciąż nie przechowuje state między wywołaniami
- Tool outputs są przekazywane z powrotem do systemu

**Przykład - Agent z narzędziami:**
```python
from typing import List, Callable
import json

# Define tools
def get_weather(city: str) -> dict:
    """Tool: Get weather for city."""
    # W rzeczywistości: API call
    return {"city": city, "temp": 22, "condition": "sunny"}

def get_time(timezone: str) -> dict:
    """Tool: Get current time."""
    from datetime import datetime
    return {"timezone": timezone, "time": datetime.now().isoformat()}

# Tool definitions for LLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get current time in timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string"}
                },
                "required": ["timezone"]
            }
        }
    }
]

# Tool registry
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "get_time": get_time
}

def l3_agent(user_query: str, max_iterations: int = 5) -> str:
    """L3: Stateless agent with tools."""

    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to tools."},
        {"role": "user", "content": user_query}
    ]

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # Check if tool call
        if message.tool_calls:
            # Execute tool
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                # Call actual function
                function_response = TOOL_FUNCTIONS[function_name](**function_args)

                # Add to messages
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_response)
                })
        else:
            # Final answer
            return message.content

    return "Max iterations reached"

# Usage
answer = l3_agent("What's the weather in Warsaw and what time is it there?")
print(answer)
# Output: "It's currently sunny and 22°C in Warsaw. The local time is 14:30."

# ⚠️ Następne wywołanie nie pamięta poprzedniego!
answer2 = l3_agent("What was the temperature there?")  # ❌ Nie wie o czym mowa
```

**Use cases:**
- Agents z dostępem do APIs
- Search + synthesis
- Data retrieval + processing

**Zalety:**
- Może wchodzić w interakcje ze światem
- Wciąż przewidywalne (stateless)
- Deterministyczne przy tym samym input+tools

**Wady:**
- Brak pamięci długoterminowej
- Każda sesja zaczyna od zera

### 6.5 L4: Stateful z Managed Memory (RED LINE)

**💡 To jest czerwona linia - przejście do prawdziwej autonomii**

**Charakterystyka:**
- **Przechowuje state między wywołaniami**
- Managed memory (system zarządza co zapamiętać)
- Może się "uczyć" z interakcji
- Traci deterministyczność

**Dlaczego "Red Line"?**
1. **Utrata przewidywalności** - system może zachować się inaczej przez historię
2. **State corruption risk** - zła pamięć = złe decyzje
3. **Privacy concerns** - co system zapamiętuje?
4. **Debugging nightmare** - trudno odtworzyć błędy
5. **Compliance issues** - regulacje o przechowywaniu danych

**Przykład - Personal Assistant z pamięcią:**
```python
from typing import Dict, List, Optional
from datetime import datetime
import json

class Memory(BaseModel):
    """Memory entry."""
    timestamp: datetime
    type: str  # e.g., "preference", "fact", "interaction"
    content: str
    importance: float = Field(ge=0, le=1)

class StatefulAssistant:
    """L4: Assistant with managed memory."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory: List[Memory] = []
        self.load_memory()  # Load from persistent storage

    def load_memory(self):
        """Load user's memory from database."""
        # In production: load from DB
        try:
            with open(f"memory_{self.user_id}.json", "r") as f:
                data = json.load(f)
                self.memory = [Memory(**m) for m in data]
        except FileNotFoundError:
            self.memory = []

    def save_memory(self):
        """Persist memory to database."""
        with open(f"memory_{self.user_id}.json", "w") as f:
            json.dump([m.dict() for m in self.memory], f, default=str)

    def get_relevant_memories(self, query: str, top_k: int = 5) -> List[Memory]:
        """Retrieve relevant memories for query."""
        # Simplified: in production use embeddings
        return sorted(
            self.memory,
            key=lambda m: m.importance,
            reverse=True
        )[:top_k]

    def extract_new_memories(self, conversation: str) -> List[Memory]:
        """Use LLM to extract what to remember."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """
Extract important information to remember from this conversation.
Focus on: user preferences, facts about user, important context.

Return as JSON array of memories with:
- type: "preference" | "fact" | "context"
- content: what to remember
- importance: 0-1 score
"""
                },
                {
                    "role": "user",
                    "content": f"Conversation:\n{conversation}"
                }
            ]
        )

        # Parse and create Memory objects
        # (Simplified for brevity)
        return []

    def chat(self, user_message: str) -> str:
        """Chat with memory."""

        # 1. Retrieve relevant memories
        relevant_memories = self.get_relevant_memories(user_message)

        # 2. Build context with memories
        memory_context = "\n".join([
            f"- {m.content}" for m in relevant_memories
        ])

        system_prompt = f"""
You are a personal AI assistant.

What you know about the user:
{memory_context}

Use this information to personalize your responses.
"""

        # 3. Generate response
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )

        answer = response.choices[0].message.content

        # 4. Extract new memories from this interaction
        conversation = f"User: {user_message}\nAssistant: {answer}"
        new_memories = self.extract_new_memories(conversation)

        # 5. Update memory
        self.memory.extend(new_memories)
        self.save_memory()

        return answer

# Usage
assistant = StatefulAssistant(user_id="john_123")

# First interaction
response1 = assistant.chat("I love Italian food, especially pizza")
# System remembers: preference=italian_food, favorite=pizza

# Later interaction (minutes, hours, or days later)
response2 = assistant.chat("Suggest a restaurant for dinner")
# System uses memory: "Since you love Italian food and especially pizza,
# I recommend Luigi's Pizzeria..."

# Even later
response3 = assistant.chat("What's my favorite food?")
# System recalls: "You love Italian food, especially pizza!"
```

**Use cases:**
- Personal assistants
- Customer service bots
- Therapeutic bots
- Educational tutors

**Zalety:**
- Personalizacja
- Kontekst długoterminowy
- Może się "uczyć" z interakcji

**Wady:**
- ⚠️ Utrata deterministyczności
- ⚠️ Memory management complexity
- ⚠️ Privacy i compliance concerns
- ⚠️ Trudne debugowanie
- ⚠️ Risk of incorrect memories

### 6.6 L5-L7: Advanced Autonomy

**L5: Multi-Agent Systems**
- Wiele agentów współpracujących
- Rozdzielone zadania i specjalizacje
- Komunikacja między agentami

**L6: Learning Systems**
- Aktywne uczenie się z feedback
- Self-improvement
- Reinforcement learning from human feedback (RLHF)

**L7: Full Autonomy**
- Pełna autonomia decision-making
- Self-directed goals
- Minimal human intervention
- ⚠️ Najwięcej ryzyka - requires strong governance

**Te poziomy są beyond scope tego przewodnika fundamentów.**

### 6.7 Choosing the Right Level

**Decision Framework:**

```
Start with L1 (Stateless) ──────────────────────────┐
                                                     │
Can it work without context? ─── YES ──────────────┤
         │                                          │
         NO                                         │
         │                                          │
         ▼                                          │
Try L2 (Context passed explicitly) ────────────────┤
                                                    │
Do you need external data/APIs? ─── NO ───────────┤
         │                                          │
         YES                                        │
         │                                          │
         ▼                                          │
Try L3 (Tools but stateless) ──────────────────────┤
                                                    │
Need personalization/memory? ─── NO ──────────────┤
         │                                          │
         YES                                        │
         │                                          │
         ▼                                          │
⚠️ L4+ (Stateful) - TYLKO jeśli konieczne ─────────┘
   - Zrozum ryzyka
   - Implement safeguards
   - Monitor closely
```

**Przykłady z odpowiednimi poziomami:**

| Use Case | Poziom | Reason |
|----------|--------|--------|
| Tłumaczenie tekstu | L1 | Stateless wystarczy |
| Chatbot FAQ | L2 | Context z bieżącej sesji |
| Research Assistant | L3 | Potrzebuje search/tools |
| Personal AI Companion | L4 | Wymaga długoterminowej pamięci |
| Email classifier | L1 | Każdy email niezależnie |
| Code reviewer | L2/L3 | Kontekst PR + możliwe tools |
| Customer service | L4 | Historia klienta |

---

## 7. AI Agents - Fundamenty

### 💡 Kluczowa Idea
**AI Agent = System z Goal + Perceive + Act + Learn**

### 7.1 Definicja AI Agent

**Agent to system który:**

1. **Ma cel (Goal)**
   - Wie co chce osiągnąć
   - Przykład: "Zarezerwuj stolik w restauracji"

2. **Postrzega środowisko (Perceive)**
   - Odbiera informacje z otoczenia
   - Przykład: Dostępność stolików, preferencje użytkownika

3. **Działa (Act)**
   - Podejmuje akcje aby osiągnąć cel
   - Przykład: Dzwoni do restauracji, potwierdza rezerwację

4. **Uczy się (Learn)** - opcjonalne
   - Poprawia się na podstawie doświadczeń
   - Przykład: Zapamiętuje ulubione restauracje

**Kontrast: LLM vs Agent**

```python
# ❌ To NIE jest Agent - to tylko LLM
def answer_question(question: str) -> str:
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}]
    ).choices[0].message.content

# ✅ To JEST Agent - ma goal, perceive, act
class RestaurantAgent:
    def __init__(self, goal: str):
        self.goal = goal  # "Book a table"
        self.tools = [check_availability, make_reservation, send_confirmation]

    def perceive(self):
        """Zbiera informacje o środowisku."""
        user_prefs = get_user_preferences()
        availability = check_restaurant_availability()
        return {"prefs": user_prefs, "availability": availability}

    def act(self, perception: dict):
        """Podejmuje akcje aby osiągnąć goal."""
        best_option = self.reason_about_best_option(perception)
        result = make_reservation(best_option)
        send_confirmation(result)
        return result

    def run(self):
        """Main loop: perceive → reason → act."""
        while not self.goal_achieved():
            perception = self.perceive()
            self.act(perception)
```

### 7.2 Typy Agentów

**1. Simple Reflex Agent (Reactive)**
- Działa na podstawie bieżącej percepcji
- Proste reguły: "IF condition THEN action"
- Brak pamięci stanu

```python
class ReflexAgent:
    """Simple reflex agent - reakcja na bieżącą percepcję."""

    def act(self, perception: dict) -> str:
        """Direct stimulus → response."""
        if perception['temperature'] > 25:
            return "turn_on_AC"
        elif perception['temperature'] < 18:
            return "turn_on_heating"
        else:
            return "do_nothing"
```

**2. Model-Based Agent**
- Utrzymuje internal model świata
- Trackuje state
- Lepsze decision making

```python
class ModelBasedAgent:
    """Model-based agent - maintains world model."""

    def __init__(self):
        self.world_model = {
            'AC_on': False,
            'heating_on': False,
            'current_temp': None
        }

    def update_model(self, perception: dict):
        """Update internal world model."""
        self.world_model['current_temp'] = perception['temperature']

    def act(self, perception: dict) -> str:
        """Act based on model."""
        self.update_model(perception)

        temp = self.world_model['current_temp']

        if temp > 25 and not self.world_model['AC_on']:
            self.world_model['AC_on'] = True
            return "turn_on_AC"
        elif temp < 18 and not self.world_model['heating_on']:
            self.world_model['heating_on'] = True
            return "turn_on_heating"
        else:
            return "maintain_current_state"
```

**3. Goal-Based Agent**
- Ma explicit goal
- Planuje sekwencję akcji do osiągnięcia celu
- Może ocenić różne strategie

```python
class GoalBasedAgent:
    """Goal-based agent - plans to achieve goal."""

    def __init__(self, goal: str):
        self.goal = goal  # e.g., "maintain_temp_20"

    def plan(self, current_state: dict, goal: str) -> List[str]:
        """Plan sequence of actions to achieve goal."""
        actions = []

        current_temp = current_state['temperature']
        target_temp = 20

        if current_temp > target_temp + 2:
            actions.append("turn_on_AC")
            actions.append("wait_5_minutes")
            actions.append("check_temperature")
        elif current_temp < target_temp - 2:
            actions.append("turn_on_heating")
            actions.append("wait_5_minutes")
            actions.append("check_temperature")

        return actions

    def execute_plan(self, actions: List[str]):
        """Execute planned actions."""
        for action in actions:
            self.perform_action(action)
            if self.goal_achieved():
                break
```

**4. Utility-Based Agent**
- Ocenia "happiness" różnych stanów
- Wybiera akcje maksymalizujące utility
- Trade-offs między celami

```python
class UtilityBasedAgent:
    """Utility-based agent - maximizes utility function."""

    def utility(self, state: dict) -> float:
        """Calculate utility of a state."""
        score = 0

        # Prefer temperature near 20°C
        temp_diff = abs(state['temperature'] - 20)
        score += max(0, 10 - temp_diff)

        # Penalize energy usage
        if state['AC_on']:
            score -= 2
        if state['heating_on']:
            score -= 3

        # Bonus for user comfort
        if 19 <= state['temperature'] <= 21:
            score += 5

        return score

    def choose_action(self, perception: dict) -> str:
        """Choose action that maximizes expected utility."""
        possible_actions = ['turn_on_AC', 'turn_on_heating', 'do_nothing']

        best_action = None
        best_utility = float('-inf')

        for action in possible_actions:
            # Simulate outcome
            predicted_state = self.predict_outcome(perception, action)
            utility = self.utility(predicted_state)

            if utility > best_utility:
                best_utility = utility
                best_action = action

        return best_action
```

**5. Learning Agent**
- Uczy się z doświadczeń
- Poprawia performance w czasie
- Adaptuje do zmieniającego się środowiska

```python
class LearningAgent:
    """Learning agent - improves from experience."""

    def __init__(self):
        self.experience = []  # History of (state, action, reward)
        self.policy = {}  # Learned policy

    def act(self, state: dict) -> str:
        """Act according to learned policy."""
        state_key = self.state_to_key(state)

        if state_key in self.policy:
            return self.policy[state_key]
        else:
            return self.explore(state)  # Try new action

    def learn(self, state: dict, action: str, reward: float):
        """Learn from experience."""
        self.experience.append((state, action, reward))

        # Simple learning: remember best action for each state
        state_key = self.state_to_key(state)

        if state_key not in self.policy or reward > self.get_best_reward(state_key):
            self.policy[state_key] = action

    def get_best_reward(self, state_key: str) -> float:
        """Get best reward seen for this state."""
        relevant = [r for s, a, r in self.experience if self.state_to_key(s) == state_key]
        return max(relevant) if relevant else float('-inf')
```

### 7.3 ReAct Pattern (Reasoning + Acting)

**💡 Najważniejszy pattern dla LLM-based agents**

**ReAct = Reason (Think) + Act + Observe → Loop**

**Schema:**
```
1. Thought: Pomyśl o sytuacji i co trzeba zrobić
2. Action: Wykonaj akcję (call tool, API, etc.)
3. Observation: Zobacz wynik akcji
4. [Repeat until goal achieved]
5. Final Answer: Zwróć wynik
```

**Podstawowa implementacja:**

```python
from enum import Enum
from typing import List, Optional

class ActionType(str, Enum):
    SEARCH = "search"
    CALCULATE = "calculate"
    FINISH = "finish"

class Step(BaseModel):
    thought: str = Field(description="Your reasoning about what to do next")
    action: ActionType = Field(description="The action to take")
    action_input: str = Field(description="Input for the action")

class ReActResponse(BaseModel):
    steps: List[Step]
    final_answer: Optional[str] = None

def react_agent(query: str, max_steps: int = 10) -> str:
    """ReAct agent implementation."""

    system_prompt = """
You are a helpful assistant that uses the ReAct (Reasoning + Acting) pattern.

Available actions:
- search(query): Search for information
- calculate(expression): Calculate mathematical expression
- finish(answer): Return final answer

For each step, provide:
1. thought: Your reasoning
2. action: Which action to take
3. action_input: Input for that action

Continue until you can finish with the answer.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {query}"}
    ]

    for step_num in range(max_steps):
        # Get next step from LLM
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_model=Step
        )

        step = response

        print(f"\nStep {step_num + 1}:")
        print(f"Thought: {step.thought}")
        print(f"Action: {step.action}({step.action_input})")

        # Execute action
        if step.action == ActionType.FINISH:
            return step.action_input

        observation = execute_action(step.action, step.action_input)

        print(f"Observation: {observation}")

        # Add to message history
        messages.append({
            "role": "assistant",
            "content": f"Thought: {step.thought}\nAction: {step.action}({step.action_input})"
        })
        messages.append({
            "role": "user",
            "content": f"Observation: {observation}"
        })

    return "Max steps reached without answer"

def execute_action(action: ActionType, action_input: str) -> str:
    """Execute the chosen action."""
    if action == ActionType.SEARCH:
        # Simplified search
        return f"Search results for '{action_input}': [dummy results]"

    elif action == ActionType.CALCULATE:
        try:
            result = eval(action_input)  # ⚠️ Unsafe - use safe math parser in production
            return f"Result: {result}"
        except Exception as e:
            return f"Error: {e}"

    return "Unknown action"

# Usage
answer = react_agent("What is 15% of 240 plus 50?")

# Output example:
# Step 1:
# Thought: I need to calculate 15% of 240 first
# Action: calculate(240 * 0.15)
# Observation: Result: 36.0
#
# Step 2:
# Thought: Now I need to add 50 to that result
# Action: calculate(36 + 50)
# Observation: Result: 86
#
# Step 3:
# Thought: I have the final answer
# Action: finish(86)
# Final answer: 86
```

**Advanced ReAct with Tools:**

```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict

class ReActAgentWithTools:
    """Production-ready ReAct agent."""

    def __init__(self, tools: List[ToolDefinition]):
        self.tools = tools
        self.tool_functions = self._register_tools()

    def _register_tools(self) -> dict:
        """Register tool functions."""
        return {
            "search_web": self.search_web,
            "calculate": self.calculate,
            "get_weather": self.get_weather,
            "send_email": self.send_email
        }

    def search_web(self, query: str) -> str:
        """Search the web."""
        # In production: actual search API
        return f"Search results for: {query}"

    def calculate(self, expression: str) -> float:
        """Safely calculate expression."""
        # Use safe math parser
        import ast
        import operator

        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow
        }

        # Parse and evaluate safely
        # (Simplified - full implementation needed)
        return eval(expression)

    def get_weather(self, city: str) -> dict:
        """Get weather for city."""
        # In production: weather API
        return {"city": city, "temp": 22, "condition": "sunny"}

    def send_email(self, to: str, subject: str, body: str) -> str:
        """Send email."""
        # In production: email API
        return f"Email sent to {to}"

    def execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool."""
        if tool_name not in self.tool_functions:
            return f"Error: Unknown tool '{tool_name}'"

        try:
            func = self.tool_functions[tool_name]
            result = func(**tool_input)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def run(self, task: str, max_iterations: int = 10) -> str:
        """Run ReAct loop."""

        system_prompt = f"""
You are a helpful AI agent using the ReAct pattern.

Available tools:
{json.dumps([t.dict() for t in self.tools], indent=2)}

For each step:
1. Think about what to do (thought)
2. Choose an action/tool (action)
3. Provide inputs (action_input)

Continue until you have the final answer, then use action="finish".
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}"}
        ]

        for i in range(max_iterations):
            # Get next step
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )

            content = response.choices[0].message.content

            # Parse step (simplified - use structured output in production)
            # ... parsing logic ...

            # Execute if not finish
            # ... execution logic ...

        return "Task completed or max iterations reached"
```

---

## Podsumowanie Części III

W tej części nauczyłeś się:

✅ **Paradygmat Software 3.0**: Pre-trained models + prompting zamiast trenowania od zera
✅ **Kiedy LLM vs klasyczny ML**: Trade-offs i hybrid approach
✅ **Spektrum autonomii (L1-L7)**: Od stateless do full autonomy
✅ **Red Line at L4**: Przejście do stateful systems i związane ryzyka
✅ **AI Agents**: Definicja, typy (reflex, model-based, goal-based, utility, learning)
✅ **ReAct Pattern**: Reasoning + Acting loop - fundamentalny pattern dla agentów

**Kluczowe zasady:**
1. **Start simple** - L1/L2 jeśli wystarczy
2. **Czerwona linia L4** - stateful systems wymagają szczególnej uwagi
3. **ReAct dla agentów** - thought → action → observation loop
4. **Hybrid approach** - łącz LLM z klasycznym ML gdzie sensowne
5. **Wybierz właściwy typ agenta** - zależy od zadania

**Następne kroki:**
W Części IV zagłębimy się w Memory Engineering - 7-warstwową architekturę pamięci, biomimetykę, memory trilemma i jak budować truly stateful agents!
# CZĘŚĆ IV: MEMORY ENGINEERING

## 8. Architektura Pamięci

### 💡 Kluczowa Idea
**Memory Engineering = Biomimetyka + 7-warstwowa architektura + Trade-offs (Trilemma)**

### 8.1 Biomimetyka - Uczenie się od Natury

**Biomimetyka** to nauka o stosowaniu rozwiązań wypracowanych przez naturę w technologii.

**Neurobiologiczne systemy pamięci:**

Ludzki mózg nie ma "jednej pamięci" - ma wiele wyspecjalizowanych systemów:

1. **Pamięć robocza (Working Memory)** - krótkoterminowa, ograniczona (7±2 elementy)
2. **Pamięć epizodyczna (Episodic Memory)** - wydarzenia, "co, gdzie, kiedy"
3. **Pamięć semantyczna (Semantic Memory)** - fakty, wiedza ogólna
4. **Pamięć proceduralna (Procedural Memory)** - umiejętności, "jak coś zrobić"

**Przypadki neurologiczne - lekcje dla AI:**

**1. H.M. (Henry Molaison)**
- Utracił zdolność tworzenia nowych wspomnień (amnezja anterogradna)
- Zachował starsze wspomnienia i umiejętności
- **Lekcja**: Różne typy pamięci są niezależne - można stracić jeden typ zachowując inne

**2. Phineas Gage**
- Uszkodzenie kory czołowej zmieniło osobowość
- Zachował pamięć i umiejętności
- **Lekcja**: "Konstytucja" osobowości (wartości, zasady) to odrębny system

**3. Clive Wearing**
- Tylko 7-30 sekund pamięci roboczej
- Zachował umiejętności muzyczne (pamięć proceduralna)
- **Lekcja**: Różne warstwy pamięci mogą funkcjonować niezależnie

**Zastosowanie w AI:**
Projektujemy memory architecture inspirowaną neurobiologią - wiele wyspecjalizowanych warstw zamiast jednej "pamięci".

### 8.2 7-Layer Memory Architecture

**Pełna architektura pamięci dla AI Agents:**

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: CONSTITUTIONAL MEMORY                      │
│ (Core values, principles, constraints)              │
│ - Immutable                                         │
│ - Defines "who the agent is"                        │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 2: WORKING MEMORY                             │
│ (Current conversation, immediate context)           │
│ - Buffer, limited capacity                          │
│ - Most recent 5-10 messages                         │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 3: WORKFLOW MEMORY                            │
│ (Current task state, multi-step processes)         │
│ - State machine                                     │
│ - Tracks progress through workflows                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 4: EPISODIC MEMORY                            │
│ (Past conversations, interactions, events)          │
│ - "What happened when"                              │
│ - Searchable history                                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 5: SEMANTIC MEMORY                            │
│ (Facts, knowledge, learned information)             │
│ - "What is true"                                    │
│ - Knowledge base                                    │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 6: PROCEDURAL MEMORY                          │
│ (How to do things, skills, procedures)              │
│ - "How to X"                                        │
│ - Reusable workflows                                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ Layer 7: RESOURCE MEMORY                            │
│ (External tools, APIs, databases)                   │
│ - Access to external systems                        │
│ - Tool definitions and credentials                  │
└─────────────────────────────────────────────────────┘
```

### 8.3 Layer-by-Layer Implementation

**Layer 1: Constitutional Memory**

```python
from pydantic import BaseModel, Field
from typing import List

class ConstitutionalMemory(BaseModel):
    """Core values and principles - IMMUTABLE."""

    agent_role: str = Field(description="Who is this agent")
    core_values: List[str] = Field(description="Fundamental values")
    constraints: List[str] = Field(description="Hard constraints")
    mission: str = Field(description="Agent's mission")

# Example: Customer Service Agent
constitutional = ConstitutionalMemory(
    agent_role="Customer Service AI Assistant",
    core_values=[
        "Always be helpful and empathetic",
        "Protect customer privacy",
        "Be honest - never make false promises",
        "Escalate to human when uncertain"
    ],
    constraints=[
        "Never share customer data with third parties",
        "Cannot process refunds over $500 without approval",
        "Must verify identity for account changes",
        "Cannot provide medical or legal advice"
    ],
    mission="Help customers resolve issues efficiently while maintaining trust"
)

def build_constitutional_prompt(constitutional: ConstitutionalMemory) -> str:
    """Build system prompt from constitutional memory."""
    return f"""
You are: {constitutional.agent_role}

Core Values:
{chr(10).join(f"- {v}" for v in constitutional.core_values)}

Constraints (MUST follow):
{chr(10).join(f"- {c}" for c in constitutional.constraints)}

Mission: {constitutional.mission}
"""
```

**Layer 2: Working Memory**

```python
from collections import deque
from typing import Deque

class WorkingMemory:
    """Limited buffer for immediate context."""

    def __init__(self, max_size: int = 10):
        self.buffer: Deque[dict] = deque(maxlen=max_size)

    def add(self, message: dict):
        """Add message to working memory."""
        self.buffer.append(message)

    def get_context(self) -> List[dict]:
        """Get current context window."""
        return list(self.buffer)

    def clear(self):
        """Clear working memory (new conversation)."""
        self.buffer.clear()

# Usage
working_memory = WorkingMemory(max_size=10)

# Add messages
working_memory.add({"role": "user", "content": "Hello"})
working_memory.add({"role": "assistant", "content": "Hi! How can I help?"})

# Get for LLM
context = working_memory.get_context()
```

**Layer 3: Workflow Memory**

```python
from enum import Enum

class OrderState(str, Enum):
    """States for pizza ordering workflow."""
    INIT = "init"
    COLLECTING_SIZE = "collecting_size"
    COLLECTING_TOPPINGS = "collecting_toppings"
    COLLECTING_DELIVERY = "collecting_delivery"
    CONFIRMING = "confirming"
    COMPLETED = "completed"

class WorkflowMemory(BaseModel):
    """State machine for multi-step workflows."""
    current_state: OrderState = OrderState.INIT
    collected_data: dict = Field(default_factory=dict)
    next_steps: List[str] = Field(default_factory=list)

    def transition_to(self, new_state: OrderState):
        """Transition to new state."""
        self.current_state = new_state

    def update_data(self, key: str, value: any):
        """Update collected data."""
        self.collected_data[key] = value

    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return self.current_state == OrderState.COMPLETED

# Usage in agent
class PizzaOrderAgent:
    def __init__(self):
        self.workflow = WorkflowMemory()

    def process_message(self, user_input: str) -> str:
        """Process message based on current state."""

        if self.workflow.current_state == OrderState.INIT:
            self.workflow.transition_to(OrderState.COLLECTING_SIZE)
            return "What size pizza? Small, Medium, or Large?"

        elif self.workflow.current_state == OrderState.COLLECTING_SIZE:
            self.workflow.update_data("size", user_input)
            self.workflow.transition_to(OrderState.COLLECTING_TOPPINGS)
            return "Great! What toppings would you like?"

        elif self.workflow.current_state == OrderState.COLLECTING_TOPPINGS:
            self.workflow.update_data("toppings", user_input)
            self.workflow.transition_to(OrderState.COLLECTING_DELIVERY)
            return "Where should we deliver?"

        # ... more states ...

        elif self.workflow.current_state == OrderState.CONFIRMING:
            if "yes" in user_input.lower():
                self.workflow.transition_to(OrderState.COMPLETED)
                return "Order confirmed! It will arrive in 30 minutes."
            else:
                self.workflow.transition_to(OrderState.INIT)
                return "Let's start over. What size pizza?"

        return "Something went wrong"
```

**Layer 4: Episodic Memory**

```python
from datetime import datetime
from typing import Optional

class Episode(BaseModel):
    """Single episode/interaction."""
    timestamp: datetime
    conversation_id: str
    user_id: str
    summary: str
    key_events: List[str]
    outcome: Optional[str] = None
    sentiment: Optional[str] = None

class EpisodicMemory:
    """Memory of past interactions."""

    def __init__(self):
        self.episodes: List[Episode] = []

    def record_episode(self, episode: Episode):
        """Store new episode."""
        self.episodes.append(episode)

    def recall_similar(self, query: str, top_k: int = 3) -> List[Episode]:
        """Recall similar past episodes."""
        # In production: use embeddings for similarity
        # For now: simple keyword matching
        relevant = []
        query_lower = query.lower()

        for episode in self.episodes:
            if any(kw in episode.summary.lower() for kw in query_lower.split()):
                relevant.append(episode)

        # Sort by timestamp (most recent first)
        relevant.sort(key=lambda e: e.timestamp, reverse=True)
        return relevant[:top_k]

    def recall_by_user(self, user_id: str, limit: int = 10) -> List[Episode]:
        """Get user's interaction history."""
        user_episodes = [e for e in self.episodes if e.user_id == user_id]
        user_episodes.sort(key=lambda e: e.timestamp, reverse=True)
        return user_episodes[:limit]

# Usage
episodic = EpisodicMemory()

# Record interaction
episode = Episode(
    timestamp=datetime.now(),
    conversation_id="conv_123",
    user_id="john_456",
    summary="User ordered large pepperoni pizza, delivered to 123 Main St",
    key_events=[
        "Selected large size",
        "Chose pepperoni topping",
        "Provided delivery address",
        "Confirmed order"
    ],
    outcome="Order completed successfully",
    sentiment="positive"
)
episodic.record_episode(episode)

# Later: recall similar situations
similar = episodic.recall_similar("pizza order")
user_history = episodic.recall_by_user("john_456")
```

**Layer 5: Semantic Memory**

```python
class Fact(BaseModel):
    """Single fact/knowledge."""
    subject: str
    relation: str
    object: str
    confidence: float = Field(ge=0, le=1)
    source: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class SemanticMemory:
    """Knowledge base - facts about the world."""

    def __init__(self):
        self.facts: List[Fact] = []

    def learn_fact(self, fact: Fact):
        """Store new fact."""
        # Check if already exists
        existing = self.query_facts(fact.subject, fact.relation)

        if existing:
            # Update if higher confidence
            if fact.confidence > existing[0].confidence:
                self.facts.remove(existing[0])
                self.facts.append(fact)
        else:
            self.facts.append(fact)

    def query_facts(
        self,
        subject: Optional[str] = None,
        relation: Optional[str] = None,
        object: Optional[str] = None
    ) -> List[Fact]:
        """Query knowledge base."""
        results = self.facts

        if subject:
            results = [f for f in results if f.subject == subject]
        if relation:
            results = [f for f in results if f.relation == relation]
        if object:
            results = [f for f in results if f.object == object]

        # Sort by confidence
        results.sort(key=lambda f: f.confidence, reverse=True)
        return results

    def get_knowledge_about(self, subject: str) -> str:
        """Get all knowledge about a subject."""
        facts = self.query_facts(subject=subject)

        if not facts:
            return f"I don't know anything about {subject}"

        knowledge = f"What I know about {subject}:\n"
        for fact in facts:
            knowledge += f"- {fact.relation} {fact.object} (confidence: {fact.confidence:.2f})\n"

        return knowledge

# Usage
semantic = SemanticMemory()

# Learn facts
semantic.learn_fact(Fact(
    subject="John",
    relation="prefers",
    object="Italian food",
    confidence=0.9,
    source="conversation 2024-01-15"
))

semantic.learn_fact(Fact(
    subject="John",
    relation="allergic_to",
    object="peanuts",
    confidence=1.0,
    source="user profile"
))

semantic.learn_fact(Fact(
    subject="Luigi's Restaurant",
    relation="serves",
    object="Italian cuisine",
    confidence=1.0,
    source="restaurant database"
))

# Query
about_john = semantic.get_knowledge_about("John")
print(about_john)
# Output:
# What I know about John:
# - allergic_to peanuts (confidence: 1.00)
# - prefers Italian food (confidence: 0.90)
```

**Layer 6: Procedural Memory**

```python
class Procedure(BaseModel):
    """Reusable procedure/workflow."""
    name: str
    description: str
    steps: List[str]
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)

class ProceduralMemory:
    """How-to knowledge - procedures and workflows."""

    def __init__(self):
        self.procedures: dict[str, Procedure] = {}

    def learn_procedure(self, procedure: Procedure):
        """Store new procedure."""
        self.procedures[procedure.name] = procedure

    def recall_procedure(self, name: str) -> Optional[Procedure]:
        """Get procedure by name."""
        return self.procedures.get(name)

    def find_procedures_for(self, goal: str) -> List[Procedure]:
        """Find procedures that might help achieve goal."""
        relevant = []
        goal_lower = goal.lower()

        for proc in self.procedures.values():
            if goal_lower in proc.description.lower():
                relevant.append(proc)

        return relevant

# Usage
procedural = ProceduralMemory()

# Learn procedures
procedural.learn_procedure(Procedure(
    name="order_pizza",
    description="How to order a pizza for the user",
    steps=[
        "Ask for pizza size",
        "Ask for toppings",
        "Ask for delivery address",
        "Confirm order details",
        "Place order via API",
        "Provide order confirmation and ETA"
    ],
    preconditions=["User wants to order pizza"],
    postconditions=["Pizza order placed", "User notified of ETA"]
))

procedural.learn_procedure(Procedure(
    name="handle_complaint",
    description="How to handle customer complaints",
    steps=[
        "Listen empathetically to the complaint",
        "Apologize for the inconvenience",
        "Gather details (order number, issue description)",
        "Check order history",
        "Offer solution (refund, replacement, discount)",
        "Get customer approval",
        "Process solution",
        "Follow up to ensure satisfaction"
    ],
    preconditions=["Customer has a complaint"],
    postconditions=["Issue resolved", "Customer satisfied"]
))

# Use procedure
complaint_procedures = procedural.find_procedures_for("customer is unhappy")
if complaint_procedures:
    proc = complaint_procedures[0]
    print(f"Following procedure: {proc.name}")
    for i, step in enumerate(proc.steps, 1):
        print(f"{i}. {step}")
```

**Layer 7: Resource Memory**

```python
class Tool(BaseModel):
    """External tool/API definition."""
    name: str
    description: str
    api_endpoint: Optional[str] = None
    parameters: dict
    requires_auth: bool = False
    rate_limit: Optional[int] = None

class ResourceMemory:
    """Access to external tools and resources."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.credentials: dict[str, str] = {}

    def register_tool(self, tool: Tool):
        """Register new tool."""
        self.tools[tool.name] = tool

    def set_credentials(self, tool_name: str, credentials: str):
        """Set credentials for tool."""
        self.credentials[tool_name] = credentials

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool definition."""
        return self.tools.get(name)

    def list_available_tools(self) -> List[str]:
        """List all available tools."""
        return list(self.tools.keys())

# Usage
resource = ResourceMemory()

# Register tools
resource.register_tool(Tool(
    name="weather_api",
    description="Get current weather for any city",
    api_endpoint="https://api.weather.com/v1/current",
    parameters={"city": "string", "units": "metric|imperial"},
    requires_auth=True,
    rate_limit=100  # calls per hour
))

resource.register_tool(Tool(
    name="restaurant_search",
    description="Search for restaurants by cuisine and location",
    api_endpoint="https://api.restaurants.com/search",
    parameters={"cuisine": "string", "location": "string", "radius": "integer"},
    requires_auth=True
))

resource.set_credentials("weather_api", "api_key_12345")
resource.set_credentials("restaurant_search", "api_key_67890")

# Agent can query available tools
tools = resource.list_available_tools()
print(f"Available tools: {tools}")
```

### 8.4 Integrated Memory System

**Complete agent with all 7 layers:**

```python
from jinja2 import Template

class IntegratedMemoryAgent:
    """Agent with full 7-layer memory architecture."""

    def __init__(self, user_id: str):
        self.user_id = user_id

        # Layer 1: Constitutional
        self.constitutional = ConstitutionalMemory(
            agent_role="Personal AI Assistant",
            core_values=["Be helpful", "Protect privacy", "Be honest"],
            constraints=["Never share user data", "Escalate when uncertain"],
            mission="Help user achieve their goals efficiently"
        )

        # Layer 2: Working Memory
        self.working = WorkingMemory(max_size=10)

        # Layer 3: Workflow Memory
        self.workflow = WorkflowMemory()

        # Layer 4: Episodic Memory
        self.episodic = EpisodicMemory()
        self._load_episodes()

        # Layer 5: Semantic Memory
        self.semantic = SemanticMemory()
        self._load_facts()

        # Layer 6: Procedural Memory
        self.procedural = ProceduralMemory()
        self._load_procedures()

        # Layer 7: Resource Memory
        self.resource = ResourceMemory()
        self._register_tools()

        self.client = OpenAI()

    def _build_context(self) -> str:
        """Build complete context from all memory layers."""

        template_str = """
{{ constitutional_prompt }}

<relevant_knowledge>
{{ semantic_context }}
</relevant_knowledge>

<past_interactions>
{{ episodic_context }}
</past_interactions>

<available_procedures>
{{ procedural_context }}
</available_procedures>

<available_tools>
{{ resource_context }}
</available_tools>

<current_conversation>
{{ working_memory }}
</current_conversation>

{% if workflow_active %}
<current_workflow>
State: {{ workflow_state }}
Collected: {{ workflow_data }}
</current_workflow>
{% endif %}
"""

        template = Template(template_str)

        # Gather context from each layer
        context = template.render(
            constitutional_prompt=build_constitutional_prompt(self.constitutional),
            semantic_context=self._get_semantic_context(),
            episodic_context=self._get_episodic_context(),
            procedural_context=self._get_procedural_context(),
            resource_context=self._get_resource_context(),
            working_memory=self._format_working_memory(),
            workflow_active=self.workflow.current_state != OrderState.INIT,
            workflow_state=self.workflow.current_state,
            workflow_data=self.workflow.collected_data
        )

        return context

    def _get_semantic_context(self) -> str:
        """Get relevant facts from semantic memory."""
        facts = self.semantic.query_facts(subject=self.user_id)
        if not facts:
            return "No prior knowledge about user"

        return "\n".join([
            f"- User {f.relation} {f.object}"
            for f in facts[:5]  # Top 5 most confident facts
        ])

    def _get_episodic_context(self) -> str:
        """Get relevant past interactions."""
        episodes = self.episodic.recall_by_user(self.user_id, limit=3)
        if not episodes:
            return "No prior interactions"

        return "\n".join([
            f"- {e.timestamp.date()}: {e.summary}"
            for e in episodes
        ])

    def _get_procedural_context(self) -> str:
        """List available procedures."""
        return "\n".join([
            f"- {name}: {proc.description}"
            for name, proc in self.procedural.procedures.items()
        ])

    def _get_resource_context(self) -> str:
        """List available tools."""
        return "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in self.resource.tools.items()
        ])

    def _format_working_memory(self) -> str:
        """Format recent conversation."""
        messages = self.working.get_context()
        return "\n".join([
            f"{m['role']}: {m['content']}"
            for m in messages
        ])

    def chat(self, user_message: str) -> str:
        """Process user message with full memory context."""

        # Add to working memory
        self.working.add({"role": "user", "content": user_message})

        # Build complete context
        context = self._build_context()

        # Generate response
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": user_message}
            ]
        )

        answer = response.choices[0].message.content

        # Add to working memory
        self.working.add({"role": "assistant", "content": answer})

        # Extract and store new memories
        self._extract_memories(user_message, answer)

        return answer

    def _extract_memories(self, user_msg: str, assistant_msg: str):
        """Extract what to remember from this interaction."""

        # Use LLM to identify new facts/knowledge
        extraction_prompt = f"""
From this conversation, extract:
1. New facts about the user
2. User preferences
3. Important events

User: {user_msg}
Assistant: {assistant_msg}

Return structured data.
"""

        # Extract and store in appropriate layers
        # (Implementation details omitted for brevity)
        pass

    def _load_episodes(self):
        """Load user's episode history from database."""
        # In production: load from persistent storage
        pass

    def _load_facts(self):
        """Load user's facts from database."""
        # In production: load from persistent storage
        pass

    def _load_procedures(self):
        """Load available procedures."""
        # Register standard procedures
        pass

    def _register_tools(self):
        """Register available tools."""
        # Register standard tools
        pass
```

### 8.5 Memory Trilemma

**💡 Nie można optymalizować wszystkiego jednocześnie**

**Memory Trilemma = Pick 2 out of 3:**

```
      Cost
       /\
      /  \
     /    \
    /      \
   /________\
Latency   Recall
```

**Trade-offs:**

1. **Low Cost + Low Latency** → Limited Recall
   - Store minimum w pamięci
   - Szybkie queries, tanie storage
   - Ale tracisz kontekst i personalizację

2. **Low Cost + High Recall** → High Latency
   - Wszystko w cheap storage (disk, S3)
   - Pełna historia dostępna
   - Ale wolne retrieval

3. **Low Latency + High Recall** → High Cost
   - Wszystko w fast memory (RAM, cache)
   - Instant access do pełnej historii
   - Ale bardzo drogie

**Przykład strategii:**

```python
class TieredMemoryStrategy:
    """Implements tiered memory to balance trilemma."""

    def __init__(self):
        # Hot tier: Fast, expensive, limited
        self.hot_cache = {}  # Last 10 conversations
        self.hot_capacity = 10

        # Warm tier: Medium speed, medium cost
        self.warm_db = {}  # Last 100 conversations

        # Cold tier: Slow, cheap, unlimited
        self.cold_storage = {}  # All history

    def store_conversation(self, conv_id: str, data: dict):
        """Store with tiering."""

        # Always to cold (cheap archive)
        self.cold_storage[conv_id] = data

        # To warm if recent
        if self._is_recent(data):
            self.warm_db[conv_id] = data

        # To hot if active
        if self._is_active(data):
            if len(self.hot_cache) >= self.hot_capacity:
                self._evict_from_hot()
            self.hot_cache[conv_id] = data

    def retrieve_conversation(self, conv_id: str) -> dict:
        """Retrieve with automatic promotion."""

        # Try hot first (fastest)
        if conv_id in self.hot_cache:
            return self.hot_cache[conv_id]

        # Try warm (medium speed)
        if conv_id in self.warm_db:
            data = self.warm_db[conv_id]
            # Promote to hot (accessed recently)
            self._promote_to_hot(conv_id, data)
            return data

        # Fall back to cold (slowest)
        if conv_id in self.cold_storage:
            data = self.cold_storage[conv_id]
            # Don't promote - rare access
            return data

        return None
```

**Production Memory Strategies:**

```python
# Strategy 1: Session-based (L2)
# - Cost: Low (no persistence)
# - Latency: Very low (in-memory)
# - Recall: Low (only current session)
# Use for: Simple chatbots, FAQs

# Strategy 2: User-scoped (L4)
# - Cost: Medium (DB per user)
# - Latency: Medium (DB queries)
# - Recall: Medium (user history)
# Use for: Personal assistants, customer service

# Strategy 3: Semantic-indexed (Advanced)
# - Cost: High (embeddings + vector DB)
# - Latency: Low-Medium (optimized queries)
# - Recall: High (semantic search across all)
# Use for: RAG systems, knowledge workers

# Strategy 4: Hybrid Tiered
# - Cost: Medium (smart caching)
# - Latency: Low (hot cache)
# - Recall: High (cold archive)
# Use for: Production systems with scale
```

### 8.6 Stateless vs Stateful - Complete Examples

**Stateless Example - Taxi Dispatcher:**

```python
class TaxiDispatcher:
    """
    Stateless agent - każde wywołanie niezależne.
    Nie pamięta poprzednich rozmów.
    """

    def __init__(self):
        self.client = OpenAI()

    def dispatch(self, request: str) -> str:
        """Handle single dispatch request - no memory."""

        system_prompt = """
You are a taxi dispatcher.

Your ONLY job:
1. Get pickup location
2. Get destination
3. Dispatch taxi
4. Provide ETA

Each call is independent. Don't remember previous calls.
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request}
            ]
        )

        return response.choices[0].message.content

# Usage - each call is independent
dispatcher = TaxiDispatcher()

response1 = dispatcher.dispatch("I need a taxi from airport to downtown")
# Output: "Taxi dispatched. ETA: 15 minutes to airport pickup."

response2 = dispatcher.dispatch("Where is my taxi?")
# Output: "I don't have information about your previous request.
#          Please provide pickup location for a new taxi."
# ❌ Nie pamięta request1!
```

**Stateful Example - Restaurant Concierge:**

```python
class RestaurantConcierge:
    """
    Stateful agent - pamięta użytkownika i historię.
    Personalizuje na podstawie preferencji.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.client = OpenAI()

        # Memory layers
        self.preferences = self._load_user_preferences()
        self.history = self._load_interaction_history()
        self.current_context = []

    def _load_user_preferences(self) -> dict:
        """Load from database."""
        # In production: DB query
        return {
            "favorite_cuisine": "Italian",
            "dietary": ["vegetarian"],
            "preferred_area": "Downtown",
            "budget": "medium",
            "favorite_restaurant": "Luigi's Trattoria"
        }

    def _load_interaction_history(self) -> List[dict]:
        """Load past interactions."""
        # In production: DB query
        return [
            {
                "date": "2024-01-10",
                "restaurant": "Luigi's Trattoria",
                "rating": 5,
                "notes": "Loved the margherita pizza"
            },
            {
                "date": "2024-01-05",
                "restaurant": "Bella Vista",
                "rating": 4,
                "notes": "Good pasta, bit crowded"
            }
        ]

    def chat(self, user_message: str) -> str:
        """Chat with memory of user and history."""

        # Build rich context
        system_prompt = f"""
You are a personal AI Concierge for restaurant recommendations.

<user_profile>
User ID: {self.user_id}
Favorite Cuisine: {self.preferences['favorite_cuisine']}
Dietary Restrictions: {', '.join(self.preferences['dietary'])}
Preferred Area: {self.preferences['preferred_area']}
Budget Level: {self.preferences['budget']}
Favorite Restaurant: {self.preferences['favorite_restaurant']}
</user_profile>

<past_visits>
{self._format_history()}
</past_visits>

<guidelines>
1. Use knowledge of user's preferences
2. Reference their past experiences
3. Make personalized suggestions
4. Remember conversation context
</guidelines>
"""

        # Add to conversation context
        self.current_context.append({
            "role": "user",
            "content": user_message
        })

        # Generate response
        messages = [{"role": "system", "content": system_prompt}] + self.current_context

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        answer = response.choices[0].message.content

        # Remember in context
        self.current_context.append({
            "role": "assistant",
            "content": answer
        })

        return answer

    def _format_history(self) -> str:
        """Format interaction history."""
        return "\n".join([
            f"- {h['date']}: {h['restaurant']} (rated {h['rating']}/5) - {h['notes']}"
            for h in self.history
        ])

# Usage - Stateful, remembers everything
concierge = RestaurantConcierge(user_id="john_123")

response1 = concierge.chat("I want dinner tonight")
# Output: "Since you love Italian food, I'd recommend Luigi's Trattoria,
#          your favorite! You gave it 5 stars last time and loved the
#          margherita pizza. They have a new vegetarian tasting menu."
# ✅ Uses preferences and history!

response2 = concierge.chat("Actually, I want to try something new")
# Output: "How about Bella Vista? You visited before and enjoyed their
#          pasta. They're in your preferred Downtown area and have
#          excellent vegetarian options within your medium budget range."
# ✅ Remembers conversation AND previous message!

response3 = concierge.chat("What did I say I wanted?")
# Output: "You initially wanted dinner tonight, but then said you'd
#          like to try something new instead of your usual favorite."
# ✅ Perfect recall of conversation!
```

**Key Differences Summary:**

| Aspect | Taxi Dispatcher (Stateless) | Restaurant Concierge (Stateful) |
|--------|---------------------------|--------------------------------|
| Memory | None between calls | Full user profile + history |
| Personalization | None | Highly personalized |
| Conversation flow | Each call independent | Continuous conversation |
| Complexity | Simple | Complex |
| Cost | Low | Higher (storage + retrieval) |
| Use case | Transactional | Relationship-based |

### 8.7 Context Engineering with Jinja2

**💡 Dynamic context injection using templates**

**Basic Template:**

```python
from jinja2 import Template

template_str = """
You are {{ agent_role }}.

User Profile:
- Name: {{ user_name }}
- Preferences: {{ preferences }}

{% if memories %}
Past Interactions:
{% for memory in memories %}
- {{ memory.date }}: {{ memory.summary }}
{% endfor %}
{% endif %}

Current Task: {{ task }}
"""

template = Template(template_str)

# Render with data
context = template.render(
    agent_role="Personal Assistant",
    user_name="John",
    preferences="Italian food, vegetarian",
    memories=[
        {"date": "2024-01-10", "summary": "Ordered pizza from Luigi's"},
        {"date": "2024-01-05", "summary": "Made reservation at Bella Vista"}
    ],
    task="Find a restaurant for tonight"
)

print(context)
```

**Advanced Template with Conditionals:**

```python
advanced_template = """
<system>
You are: {{ agent.role }}
Mission: {{ agent.mission }}
</system>

<user_context>
{% if user.preferences %}
Preferences:
{% for key, value in user.preferences.items() %}
- {{ key }}: {{ value }}
{% endfor %}
{% endif %}

{% if user.constraints %}
Constraints:
{% for constraint in user.constraints %}
⚠️ {{ constraint }}
{% endfor %}
{% endif %}
</user_context>

{% if memories.episodic %}
<episodic_memory>
Recent interactions (last {{ memories.episodic|length }}):
{% for ep in memories.episodic %}
{{ loop.index }}. [{{ ep.timestamp }}] {{ ep.summary }}
   {% if ep.outcome %}→ Outcome: {{ ep.outcome }}{% endif %}
{% endfor %}
</episodic_memory>
{% endif %}

{% if memories.semantic %}
<semantic_memory>
Known facts:
{% for fact in memories.semantic %}
- {{ fact.subject }} {{ fact.relation }} {{ fact.object }}
  (confidence: {{ "%.0f"|format(fact.confidence * 100) }}%)
{% endfor %}
</semantic_memory>
{% endif %}

{% if workflows.active %}
<active_workflow>
Current workflow: {{ workflows.current.name }}
State: {{ workflows.current.state }}
Progress: {{ workflows.current.progress }}
Next steps:
{% for step in workflows.current.next_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}
</active_workflow>
{% endif %}

<task>
{{ current_task }}
</task>
"""

# Usage
from jinja2 import Template

tmpl = Template(advanced_template)

rich_context = tmpl.render(
    agent={
        "role": "Personal AI Concierge",
        "mission": "Help user find perfect dining experiences"
    },
    user={
        "preferences": {
            "cuisine": "Italian",
            "dietary": "vegetarian",
            "price_range": "medium"
        },
        "constraints": [
            "No peanuts (allergy)",
            "Must have parking"
        ]
    },
    memories={
        "episodic": [
            {
                "timestamp": "2024-01-10 19:30",
                "summary": "Dined at Luigi's Trattoria",
                "outcome": "Excellent experience, 5/5 rating"
            }
        ],
        "semantic": [
            Fact(subject="User", relation="favorite_dish", object="Margherita Pizza", confidence=0.95),
            Fact(subject="User", relation="prefers", object="quiet ambiance", confidence=0.8)
        ]
    },
    workflows={
        "active": True,
        "current": {
            "name": "Restaurant Selection",
            "state": "collecting_preferences",
            "progress": "2/5",
            "next_steps": [
                "Confirm preferred area",
                "Check availability",
                "Make reservation"
            ]
        }
    },
    current_task="Find Italian restaurant for tonight, 7pm, party of 2"
)
```

---

## Podsumowanie Części IV

W tej części nauczyłeś się:

✅ **Biomimetyka**: Uczenie się od neurobiologicznych systemów pamięci
✅ **7-Layer Architecture**: Constitutional → Working → Workflow → Episodic → Semantic → Procedural → Resource
✅ **Memory Trilemma**: Cost vs Latency vs Recall - nie można mieć wszystkiego
✅ **Stateless vs Stateful**: Kiedy którego użyć (Taxi vs Concierge)
✅ **Context Engineering**: Jinja2 templates dla dynamic context injection
✅ **Production strategies**: Tiered memory, caching, optimization

**Kluczowe zasady:**
1. **Różne typy pamięci** - jeden system to za mało
2. **Memory ≠ storage** - to o tym co zapamiętać i jak użyć
3. **Trilemma is real** - musisz wybrać trade-offs
4. **Stateful = RED LINE** - używaj tylko gdy konieczne
5. **Context engineering** - jak dostarczasz pamięć do LLM ma znaczenie

**Fundamentalna truth:**
> "The quality of an AI agent's decisions is directly proportional to the quality of its memory architecture."

**Przykłady zastosowań:**

| Use Case | Layers Used | Memory Strategy |
|----------|-------------|-----------------|
| FAQ Chatbot | L1, L2 | Stateless, session-only |
| Customer Service | L1-L4 | User-scoped, episodic |
| Personal Assistant | L1-L5 | Full memory, semantic |
| Workflow Automation | L1-L3, L6 | Procedural, state machine |
| Research Agent | L1-L5, L7 | Semantic + tools |
| Enterprise AI | All 7 | Hybrid tiered |

**Co dalej?**
Masz teraz kompletny fundament - od podstaw LLM przez RAG i Agents aż do zaawansowanej Memory Engineering. W realnych projektach będziesz łączyć te wszystkie elementy razem!
