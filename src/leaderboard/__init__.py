"""EQD-AI v2 — L1 leaderboard package (Phase 3).

Modules:
  - registry.py — central run registry (RunManifest + long-format run_metrics),
    with `load_matrix()` pivoting into a metric × (gen × embed) matrix.
  - harness.py — runs the (gen × embed × k) matrix, headless and sim-blind, each
    combo into its own run DB, recording manifests + metrics in the registry.
  - report.py — renders the registry pivot as Markdown / CSV with metric
    directions and (k>1) variance.
"""
