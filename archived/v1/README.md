# archived/v1 — EQD-AI v1 (full L0–L4 pipeline)

Everything from the **first version** of EQD-AI lives here after the v2 pivot to
an evidence-extraction (L0–L1) focus. Kept visible as history/knowledge; nothing
is deleted. The full v1 *codebase* is also preserved in the `v1-full-pipeline`
git tag and the `archive/full-pipeline` branch.

```
archived/v1/
  docs/      # v1 architecture, design (L4/L5), plans, test-run summaries, .docx refs
  skills/    # pipeline-test-analysis (full-pipeline test analysis: 18-metric ref,
             #   TEST_RUN_SUMMARY template, iteration-1 evals)
  scripts/   # compare_runs.py (v1 full-pipeline results-JSON comparison)
  runs/      # v1 run artifacts: .db, reasoning .jsonl, results .json (ON DISK ONLY)
  linkedin/  # v1-era whiteboard photos (ON DISK ONLY)
```

> **On disk only:** `runs/` and `linkedin/` here are gitignored (`runs/`,
> `linkedin/` patterns) — large binaries / images are kept locally as history but
> are **not** committed to the repo. The v1 code/docs above *are* in git, plus the
> `v1-full-pipeline` tag. `docs/`, `skills/`, `scripts/` are tracked.

## What was deliberately NOT archived (stays active for v2)

- **Code** — all of `src/` is the v2 evidence-extraction (L0–L1) codebase.
- **`data/`** — datasets are shared across versions (and gitignored).
- **`docs/reference/DESIGN_PRINCIPLES.md`** — cross-layer principles still apply.
- General reference (`docs/reference/` guides, initial concept, research) and
  `docs/design/CODEBOOK_VERSIONING_DESIGN.md` (codebook is core to L1).
- The 4 active project-dev skills (`eqa-arch-review`, `eqa-decision-protocol`,
  `eqa-ideas-maintenance`, `eqa-repo-standards`).

For the active v2 direction see `docs/v2/` and the project `CLAUDE.md`.
