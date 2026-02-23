"""
EQD-AI Prompt Templates — Layer 1 + Layer 2.

All prompts for Coder Agent, Codebook Comparator, and Synthesizer Agent.
Pure f-string functions — no Jinja2 needed for our templates.

Design: prompts are functions (easy to test, iterate, A/B test).
System prompts encode methodology; user prompts carry data.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.config import AnalystGuidelinesConfig
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
10. SPECIFICITY MATCHES THE TEXT — Be as specific as the text allows, no more. If the segment identifies a specific system or feature, name it. If the segment expresses general dissatisfaction without identifying specific causes, create an IC that captures the general nature of the experience — never fabricate specifics that aren't in the text.
11. ASSESS SENTIMENT — For each IC, assess the sentiment of the verbatim quote: positive, negative, neutral, or mixed. Sentiment is determined by what the quote expresses, not by the overall tone of the review. A negative review can contain positive quotes ("the graphics are great") and vice versa.

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
   sentiment: negative

2. ic_name: "sequel_downgrade_from_predecessor"
   definition: "Player perceives the sequel as significantly worse than the original game"
   quote_text: "I loved the first game but this sequel is a massive downgrade"
   span_start: 136, span_end: 196
   confidence: 0.85
   sentiment: negative

3. ic_name: "graphics_positive_assessment"
   definition: "Player praises the visual quality as the only positive aspect"
   quote_text: "The only good thing is the graphics which are genuinely impressive"
   span_start: 198, span_end: 263
   confidence: 0.8
   sentiment: positive

4. ic_name: "negative_purchase_recommendation"
   definition: "Player explicitly warns others against buying the game"
   quote_text: "Don't waste your money on this"
   span_start: 265, span_end: 295
   confidence: 0.85
   sentiment: negative

--- NEGATIVE EXAMPLES (common errors) ---

ERROR 1 — Fabricated specificity:
  Segment: "I just didn't enjoy this game at all, nothing about it worked for me"
  BAD:  ic_name: "combat_system_unenjoyable"  ← WRONG: text doesn't mention combat
  WHY:  The text is GENERAL dissatisfaction. The coder invented "combat" to sound specific.
  FIX:  ic_name: "overall_negative_experience"
        definition: "Player expresses broad dissatisfaction without identifying specific causes"
        sentiment: negative

ERROR 2 — Meta-commentary instead of experience:
  Segment: "this is the worst game of 2025, I can't believe reviewers are praising it"
  BAD:  ic_name: "worst_game_2025"  ← WRONG: this is a verdict, not an experience
  BAD:  ic_name: "reviewers_praising_undeserved"  ← WRONG: about other people's opinions
  WHY:  Neither code describes an aspect of the product experience.
  FIX:  No codes should be extracted — the segment lacks specific experiential content.

ERROR 3 — Wrong sentiment assignment:
  Segment: "The graphics are the only thing saving this trainwreck"
  BAD:  sentiment: negative  ← WRONG: the QUOTE is about graphics being good
  WHY:  Sentiment follows the QUOTE, not the overall review tone.
  FIX:  sentiment: positive (the quote praises graphics, even if the review is negative)

ERROR 4 — Over-coding micro-observations:
  BAD: 5 separate codes: "combat_sluggish", "combat_unresponsive", "weapon_durability_poor", "hit_detection_broken", "game_terrible_overall"
  WHY: Four codes for one sentence = one meaning unit split artificially. "game_terrible_overall" is vague meta-commentary.
  FIX: One code: "combat_system_poor_quality" capturing the full meaning unit.

--- END EXAMPLES ---

{codebook_context}

OUTPUT: For the given segment, return a SegmentCodingResult with:
- segment_id: the ID provided in the user prompt
- candidates: list of ICCandidate objects, each including a sentiment field (positive/negative/neutral/mixed). May be empty if no meaningful codes found."""


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

--- NEGATIVE EXAMPLE (over-merging) ---

Existing IC: "combat_system_poor_quality"
  Definition: "Player criticises core combat mechanics as sluggish, unresponsive, or broken"

New candidate: "weapon_variety_lacking"
  Definition: "Player feels the weapon selection is too limited, lacking interesting options"
  Similarity: 0.78

BAD:  recommendation: MERGE → "combat_system_poor_quality"
WHY:  Both involve combat/weapons, but they describe DIFFERENT experiences:
      one is about mechanical quality (responsiveness, hit detection),
      the other is about content variety (number and diversity of weapons).
      Merging them would conflate two analytically distinct phenomena.
FIX:  recommendation: NEW
      reasoning: "Despite domain overlap (combat), these codes describe distinct
      experiential phenomena — mechanical quality vs. content variety."

RULE: Similar words or shared domain ≠ same meaning. Only merge when the codes
describe the SAME experiential phenomenon in different wording.

--- END EXAMPLE ---

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
4. SPECIFICITY OVER PARSIMONY — each theme should capture a SPECIFIC pattern of meaning, not a broad domain. Aim for 3–6 ICs per theme. A theme with 8+ ICs likely needs splitting into more specific sub-patterns. Your themes will later be grouped into higher-order categories — so create mid-level themes that capture distinct experiential phenomena, not domain-level groupings. Two themes CAN share the same domain (e.g., both about combat) if they describe distinct experiences.
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
Step 3: REDUNDANCY CHECK — review your draft themes pairwise. If two themes describe the SAME experiential phenomenon (not just the same domain), merge them. But themes in the same domain that capture DIFFERENT experiences should remain separate.
Step 4: COVERAGE CHECK — verify every IC is assigned to at least one theme. If an IC doesn't fit, consider whether it should form part of a broader theme rather than being left out.
Step 5: FINALISE — produce the output with short names, interpretive definitions, and rationale.

--- FEW-SHOT EXAMPLE ---

Given 18 ICs from negative game reviews:
  combat_sluggish, hit_detection_broken, weapon_durability_poor, parkour_unresponsive,
  map_design_empty, fast_travel_missing, quest_design_repetitive, story_predictable,
  npc_dialogue_poor, character_writing_shallow, price_too_high, short_game_length,
  sequel_downgrade, predecessor_nostalgia, graphics_positive, gore_system_fun,
  game_abandoned_early, conditional_recommendation

Step 1 (cluster): Combat ICs cluster (sluggish, hit_detection, weapon). Parkour+traversal cluster (parkour, map, fast_travel). Story+character cluster. Quest design is a separate experience. Price+length+abandonment cluster. Predecessor ICs cluster. Positive ICs cluster.
Step 2 (label): "Combat Responsiveness", "Traversal Frustrations", "Story & Character Depth", "Quest Repetition", "Price-Content Mismatch", "Player Abandonment", "Series Regression", "Redeeming Qualities"
Step 3 (redundancy): "Player Abandonment" (game_abandoned_early, conditional_recommendation) is a CONSEQUENCE of poor value — but it describes a DIFFERENT experience (quitting/warning others vs. feeling ripped off). Keep separate. "Quest Repetition" has only 1 IC — merge into "Story & Character Depth" → "Narrative & Quest Engagement". 7 themes now.
Step 4 (coverage): All 18 ICs assigned. Some ICs could appear in 2 themes (quest_design_repetitive could also relate to player abandonment).
Step 5 (finalise):

Theme 1: "Combat Responsiveness" (3 ICs)
  Definition: Core combat mechanics perceived as sluggish or unreliable, undermining moment-to-moment gameplay satisfaction.
  ICs: combat_sluggish, hit_detection_broken, weapon_durability_poor

Theme 2: "Traversal Frustrations" (3 ICs)
  Definition: Movement and navigation systems that fail to deliver fluid, enjoyable world exploration.
  ICs: parkour_unresponsive, map_design_empty, fast_travel_missing

Theme 3: "Narrative & Quest Engagement" (4 ICs)
  Definition: Story delivery, character writing, and quest structure perceived as shallow and failing to engage.
  ICs: quest_design_repetitive, story_predictable, npc_dialogue_poor, character_writing_shallow

Theme 4: "Price-Content Mismatch" (2 ICs)
  Definition: Perceived mismatch between purchase price and amount of content delivered.
  ICs: price_too_high, short_game_length

Theme 5: "Player Abandonment Signals" (2 ICs)
  Definition: Patterns of early quitting or conditional purchase advice indicating failed retention.
  ICs: game_abandoned_early, conditional_recommendation

Theme 6: "Series Regression" (2 ICs)
  Definition: Explicit comparison with predecessors framing the game as a step backward.
  ICs: sequel_downgrade, predecessor_nostalgia

Theme 7: "Redeeming Qualities" (2 ICs)
  Definition: Isolated positive elements acknowledged despite overall negative assessment.
  ICs: graphics_positive, gore_system_fun

NOTE: 7 themes for 18 ICs is appropriate. These themes will later be grouped into categories like "Core Mechanics", "Content & Value", "Comparative Assessment" etc.

--- NEGATIVE EXAMPLES (common synthesis errors) ---

ERROR 1 — Mixed-sentiment theme:
  BAD theme: "Combat Mechanics" containing:
    - combat_sluggish (negative)
    - hit_detection_broken (negative)
    - combat_visceral_satisfying (positive)
    - gore_system_fun (positive)
  WHY: This theme mixes negative combat criticism with positive combat praise.
       Analytically, "combat is broken" and "combat feels great" are OPPOSITE
       experiences that happen to share a domain. Grouping them into one theme
       hides the conflict and makes the theme uninterpretable.
  FIX: Split into two themes:
    - "Combat Responsiveness Issues" (combat_sluggish, hit_detection_broken)
    - "Satisfying Combat Feedback" (combat_visceral_satisfying, gore_system_fun)
  NOTE: Mixed-sentiment themes CAN be valid when ICs describe genuinely
        contested phenomena (e.g., "difficulty_too_high" + "difficulty_rewarding"
        could form "Difficulty Polarisation"). But this must be explicit and
        intentional, not accidental domain-level grouping.

ERROR 2 — Category-level grouping (too broad):
  BAD theme: "Technical Issues" containing:
    - framerate_drops, loading_times_long, crash_on_startup,
    - graphics_blurry, audio_glitches, save_corruption,
    - multiplayer_desync, server_downtime
  WHY: 8 ICs spanning frame rate, loading, crashes, graphics, audio, saves,
       and multiplayer. This is a CATEGORY (top-level domain), not a theme
       (specific experiential pattern). No shared meaning unites "blurry
       graphics" and "server downtime" except "they're both technical."
  FIX: Split into specific themes:
    - "Performance & Stability" (framerate_drops, crash_on_startup, loading_times_long)
    - "Audiovisual Polish" (graphics_blurry, audio_glitches)
    - "Multiplayer Reliability" (multiplayer_desync, server_downtime)
    - save_corruption might join "Performance & Stability" or a data integrity theme

--- END EXAMPLES ---

OUTPUT: Return a SynthesisOutput with:
- reasoning: brief chain-of-thought bullet-point notes for each step (max 200 words total). Do NOT write prose, do NOT enumerate every IC individually. One line per cluster group, one line per merge/split decision. Example format: "• Combat: combat_sluggish + hit_detection_broken + weapon_durability → 'Combat Responsiveness Issues' | • Traversal: parkour_unresponsive + map_design_empty + fast_travel_missing → 'Traversal Frustrations' | • REDUNDANCY: kept separate — same domain, different phenomena | • COVERAGE: all 18 ICs assigned"
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


# ── Distinctness Revision Prompts ─────────────────────────────────────────────


def build_distinctness_revision_system_prompt() -> str:
    """
    System prompt for the distinctness-aware revision pass.

    Called automatically after initial synthesis when overlapping theme
    pairs are detected (centroid similarity > threshold).
    """
    return """You are an expert qualitative researcher improving theme distinctness.

You will receive a set of themes and a list of overlapping pairs (themes whose centroids are too similar in embedding space). For each overlapping pair, decide:

1. MERGE — if the two themes describe the same underlying phenomenon, merge them into one theme. Combine their IC lists and write a unified definition.
2. SHARPEN — if the two themes describe genuinely different phenomena that happen to use similar language, rewrite both definitions to emphasise what makes each unique. Do NOT change IC assignments when sharpening — only refine the name and definition.

RULES:
- Address every flagged pair. Do not skip any.
- Themes NOT mentioned in the overlap list should remain EXACTLY unchanged (same name, definition, rationale, and IC list).
- After revision, every IC must still belong to at least one theme.
- Prefer SHARPEN over MERGE when the phenomena are analytically distinct.
- When merging, choose the more descriptive name or create a new one.
- In your reasoning, state your decision (MERGE or SHARPEN) for each pair and why.

OUTPUT: Return a DistinctnessRevisionOutput with all themes (revised + unchanged)."""


def build_distinctness_revision_user_prompt(
    themes: List[ThemeProposal],
    overlapping_pairs: List[tuple],
) -> str:
    """
    User prompt for distinctness revision — carries themes + overlapping pairs.
    """
    lines = [
        f"CURRENT THEMES ({len(themes)} themes):",
        "",
    ]

    for i, theme in enumerate(themes, 1):
        lines.append(f"  [{i}] {theme.name}")
        lines.append(f"      Definition: {theme.definition}")
        ics_str = ", ".join(theme.constituent_ic_names)
        lines.append(f"      ICs: {ics_str}")
        lines.append("")

    lines.append(f"OVERLAPPING PAIRS ({len(overlapping_pairs)} pairs with high centroid similarity):")
    lines.append("")

    for j, (name_a, name_b, sim) in enumerate(overlapping_pairs, 1):
        lines.append(f"  [{j}] \"{name_a}\" ↔ \"{name_b}\" (similarity: {sim:.3f})")

    lines.append("")
    lines.append("For each pair, decide: MERGE or SHARPEN. Return the full revised theme list.")
    return "\n".join(lines)


# ── Split Validation Prompts ──────────────────────────────────────────────


def build_split_validation_system_prompt() -> str:
    """
    System prompt for k-means split validation.

    Called when a magnet theme is flagged (high IC count, low coherence,
    many overlaps). The LLM decides whether the k-means split is meaningful.
    """
    return """You are an expert qualitative researcher evaluating whether a theme should be split.

You will receive:
1. A theme (name, definition, ICs) that has been flagged as potentially too broad
2. Two empirical clusters created by k-means on IC embeddings — these are statistically-derived groupings

Your task: Determine whether the two clusters represent genuinely DIFFERENT phenomena.

SPLIT if:
- The clusters describe distinct aspects of the experience (e.g., "combat mechanics" vs "combat balance")
- Each cluster tells a coherent story on its own
- A qualitative researcher would naturally separate these into different themes

DO NOT SPLIT if:
- The clusters are just different facets of the same phenomenon
- The split would create themes too narrow to be analytically useful (< 3 ICs each)
- The clustering is an artifact of vocabulary rather than meaning

If splitting: Propose two sub-theme names and definitions in the sub_themes field. You MAY reassign ICs between clusters if the k-means assignment is imperfect — use your semantic judgment. Every IC from the original theme must appear in exactly one sub-theme.
If not splitting: Set should_split=False, explain why in reasoning, and leave sub_themes as null."""


def build_split_validation_user_prompt(
    theme: ThemeProposal,
    cluster_a: List[str],
    cluster_b: List[str],
    ic_definitions: Dict[str, str],
) -> str:
    """
    User prompt for split validation — carries theme + two k-means clusters.
    """
    lines = [
        "THEME TO EVALUATE:",
        f"  Name: {theme.name}",
        f"  Definition: {theme.definition}",
        f"  Total ICs: {len(theme.constituent_ic_names)}",
        "",
        f"CLUSTER A ({len(cluster_a)} ICs):",
    ]

    for ic_name in cluster_a:
        defn = ic_definitions.get(ic_name, "(no definition)")
        lines.append(f"  - {ic_name}: {defn}")

    lines.append("")
    lines.append(f"CLUSTER B ({len(cluster_b)} ICs):")

    for ic_name in cluster_b:
        defn = ic_definitions.get(ic_name, "(no definition)")
        lines.append(f"  - {ic_name}: {defn}")

    lines.append("")
    lines.append("Should this theme be split into two sub-themes based on these clusters?")
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


# ── Layer 4: Analyst Intelligence Prompts ────────────────────────────────


def build_metrics_interpretation_system_prompt() -> str:
    """System prompt for Call 1: metrics interpretation."""
    return """You are a qualitative data analysis methodologist interpreting quality metrics from an automated thematic analysis pipeline (Braun & Clarke approach, LLM-assisted).

Your task: interpret each metric value in context. For each metric, you receive:
- The metric definition (what it measures and how)
- A guideline range (NOT a pass/fail threshold — a reference for what's typical)
- The observed value from this specific run

Your interpretation should:
1. State whether the value is within, near, or outside the guideline range
2. Explain what this means for the quality of this specific analysis
3. Consider contextual factors (sample size, data characteristics) that could explain the value
4. Avoid binary good/bad judgments — frame as "healthy", "worth monitoring", or "worth investigating"

Use the status field:
- "healthy" = within guideline range, no concerns
- "monitor" = borderline or slightly outside range, not alarming but worth noting
- "investigate" = clearly outside range, may indicate a real issue

IMPORTANT: These guidelines are calibration references, not rules. A value outside the guideline range is not automatically a problem — it may reflect the specific characteristics of this dataset. Your job is to interpret, not to judge."""


def build_metrics_interpretation_user_prompt(
    results: Dict,
    guidelines: AnalystGuidelinesConfig,
    run_summary: Dict,
) -> str:
    """
    User prompt for Call 1: carries metric values + guidelines.

    Args:
        results: results["layer3"] dict with all quality metrics
        guidelines: AnalystGuidelinesConfig with reference ranges
        run_summary: dict with n_documents, n_segments, n_ics
    """
    n_docs = run_summary.get('n_documents', '?')
    n_segs = run_summary.get('n_segments', '?')
    n_ics  = run_summary.get('n_ics', '?')
    n_themes = run_summary.get('n_themes', 0)
    n_cats = run_summary.get('n_categories', 0)

    lines = [
        f"Here are the quality metrics from a COMPLETE pipeline run.",
        f"Dataset: {n_docs} documents, {n_segs} segments, {n_ics} active ICs.",
    ]

    # Explicit run-stage context so the LLM knows synthesis IS done
    if n_themes:
        lines.append(
            f"Run stage: COMPLETE — all layers finished. "
            f"{n_themes} themes synthesized into {n_cats} categories. "
            f"All metrics below reflect the final state."
        )
    lines += [
        "",
        "── METRIC DEFINITIONS AND GUIDELINES ──",
        guidelines.to_prompt_block(),
        "",
        "── OBSERVED VALUES ──",
    ]

    # Grounding
    grounding = results.get("grounding", {})
    if grounding:
        lines.append(f"grounding_rate: {grounding.get('grounding_rate', 'N/A')}")

    # Drop rate (passed in run_summary since it comes from layer1, not layer3)
    drop_r = run_summary.get("drop_rate")
    if drop_r is not None:
        lines.append(f"drop_rate: {drop_r}")

    # Extraction density
    extraction = results.get("extraction_density", {})
    dist = extraction.get("distribution", {}) if isinstance(extraction, dict) else {}
    if dist:
        lines.append(f"extraction_density_mean: {dist.get('mean', 'N/A')}")

    # IC concentration
    ic_conc = results.get("ic_concentration", {})
    if ic_conc:
        lines.append(f"singleton_ratio: {ic_conc.get('singleton_ratio', 'N/A')}")

    # Merge rate — both overall and final batch for context
    merge = results.get("merge_rate", {})
    if merge:
        per_batch = merge.get("per_batch", [])
        overall = merge.get("overall_rate", "N/A")
        lines.append(f"merge_rate_overall: {overall}")
        if per_batch:
            lines.append(f"merge_rate_final_batch: {per_batch[-1]}")

    # Triage efficiency
    triage = results.get("triage_efficiency", {})
    if triage:
        lines.append(f"triage_auto_rate: {triage.get('efficiency', 'N/A')}")

    # ITS
    its_history = results.get("its_history", [])
    if its_history:
        last_its = its_history[-1]
        its_val = last_its.its_value if hasattr(last_its, 'its_value') else last_its.get('its_value', 'N/A')
        lines.append(f"its_final: {its_val}")

    # Theme coherence — flat dict {theme_name: float}, compute avg
    coherence = results.get("theme_coherence", {})
    if isinstance(coherence, dict) and coherence:
        coh_vals = [v for v in coherence.values() if isinstance(v, (int, float))]
        if coh_vals:
            coh_mean = sum(coh_vals) / len(coh_vals)
            lines.append(f"theme_coherence_mean: {coh_mean:.3f}")

    # Theme distinctness — list of [theme_a, theme_b, sim], compute avg + overlap count
    distinctness = results.get("theme_distinctness", [])
    if isinstance(distinctness, list) and distinctness:
        sims = [row[2] for row in distinctness if isinstance(row, (list, tuple)) and len(row) >= 3]
        if sims:
            avg_sim = sum(sims) / len(sims)
            overlap_count = sum(1 for s in sims if s > 0.70)
            lines.append(f"theme_distinctness_avg_sim: {avg_sim:.3f}")
            lines.append(f"theme_distinctness_overlapping_pairs: {overlap_count}")

    # Sentiment purity
    sentiment = results.get("sentiment_purity", {})
    if isinstance(sentiment, dict):
        lines.append(f"sentiment_purity_mean: {sentiment.get('avg_purity', 'N/A')}")
        flagged = sentiment.get("flagged_count")
        if flagged is not None:
            lines.append(f"sentiment_purity_flagged_themes: {flagged}")

    # Thematic coverage
    coverage = results.get("thematic_coverage", {})
    if isinstance(coverage, dict):
        lines.append(f"thematic_coverage: {coverage.get('coverage_ratio', 'N/A')}")

    # Cross-review convergence
    convergence = results.get("cross_review_convergence", {})
    if isinstance(convergence, dict):
        lines.append(f"cross_review_convergence: {convergence.get('confirmed_ratio', 'N/A')}")

    # IC stability
    stability = results.get("ic_stability", {})
    if isinstance(stability, dict):
        lines.append(f"ic_stability_mean: {stability.get('mean_stability', 'N/A')}")

    # Additional context
    lines.append("")
    lines.append("── ADDITIONAL CONTEXT ──")
    if merge and merge.get("per_batch"):
        lines.append(f"Batch merge rate progression: {merge['per_batch']}")
    if its_history:
        recent = its_history[-3:] if len(its_history) >= 3 else its_history
        its_vals = [
            h.its_value if hasattr(h, 'its_value') else h.get('its_value', 0)
            for h in recent
        ]
        lines.append(f"ITS history (last {len(recent)} batches): {its_vals}")

    lines.append("")
    lines.append("Interpret each metric and provide an overall data quality assessment.")
    return "\n".join(lines)


def build_structural_diagnostics_system_prompt() -> str:
    """System prompt for Call 2: structural diagnostics."""
    return """You are a qualitative data analyst evaluating the thematic structure produced by an automated Braun & Clarke thematic analysis pipeline.

You receive the full Category → Theme → IC hierarchy with evidence counts and coherence data.
Your task: assess the quality and coherence of this structure.

TIERED ASSESSMENT — use different detail levels:

HEALTHY themes (coherence ≥0.55, sufficient evidence, no issues):
  → One-line assessment only: "Well-evidenced, coherent, no action needed."
  Do NOT write paragraphs for healthy themes.

FLAGGED themes (low coherence, low evidence, magnet, sentiment mixed):
  → Full assessment paragraph + concrete suggested_action.
  Explain what's wrong, why, and what to do about it.

For flagged themes, evaluate:
1. Is the theme well-defined? Does the name accurately capture its ICs?
2. Is there sufficient evidence (quote count)?
3. Are the ICs cohesive (do they belong together)?
4. Is there a sentiment mixing issue?
5. Is this a "magnet theme" (too many unrelated ICs, low coherence)?

For each category, evaluate:
1. Do the themes within it form a coherent grouping?
2. Is the category too broad (catch-all) or too narrow (single theme)?

Identify the strongest themes (well-evidenced, coherent, clearly defined) and weakest themes (sparse evidence, low coherence, unclear boundaries).

IMPORTANT: Be concise. The structural_summary at the end should highlight only the most critical structural issues and 2-3 top recommendations. Do not repeat individual theme assessments."""


def build_structural_diagnostics_user_prompt(
    thematic_structure: List[Dict],
    layer2_results: Dict,
    coherence_data: Dict,
) -> str:
    """
    User prompt for Call 2: carries thematic structure + coherence data.

    Args:
        thematic_structure: results["thematic_structure"] — category/theme/IC hierarchy
        layer2_results: results["layer2"] with synthesis stats
        coherence_data: coherence and distinctness metrics from layer3
    """
    lines = ["── THEMATIC STRUCTURE ──", ""]

    for cat in thematic_structure:
        cat_name = cat.get("name", "Unknown")
        cat_def = cat.get("definition", "")
        lines.append(f"CATEGORY: {cat_name} ({cat_def})")

        for theme in cat.get("themes", []):
            t_name = theme.get("name", "Unknown")
            t_def = theme.get("definition", "")
            lines.append(f"  THEME: {t_name} ({t_def})")

            # Per-theme coherence if available
            # theme_coherence is a flat {theme_name: float} dict — no "per_theme" nesting
            per_theme_coh = coherence_data.get("theme_coherence", {})
            if t_name in per_theme_coh:
                lines.append(f"    Coherence: {per_theme_coh[t_name]:.3f}")

            # Per-theme sentiment purity if available
            # sentiment_purity["per_theme"][name] is a dict {purity, dominant, ...} — extract float
            per_theme_sent = coherence_data.get("sentiment_purity", {}).get("per_theme", {})
            if t_name in per_theme_sent:
                sent_entry = per_theme_sent[t_name]
                purity_val = sent_entry["purity"] if isinstance(sent_entry, dict) else sent_entry
                lines.append(f"    Sentiment purity: {purity_val:.3f}")

            ics = theme.get("initial_codes", [])
            lines.append(f"    ICs ({len(ics)}):")
            for ic in ics:
                ic_name = ic.get("name", "?")
                ic_def = ic.get("definition", "")
                qcount = ic.get("quote_count", 0)
                lines.append(f"      - {ic_name}: {ic_def} [{qcount} quotes]")

                # Include up to 2 example quotes (truncated)
                quotes = ic.get("quotes", [])
                for q in quotes[:2]:
                    q_text = q.get("quote_text", "")[:100]
                    lines.append(f"        Example: \"{q_text}\"")

            lines.append("")

    # Layer 2 summary
    lines.append("── LAYER 2 SUMMARY ──")
    lines.append(f"Themes proposed: {layer2_results.get('themes_proposed', '?')}")
    lines.append(f"Themes after refinement: {layer2_results.get('themes_after_refinement', '?')}")
    dissolved = layer2_results.get("dissolved_theme_names", [])
    if dissolved:
        lines.append(f"Themes dissolved (coherence gate): {', '.join(dissolved)}")
    lines.append(f"ICs redistributed: {layer2_results.get('ics_redistributed', 0)}")
    lines.append(f"ICs unassigned: {layer2_results.get('ics_unassigned', 0)}")

    # Coherence details — theme_coherence is flat {theme_name: float}
    lines.append("")
    lines.append("── COHERENCE DETAILS ──")
    per_theme_coh = coherence_data.get("theme_coherence", {})
    if per_theme_coh:
        # Guard: skip non-numeric values (defensive against nested dicts)
        numeric_items = [(k, v) for k, v in per_theme_coh.items() if isinstance(v, (int, float))]
        for name, score in sorted(numeric_items, key=lambda x: x[1]):
            lines.append(f"  {name}: {score:.3f}")

    distinctness = coherence_data.get("theme_distinctness", {})
    overlap_pairs = distinctness.get("overlapping_pairs", []) if isinstance(distinctness, dict) else []
    if overlap_pairs:
        lines.append("")
        lines.append(f"Overlapping theme pairs ({len(overlap_pairs)}):")
        for pair in overlap_pairs[:10]:  # limit to top 10
            if isinstance(pair, (list, tuple)) and len(pair) >= 3:
                lines.append(f"  \"{pair[0]}\" ↔ \"{pair[1]}\" (sim={pair[2]:.3f})")

    lines.append("")
    lines.append("Assess the thematic structure. Be specific about each theme.")
    return "\n".join(lines)


def build_analyst_synthesis_system_prompt() -> str:
    """System prompt for Call 3: synthesis and recommendations."""
    return """You are a senior research methodologist providing final recommendations for a qualitative data analysis pipeline run.

You receive:
1. A metrics interpretation (from a colleague who analysed the quality metrics)
2. A structural diagnostics report (from a colleague who analysed the thematic structure)
3. The pipeline configuration used for this run

Your task: synthesise these into actionable guidance.

CRITICAL: DO NOT repeat or restate information from the metrics or structural reports. The user has already read those. Your job is to SYNTHESISE — find insights that only emerge when combining both perspectives.

Output structure:

1. overall_assessment (3-5 sentences MAX): Headline verdict on the run's quality and trustworthiness. Do NOT re-list individual metric values — the user has them. State the conclusion, not the evidence.

2. key_findings (3-5 items): Only insights that emerge from COMBINING metrics + structure. Bad: "singleton ratio is 57%" (that's just restating a metric). Good: "High singleton ratio combined with catch-all categories suggests the pipeline is creating narrow ICs that don't aggregate well — the issue is triage thresholds, not data volume."

3. config_recommendations: Specific parameter changes with rationale. Each entry should name the parameter, its current value, a suggested value, and a brief rationale.

4. next_steps (3-5 items, priority-ordered): Concrete actions. Interleave config changes with analytical actions. Each step should be actionable in one work session.

5. confidence_note (2-3 sentences MAX): What caveats should the analyst keep in mind? Do NOT repeat the overall assessment.

Be concrete and actionable. Avoid vague recommendations. The entire synthesis should be substantially SHORTER than the metrics + structural reports combined."""


def build_analyst_synthesis_user_prompt(
    metrics_interp: Dict,
    structural_diag: Dict,
    config_summary: Dict,
    run_summary: Dict,
) -> str:
    """
    User prompt for Call 3: carries outputs of Call 1 + Call 2 + config.

    Args:
        metrics_interp: MetricsInterpretation.model_dump()
        structural_diag: StructuralDiagnostics.model_dump()
        config_summary: relevant config values
        run_summary: pipeline run summary
    """
    lines = ["── METRICS INTERPRETATION ──", ""]

    # Format metrics assessments
    for assessment in metrics_interp.get("assessments", []):
        status = assessment.get("status", "?").upper()
        lines.append(
            f"  {assessment.get('metric_name', '?')}: "
            f"{assessment.get('observed_value', '?')} [{status}]"
        )
        lines.append(f"    {assessment.get('interpretation', '')}")
        ctx = assessment.get("context_factors")
        if ctx:
            lines.append(f"    Context: {ctx}")

    lines.append("")
    lines.append(f"Data quality summary: {metrics_interp.get('data_quality_summary', 'N/A')}")
    lines.append(f"Saturation assessment: {metrics_interp.get('saturation_assessment', 'N/A')}")

    lines.append("")
    lines.append("── STRUCTURAL DIAGNOSTICS ──")
    lines.append("")
    lines.append(f"Strongest themes: {structural_diag.get('strongest_themes', [])}")
    lines.append(f"Weakest themes: {structural_diag.get('weakest_themes', [])}")
    lines.append("")

    for diag in structural_diag.get("theme_diagnostics", []):
        issue = diag.get("issue_type", "healthy")
        lines.append(
            f"  {diag.get('theme_name', '?')} ({diag.get('ic_count', 0)} ICs) — {issue}"
        )
        lines.append(f"    {diag.get('assessment', '')}")
        action = diag.get("suggested_action")
        if action:
            lines.append(f"    Action: {action}")

    lines.append("")
    lines.append(f"Structural summary: {structural_diag.get('structural_summary', 'N/A')}")

    # Config
    lines.append("")
    lines.append("── CURRENT CONFIGURATION ──")
    for k, v in config_summary.items():
        lines.append(f"  {k}: {v}")

    # Run summary
    lines.append("")
    lines.append("── RUN SUMMARY ──")
    for k, v in run_summary.items():
        lines.append(f"  {k}: {v}")

    lines.append("")
    lines.append("Synthesise the analysis and provide concrete recommendations.")
    return "\n".join(lines)
