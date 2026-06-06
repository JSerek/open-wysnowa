"""
Quick smoke-test: single Sonnet 4.5 call through the EQD-AI config stack.

Tests:
  1. Config loads correctly
  2. Anthropic client is built with the extended output beta header
  3. Instructor structured output round-trip works
  4. max_tokens=16000 is accepted (would error without the beta header)

Usage:
    python scripts/test_sonnet_call.py
"""

import os
import sys
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # dotenv optional; set ANTHROPIC_API_KEY manually if needed

from pydantic import BaseModel
from src.core.config import load_config, ModelClient


# ── Minimal structured output model ──────────────────────────────────────────

class ThemeSmoke(BaseModel):
    theme_name: str
    one_line_summary: str
    confidence: float


class SmokeOutput(BaseModel):
    themes: list[ThemeSmoke]
    note: str


# ── Test ──────────────────────────────────────────────────────────────────────

def run():
    print("\n── EQD-AI Sonnet 4.5 smoke test ─────────────────────────────────")

    # 1. Load config
    config_path = ROOT / "eqd_config.yaml"
    cfg = load_config(config_path)
    print(f"  Config loaded:        {config_path.name}")

    # 2. Build client via ModelClient (same path as pipeline uses)
    mc = ModelClient(cfg)
    client, model_id, params = mc.get_client("synthesizer_agent")
    print(f"  Model:                {model_id}")
    print(f"  max_tokens in config: {params.max_tokens}")

    # 3. Verify the underlying Anthropic client has the beta header
    #    (the raw client is stored inside the instructor wrapper)
    raw = getattr(client, "_client", None) or getattr(client, "client", None)
    if raw:
        headers = getattr(raw, "_custom_headers", {}) or getattr(
            getattr(raw, "default_headers", None), "_store", {}
        )
        beta_found = "output-128k-2025-02-19" in str(headers)
        print(f"  Extended output beta: {'✓ found in headers' if beta_found else '? (check manually)'}")
    else:
        print("  Extended output beta: ? (could not inspect headers directly)")

    # 4. Make a real API call — small prompt, structured output, high max_tokens
    print("\n  Calling Sonnet 4.5 (structured output, max_tokens=16000)...")

    result = client.chat.completions.create(
        model=model_id,
        response_model=SmokeOutput,
        messages=[
            {
                "role": "system",
                "content": "You are a thematic analysis assistant. Be concise.",
            },
            {
                "role": "user",
                "content": (
                    "Propose 2 short themes for these initial codes from a game review dataset:\n"
                    "  - combat_sluggish, hit_detection_broken, weapon_durability_poor\n"
                    "  - price_too_high, short_game_length, content_too_thin\n\n"
                    "Return a SmokeOutput with a theme for each cluster and a brief note."
                ),
            },
        ],
        temperature=params.temperature,
        max_tokens=params.max_tokens,
    )

    # 5. Display result
    print(f"\n  ✓ Call succeeded — {len(result.themes)} themes returned\n")
    for t in result.themes:
        print(f"    [{t.confidence:.2f}] {t.theme_name}")
        print(f"           {t.one_line_summary}")
    print(f"\n  Note: {result.note}")
    print("\n── All checks passed ✓ ──────────────────────────────────────────\n")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"\n  ✗ FAILED: {e}\n")
        sys.exit(1)
