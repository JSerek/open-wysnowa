# LLM & AGENTIC AI - BEST PRACTICES & PRODUCTION PATTERNS

## Praktyczny przewodnik do budowania rozwiązań opartych o LLM i AI Agents

**Cel dokumentu:** Reference guide i code templates do użycia przy implementacji systemów z LLM/Agents.
**Użycie:** Wrzuć jako context do Claude Code / AI assistant przy budowaniu rozwiązań.

---

## SPIS TREŚCI

1. [Core Setup & Libraries](#1-core-setup--libraries)
2. [Structured Outputs - Best Practices](#2-structured-outputs---best-practices)
3. [RAG Architecture Patterns](#3-rag-architecture-patterns)
4. [Agent Design Patterns](#4-agent-design-patterns)
5. [Memory Architecture](#5-memory-architecture)
6. [Production Checklist](#6-production-checklist)
7. [Decision Trees](#7-decision-trees)
8. [Anti-Patterns to Avoid](#8-anti-patterns-to-avoid)

---

## 1. CORE SETUP & LIBRARIES

### Essential Stack

```python
# Core
from openai import OpenAI
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

# Structured Outputs
import instructor

# Templates & Context
from jinja2 import Template

# Optional but useful
import json
from tenacity import retry, stop_after_attempt, wait_exponential
```

### Client Setup Pattern

```python
# Basic setup
client = OpenAI()  # Uses OPENAI_API_KEY env var

# With Instructor (RECOMMENDED for structured outputs)
client = instructor.patch(client, mode=instructor.Mode.MD_JSON)
```

---

## 2. STRUCTURED OUTPUTS - BEST PRACTICES

### ✅ ALWAYS Use Pydantic for LLM Outputs

```python
# TEMPLATE: Basic Model
class OutputModel(BaseModel):
    """Always document what this model represents."""
    field_name: str = Field(description="Clear description for LLM")
    confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
    reasoning: str = Field(description="LLM's reasoning process")

# TEMPLATE: Nested Model
class SubModel(BaseModel):
    name: str
    value: float

class MainModel(BaseModel):
    items: List[SubModel]
    summary: str
    metadata: Dict[str, Any]
```

### Field Validation Patterns

```python
# Common validators
class ValidatedModel(BaseModel):
    email: str = Field(pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    age: int = Field(ge=0, le=150)
    score: float = Field(gt=0, le=100)
    name: str = Field(min_length=1, max_length=100)
    tags: List[str] = Field(min_items=1, max_items=10)

    @validator('name')
    def name_must_not_be_blank(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be blank')
        return v.title()
```

### API Call Pattern with Instructor

```python
# PRODUCTION PATTERN
def call_llm_structured(
    prompt: str,
    response_model: type[BaseModel],
    system_prompt: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7
) -> BaseModel:
    """Standard pattern for structured LLM calls."""

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return client.chat.completions.create(
        model=model,
        messages=messages,
        response_model=response_model,
        temperature=temperature
    )
```

### Error Handling Pattern

```python
from pydantic import ValidationError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def safe_llm_call(prompt: str, model_class: type[BaseModel]):
    """With automatic retry on validation errors."""
    try:
        return call_llm_structured(prompt, model_class)
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise
    except Exception as e:
        print(f"API error: {e}")
        raise
```

---

## 3. RAG ARCHITECTURE PATTERNS

### ❌ ANTI-PATTERN: Naive Chunking

```python
# NEVER DO THIS
def bad_chunking(text: str, chunk_size: int = 500):
    """This destroys semantic structure - especially tables!"""
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
```

### ✅ PROPER: Semantic Document Model

```python
class Document(BaseModel):
    """Semantic unit of knowledge - NOT arbitrary chunks."""
    id: str
    content: str  # Full semantic unit (table, section, etc.)
    metadata: Dict[str, Any]  # source, section, date, etc.
    embedding: Optional[List[float]] = None
    doc_type: str  # "table", "section", "paragraph"
```

### Context Formatting Patterns

```python
# PATTERN 1: XML Tags (RECOMMENDED)
def format_context_xml(documents: List[Document]) -> str:
    """Best for structured data."""
    context = "<context>\n"
    for doc in documents:
        context += f"""
<document id="{doc.id}">
<metadata>{doc.metadata}</metadata>
<content>
{doc.content}
</content>
</document>
"""
    context += "</context>"
    return context

# PATTERN 2: Markdown (for tables)
def format_as_markdown_table(data: List[dict], columns: List[str]) -> str:
    """LLM understands markdown tables well."""
    table = "| " + " | ".join(columns) + " |\n"
    table += "|" + "|".join(["---"] * len(columns)) + "|\n"
    for row in data:
        table += "| " + " | ".join(str(row.get(col, "")) for col in columns) + " |\n"
    return table
```

### Simple RAG System Template

```python
class SimpleRAG:
    """Minimal RAG implementation."""

    def __init__(self, documents: List[Document]):
        self.documents = documents
        self.client = OpenAI()

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate similarity."""
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def retrieve(self, query: str, top_k: int = 3) -> List[Document]:
        """Retrieve relevant documents."""
        query_emb = self._get_embedding(query)

        # Ensure all docs have embeddings
        for doc in self.documents:
            if doc.embedding is None:
                doc.embedding = self._get_embedding(doc.content)

        # Score and sort
        scored = [(doc, self._cosine_similarity(query_emb, doc.embedding))
                  for doc in self.documents]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in scored[:top_k]]

    def answer(self, query: str, response_model: type[BaseModel]) -> BaseModel:
        """RAG answer with structured output."""
        # Retrieve
        docs = self.retrieve(query, top_k=3)

        # Format context
        context = format_context_xml(docs)

        # Generate
        system_prompt = """Answer based ONLY on provided context.

<guidelines>
- Use only information from <context>
- If no relevant info: say "Information not found"
- Cite sources by document ID
</guidelines>"""

        prompt = f"{context}\n\nQuery: {query}"

        return call_llm_structured(prompt, response_model, system_prompt)
```

---

## 4. AGENT DESIGN PATTERNS

### Choose Agent Level (L1-L7)

```
L1: Stateless, no context → Use for: classification, extraction
L2: Stateless + context passed → Use for: chatbots with session
L3: Stateless + tools → Use for: search agents, API integrators
L4+: Stateful (RED LINE) → Use ONLY when must remember long-term
```

### ReAct Pattern (CORE AGENT PATTERN)

```python
class ActionType(str, Enum):
    SEARCH = "search"
    CALCULATE = "calculate"
    CALL_API = "call_api"
    FINISH = "finish"

class Step(BaseModel):
    thought: str = Field(description="Reasoning about what to do")
    action: ActionType = Field(description="Action to take")
    action_input: str = Field(description="Input for the action")

class ReActAgent:
    """ReAct pattern implementation."""

    def __init__(self, tools: Dict[str, callable]):
        self.tools = tools
        self.client = instructor.patch(OpenAI(), mode=instructor.Mode.MD_JSON)

    def run(self, task: str, max_steps: int = 10) -> str:
        """Execute task using ReAct loop."""

        system_prompt = f"""You use ReAct pattern: Thought → Action → Observation.

Available actions: {', '.join(self.tools.keys())}

For each step:
1. thought: Reason about what to do
2. action: Choose an action
3. action_input: Provide input

Use action="finish" when done."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}"}
        ]

        for step_num in range(max_steps):
            # Get next step
            step = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_model=Step
            )

            print(f"\nStep {step_num + 1}:")
            print(f"Thought: {step.thought}")
            print(f"Action: {step.action}({step.action_input})")

            # Execute
            if step.action == ActionType.FINISH:
                return step.action_input

            observation = self._execute_action(step.action, step.action_input)
            print(f"Observation: {observation}")

            # Add to history
            messages.append({
                "role": "assistant",
                "content": f"Thought: {step.thought}\nAction: {step.action}({step.action_input})"
            })
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}"
            })

        return "Max steps reached"

    def _execute_action(self, action: ActionType, action_input: str) -> str:
        """Execute tool."""
        if action.value in self.tools:
            return str(self.tools[action.value](action_input))
        return f"Unknown action: {action}"
```

### Tool Registration Pattern

```python
class Tool(BaseModel):
    """Tool definition for agents."""
    name: str
    description: str
    function: callable
    parameters: Dict[str, Any]

def register_tools() -> Dict[str, callable]:
    """Register available tools."""
    return {
        "search": lambda q: f"Search results for: {q}",
        "calculate": lambda expr: eval(expr),  # ⚠️ Use safe eval in production
        "get_weather": lambda city: {"temp": 22, "condition": "sunny"}
    }
```

---

## 5. MEMORY ARCHITECTURE

### Choose Memory Strategy

```
Stateless (L1-L3):
→ No persistence needed
→ Low cost, low latency
→ Limited recall
→ Use for: transactions, one-off tasks

Stateful (L4+):
→ Persistence required
→ Higher cost, medium latency
→ High recall
→ Use for: personal assistants, customer service
```

### 7-Layer Memory Implementation

```python
# Layer 1: Constitutional (Immutable)
class Constitutional(BaseModel):
    role: str
    values: List[str]
    constraints: List[str]
    mission: str

# Layer 2: Working (Buffer)
class WorkingMemory:
    def __init__(self, max_size: int = 10):
        from collections import deque
        self.buffer = deque(maxlen=max_size)

    def add(self, message: dict):
        self.buffer.append(message)

    def get_context(self) -> List[dict]:
        return list(self.buffer)

# Layer 4: Episodic (Past interactions)
class Episode(BaseModel):
    timestamp: datetime
    user_id: str
    summary: str
    outcome: Optional[str] = None

# Layer 5: Semantic (Facts)
class Fact(BaseModel):
    subject: str
    relation: str
    object: str
    confidence: float = Field(ge=0, le=1)
```

### Context Building with Jinja2

```python
from jinja2 import Template

CONTEXT_TEMPLATE = """
<system>
Role: {{ constitutional.role }}
Mission: {{ constitutional.mission }}

Values:
{% for value in constitutional.values %}
- {{ value }}
{% endfor %}
</system>

{% if semantic_memory %}
<knowledge>
{% for fact in semantic_memory %}
- {{ fact.subject }} {{ fact.relation }} {{ fact.object }}
{% endfor %}
</knowledge>
{% endif %}

{% if episodic_memory %}
<history>
{% for episode in episodic_memory %}
- {{ episode.timestamp }}: {{ episode.summary }}
{% endfor %}
</history>
{% endif %}

<current_task>
{{ task }}
</current_task>
"""

def build_context(
    constitutional: Constitutional,
    task: str,
    semantic_memory: List[Fact] = None,
    episodic_memory: List[Episode] = None
) -> str:
    """Build rich context from memory layers."""
    template = Template(CONTEXT_TEMPLATE)
    return template.render(
        constitutional=constitutional,
        task=task,
        semantic_memory=semantic_memory or [],
        episodic_memory=episodic_memory or []
    )
```

---

## 6. PRODUCTION CHECKLIST

### Before Deployment

#### API & Cost Management
- [ ] Rate limiting implemented
- [ ] Token counting for cost estimation
- [ ] Fallback for API errors
- [ ] Timeout handling
- [ ] Cost monitoring per user/session

#### Quality Control
- [ ] Output validation with Pydantic
- [ ] Retry logic for failed validations
- [ ] Logging for all LLM calls
- [ ] Confidence scores in outputs
- [ ] Human-in-the-loop for low confidence

#### Security & Privacy
- [ ] Input sanitization (prevent prompt injection)
- [ ] PII detection and masking
- [ ] User data isolation
- [ ] API key management (env vars, not hardcoded)
- [ ] Audit logs for sensitive operations

#### Performance
- [ ] Caching for repeated queries
- [ ] Streaming for long responses
- [ ] Parallel processing where possible
- [ ] Database indexing for memory queries
- [ ] Token optimization (shorter prompts)

#### Monitoring
- [ ] Success/failure metrics
- [ ] Latency tracking
- [ ] Cost per operation
- [ ] User satisfaction scores
- [ ] Error rate monitoring

---

## 7. DECISION TREES

### "Should I use LLM or Classical ML?"

```
Is the task text/language-based?
├─ YES → Is it generation, summarization, or reasoning?
│         ├─ YES → Use LLM
│         └─ NO → Is it classification/extraction?
│                  ├─ Have <1000 training examples? → Use LLM (few-shot)
│                  └─ Have >1000 examples? → Classical ML might be better
└─ NO → Is it structured/tabular prediction?
          └─ YES → Use Classical ML (XGBoost, etc.)
```

### "What autonomy level do I need?"

```
Does agent need to remember past interactions?
├─ NO → Can task be done in one call?
│        ├─ YES → L1 (Stateless)
│        └─ NO → Need conversation context?
│                 ├─ Just current session → L2 (Context passed)
│                 └─ Need external data → L3 (Tools)
└─ YES → Need long-term memory?
         └─ YES → L4+ (Stateful) ⚠️ RED LINE
                  - Implement safeguards
                  - Clear memory policies
                  - User data controls
```

### "How to structure my RAG?"

```
What's your data type?
├─ Tables/structured → Keep tables whole, use markdown format
├─ Documents/sections → Chunk by semantic units (sections)
├─ Conversations → Store by episode with metadata
└─ Mixed → Separate by type, different retrieval strategies

Retrieval strategy?
├─ Small corpus (<1000 docs) → Simple semantic search
├─ Medium (1k-100k) → Hybrid (semantic + keyword)
└─ Large (>100k) → Tiered strategy + metadata filtering
```

---

## 8. ANTI-PATTERNS TO AVOID

### ❌ Data & RAG Anti-Patterns

```python
# ❌ DON'T: Naive fixed-size chunking
chunks = [text[i:i+500] for i in range(0, len(text), 500)]
# ✅ DO: Semantic chunking by document structure

# ❌ DON'T: Break tables across chunks
chunk_anywhere(table_text)
# ✅ DO: Keep tables as single documents

# ❌ DON'T: Ignore metadata
Document(content=text)
# ✅ DO: Rich metadata
Document(content=text, metadata={"source": "...", "date": "...", "type": "..."})
```

### ❌ Prompt Anti-Patterns

```python
# ❌ DON'T: Vague prompts
"Tell me about cats"
# ✅ DO: Specific instructions
"Write 3 paragraphs about cat social behavior, citing research"

# ❌ DON'T: Mix role and task in user prompt
{"role": "user", "content": "You are an expert. Do X."}
# ✅ DO: Separate concerns
{"role": "system", "content": "You are an expert."}
{"role": "user", "content": "Do X."}

# ❌ DON'T: Expect math accuracy
"Calculate 15.7% of 892.34"
# ✅ DO: Use tools for calculations
Use calculate() tool, not LLM
```

### ❌ Architecture Anti-Patterns

```python
# ❌ DON'T: No validation
response = client.chat.completions.create(...)
result = response.choices[0].message.content
# ✅ DO: Always validate with Pydantic

# ❌ DON'T: Stateful when stateless works
Implement L4 for simple classification
# ✅ DO: Start with L1, add complexity only if needed

# ❌ DON'T: No error handling
call_llm(prompt)
# ✅ DO: Retry logic + error handling
@retry(...) + try/except
```

### ❌ Production Anti-Patterns

```python
# ❌ DON'T: Hardcoded API keys
client = OpenAI(api_key="sk-...")
# ✅ DO: Environment variables
client = OpenAI()  # Reads from OPENAI_API_KEY

# ❌ DON'T: No cost tracking
Just call API whenever
# ✅ DO: Monitor tokens and costs
Log every call, track per user

# ❌ DON'T: Block on long operations
result = long_llm_call()
# ✅ DO: Async or streaming
async def or streaming=True
```

---

## 9. QUICK REFERENCE - CODE SNIPPETS

### Minimal Working Examples

**1. Structured Extraction**
```python
class Data(BaseModel):
    field: str
    value: float

client = instructor.patch(OpenAI(), mode=instructor.Mode.MD_JSON)
result = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Extract: ..."}],
    response_model=Data
)
```

**2. Simple RAG**
```python
docs = retrieve_relevant(query, top_k=3)
context = format_context_xml(docs)
answer = call_llm_structured(
    f"{context}\n\nQuery: {query}",
    AnswerModel,
    system_prompt="Answer based only on context"
)
```

**3. ReAct Agent**
```python
agent = ReActAgent(tools={"search": search_fn, "finish": lambda x: x})
result = agent.run("Find and summarize X")
```

**4. Stateful Agent**
```python
class Agent:
    def __init__(self, user_id):
        self.user_id = user_id
        self.memory = load_memory(user_id)

    def chat(self, msg):
        context = build_context(self.memory, msg)
        response = call_llm(context)
        self.memory.add(msg, response)
        save_memory(self.user_id, self.memory)
        return response
```

---

## 10. PRODUCTION PATTERNS

### Cost Optimization

```python
# 1. Use cheaper models when possible
MODELS = {
    "cheap": "gpt-4o-mini",      # Fast, cheap
    "standard": "gpt-4o",         # Balanced
    "premium": "gpt-4-turbo"      # Best quality
}

def choose_model(task_complexity: str) -> str:
    """Choose model based on task."""
    if task_complexity == "simple":
        return MODELS["cheap"]
    elif task_complexity == "complex":
        return MODELS["premium"]
    return MODELS["standard"]

# 2. Cache responses
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_llm_call(prompt: str, model: str) -> str:
    """Cache identical prompts."""
    return call_llm(prompt, model)

# 3. Token counting
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens before calling API."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

### Streaming Pattern

```python
def stream_response(prompt: str):
    """Stream for long responses."""
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

### Async Pattern

```python
import asyncio
from openai import AsyncOpenAI

async def batch_process(prompts: List[str]):
    """Process multiple prompts concurrently."""
    client = AsyncOpenAI()

    async def process_one(prompt):
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    results = await asyncio.gather(*[process_one(p) for p in prompts])
    return results
```

---

## 11. FINAL CHECKLIST FOR NEW PROJECT

### Phase 1: Design
- [ ] Define clear use case (what problem solved?)
- [ ] Choose autonomy level (L1-L7)
- [ ] Identify required memory layers
- [ ] Design data models (Pydantic)
- [ ] Plan RAG architecture (if needed)
- [ ] Select models (cost vs quality trade-off)

### Phase 2: Implementation
- [ ] Set up Pydantic models for all outputs
- [ ] Implement with Instructor for validation
- [ ] Add proper error handling + retry
- [ ] Build context engineering (templates)
- [ ] Implement tools (if L3+)
- [ ] Add memory persistence (if L4+)

### Phase 3: Testing
- [ ] Unit tests for all components
- [ ] Integration tests for full flow
- [ ] Test edge cases (validation failures)
- [ ] Performance testing (latency, cost)
- [ ] Security testing (prompt injection)

### Phase 4: Production
- [ ] Implement monitoring and logging
- [ ] Set up cost tracking
- [ ] Configure rate limiting
- [ ] Add user feedback mechanism
- [ ] Document for team
- [ ] Create runbook for issues

---

## QUICK WINS

### Immediate Improvements to Existing Code

1. **Add Pydantic validation** - Single biggest quality improvement
2. **Use Instructor** - Simplifies structured outputs dramatically
3. **Implement retry logic** - Handles transient failures
4. **Add caching** - Reduces costs and latency
5. **Use templates (Jinja2)** - Makes prompts maintainable
6. **Separate system/user prompts** - Better role definition
7. **Add metadata to documents** - Improves RAG relevance
8. **Monitor token usage** - Control costs

---

## CONTACTS & RESOURCES

**Key Libraries:**
- OpenAI: `pip install openai`
- Pydantic: `pip install pydantic`
- Instructor: `pip install instructor`
- Jinja2: `pip install jinja2`

**This document last updated:** 2026-02-14

**Maintained by:** Jakub (serekkuba@gmail.com)

---

**Remember:**
1. Start simple (L1) and add complexity only when needed
2. Always validate outputs with Pydantic
3. Test with cheap models first, optimize later
4. Monitor costs from day one
5. Document your decisions

**Good luck building!** 🚀
