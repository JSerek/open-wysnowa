# Layer 5: Lens-Perspective Shifting — Design Document

## Purpose

Layer 5 is a post-analysis consultation layer that helps stakeholders ask better questions of their data. It operates after Layers 1-4 have completed a full bottom-up analysis. Rather than simply reconfiguring themes, it provides a structured dialogue that excavates the user's real analytical needs, then produces alternative thematic framings (lenses) that address those needs.

The core insight: stakeholders rarely articulate their actual question on the first try. Layer 5 encodes the researcher's skill of "excavating the real need" as an explicit pipeline step.

---

## Architectural Position

```
Layer 0: Data Ingestion       (observation)
Layer 1: IC Extraction         (observation — ground truth, immutable)
Layer 2: Theme Synthesis       (interpretation — bottom-up)
Layer 3: Quality Metrics       (evaluation)
Layer 4: Analyst Intelligence  (interpretation — meta-analysis)
Layer 5: Lens Consultation     (reframing — human-directed)
```

Layer 5 is invoked **separately** from the main pipeline via CLI:
```
python run_layer5.py results_stab_30.json
```

It uses Layer 4's analytical brief as the consultant's briefing document. The consultant knows what the data contains before engaging the user.

---

## Core Components

### 1. Consultant Agent (Manager)

A stateful ReAct-style agent that manages the entire Layer 5 session. It handles user dialogue, decides which sub-agent to spawn, integrates results, and presents the final coherent analysis.

**State Machine:**

```
INTERROGATE → SYNTHESIZE → DELEGATE → INTEGRATE → PRESENT → SAVE
                                         ↑                    │
                                         └── (next iteration) ─┘
```

| State | Purpose | Exit Condition |
|-------|---------|----------------|
| INTERROGATE | Structured conversation with user. Gathers business context, constraints, hypotheses. | All critical dimensions filled OR max turns reached. |
| SYNTHESIZE | Consolidates user inputs into a lens specification. Decides reframe vs. adjust mode. Asks user to confirm. | User confirms lens spec and mode. |
| DELEGATE | Hands lens spec to appropriate sub-agent. Waits for results. | Sub-agent returns overlay + metrics. |
| INTEGRATE | Combines sub-agent results with Layer 4 canonical analysis. Frames against user's question. Computes deltas. | Integration complete. |
| PRESENT | Delivers coherent answer to user. Asks: answered your question, or refine? | User responds. |
| SAVE | Persists full conversation, state history, lens results, and structured summary to .db. | Write confirmed. |

**Iteration:** The user can loop back from PRESENT to INTERROGATE for a refined lens. Maximum **3 full loops** for v1. Each iteration loads the previous iteration's structured summary as context.

### 2. Dimension Tracking Model

The consultant tracks which analytical dimensions have been covered during interrogation. This is a Pydantic model that acts as a "form to fill" — the consultant adaptively asks about unfilled dimensions rather than following a fixed question order.

**Dimensions:**

| Dimension | Description | Example |
|-----------|-------------|---------|
| `business_problem` | What business/product outcome is the user trying to affect? | "Reduce churn in first 30 days" |
| `scope_constraints` | What can the user actually influence or change? | "Only the combat animation system, no engine changes" |
| `hypotheses` | What does the user already suspect or believe? | "Animation stiffness is the main pain point" |
| `success_criteria` | How would the user know the analysis answered their question? | "Identify top 3 specific combat mechanics to improve" |
| `priority_context` | Urgency, resources, timeline — what shapes decision-making? | "Next patch is in 6 weeks, limited animation budget" |

Each dimension has a status: `empty`, `partial`, `filled`.

**Exit logic:** The consultant checks after each turn: "Do I have enough filled dimensions to produce an actionable lens specification?" When yes, it transitions to SYNTHESIZE. The consultant does not ask unnecessary questions — if the user's first message already covers 3 dimensions, it skips those.

**Triage:** If the user's initial question is already well-specified (all critical dimensions inferable), the consultant proposes a lens directly and asks for confirmation rather than interrogating.

### 3. Lens Specification

The structured contract between the consultant and sub-agents. Produced during SYNTHESIZE.

```
lens_name: str                    # e.g., "Combat System Improvement"
research_question: str            # The reframed question
analytical_lenses: List[str]      # Named perspectives to apply (can be >1)
dimensions_to_emphasize: List[str]  # What to weight more heavily
user_constraints: List[str]       # Boundaries the sub-agent must respect
mode: "reframe" | "adjust"       # Which sub-agent to invoke
adjust_instructions: Optional[List[str]]  # Only for adjust mode: specific theme changes
```

The consultant produces this; the sub-agent consumes it. The consultant does NOT include specific theme split/merge suggestions — that's the sub-agent's analytical responsibility.

### 4. Sub-Agent: Reframe

Re-examines all ICs from scratch through the lens. Does **not** use existing themes as input to avoid anchoring bias.

**Input:** All ICs with evidence (quotes), lens specification.
**Process:** Single-pass synthesis (v1). Injects lens context into the grouping prompt: "Group these initial codes through the lens of [lens_name]. You are looking for connections relevant to [research_question], emphasizing [dimensions]."
**Output:** New thematic structure (themes + categories) as an overlay.

The reframe sub-agent has its own code path but reuses existing Layer 2-3 utility functions where applicable (e.g., similarity computation, merge logic). It does NOT use the iterative batch processing of canonical Layer 2 — single-pass is sufficient for an overlay that doesn't need to build a canonical codebook.

### 5. Sub-Agent: Adjust

Makes targeted modifications to the existing thematic structure based on explicit user instructions.

**Input:** Existing themes and categories, ICs with evidence, lens specification with `adjust_instructions`.
**Process:** Applies specific operations (split theme X into A and B, merge themes Y and Z, re-examine theme W's ICs for sub-patterns). Preserves all themes the user didn't mention.
**Output:** Modified thematic structure as an overlay.

The adjust sub-agent CAN use existing themes because the user is explicitly choosing to preserve the current frame and make surgical changes. This is a different operation from reframing.

**Routing decision:** The consultant decides reframe vs. adjust during SYNTHESIZE based on the interrogation. If the user's need requires a fundamentally different perspective → reframe. If the user is satisfied with the overall structure but wants specific changes → adjust. The consultant proposes the mode and asks for user confirmation.

---

## Quality Re-validation

Every overlay produced by a sub-agent goes through full quality re-validation:

1. **Layer 3 metrics** recomputed on the new thematic structure (coherence, distinctness, sentiment purity, coverage, etc.)
2. **Layer 4 Analyst Intelligence** runs on the overlay. Layer 4's prompt is updated to include the canonical run's metrics and brief, so it can comment on **deltas** — not just absolute values.

This produces two complete analytical packages side by side: canonical and lens-derived. The comparison itself is analytical signal (e.g., "coherence improved but coverage dropped — the lens sharpened focus but lost peripheral signal").

---

## Data Storage

### File Strategy

Each lens produces a **separate JSON file** referencing the canonical run:

```
results_stab_30.json              # canonical (immutable after Layer 4)
results_stab_30_lens_1.json       # first lens overlay
results_stab_30_lens_2.json       # second lens (iteration 2)
```

Canonical results are never modified. Overlays contain only the reframed structure plus a pointer to the source run.

### Database Schema

Three tables in the project .db file:

#### `lens_sessions`

| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT PK | Unique identifier |
| timestamp | DATETIME | Session start time |
| canonical_run_ref | TEXT | Path to canonical results JSON |
| parent_session_id | TEXT FK NULL | Previous iteration's session_id (NULL for first) |
| iteration_number | INTEGER | 1-indexed iteration count |
| lens_mode | TEXT | "reframe" or "adjust" |
| lens_specification | JSON | Full lens spec as produced by consultant |
| outcome_status | TEXT | "completed", "abandoned", "user_refined" |
| structured_summary | JSON | Compressed summary for next-iteration context |

#### `conversation_turns`

| Column | Type | Description |
|--------|------|-------------|
| turn_id | TEXT PK | Unique identifier |
| session_id | TEXT FK | Parent session |
| turn_number | INTEGER | Sequential turn count |
| role | TEXT | "user", "consultant", "system" |
| content | TEXT | Raw message content |
| consultant_state | TEXT | Current state machine state |
| dimension_snapshot | JSON | Full Pydantic dimension model state at this turn |
| timestamp | DATETIME | Turn timestamp |

The `dimension_snapshot` stores the **full** Pydantic model state (not diffs). Storage is cheap; debugging is easier when you can see the complete picture at any turn.

#### `lens_results`

| Column | Type | Description |
|--------|------|-------------|
| result_id | TEXT PK | Unique identifier |
| session_id | TEXT FK | Parent session |
| overlay_json_path | TEXT | Path to lens overlay JSON file |
| metrics_snapshot | JSON | Layer 3 metric values on the overlay |
| layer4_brief | JSON | Layer 4 analytical brief on the overlay |
| delta_vs_canonical | JSON | Metric deltas against canonical run |
| delta_vs_parent | JSON NULL | Metric deltas against previous iteration (NULL for first) |
| n_themes | INTEGER | Theme count in overlay |
| n_categories | INTEGER | Category count in overlay |

### Structured Summary (for cross-iteration context)

Stored in `lens_sessions.structured_summary`. This is what the consultant loads at the start of iteration N+1.

```json
{
  "session_id": "...",
  "iteration_number": 1,
  "timestamp": "...",
  "lens_name": "Combat System Improvement",
  "research_question": "What specific combat mechanics frustrate players most?",
  "user_constraints": ["team can only modify animation system"],
  "hypotheses_explored": ["animation fluidity is main pain point"],
  "dimensions_covered": {
    "business_problem": true,
    "scope_constraints": true,
    "hypotheses": true,
    "success_criteria": "partial",
    "priority_context": false
  },
  "mode_used": "reframe",
  "themes_changed": {
    "added": ["Animation Stiffness", "Hit Feedback Gap"],
    "removed_from_view": ["General Combat"],
    "split": [],
    "merged": []
  },
  "quality_delta": {
    "coherence": "+0.08",
    "distinctness": "-0.03",
    "coverage": "-0.02"
  },
  "key_insight": "Separating animation complaints from hit-feedback revealed 3x stronger negative sentiment correlation with animation issues",
  "user_reaction": "wants to drill deeper into animation specifics"
}
```

---

## Relationship to Other Concepts

**Codebook Versioning:** Operates on the ground truth layer (ICs, their definitions, merge/split decisions). It's about improving the coding instrument over time. Lenses are a separate concept — same ICs, different thematic groupings. They are orthogonal. A lens could be run on any codebook version's ICs.

**Layer 4:** Layer 5 consumes Layer 4's output as context. Layer 4 also runs on each overlay to provide interpretation of the reframed analysis. Layer 4's prompts are extended to include canonical metrics for delta commentary.

**Design Principles Alignment:**
- Principle 1 (Raw data immutable): ICs never touched. Only themes/categories reconfigured.
- Principle 2 (Traceability): Full conversation + state history persisted. Every overlay references its source.
- Principle 3 (Bottom-up first): Canonical analysis is always inductive. Lenses are explicitly labeled as reframings.
- Principle 5 (Non-destructive): Overlays sit alongside canonical. Never replace.

---

## V1 Scope

**In scope:**
- Consultant agent with stateful interrogation (terminal I/O)
- Dimension tracking Pydantic model
- Reframe sub-agent (single-pass from ICs)
- Adjust sub-agent (targeted theme modifications)
- Full Layer 3 + Layer 4 re-validation on overlays
- Delta computation (vs. canonical + vs. parent iteration)
- .db persistence (3 tables)
- Structured summary for cross-iteration context
- Max 3 iterations per session
- Separate CLI invocation
- Consultant tools: context-only (Layer 4 brief + thematic structure injected into prompt)

**Explicitly out of scope for v1:**
- Automated lens mode (Layer 5 self-proposes improvements without human input)
- Consultant query tools (Option B: function calls to DB)
- UI beyond terminal
- Parallel lens execution
- Integration into main pipeline flow

---

## Open Questions for Implementation

1. **Prompt architecture for consultant:** Exact ReAct prompt structure, CoT token budget, and system prompt content. To be determined during implementation through experimentation.
2. **Error handling:** What happens if the reframe sub-agent produces a degenerate overlay (e.g., all ICs in one theme)? Needs a validation gate before INTEGRATE.
3. **IC volume limits:** For large datasets, single-pass synthesis of all ICs may exceed context windows. May need batching strategy. To be assessed against real data sizes.
4. **Lens specification validation:** Should the consultant's lens spec be validated before delegation (e.g., are the lenses actionable, are constraints contradictory)?
5. **Adjust mode granularity:** How specific can adjust instructions be? "Split theme X" is clear, but "make theme X more specific" is vague. Need to define the operation vocabulary.
