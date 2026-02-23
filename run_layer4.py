"""
Standalone Layer 4 runner.

Loads a saved results JSON and re-runs only the Analyst Intelligence layer
without touching the database or re-running Layers 1-3.

Usage:
    python run_layer4.py                          # uses results_stab_30.json
    python run_layer4.py results_stab_30.json
    python run_layer4.py results_stab_30.json --save  # also writes *_layer4.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.analyst_agent import AnalystAgent
from src.config import load_config, ModelClient
from src.quality_report import display_analytical_brief


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Layer 4 on a saved results JSON")
    parser.add_argument(
        "results_file",
        nargs="?",
        default="results_stab_30.json",
        help="Path to the pipeline results JSON (default: results_stab_30.json)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the AnalyticalBrief to <results_file stem>_layer4.json",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to eqd_config.yaml (default: eqd_config.yaml in project root)",
    )
    args = parser.parse_args()

    results_path = Path(args.results_file)
    if not results_path.exists():
        print(f"Error: results file not found: {results_path}")
        sys.exit(1)

    # ── Load results ──────────────────────────────────────────────────────────
    print(f"Loading: {results_path}")
    with open(results_path) as f:
        results = json.load(f)

    # Quick sanity check — make sure the JSON has the expected keys
    for required in ("layer3", "thematic_structure"):
        if required not in results:
            print(f"Error: results JSON missing key '{required}' — was this produced by EQD-AI?")
            sys.exit(1)

    # ── Load config + model client ────────────────────────────────────────────
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    model_client = ModelClient(config)

    # ── Run Layer 4 ───────────────────────────────────────────────────────────
    print(f"Running Layer 4 (analyst_agent → {config.agents['analyst_agent'].model})...")
    print()

    t0 = time.time()
    analyst = AnalystAgent(model_client, config)

    try:
        brief = analyst.analyze(results)
    except Exception as e:
        print(f"Layer 4 failed: {e}")
        sys.exit(1)

    elapsed = time.time() - t0
    print(f"Layer 4 complete in {elapsed:.1f}s")
    print()

    # ── Display ───────────────────────────────────────────────────────────────
    display_analytical_brief(brief.model_dump())

    # ── Optionally save ───────────────────────────────────────────────────────
    if args.save:
        out_path = results_path.parent / f"{results_path.stem}_layer4.json"
        with open(out_path, "w") as f:
            json.dump(brief.model_dump(), f, indent=2)
        print(f"\nBrief saved to: {out_path}")


if __name__ == "__main__":
    main()
