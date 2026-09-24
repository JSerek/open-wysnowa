"""
EQD-AI v2 — Leaderboard report rendering (Phase 3).

Turns the registry pivot (`RunRegistry.load_matrix`) into a human-readable matrix:
rows = metrics, columns = (gen × embed) combos, cells = mean (± sd when k>1).
Metric direction (Appendix A) is shown as an arrow next to the metric name so a
reader knows which way is better without leaving the table. The matrix — never a
single composite score — is the artefact a human compares (contract #8).
"""

from __future__ import annotations

import statistics as _stats
from typing import Any, Dict, List, Optional, Tuple

# Direction → arrow. "more" = higher is better, "less" = lower is better, "" = no
# inherent direction (descriptive).
_ARROW = {"more": "↑", "less": "↓", "": ""}


def aggregate_cell(values: List[float]) -> Dict[str, Optional[float]]:
    """
    Aggregate the raw per-run values of one (metric, column) cell.

    Returns {mean, sd, n}. sd is the sample standard deviation across runs (the
    k>1 stability signal); None when fewer than two values.
    """
    if not values:
        return {"mean": None, "sd": None, "n": 0}
    n = len(values)
    mean = sum(values) / n
    sd = _stats.stdev(values) if n > 1 else None
    return {"mean": mean, "sd": sd, "n": n}


def _fmt_cell(agg: Dict[str, Optional[float]]) -> str:
    """Format one aggregated cell as 'mean' or 'mean ± sd' (k>1)."""
    if agg["mean"] is None:
        return "—"
    out = f"{agg['mean']:.3f}"
    if agg["sd"] is not None:
        out += f" ± {agg['sd']:.3f}"
    return out


def _metric_label(metric: str, direction: str) -> str:
    arrow = _ARROW.get(direction, "")
    return f"{metric} {arrow}".rstrip()


def _ordered(matrix: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Stable metric (sorted) and column (registry insertion) ordering."""
    metrics = sorted(matrix.get("cells", {}).keys())
    columns = list(matrix.get("columns", []))
    return metrics, columns


_JUDGE_FAILURE_METRIC = "judge_failure_rate"


def _judge_failure_columns(matrix: Dict[str, Any]) -> set:
    """Columns where any run reported judge failures (results unreliable)."""
    per_col = matrix.get("cells", {}).get(_JUDGE_FAILURE_METRIC, {})
    return {col for col, values in per_col.items() if any(v > 0 for v in values)}


def render_matrix_markdown(matrix: Dict[str, Any]) -> str:
    """
    Render the pivot as a GitHub-flavoured Markdown table.

    matrix is the dict returned by `RunRegistry.load_matrix()`:
        {"columns": [...], "directions": {metric: dir}, "cells": {metric: {col: [v]}},
         "pipeline_version": str | None, "excluded_runs": int}
    Columns with judge_failure_rate > 0 in any run are marked ⚠ (P0).
    """
    metrics, columns = _ordered(matrix)
    directions = matrix.get("directions", {})
    cells = matrix.get("cells", {})

    # Version header first — even an empty matrix must say older runs were filtered.
    lines: List[str] = []
    if matrix.get("pipeline_version"):
        lines.append(
            f"_pipeline_version: {matrix['pipeline_version']} — "
            f"{matrix.get('excluded_runs', 0)} run(s) of other versions excluded_"
        )
        lines.append("")

    if not metrics:
        lines.append("_(no metrics recorded)_")
        return "\n".join(lines)

    flagged = _judge_failure_columns(matrix)
    header = ["Metric", *[f"{c} ⚠" if c in flagged else c for c in columns]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for metric in metrics:
        row = [_metric_label(metric, directions.get(metric, ""))]
        col_cells = cells.get(metric, {})
        for col in columns:
            row.append(_fmt_cell(aggregate_cell(col_cells.get(col, []))))
        lines.append("| " + " | ".join(row) + " |")
    if flagged:
        lines.append("")
        lines.append(
            "⚠ judge_failure_rate > 0 in at least one run of this column — "
            "judge fell back to NEW; results are unreliable."
        )
    return "\n".join(lines)


def render_matrix_csv(matrix: Dict[str, Any]) -> str:
    """
    Render the pivot as CSV (mean per cell; sd in a parallel `<col>_sd` column).

    Machine-readable companion to the Markdown table — one row per metric, a mean
    column and an sd column per model combo, plus the metric direction.
    """
    import csv
    import io

    metrics, columns = _ordered(matrix)
    directions = matrix.get("directions", {})
    cells = matrix.get("cells", {})

    buf = io.StringIO()
    writer = csv.writer(buf)

    header = ["metric", "direction"]
    for col in columns:
        header.extend([col, f"{col}_sd"])
    writer.writerow(header)

    for metric in metrics:
        row: List[Any] = [metric, directions.get(metric, "")]
        col_cells = cells.get(metric, {})
        for col in columns:
            agg = aggregate_cell(col_cells.get(col, []))
            row.append("" if agg["mean"] is None else round(agg["mean"], 6))
            row.append("" if agg["sd"] is None else round(agg["sd"], 6))
        writer.writerow(row)

    return buf.getvalue()
