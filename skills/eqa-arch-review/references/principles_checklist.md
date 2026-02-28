# EQD-AI Design Principles — Review Checklist

Quick-reference for evaluating architecture proposals.
Full text: `eqa_ai/DESIGN_PRINCIPLES.md`

---

## P1 — Raw data is immutable after extraction
**Test:** Does the proposal mutate ICs, VerbatimQuotes, or Segments after
Layer 1 creates them?
- ✅ OK: reads, references, new versions alongside old ones
- ❌ Violation: in-place update of IC definitions, quote text, segment canonical_text

**Severity: CRITICAL** — violates analytical integrity. Reject without strong justification.

---

## P2 — Every transformation must be traceable
**Test:** Can you reconstruct "how did we get here" from the audit trail?
- ✅ OK: new log entry, new version, decision_logs updated
- ❌ Violation: silent mutation, opaque batch operations with no record

**Severity: CRITICAL** — kills reproducibility. Reject without strong justification.

---

## P3 — Bottom-up first, interpretation second
**Test:** Does the proposal impose structure before data speaks (Layers 1-3)?
- ✅ OK: any Layer 4+ reframing, analyst-driven lenses, explicit overlays
- ❌ Violation: seed themes in Layer 1, predefined category lists fed into synthesis

**Severity: HIGH** — compromises discovery. Can be accepted if strictly isolated to Layer 4+.

---

## P4 — Human judgment is irreplaceable
**Test:** Does the proposal remove a meaningful HIL checkpoint, or automate
a decision that requires analyst domain knowledge?
- ✅ OK: adding HIL, making HIL optional with --no-hil flag
- ❌ Violation: auto-approving codebook sign-off, removing analyst synthesis gate

**Severity: MEDIUM** — assess whether the automated decision is truly deterministic.

---

## P5 — Non-destructive iteration over replacement
**Test:** Does the proposal delete, overwrite, or lose prior state?
- ✅ OK: new version alongside old, archive flag, explicit user confirmation
- ❌ Violation: overwrite without versioning, delete without trace

**Severity: CRITICAL** — reject unless paired with an explicit versioning mechanism.

---

## P6 — Provider agnosticism as a structural hedge
**Test:** Does the proposal couple implementation to a specific LLM provider?
- ✅ OK: provider-specific handling in config.py client factory only
- ❌ Violation: OpenAI-specific API call in a pipeline layer, Anthropic SDK import in orchestrator

**Severity: MEDIUM** — can accept if isolated to config/factory; reject if it leaks into layers.

---

## P7 — The pipeline must be transparent
**Test:** Can a human reading terminal output understand what happened?
- ✅ OK: explicit logging, graceful degradation with log warning
- ❌ Violation: silent failure, skipped layer with no log entry, opaque LLM call

**Severity: LOW-MEDIUM** — rarely a hard reject; usually a "fix the logging" note.

---

## Rating Guide

| Rating | When to use |
|--------|-------------|
| ✅ Accept | No principle conflicts; or conflict is minor and contained |
| 🔜 Defer | Direction is right, but timing/dependencies wrong; add to IDEAS.md [design] |
| ❌ Reject | Conflicts with P1, P2, or P5 (critical); or conflicts with P3/P4/P6/P7 and no mitigation is possible |

**Defer ≠ Reject.** Defer means "right idea, wrong sprint." Always state the precondition.
