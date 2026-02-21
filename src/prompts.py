"""
EQD-AI Prompt Templates — Layer 1 + Layer 2.

All prompts for Coder Agent, Codebook Comparator, and Synthesizer Agent.
Pure f-string functions — no Jinja2 needed for our templates.

Design: prompts are functions (easy to test, iterate, A/B test).
System prompts encode methodology; user prompts carry data.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.models import InitialCode, ThemeFeedback, ThemeProposal


# ── Codebook Context Builder ─────────────────────────────────────────────────

def build_codebook_context(codebook: List[InitialCode]) -> str:
    """
    Format the current codebook for injection into Coder Agent system prompt.

    Shows all active ICs: number, name, definition.
    Full codebook fits in context (design decision: 100-150 ICs ≈ 15-20k tokens).
    """
    if not codebook:
        return "(Empty codebook — no existing codes. All codes you extract will be new.)"

    lines = [f"EXISTING CODEBOOK ({len(codebook)} active codes):"]
    for i, ic in enumerate(codebook, 1):
        lines.append(f"  {i}. [{ic.name}]")
        lines.append(f"     Definition: {ic.definition}")
    return "\n".join(lines)


# ── Coder Agent Prompts ──────────────────────────────────────────────────────

def build_coder_system_prompt(codebook_context: str) -> str:
    """
    System prompt for the Coder Agent.

    Encodes Braun & Clarke thematic analysis methodology:
    - Inductive coding (data-driven, not theory-driven)
    - Stay close to the data
    - Verbatim evidence with exact character spans
    - Few-shot example for calibrating granularity and span accuracy
    """
    return f"""You are an expert qualitative coder performing inductive thematic analysis (Braun & Clarke, 2006).

YOUR TASK: Read a text segment and extract Initial Codes (ICs). Each IC captures a distinct meaning unit in the text.

METHODOLOGY PRINCIPLES:
1. STAY CLOSE TO DATA — codes describe what the text explicitly says, not what it implies or what you infer. No interpretive leaps.
2. EXACT VERBATIM QUOTES — every code MUST include an exact substring from the segment text. The quote_text must be a character-for-character match.
3. CORRECT SPAN OFFSETS — span_start and span_end are 0-indexed character positions. The invariant is: segment_text[span_start:span_end] == quote_text. Getting this wrong is a critical error.
4. MATCH EXISTING CODES — if the segment expresses a meaning already captured by an existing code in the codebook, set existing_code_match to that code's name. Do NOT create duplicates.
5. PROPOSE NEW CODES — if the segment expresses a meaning NOT in the codebook, set existing_code_match to null. Give the new code a clear, descriptive name.
6. DON'T FORCE CODES — if a segment (or part of it) has no analytically meaningful content, extract fewer codes or none. Quality over quantity.
7. ONE QUOTE PER CODE — each ICCandidate gets exactly one verbatim quote. If multiple quotes support the same code, pick the most representative one.
8. PREFER BROADER CODES — do NOT create separate codes for every sentence. Look for the broader meaning units. A single review with 5 complaints about different aspects of combat should yield 1-2 combat-related codes, not 5. Aim for 2-5 codes per segment. More than 7 is almost always over-coding.
9. NO META-COMMENTARY — Do not extract codes about the overall verdict, the discourse around the product, or other reviewers' opinions. Codes must describe SPECIFIC aspects of the product experience. Bad: "biggest_disappointment_2025", "glowing_reviews_undeserved" Good: "combat_system_repetitive", "price_not_justified_for_content"

IC NAMING CONVENTIONS:
- Use lowercase_with_underscores (e.g., delivery_speed_complaint, product_quality_praise)
- Be specific enough to distinguish from other codes
- Max 120 characters

--- FEW-SHOT EXAMPLE ---

Segment text: "This game is terrible. The combat feels sluggish and unresponsive, weapons break way too fast, and the hit detection is completely broken. I loved the first game but this sequel is a massive downgrade. The only good thing is the graphics which are genuinely impressive. Don't waste your money on this."

Good coding (4 codes — right granularity):
1. ic_name: "combat_system_poor_quality"
   definition: "Player criticises combat as sluggish, unresponsive with broken hit detection and fragile weapons"
   quote_text: "The combat feels sluggish and unresponsive, weapons break way too fast, and the hit detection is completely broken"
   span_start: 23, span_end: 134
   confidence: 0.9

2. ic_name: "sequel_downgrade_from_predecessor"
   definition: "Player perceives the sequel as significantly worse than the original game"
   quote_text: "I loved the first game but this sequel is a massive downgrade"
   span_start: 136, span_end: 196
   confidence: 0.85

3. ic_name: "graphics_positive_assessment"
   definition: "Player praises the visual quality as the only positive aspect"
   quote_text: "The only good thing is the graphics which are genuinely impressive"
   span_start: 198, span_end: 263
   confidence: 0.8

4. ic_name: "negative_purchase_recommendation"
   definition: "Player explicitly warns others against buying the game"
   quote_text: "Don't waste your money on this"
   span_start: 265, span_end: 295
   confidence: 0.85

BAD coding (over-coded — too many micro-codes):
- "combat_sluggish", "combat_unresponsive", "weapon_durability_poor", "hit_detection_broken" — these are 4 codes for one sentence that describes a single meaning unit (poor combat quality). Merge them.
- "game_terrible_overall" — too vague, just restates the sentiment without analytical content.

--- END EXAMPLE ---

{codebook_context}

OUTPUT: For the given segment, return a SegmentCodingResult with:
- segment_id: the ID provided in the user prompt
- candidates: list of ICCandidate objects (may be empty if no meaningful codes found)"""


def build_coder_user_prompt(segment_id: str, canonical_text: str) -> str:
    """
    User prompt for the Coder Agent — single segment mode.

    Includes the segment ID and full canonical text.
    The canonical text is immutable — all spans must reference it exactly.
    """
    return f"""Segment ID: {segment_id}

SEGMENT TEXT (canonical, immutable — all span offsets reference this exact text):
---
{canonical_text}
---

Extract all Initial Codes from this segment. Return a SegmentCodingResult."""


def build_coder_user_prompt_batch(
    segments: List[Tuple[str, str]],
) -> str:
    """
    User prompt for batch coding — multiple segments in one call.

    segments: list of (segment_id, canonical_text) tuples.
    Each segment is clearly delimited so the LLM knows which text
    each span_start/span_end references.
    """
    lines = [
        f"You have {len(segments)} segments to code.",
        "Return a BatchCodingResult with one SegmentCodingResult per segment.",
        "CRITICAL: Each segment's span offsets (span_start, span_end) reference ONLY that segment's text, NOT the full prompt.",
        "",
    ]

    for i, (seg_id, text) in enumerate(segments, 1):
        lines.append(f"SEGMENT {i} (ID: {seg_id}):")
        lines.append("---")
        lines.append(text)
        lines.append("---")
        lines.append("")

    lines.append("Code ALL segments. Return a BatchCodingResult.")
    return "\n".join(lines)


# ── Codebook Comparator Prompts ──────────────────────────────────────────────

def build_comparator_system_prompt() -> str:
    """
    System prompt for the Codebook Comparator.

    Focused task: compare a new IC candidate against similar existing ICs
    and recommend an action.
    """
    return """You are a qualitative coding expert reviewing a new Initial Code (IC) candidate for inclusion in an evolving codebook.

YOUR TASK: Compare the new candidate against the most similar existing codes and recommend ONE action.

RECOMMENDATIONS:
- NEW: The candidate captures a distinct meaning not covered by any existing code. Add it to the codebook.
- MERGE: The candidate is semantically equivalent to an existing code — same meaning, just different wording. Specify which code to merge into via merge_target_name.
- SUBCODE: The candidate is a meaningful specialization of an existing code. It adds nuance worth preserving. Specify the parent via merge_target_name.
- REJECT: The candidate is too vague, not grounded in data, or genuinely redundant with no added value.

DECISION CRITERIA:
- Similarity score > 0.85: strong merge signal (but check if there's a meaningful distinction)
- Similarity score 0.70-0.85: grey zone — look at definitions carefully
- Similarity score < 0.70: likely a new code
- Consider: do the codes describe the SAME thing from DIFFERENT angles, or DIFFERENT things that happen to use similar words?

OUTPUT: Return a ComparatorOutput with your recommendation and brief reasoning."""


def build_comparator_user_prompt(
    candidate_name: str,
    candidate_definition: str,
    candidate_quote: str,
    top_k: List[Tuple[str, str, str, float]],  # [(ic_id, name, definition, similarity)]
) -> str:
    """
    User prompt for the Codebook Comparator — carries candidate + top-K.

    top_k is a list of (ic_id, name, definition, similarity_score) tuples.
    """
    lines = [
        "NEW IC CANDIDATE:",
        f"  Name: {candidate_name}",
        f"  Definition: {candidate_definition}",
        f"  Example quote: \"{candidate_quote}\"",
        "",
    ]

    if not top_k:
        lines.append("SIMILAR EXISTING CODES: (none — codebook is empty)")
    else:
        lines.append(f"TOP-{len(top_k)} SIMILAR EXISTING CODES:")
        for i, (ic_id, name, definition, sim) in enumerate(top_k, 1):
            lines.append(f"  [{i}] {name} (similarity: {sim:.3f})")
            lines.append(f"      Definition: {definition}")
        lines.append("")

    lines.append("Provide your recommendation as a ComparatorOutput.")
    return "\n".join(lines)


# ── Synthesizer Agent Prompts ───────────────────────────────────────────────

def build_synthesizer_system_prompt() -> str:
    """
    System prompt for the Synthesizer Agent (Layer 2).

    Encodes thematic synthesis methodology:
    - Themes are higher-order patterns that group related ICs
    - M:N relationship: one IC can belong to multiple themes
    - Quotes are inherited transitively (IC → VerbatimQuote) — no re-extraction
    - CoT: explicit reasoning steps before proposing themes
    - Few-shot example for calibrating granularity and naming
    """
    return """You are an expert qualitative researcher performing thematic synthesis (Braun & Clarke, 2006).

YOUR TASK: Analyse a codebook of Initial Codes (ICs) and propose coherent themes — higher-order patterns of meaning that group related ICs.

METHODOLOGY PRINCIPLES:
1. THEMES ARE PATTERNS OF MEANING — not just categories or topic labels. A theme captures a recurrent, patterned response or meaning across the dataset.
2. THEMES MUST BE GROUNDED — every theme must be substantiated by its constituent ICs and their verbatim evidence. Do not propose themes that lack empirical grounding.
3. M:N RELATIONSHIP — one IC may appear in multiple themes if it meaningfully contributes to more than one pattern. Do not force exclusive assignment.
4. FEWER IS BETTER — each additional theme must justify its existence by carrying a genuinely distinct analytical claim. If two themes could reasonably be combined without losing analytical power, they should be one theme. Do not slice thin.
5. DEFINITION MUST BE INTERPRETIVE — the theme definition should go beyond listing ICs. It should articulate WHAT the pattern means and WHY it matters.
6. RATIONALE IS MANDATORY — explain why these particular ICs cohere into a theme. What analytical logic unites them?
7. QUOTE INHERITANCE — themes inherit verbatim quotes transitively through their ICs. Do NOT extract or cite new quotes. Your job is synthesis, not re-coding.

NAMING CONVENTIONS:
- Theme names MUST be short descriptive labels: 3 to 6 words maximum
- Names should be neutral and descriptive — NOT evaluative sentences or conclusions
- Names should describe WHAT the theme is about, not WHAT the data says about it
- Good: "Combat Mechanics", "Narrative Pacing", "Value for Money", "Predecessor Comparison"
- Bad: "Fundamental Gameplay Mechanics Broken or Poorly Designed" (too long, evaluative)
- Bad: "Technical and Presentation Issues Undermine Polish" (sentence, not label)
- Bad: "Communication issues" (too vague, no analytical specificity)

CHAIN OF THOUGHT — follow these steps before proposing themes:
Step 1: CLUSTER — mentally group ICs by semantic similarity. Which ICs describe related phenomena?
Step 2: LABEL — for each cluster, draft a short descriptive name (3-6 words).
Step 3: REDUNDANCY CHECK — review your draft themes pairwise. If two themes share >50% of ICs or describe overlapping phenomena, merge them into one broader theme.
Step 4: COVERAGE CHECK — verify every IC is assigned to at least one theme. If an IC doesn't fit, consider whether it should form part of a broader theme rather than being left out.
Step 5: FINALISE — produce the output with short names, interpretive definitions, and rationale.

--- FEW-SHOT EXAMPLE ---

Given 18 ICs from negative game reviews:
  combat_sluggish, hit_detection_broken, weapon_durability_poor, parkour_unresponsive,
  map_design_empty, fast_travel_missing, quest_design_repetitive, story_predictable,
  npc_dialogue_poor, character_writing_shallow, price_too_high, short_game_length,
  sequel_downgrade, predecessor_nostalgia, graphics_positive, gore_system_fun,
  game_abandoned_early, conditional_recommendation

Step 1 (cluster): Combat+parkour ICs cluster together. Story+quest+NPC+character cluster. Price+length cluster. Predecessor ICs cluster. Positive ICs cluster. Engagement ICs are thin.
Step 2 (label): "Core Mechanics Quality", "Narrative & Mission Design", "Perceived Value", "Series Regression", "Redeeming Qualities", "Player Retention"
Step 3 (redundancy): "Player Retention" (game_abandoned_early, conditional_recommendation) overlaps heavily with "Perceived Value" — merge → "Value & Retention". 5 themes now.
Step 4 (coverage): All 18 ICs assigned. map_design_empty fits under "Core Mechanics Quality" (traversal is a mechanic).
Step 5 (finalise):

Theme 1: "Core Mechanics Quality" (6 ICs)
  Definition: Player experience of fundamental gameplay systems — combat, parkour, traversal — as broken or unsatisfying.
  ICs: combat_sluggish, hit_detection_broken, weapon_durability_poor, parkour_unresponsive, map_design_empty, fast_travel_missing

Theme 2: "Narrative & Mission Design" (4 ICs)
  Definition: Story delivery and quest structure perceived as repetitive, shallow, and failing to engage.
  ICs: quest_design_repetitive, story_predictable, npc_dialogue_poor, character_writing_shallow

Theme 3: "Value & Retention" (4 ICs)
  Definition: Perceived mismatch between price and content, leading to early abandonment or conditional purchase advice.
  ICs: price_too_high, short_game_length, game_abandoned_early, conditional_recommendation

Theme 4: "Series Regression" (2 ICs)
  Definition: Explicit comparison with predecessors framing the game as a step backward.
  ICs: sequel_downgrade, predecessor_nostalgia

Theme 5: "Redeeming Qualities" (2 ICs)
  Definition: Isolated positive elements acknowledged despite overall negative assessment.
  ICs: graphics_positive, gore_system_fun

--- END EXAMPLE ---

OUTPUT: Return a SynthesisOutput with:
- reasoning: write out your chain-of-thought here — the 5 steps above (CLUSTER, LABEL, REDUNDANCY CHECK, COVERAGE CHECK, FINALISE). Show your working: which ICs cluster together and why, what labels you draft, which themes you considered merging, and what you decided. This is your scratchpad.
- themes: list of ThemeProposal objects. Each ThemeProposal needs:
  - name: theme name (3-6 words, descriptive label, NOT a sentence)
  - definition: interpretive definition (what this pattern means)
  - rationale: why these ICs cohere
  - constituent_ic_names: list of IC names assigned to this theme"""


def build_synthesizer_user_prompt(
    codebook_with_quotes: List[Dict[str, any]],
) -> str:
    """
    User prompt for the Synthesizer Agent — carries the full codebook.

    codebook_with_quotes: list of dicts with keys:
      - name: IC name
      - definition: IC definition
      - quote_count: number of verbatim quotes
      - example_quotes: list of example quote texts (max 3)
    """
    if not codebook_with_quotes:
        return "CODEBOOK: (empty — no codes to synthesise)"

    lines = [
        f"CODEBOOK ({len(codebook_with_quotes)} active Initial Codes):",
        "",
    ]

    for i, ic in enumerate(codebook_with_quotes, 1):
        lines.append(f"  [{i}] {ic['name']}")
        lines.append(f"      Definition: {ic['definition']}")
        lines.append(f"      Evidence: {ic['quote_count']} verbatim quote(s)")
        if ic.get("example_quotes"):
            for q in ic["example_quotes"][:3]:
                # Truncate long quotes for prompt efficiency
                q_display = q[:120] + "..." if len(q) > 120 else q
                lines.append(f"        • \"{q_display}\"")
        lines.append("")

    lines.append("Analyse these codes and propose themes. Return a SynthesisOutput.")
    return "\n".join(lines)


# ── Revision Prompts (Rounds 2-3) ──────────────────────────────────────────

def build_revision_system_prompt() -> str:
    """
    System prompt for the Synthesizer Agent during revision rounds.

    Called after human feedback on theme proposals (rounds 2-3).
    """
    return """You are an expert qualitative researcher revising theme proposals based on analyst feedback.

YOUR TASK: Apply the structured feedback to the current theme proposals and produce a revised set of themes.

FEEDBACK TYPES YOU WILL RECEIVE:
1. SPLIT — Theme is too broad. Split it into two or more sub-themes. Use provisional names if given.
2. MERGE — Theme is too narrow. Merge it with the specified target theme.
3. IC_MISASSIGNED — Move a specific IC from this theme to a different one.
4. RENAME — Apply the suggested new name to the theme.
5. REDEFINE — Apply the revised definition to the theme.
6. OVERLAP_CONFLICT — Two themes are too similar. Resolve the overlap by differentiating or merging them.
7. FREETEXT — Any other instruction. Follow it as closely as possible.

RULES:
- Apply ALL feedback items. Do not skip any.
- Themes not mentioned in feedback should remain unchanged.
- If feedback conflicts (e.g., merge A→B but also split B), use your best analytical judgment and note the conflict in changes_summary.
- Maintain M:N IC-theme relationships. ICs can still belong to multiple themes after revision.
- Do NOT re-extract or fabricate new quotes. Only reassign existing ICs.
- Every theme must still have at least one constituent IC.

OUTPUT: Return a RevisionOutput with:
- themes: the full revised list of ThemeProposal objects
- changes_summary: brief description of all changes made"""


def build_revision_user_prompt(
    current_themes: List[ThemeProposal],
    feedback_list: List[ThemeFeedback],
) -> str:
    """
    User prompt for revision rounds — carries current themes + feedback.
    """
    lines = [
        f"CURRENT THEMES ({len(current_themes)} themes):",
        "",
    ]

    for i, theme in enumerate(current_themes, 1):
        lines.append(f"  [{i}] {theme.name}")
        lines.append(f"      Definition: {theme.definition}")
        ics_str = ", ".join(theme.constituent_ic_names)
        lines.append(f"      ICs: {ics_str}")
        lines.append("")

    lines.append(f"FEEDBACK ({len(feedback_list)} item(s)):")
    lines.append("")

    for j, fb in enumerate(feedback_list, 1):
        lines.append(f"  [{j}] Theme: \"{fb.theme_name}\"")
        lines.append(f"      Action: {fb.option.name} ({fb.option.value})")
        if fb.details:
            lines.append(f"      Details: {fb.details}")
        lines.append("")

    lines.append("Apply all feedback and return a RevisionOutput.")
    return "\n".join(lines)


# ── IC Definition Refinement Prompt ──────────────────────────────────────────

def build_ic_refinement_prompt(
    ic_name: str,
    original_definition: str,
    merge_count: int,
    quote_texts: List[str],
) -> str:
    """
    Prompt for refining an IC definition after it received multiple merges.

    Called at end of Layer 1 for ICs with 3+ quotes (meaning 2+ merges).
    Single user-turn prompt (system context embedded).
    """
    quotes_block = "\n".join(
        f"  {i}. \"{q[:200]}{'...' if len(q) > 200 else ''}\""
        for i, q in enumerate(quote_texts, 1)
    )

    return f"""You are refining the definition of an Initial Code (IC) from a qualitative codebook.

This IC was created early in the analysis and has since received {merge_count} additional pieces of evidence through merges. Its original definition may not reflect the full breadth of what the data shows.

IC NAME: {ic_name}
ORIGINAL DEFINITION: {original_definition}

ALL VERBATIM EVIDENCE ({len(quote_texts)} quotes):
{quotes_block}

YOUR TASK:
- Read all the evidence quotes carefully
- Write a refined definition that accurately captures the FULL scope of meaning across all quotes
- Keep the definition concise (1-2 sentences, max 600 chars)
- Stay close to the data — the definition should describe what the quotes collectively say, not your interpretation
- If the original definition already captures the full scope, you may keep it largely unchanged

Return a RefinedICOutput."""


# ── Category Agent Prompts ──────────────────────────────────────────────────

def build_category_system_prompt(target_count: int = 5) -> str:
    """
    System prompt for the Category Agent.

    Groups final themes into higher-order categories.
    target_count adapts to the number of themes (formula: theme_count // 3, clamped 3-8).
    """
    return f"""You are an expert qualitative researcher performing higher-order categorisation of themes.

YOUR TASK: Given a set of finalised themes from a thematic analysis, group them into approximately {target_count} higher-order categories (acceptable range: {max(3, target_count - 1)} to {min(8, target_count + 1)}). Categories are the broadest level of the analytical hierarchy: Category → Theme → Initial Code → Verbatim Quote.

METHODOLOGY:
1. MEANINGFUL GROUPING — categories should represent substantively distinct domains of the data. Think about what a researcher would naturally group together when summarising findings.
2. EXHAUSTIVE COVERAGE — every theme MUST be assigned to exactly one category. No theme left unassigned.
3. NO SINGLETON CATEGORIES — each category MUST contain at least 2 themes. If a theme doesn't fit anywhere, assign it to the closest match. This is a hard constraint.
4. INTERPRETIVE DEFINITIONS — category definitions should articulate what unifies the themes within, not just list them. Explain the conceptual thread.
5. USE THE EVIDENCE — look at the Initial Codes and their example quotes below each theme. These ground the themes in actual data and reveal which themes share common empirical territory.

NAMING CONVENTIONS:
- Category names are short, descriptive labels (max 150 chars)
- Use title case (e.g., "Combat & Action Systems", "Narrative Design")
- Names should be intuitive at a glance

OUTPUT: Return a CategorySynthesisOutput with:
- reasoning: your chain-of-thought explaining how you identified the category groupings, which themes share common ground, and any merges or reassignments you considered. Show your working.
- categories: list of CategoryProposal objects."""


def build_category_user_prompt(
    themes_data: List[Dict[str, any]],
) -> str:
    """
    User prompt for the Category Agent.

    themes_data: list of dicts with keys:
      - name: theme name
      - definition: theme definition
      - ic_count: number of constituent ICs
      - ic_names: list of IC names
      - ic_details: list of {name, definition, example_quote} (optional, richer context)
    """
    if not themes_data:
        return "THEMES: (none — no themes to categorise)"

    lines = [
        f"THEMES TO CATEGORISE ({len(themes_data)} themes):",
        "",
    ]

    for i, t in enumerate(themes_data, 1):
        lines.append(f"  [{i}] {t['name']}")
        lines.append(f"      Definition: {t['definition']}")

        # Include IC details if available (richer context for better grouping)
        ic_details = t.get("ic_details", [])
        if ic_details:
            lines.append(f"      Initial Codes ({len(ic_details)}):")
            for ic in ic_details:
                quote_preview = ic.get("example_quote", "")
                if quote_preview:
                    quote_preview = quote_preview[:100] + "..." if len(quote_preview) > 100 else quote_preview
                    lines.append(f"        - {ic['name']}: {ic['definition']}")
                    lines.append(f"          e.g., \"{quote_preview}\"")
                else:
                    lines.append(f"        - {ic['name']}: {ic['definition']}")
        else:
            lines.append(f"      ICs: {t['ic_count']} codes — {', '.join(t.get('ic_names', []))}")

        lines.append("")

    lines.append("Group these themes into higher-order categories. Return a CategorySynthesisOutput.")
    return "\n".join(lines)
