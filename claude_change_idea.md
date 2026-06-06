# Proposed Enhancements for EQD-AI

This document outlines several potential evolutionary directions for the EQD-AI pipeline to increase its analytical depth and objectivity.

## 1. Counter-Narrative Agent (Adwokat Diabła)
**Goal:** Mitigate confirmation bias in both LLM synthesis and human interpretation.
**Mechanism:** An agent tasked with actively searching for "anomalies" and "minority voices" that contradict the dominant themes identified in the pipeline.
**Value:** Increases objectivity and prevents overly homogenized results.

## 2. Relational Knowledge Graph
**Goal:** Move beyond hierarchical structures (IC -> Theme -> Category) to capture complex relationships.
**Mechanism:** Implementing a graph-based model that identifies relationships such as `[Problem] --(causes)--> [Emotion]` or `[Feature] --(leads to)--> [Behavior]`.
**Value:** Enables much deeper interpretive reporting (L4) about how phenomena interact.

## 3. Hypothesis-to-Validation Loop
**Goal:** Transform the pipeline from a passive tool to an active research assistant.
**Mechanism:** Automatically generating hypotheses from Layer 4 analysis and suggesting specific "Validation" or "Saturation" runs to confirm or refute them.
**Value:** Creates a proactive research workflow.

## 4. Multimodal Evidence Integration
**Goal:** Leverage non-textual data (e.g., Steam screenshots) to improve grounding.
**Mechanism:** Using vision-capable models to verify if visual evidence matches the text-based Initial Codes (ICs).
**Value:** Dramatically improves the `Grounding` metric and provides more robust technical evidence.
