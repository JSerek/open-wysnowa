"""L0 preprocessing: segmentation/normalization + quote grounding.

Re-exports the public API of the `segmentation` and `grounding` submodules so
call sites can use `from src.preprocessing import preprocess_documents,
verify_quote, ...` without referencing the submodule paths.
"""

from src.preprocessing.segmentation import (
    normalize,
    canonicalize,
    segment_corpus,
    batch_segments,
    persist_documents,
    persist_segments,
    preprocess_documents,
)
from src.preprocessing.grounding import (
    verify_quote,
    attempt_realign,
    verify_ic_quotes,
    compute_coverage,
    compute_corpus_coverage,
    corpus_coverage_summary,
    GroundingReport,
    DropClass,
    QuoteMatch,
    locate_quote,
)

__all__ = [
    "normalize",
    "canonicalize",
    "segment_corpus",
    "batch_segments",
    "persist_documents",
    "persist_segments",
    "preprocess_documents",
    "verify_quote",
    "attempt_realign",
    "verify_ic_quotes",
    "compute_coverage",
    "compute_corpus_coverage",
    "corpus_coverage_summary",
    "GroundingReport",
    "DropClass",
    "QuoteMatch",
    "locate_quote",
]
