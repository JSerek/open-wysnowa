# EQD-AI Testing Plan — Dying Light: The Beast Steam Reviews

## Status Overview

| Component | Files | Status |
|-----------|-------|--------|
| Layer 0 — Preprocessing | `models.py`, `db.py`, `config.py`, `preprocessing.py`, `embeddings.py`, `grounding.py` | ✅ Coded |
| Layer 1 — IC Extraction | `prompts.py`, `coder_agent.py`, `codebook_comparator.py`, `hil.py`, `orchestrator.py` | ✅ Coded |
| Bridge — Codebook Sign-Off | `codebook_signoff.py` | ✅ Coded |
| Layer 2 — Theme Synthesis | `synthesizer_agent.py`, `theme_hil.py` | ✅ Coded |
| Layer 3 — Quality Metrics | `quality_metrics.py`, `quality_report.py` | ✅ Coded |
| Pipeline Orchestrator | `pipeline.py` | ✅ Coded |
| Data Loader | — | ❌ Needed |
| CLI Run Script | — | ❌ Needed |
| Unit Tests (Layer 0-1) | 10 test files | ✅ Written (not runnable in sandbox — needs `pytest`) |
| Unit Tests (Layer 2-3) | — | ❌ Not yet written |

---

## Pre-Requisites

Before any testing, you need a working Python environment with all dependencies.

### Step 0: Environment Setup

```bash
# 1. Create virtual environment
cd eqa_ai/
python3 -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API keys
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY and ANTHROPIC_API_KEY

# 4. Initialize database
python -m scripts.init_db

# 5. Verify basic setup
python -c "from src.config import load_config; c = load_config(); print(f'Config OK: {len(c.agents)} agents')"
python -c "from src.db import Database; db = Database(); db.init_schema(); print('DB OK')"
```

**Expected result:** Config loads, DB file `eqa_ai.db` created with 8 tables.

---

## Phase 1: Unit Tests (No API Calls)

These test deterministic logic only — no LLM or embedding API calls needed.

### Step 1.1: Run Existing Unit Tests

```bash
pytest tests/ -v --tb=short
```

**What's being tested:**
- `test_models.py` — Pydantic validation, hash computation, span verification
- `test_db.py` — CRUD for all 8 repository classes, foreign keys, WAL mode
- `test_config.py` — YAML loading, provider routing, missing key detection
- `test_preprocessing.py` — Normalization (NFKC, whitespace collapsing, zero-width removal, NO lowercasing), canonicalization, segmentation, batching
- `test_embeddings.py` — Cosine similarity (orthogonal, identical, zero vectors), vector length mismatch
- `test_grounding.py` — Quote verification (exact match, mismatch, realignment), coverage computation
- `test_prompts.py` — Prompt string construction, key methodology terms present
- `test_coder_agent.py` — Span validation logic (valid, out-of-bounds, mismatch)
- `test_codebook_comparator.py` — Empty codebook → immediate NEW
- `test_orchestrator.py` — ITS tracker (saturation detection, consecutive low counting)

**Expected result:** All tests pass. If any fail, fix before proceeding.

### Step 1.2: Write and Run Layer 2-3 Unit Tests

You'll need test files for the new components. Key things to test:

**`tests/test_synthesizer_prompts.py`** — Verify:
- `build_synthesizer_system_prompt()` contains "PATTERNS OF MEANING", "M:N", "QUOTE INHERITANCE"
- `build_synthesizer_user_prompt()` formats codebook correctly, handles empty codebook
- `build_revision_system_prompt()` mentions all 7 feedback types
- `build_revision_user_prompt()` includes theme names, IC lists, feedback details

**`tests/test_quality_metrics.py`** — Verify:
- Meaning saturation clustering: 4 embeddings (2 similar + 2 distinct) → 3 clusters
- Grounding metric with pre-verified quotes → 100% rate
- Coverage with partial coding → correct percentage

**`tests/test_quality_report.py`** — Verify:
- `_mini_bar()` produces correct width, fill ratio
- Report functions don't crash on empty/partial data

**Expected result:** All new tests pass alongside existing ones.

---

## Phase 2: Integration Smoke Test (Small Dataset, API Calls)

Test the pipeline end-to-end with a tiny dataset before running the full corpus.

### Step 2.1: Create a Data Loader

You need a script to read your Steam reviews into `Document` objects. Create `scripts/load_steam_reviews.py`:

The loader should:
1. Read your CSV/JSON file (check what format you exported from Steam)
2. For each review, create a `Document(raw_text=review_text, source_file="dying_light_beast.csv", metadata={"steam_id": ..., "recommended": ..., "hours_played": ...})`
3. Return a `List[Document]`

Key decisions:
- **Which columns?** You want the review text column. Also preserve metadata (recommended, hours, date) for later analysis.
- **Filtering?** Drop very short reviews (< 20 chars) — they won't produce meaningful codes.
- **Encoding?** Steam reviews can have Unicode (emojis, non-Latin scripts). Our `normalize()` handles NFKC but does NOT lowercase — this is intentional for preserving proper nouns.

### Step 2.2: Run Pipeline on 5 Reviews (Smoke Test)

```python
# scripts/run_smoke_test.py
import logging
from src.pipeline import EQDPipeline
from scripts.load_steam_reviews import load_reviews

logging.basicConfig(level=logging.INFO)

# Load just 5 reviews
docs = load_reviews("path/to/your/reviews.csv", limit=5)
print(f"Loaded {len(docs)} reviews")

# Run with HIL enabled
pipeline = EQDPipeline(db_path="smoke_test.db")
results = pipeline.run(docs, enable_hil=True)

print(f"\nResults: {results}")
```

**What to check:**
1. **Layer 0** — Do reviews get segmented correctly? Short reviews should be 1 segment. Longer reviews might split at sentence boundaries.
2. **Layer 1** — Does the Coder Agent extract ICs? Are span offsets correct (verbatim quotes should highlight in the original text)?
3. **Comparator** — For the first batch, all ICs should be recommended as NEW (empty codebook).
4. **HIL** — Can you review candidates in the terminal? Does N/M/R work?
5. **No crashes** — The whole flow should complete without exceptions.

**Expected output:** ~5-20 ICs from 5 reviews, 100% grounding (all spans valid).

### Step 2.3: Verify Database State

After the smoke test, inspect the database:

```bash
sqlite3 smoke_test.db

-- Check counts
SELECT COUNT(*) FROM documents;         -- should be 5
SELECT COUNT(*) FROM segments;          -- should be ~5 (1 per short review)
SELECT COUNT(*) FROM initial_codes WHERE status='active';  -- your ICs
SELECT COUNT(*) FROM verbatim_quotes;   -- at least 1 per IC
SELECT COUNT(*) FROM decision_logs;     -- audit trail

-- Check grounding
SELECT q.quote_text, q.span_start, q.span_end, q.is_verified,
       substr(s.canonical_text, q.span_start+1, q.span_end - q.span_start) as reconstructed
FROM verbatim_quotes q
JOIN segments s ON q.segment_id = s.id
LIMIT 10;
-- The quote_text and reconstructed columns should match exactly
-- (Note: SQLite substr is 1-indexed, Python is 0-indexed, hence +1)

-- Check embeddings are stored
SELECT name, length(embedding_json) as emb_size FROM initial_codes LIMIT 5;
-- emb_size should be > 0 for all ICs
```

**Expected result:** Clean data, verified quotes, embeddings present.

---

## Phase 3: Full Pipeline Test (Dying Light: The Beast)

### Step 3.1: Determine Dataset Size

Before running, check your dataset:
- **How many reviews?** Steam datasets can be 100s to 10,000s.
- **Recommended sample:** Start with 50-100 reviews. Enough for meaningful patterns, manageable for HIL review.
- **Batch size:** Default is 15 segments per batch. 100 reviews ≈ ~7 batches.

**Cost estimate per 100 reviews:**
- Coder Agent (Haiku): ~100 segments × ~2K tokens each = ~200K tokens input + ~100K output ≈ $0.05-0.10
- Comparator (Haiku): ~50-100 new candidates × ~500 tokens each ≈ $0.02
- Embeddings (text-embedding-3-small): ~200 embeds × ~50 tokens ≈ $0.001
- Synthesizer (Sonnet): 1-3 calls × ~8K tokens ≈ $0.05-0.15
- **Total: ~$0.15-0.30 per 100 reviews**

### Step 3.2: Run Layer 1 with HIL

```python
# Use a fresh database for the full run
pipeline = EQDPipeline(db_path="dying_light_beast.db")
docs = load_reviews("path/to/reviews.csv", limit=100)
results = pipeline.run(docs, enable_hil=True)
```

**During Layer 1 HIL review, pay attention to:**

1. **IC quality** — Are the codes meaningful and data-driven? Or generic ("positive sentiment", "negative sentiment")?
2. **Span accuracy** — Do the verbatim quotes actually appear in the text? (100% grounding is the target)
3. **Codebook growth** — Watch the ITS value. It should start high (many new codes) and decrease as the codebook stabilises.
4. **Merge detection** — After 2-3 batches, the comparator should start recommending MERGE for similar codes. Check if the merge suggestions make sense.
5. **Saturation checkpoint** — If ITS drops below 0.02 for 3 consecutive batches, you'll get a checkpoint prompt. For 100 reviews, you may or may not hit this.

**Common issues at this stage:**
- LLM gives bad span offsets → candidates get dropped (logged as warnings). Some dropout is normal (~5-10%). If > 30%, check if the canonical text has unexpected normalization.
- Too many trivially similar codes → the merge threshold (0.75) might need tuning in `eqd_config.yaml`.
- Coder extracts too many / too few codes per segment → adjust temperature (currently 0.2).

### Step 3.3: Codebook Sign-Off

After Layer 1, you'll enter the codebook sign-off (HIL Level 2). This is where you:

1. **Review the full codebook** — look at all active ICs with their evidence counts.
2. **Flag thin evidence** — ICs with < 3 quotes are flagged with ⚠. Consider deprecating or merging them.
3. **Rename vague codes** — e.g., "gameplay_issue" → "combat_system_unresponsive".
4. **Merge duplicates** — if the comparator missed any.
5. **Sign off** — locks the codebook for theme synthesis.

**What to evaluate:**
- Does the codebook cover the range of topics in Dying Light reviews? (gameplay, story, bugs, performance, graphics, value, comparison to DL1/DL2, etc.)
- Are there orphan codes that don't fit anywhere?
- Is the granularity right? (not too broad, not too narrow)

### Step 3.4: Theme Synthesis + Iteration

After sign-off, the Synthesizer Agent proposes themes. You review and iterate (max 3 rounds).

**Round 1: Initial proposal.** Check:
- Do the themes represent genuine patterns (not just topic categories)?
- Is the M:N assignment correct? Some ICs should appear in multiple themes.
- Are there unassigned ICs? (the display flags these)
- Coherence scores: > 0.7 is good, < 0.4 is concerning.
- Distinctness warnings: overlapping pairs > 0.70 similarity need attention.

**Rounds 2-3: Feedback.** Use the structured options:
- SPLIT a theme if it's too broad (e.g., "game quality" → "gameplay mechanics" + "technical performance")
- MERGE if too narrow
- IC_MISASSIGNED if a code belongs in a different theme
- RENAME/REDEFINE for clarity

**Accept when:**
- Themes are interpretively meaningful (not just categories)
- Each theme has a clear analytical claim
- IC assignments make sense
- No major overlaps

### Step 3.5: Quality Report Review

After theme finalization, Layer 3 computes all metrics and displays the final report.

**Target benchmarks for a healthy analysis:**

| Metric | Target | Concern Threshold |
|--------|--------|-------------------|
| Grounding rate | 100% | < 95% — investigate failed quotes |
| Segment coverage | > 80% | < 60% — codebook may be incomplete |
| Final ITS | < 0.02 | > 0.05 — codebook may not have saturated |
| Meaning saturation diversity | 0.3 - 1.0 per IC | < 0.3 with 3+ quotes — redundant evidence |
| Theme coherence (avg) | > 0.5 | < 0.3 — ICs in theme may not belong together |
| Theme distinctness (overlap pairs) | < 0.70 | > 0.70 — themes too similar, consider merging |

---

## Phase 4: Automated Pipeline Test (No HIL)

After validating the interactive flow, run the same data with `enable_hil=False` to test the automated path:

```python
pipeline = EQDPipeline(db_path="dying_light_auto.db")
docs = load_reviews("path/to/reviews.csv", limit=100)
results = pipeline.run(docs, enable_hil=False)
```

**What to check:**
- Pipeline completes without human intervention
- LLM recommendations are auto-accepted
- Quality metrics are computed
- Compare results to HIL run: are there major differences in codebook size, theme count, quality scores?

This is useful for benchmarking: how much does HIL improve quality over pure LLM?

---

## Phase 5: Edge Cases & Stress Tests

### 5.1 Edge Case: Very Short Reviews
Test with reviews like "bad game", "10/10", "meh". These should:
- Produce 0-1 ICs (not forced codes)
- Not crash the pipeline

### 5.2 Edge Case: Non-English Content
Steam reviews can be in Polish, Russian, Chinese, etc. Test with:
- Polish reviews (relevant for your context)
- Mixed-language reviews

**Expected:** Normalization handles Unicode correctly (NFKC, no lowercasing). LLM should still extract ICs (Claude handles multilingual text well).

### 5.3 Edge Case: Duplicate Reviews
Add the same review twice. The content hash should be different (different document IDs / segment indices), but the ICs should merge (comparator detects duplicates).

### 5.4 Stress Test: Large Batch
Run with 500+ reviews to test:
- ITS saturation detection (should trigger checkpoint)
- Memory usage (embeddings stored as JSON in SQLite — watch DB size)
- API rate limits (tenacity retry should handle 429s)

### 5.5 Edge Case: Empty Input
```python
results = pipeline.run([], enable_hil=False)
# Should return early with empty results, no crash
```

---

## Phase 6: Component-Level Validation

If Phase 2-3 reveal issues, isolate components:

### 6.1 Test Preprocessing Alone
```python
from src.models import Document
from src.preprocessing import preprocess_documents
from src.db import Database

db = Database(":memory:")
db.init_schema()

doc = Document(raw_text="Your test review text here...")
segments = preprocess_documents([doc], db)
for seg in segments:
    print(f"  [{seg.char_count} chars] {seg.canonical_text[:80]}...")
```

### 6.2 Test Embeddings Alone
```python
from src.config import load_config, ModelClient
from src.embeddings import EmbeddingService, cosine_similarity
from src.db import Database

config = load_config()
mc = ModelClient(config)
db = Database(":memory:")
db.init_schema()
emb_svc = EmbeddingService(mc, db)

v1 = emb_svc.embed_text("game crashed on startup")
v2 = emb_svc.embed_text("crash bug when launching")
v3 = emb_svc.embed_text("beautiful open world graphics")
print(f"crash vs bug: {cosine_similarity(v1, v2):.3f}")     # should be high (>0.8)
print(f"crash vs graphics: {cosine_similarity(v1, v3):.3f}") # should be low (<0.5)
```

### 6.3 Test Coder Agent Alone
```python
from src.coder_agent import CoderAgent
from src.config import load_config, ModelClient
from src.db import Database
from src.models import Segment

config = load_config()
mc = ModelClient(config)
db = Database("test_coder.db")
db.init_schema()

coder = CoderAgent(mc, db, config)
seg = Segment(
    document_id="test",
    canonical_text="The parkour feels clunky compared to the original Dying Light. Combat is okay but repetitive after 10 hours.",
    original_text="The parkour feels clunky compared to the original Dying Light. Combat is okay but repetitive after 10 hours.",
    char_count=102,
    content_hash="test",
)
results = coder.process_batch([seg])
for cand in results.get(seg.id, []):
    print(f"  IC: {cand.ic_name}")
    print(f"     Quote: \"{cand.quote_text}\"")
    print(f"     Span valid: {seg.canonical_text[cand.span_start:cand.span_end] == cand.quote_text}")
```

---

## Decision Log: What to Tune

As you test, these are the main knobs you can turn in `eqd_config.yaml`:

| Parameter | Current | When to change |
|-----------|---------|----------------|
| `coder_agent.temperature` | 0.2 | ↑ if codes are too conservative, ↓ if too creative |
| `coder_agent.model` | claude_haiku | Switch to sonnet if quality is poor |
| `codebook_comparator.temperature` | 0.1 | Keep low — consistency matters here |
| `synthesizer_agent.temperature` | 0.3 | ↑ for more creative themes, ↓ for safer ones |
| `synthesizer_agent.model` | claude_sonnet | Sonnet is right here — themes need interpretive depth |
| `batch_size` | 15 | ↑ for fewer HIL interruptions, ↓ for finer control |
| `its_saturation_threshold` | 0.02 | ↑ to trigger saturation earlier |
| `similarity_prefilter_k` | 5 | ↑ if comparator misses merges |
| `merge_conflict_similarity_threshold` | 0.75 | ↓ if too many duplicates survive |

---

## Checklist Summary

- [ ] Environment set up (venv, deps, API keys)
- [ ] `pytest tests/ -v` — all unit tests pass
- [ ] Data loader script created for Steam reviews
- [ ] Smoke test (5 reviews) — pipeline completes, grounding 100%
- [ ] Database state verified after smoke test
- [ ] Full run (50-100 reviews) — Layer 1 + HIL review
- [ ] Codebook sign-off — reviewed, thin evidence addressed
- [ ] Theme synthesis — 1-3 rounds of iteration
- [ ] Quality report — all 6 metrics in target range
- [ ] Automated run (no HIL) — compare to interactive results
- [ ] Edge cases tested (short, multilingual, duplicates, empty)
- [ ] Tuning decisions documented
