"""
OpenRouter connectivity + instructor compliance check.

Tests two things:
  1. Can we reach OpenRouter at all (auth works, key is valid)?
  2. Do the configured models return valid structured output via instructor?

Usage:
  .venv/bin/python scripts/test_openrouter.py

Requires OPENROUTER_API_KEY in .env (same as the full pipeline).
No DB, no embeddings, no pipeline code — pure API smoke test.

Cost: ~1–2 API calls per model, trivially cheap (~$0.001 total).
"""

import os
import sys
import json
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────
# Simple manual load — avoids pulling in dotenv if not installed.
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# ── Imports ───────────────────────────────────────────────────────────────────
try:
    import instructor
    from openai import OpenAI
    from pydantic import BaseModel, Field
except ImportError as e:
    print(f"\n❌ Missing dependency: {e}")
    print("   Run: .venv/bin/pip install instructor openai pydantic")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODELS_TO_TEST = [
    ("or_fast", "openai/gpt-5-nano"),
    ("or_smart", "google/gemini-3-flash-preview"),
]

# ── Minimal response schema ───────────────────────────────────────────────────
class Ping(BaseModel):
    """Trivial structured response to verify instructor compliance."""
    message: str = Field(description="A short greeting or acknowledgement")
    ok: bool = Field(description="Always true if the model responded correctly")
    model_name: str = Field(description="Which model is responding (fill in your own name)")


# ── Test runner ───────────────────────────────────────────────────────────────
def test_model(alias: str, model_id: str, client) -> dict:
    """
    Run a single structured-output call against one model.
    Returns a result dict with keys: alias, model_id, success, response, error.
    """
    result = {"alias": alias, "model_id": model_id, "success": False, "response": None, "error": None}
    try:
        response: Ping = client.chat.completions.create(
            model=model_id,
            response_model=Ping,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reply with a short greeting. Set ok=true and fill in your model name. "
                        "This is a connectivity test."
                    ),
                }
            ],
            max_tokens=1500,  # reasoning models (e.g. gpt-5-nano) consume tokens on internal
                              # chain-of-thought before emitting output — 200 was too small
            temperature=0.0,
        )
        result["success"] = True
        result["response"] = response.model_dump()
    except Exception as e:
        result["error"] = str(e)
    return result


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("\n❌ OPENROUTER_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  OpenRouter Connectivity + Instructor Compliance Test")
    print("=" * 60)
    print(f"  Base URL : {OPENROUTER_BASE_URL}")
    print(f"  Key      : {api_key[:8]}...{api_key[-4:]}  (masked)")
    print(f"  Mode     : instructor.Mode.JSON  (matches eqd_config.yaml)")
    print("=" * 60)

    # instructor-patched OpenAI client pointed at OpenRouter
    raw_client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )
    client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON)

    results = []
    for alias, model_id in MODELS_TO_TEST:
        print(f"\n  Testing [{alias}] {model_id} ...")
        r = test_model(alias, model_id, client)
        results.append(r)

        if r["success"]:
            resp = r["response"]
            print(f"  ✅ OK")
            print(f"     message    : {resp.get('message', '')}")
            print(f"     ok         : {resp.get('ok')}")
            print(f"     model_name : {resp.get('model_name', '')}")
        else:
            print(f"  ❌ FAILED")
            print(f"     error: {r['error']}")

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"  Result: {passed}/{total} models passed")

    if passed == total:
        print("  → OpenRouter is reachable and both models support structured output.")
        print("  → Safe to activate the OpenRouter agents block in eqd_config.yaml.")
    else:
        failed = [r for r in results if not r["success"]]
        for r in failed:
            print(f"\n  [{r['alias']}] {r['model_id']} — diagnosis:")
            err = r["error"] or ""
            if "401" in err or "authentication" in err.lower() or "api key" in err.lower():
                print("    → Auth failure. Check OPENROUTER_API_KEY in .env.")
            elif "max_tokens" in err.lower() or "length limit" in err.lower() or "incomplete" in err.lower():
                print("    → Reasoning model hit max_tokens: internal thinking consumed all the budget.")
                print("      This model uses chain-of-thought tokens before emitting output.")
                print("      Fix: increase max_tokens further, or disable reasoning via extra_body.")
                print(f"      Tested ID: {r['model_id']}")
            elif "404" in err or ("model" in err.lower() and "not found" in err.lower()):
                print("    → Model ID not found on OpenRouter. Verify at https://openrouter.ai/models")
                print(f"      Tested ID: {r['model_id']}")
            elif "pydantic" in err.lower() or "validation" in err.lower():
                print("    → Structured output validation failed — model responded but didn't follow schema.")
                print("      Try instructor.Mode.JSON_SCHEMA or switch to a different model.")
            elif "timeout" in err.lower() or "connection" in err.lower():
                print("    → Network/connection error. Check internet access.")
            else:
                print(f"    → Unknown error: {err}")

    print("=" * 60 + "\n")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
