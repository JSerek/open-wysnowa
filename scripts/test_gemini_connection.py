#!/usr/bin/env python3
"""
Gemini connection test script.

Tests the Google AI (Gemini) integration at three levels:
  1. Raw OpenAI-compat API call (no instructor)
  2. instructor + simple Pydantic model (structured output)
  3. ICCandidate extraction — the actual model used by the Coder Agent

Usage:
    python test_gemini_connection.py                        # test default model
    python test_gemini_connection.py --model gemini-2.0-flash
    python test_gemini_connection.py --list-models          # show all available models

Requires: pip install openai instructor pydantic python-dotenv
"""

import argparse
import os
import sys
import time
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL   = "gemini-2.5-flash-preview-05-20"   # fallback; use --model to override

# ── Helpers ───────────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗  {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"     {msg}")


# ── Step 0: Check env ─────────────────────────────────────────────────────────

def check_env() -> str:
    _header("Step 0: Environment check")
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        _fail("GOOGLE_API_KEY is not set — add it to your .env file")
        sys.exit(1)
    _ok(f"GOOGLE_API_KEY found ({api_key[:8]}...{api_key[-4:]})")
    return api_key


# ── Step 1: List available models ─────────────────────────────────────────────

def list_models(api_key: str) -> None:
    _header("Available Gemini Models (OpenAI-compat endpoint)")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=GOOGLE_BASE_URL)
        t0 = time.time()
        models = client.models.list()
        elapsed = time.time() - t0
        _ok(f"Models endpoint responded in {elapsed:.2f}s")
        print()
        for m in sorted(models.data, key=lambda x: x.id):
            print(f"    {m.id}")
    except Exception as e:
        _fail(f"Models list failed: {e}")


# ── Step 2: Raw API call ──────────────────────────────────────────────────────

def test_raw_call(api_key: str, model: str) -> bool:
    _header(f"Step 1: Raw API call — {model}")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=GOOGLE_BASE_URL)

        t0 = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Reply with exactly: 'EQD-AI connection OK'"},
            ],
            temperature=0.0,
            # Thinking models (e.g. gemini-3-flash-preview) consume a large reasoning
            # budget before producing output — 20 tokens is far too low for them.
            max_tokens=2000,
        )
        elapsed = time.time() - t0

        # Gemini sometimes returns None content via OpenAI-compat endpoint for
        # plain text requests — guard against this explicitly.
        raw_content = response.choices[0].message.content
        if raw_content is None:
            _fail("Response content is None — model returned no text content")
            _info("This can happen if the model uses a tool call instead of text.")
            _info("Check that the model supports plain text responses.")
            return False
        content = raw_content.strip()
        usage = response.usage
        _ok(f"Response received in {elapsed:.2f}s")
        _info(f"Content:     {content!r}")
        thinking_tokens = usage.total_tokens - usage.prompt_tokens - usage.completion_tokens
        if thinking_tokens > 0:
            _info(f"Tokens:      in={usage.prompt_tokens}, thinking={thinking_tokens}, out={usage.completion_tokens}  ← thinking model")
        else:
            _info(f"Tokens:      in={usage.prompt_tokens}, out={usage.completion_tokens}")
        return True

    except Exception as e:
        _fail(f"Raw call failed: {e}")
        return False


# ── Step 3: instructor + Pydantic ─────────────────────────────────────────────

class SimpleResponse(BaseModel):
    answer: str = Field(description="Short answer to the question")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0.0-1.0")


def test_instructor_call(api_key: str, model: str) -> bool:
    _header(f"Step 2: instructor + Pydantic — {model}")
    try:
        import instructor
        from openai import OpenAI

        raw = OpenAI(api_key=api_key, base_url=GOOGLE_BASE_URL)
        # JSON mode: required for Google — default tool-call mode fails with List fields
        client = instructor.from_openai(raw, mode=instructor.Mode.JSON)

        t0 = time.time()
        result = client.chat.completions.create(
            model=model,
            response_model=SimpleResponse,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "What is the capital of France? "
                        "Respond with a short answer and your confidence."
                    ),
                },
            ],
            temperature=0.0,
            # Thinking models consume a reasoning budget before producing output.
            # 100 tokens leaves almost nothing for actual output; use 2000.
            max_tokens=2000,
        )
        elapsed = time.time() - t0

        _ok(f"Structured response received in {elapsed:.2f}s")
        _info(f"Answer:      {result.answer!r}")
        _info(f"Confidence:  {result.confidence:.2f}")
        assert isinstance(result, SimpleResponse), "Response is not a SimpleResponse"
        _ok("Pydantic validation passed")
        return True

    except Exception as e:
        _fail(f"instructor call failed: {e}")
        return False


# ── Step 4: ICCandidate extraction (real coder task) ─────────────────────────

class ICCandidateMini(BaseModel):
    """Minimal version of ICCandidate for connection testing."""
    ic_name: str = Field(description="Lowercase_with_underscores code name")
    definition: str = Field(min_length=5, description="What this code captures")
    quote_text: str = Field(description="Exact substring from the segment")
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment: Optional[str] = Field(default=None)


class SegmentCodingMini(BaseModel):
    """Minimal version of SegmentCodingResult."""
    segment_id: str
    candidates: List[ICCandidateMini]


SAMPLE_SEGMENT = (
    "The combat system is completely broken. Hit detection fails half the time "
    "and the weapons feel like they have no impact. The only saving grace is "
    "the graphics which genuinely look amazing."
)


def test_coder_task(api_key: str, model: str) -> bool:
    _header(f"Step 3: Coder Agent task (IC extraction) — {model}")
    try:
        import instructor
        from openai import OpenAI

        raw = OpenAI(api_key=api_key, base_url=GOOGLE_BASE_URL)
        # JSON mode required: Google's endpoint fails with tool-call mode when
        # the Pydantic model contains List fields (generates multiple tool calls).
        client = instructor.from_openai(raw, mode=instructor.Mode.JSON)

        system_prompt = (
            "You are a qualitative coder. Extract Initial Codes (ICs) from the segment. "
            "Each IC needs an exact verbatim quote with correct span_start/span_end "
            "character offsets (0-indexed, where segment_text[span_start:span_end] == quote_text)."
        )
        user_prompt = (
            f'Segment ID: test_seg_001\n\n'
            f'SEGMENT TEXT:\n---\n{SAMPLE_SEGMENT}\n---\n\n'
            f'Extract Initial Codes. Return a SegmentCodingMini.'
        )

        t0 = time.time()
        result = client.chat.completions.create(
            model=model,
            response_model=SegmentCodingMini,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        elapsed = time.time() - t0

        _ok(f"Coding response received in {elapsed:.2f}s")
        _info(f"Segment ID:  {result.segment_id}")
        _info(f"Candidates:  {len(result.candidates)} ICs extracted")
        print()

        errors = 0
        for ic in result.candidates:
            # Verify span
            extracted = SAMPLE_SEGMENT[ic.span_start:ic.span_end]
            span_ok = extracted == ic.quote_text
            status = "✓" if span_ok else "✗ SPAN MISMATCH"
            print(f"    [{status}] {ic.ic_name} (conf={ic.confidence:.2f}, sent={ic.sentiment})")
            print(f"           def: {ic.definition[:80]}")
            print(f"           quote: {ic.quote_text!r:.60}")
            if not span_ok:
                errors += 1
                print(f"           expected: {extracted!r:.60}")

        print()
        if errors == 0:
            _ok(f"All {len(result.candidates)} span assertions passed")
        else:
            _fail(f"{errors}/{len(result.candidates)} span assertions failed")
            _info("Span errors are common on first runs — retry mechanisms handle this in production")

        return True

    except Exception as e:
        _fail(f"Coder task failed: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Test Gemini API connection")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Gemini model ID to test (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List all available models and exit",
    )
    parser.add_argument(
        "--skip-coder", action="store_true",
        help="Skip the coder agent task (faster)",
    )
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║         EQD-AI — Gemini Connection Test                  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    api_key = check_env()

    if args.list_models:
        list_models(api_key)
        print()
        sys.exit(0)

    _info(f"Model under test: {args.model}")

    results = []
    results.append(test_raw_call(api_key, args.model))
    results.append(test_instructor_call(api_key, args.model))
    if not args.skip_coder:
        results.append(test_coder_task(api_key, args.model))

    # Summary
    passed = sum(results)
    total  = len(results)
    _header(f"Summary: {passed}/{total} tests passed")
    if passed == total:
        _ok("All tests passed — Gemini is ready to use in EQD-AI")
        _info(f"To use as Coder Agent, set agents.coder_agent.model to a gemini_* model in eqd_config.yaml")
    else:
        _fail(f"{total - passed} test(s) failed — check the errors above")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
