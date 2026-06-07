"""
EQD-AI v2 Prompt Templates — Layer 1 (Evidence Extraction).

All prompts for the Coder Agent and Codebook Comparator, plus IC definition
refinement. Pure f-string functions — no Jinja2 needed for our templates.

Design: prompts are functions (easy to test, iterate, A/B test).
System prompts encode methodology; user prompts carry data.
"""

from __future__ import annotations

from typing import List, Tuple

from src.core.models import InitialCode


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
    - Verbatim evidence (quote text only — the system computes offsets)
    - Few-shot example for calibrating granularity
    """
    return f"""You are an expert qualitative coder performing inductive thematic analysis (Braun & Clarke, 2006).

YOUR TASK: Read a text segment and extract Initial Codes (ICs). Each IC captures a distinct meaning unit in the text.

METHODOLOGY PRINCIPLES:
1. STAY CLOSE TO DATA — codes describe what the text explicitly says, not what it implies or what you infer. No interpretive leaps.
2. EXACT VERBATIM QUOTES — every code MUST include a quote_text that is an EXACT, character-for-character substring of the segment. Copy it verbatim: do NOT paraphrase, fix typos, normalise whitespace, merge non-adjacent fragments, or insert ellipses (...). You do NOT provide character offsets — the system locates your quote in the text automatically. If the quote you write is not found verbatim, the code is discarded.
3. MATCH EXISTING CODES — if the segment expresses a meaning already captured by an existing code in the codebook, set existing_code_match to that code's name. Do NOT create duplicates.
4. PROPOSE NEW CODES — if the segment expresses a meaning NOT in the codebook, set existing_code_match to null. Give the new code a clear, descriptive name.
5. DON'T FORCE CODES — if a segment (or part of it) has no analytically meaningful content, extract fewer codes or none. Quality over quantity.
6. ONE QUOTE PER CODE — each candidate gets exactly one verbatim quote. If multiple quotes support the same code, pick the most representative one.
7. PREFER BROADER CODES — do NOT create separate codes for every sentence. Look for the broader meaning units. A single review with 5 complaints about different aspects of combat should yield 1-2 combat-related codes, not 5. Aim for 2-5 codes per segment. More than 7 is almost always over-coding.
8. NO META-COMMENTARY — Do not extract codes about the overall verdict, the discourse around the product, or other reviewers' opinions. Codes must describe SPECIFIC aspects of the product experience. Bad: "biggest_disappointment_2025", "glowing_reviews_undeserved" Good: "combat_system_repetitive", "price_not_justified_for_content"
9. SPECIFICITY MATCHES THE TEXT — Be as specific as the text allows, no more. If the segment identifies a specific system or feature, name it. If the segment expresses general dissatisfaction without identifying specific causes, create an IC that captures the general nature of the experience — never fabricate specifics that aren't in the text.
10. ASSESS SENTIMENT — For each IC, assess the sentiment of the verbatim quote: positive, negative, neutral, or mixed. Sentiment is determined by what the quote expresses, not by the overall tone of the review. A negative review can contain positive quotes ("the graphics are great") and vice versa.
11. ASSESS NOVELTY CONFIDENCE — Rate confidence (0.0–1.0) as: how certain are you that this concept is NOT already captured by any existing IC in the current codebook?
    - 1.0 = Clearly new; no existing IC comes close
    - 0.7–0.9 = Probably new, but some thematic overlap with existing codes
    - 0.5 = Uncertain — could plausibly be merged with an existing code
    - 0.0–0.4 = Almost certainly overlapping with an existing IC
    When the codebook is empty, default to 0.9.

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
   confidence: 0.9  # codebook empty → clearly new; specific system named
   sentiment: negative

2. ic_name: "sequel_downgrade_from_predecessor"
   definition: "Player perceives the sequel as significantly worse than the original game"
   quote_text: "I loved the first game but this sequel is a massive downgrade"
   confidence: 0.75  # codebook has combat code; this is different but franchise comparison could overlap
   sentiment: negative

3. ic_name: "graphics_positive_assessment"
   definition: "Player praises the visual quality as the only positive aspect"
   quote_text: "The only good thing is the graphics which are genuinely impressive"
   confidence: 0.9  # clearly distinct from combat/sequel codes
   sentiment: positive

4. ic_name: "negative_purchase_recommendation"
   definition: "Player explicitly warns others against buying the game"
   quote_text: "Don't waste your money on this"
   confidence: 0.9  # clearly distinct; no purchase-advice code exists
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
- candidates: list of code candidates, each with ic_name, definition, an exact verbatim quote_text, confidence, and sentiment (positive/negative/neutral/mixed). No character offsets. May be empty if no meaningful codes found."""



def build_coder_user_prompt(segment_id: str, canonical_text: str) -> str:
    """
    User prompt for the Coder Agent — single segment mode.

    Includes the segment ID and full canonical text. Quotes must be copied
    verbatim from this text — the system locates them; no offsets are needed.
    """
    return f"""Segment ID: {segment_id}

SEGMENT TEXT (copy any quote_text verbatim, character-for-character, from this exact text):
---
{canonical_text}
---

Extract all Initial Codes from this segment. Return a SegmentCodingResult."""



# ── Codebook Comparator Prompts ──────────────────────────────────────────────

def build_comparator_system_prompt() -> str:
    """
    System prompt for the Codebook Comparator (v2 — single decision track).

    Focused task: compare a new IC candidate against the most similar existing
    ICs and recommend ONE action. In v2 there are no operating thresholds — every
    candidate (against a non-empty codebook) is judged here by the LLM. The
    embedding only supplies the top-k shortlist; the decision is the model's.
    """
    return """You are a qualitative coding expert reviewing a new Initial Code (IC) candidate for inclusion in an evolving codebook.

YOUR TASK: Compare the new candidate against the most similar existing codes and recommend ONE action.

RECOMMENDATIONS:
- NEW: The candidate captures a distinct meaning not covered by any existing code. Add it to the codebook.
- MERGE: The candidate is semantically equivalent to an existing code — same meaning, just different wording, or a meaningful specialisation that doesn't warrant a separate code. Specify which code to merge into via merge_target_name.
- REJECT: The candidate is too vague, not grounded in data, or genuinely redundant with no added value.

DECISION CRITERIA:
- Merge only when the codes describe the SAME experiential phenomenon — same meaning
  in different wording, or a specialisation that doesn't warrant its own code.
- Keep NEW when the candidate extends meaningfully beyond every neighbour, even if it
  shares vocabulary or domain with them.
- Consider: do the codes describe the SAME experience from DIFFERENT angles, or DIFFERENT
  experiences that happen to share vocabulary?

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

    Structure: candidate first (establish what we're evaluating), then the
    scored neighbours as the primary comparison signal, then the decision
    question that ties scores to action.

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
        lines.append("MOST SIMILAR EXISTING CODES: (none — codebook is empty)")
        lines.append("")
        lines.append("Decision: this is a NEW code by default (no existing codes to compare against).")
    else:
        lines.append(f"TOP-{len(top_k)} MOST SIMILAR EXISTING CODES (ranked by embedding similarity):")
        for i, (ic_id, name, definition, sim) in enumerate(top_k, 1):
            lines.append(f"  [{i}] {name}  (similarity: {sim:.3f})")
            lines.append(f"      Definition: {definition}")
        lines.append("")
        lines.append("---")
        lines.append("Does the candidate describe the SAME experiential phenomenon as any of the")
        lines.append("codes above (→ MERGE), a DISTINCT phenomenon not captured above (→ NEW),")
        lines.append("or is it too vague / redundant to include (→ REJECT)?")
        lines.append("Use the similarity scores and definitions as your primary signal.")

    lines.append("")
    lines.append("Return a ComparatorOutput with your recommendation and brief reasoning.")
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

