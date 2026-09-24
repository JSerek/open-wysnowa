"""
Tests for src.eval.l1_metrics.L1MetricsEngine — the v2 evidence-extraction
metric suite extracted from v1's Layer-3 engine.

Covers the pure/aggregate metrics (deterministic) and the DB-backed metrics
(grounding, extraction density, IC concentration, cross-review convergence,
quote coverage) against an in-memory database.
"""

import pytest

from src.core.db import (
    DocumentRepo,
    InitialCodeRepo,
    SegmentRepo,
    VerbatimQuoteRepo,
)
from src.eval.l1_metrics import L1MetricsEngine


@pytest.fixture
def engine(db):
    """L1MetricsEngine on an in-memory DB (no embedding service needed)."""
    return L1MetricsEngine(db, embedding_service=None)


@pytest.fixture
def populated_db(db, sample_documents, sample_segment, sample_ics, sample_quotes):
    """DB with one document, one segment, three ICs, and two grounded quotes."""
    DocumentRepo(db).insert(sample_documents[0])  # doc_001
    SegmentRepo(db).insert(sample_segment)        # seg_001 -> doc_001
    ic_repo = InitialCodeRepo(db)
    for ic in sample_ics:                          # ic_001, ic_002, ic_003
        ic_repo.insert(ic)
    vq_repo = VerbatimQuoteRepo(db)
    for q in sample_quotes:                         # vq_001 (ic_001), vq_002 (ic_003)
        vq_repo.insert(q)
    return db


# ── Pure / aggregate metrics ──────────────────────────────────────────────────

class TestMergeSpans:
    def test_merges_overlaps(self):
        # (0,5) and (3,8) merge to (0,8)=8 chars; (10,12)=2 chars -> 10
        assert L1MetricsEngine._merge_spans([(0, 5), (3, 8), (10, 12)]) == 10

    def test_empty(self):
        assert L1MetricsEngine._merge_spans([]) == 0

    def test_disjoint(self):
        assert L1MetricsEngine._merge_spans([(0, 2), (5, 9)]) == 6


class TestQuoteHallucinationRate:
    def test_rate(self, engine):
        r = engine.compute_quote_hallucination_rate(total_dropped=2, total_valid_candidates=8)
        assert r["quote_hallucination_rate"] == 0.2          # 2 / (8+2)
        assert r["hallucinated"] == 2
        assert r["total_raw_candidates"] == 10

    def test_no_candidates(self, engine):
        r = engine.compute_quote_hallucination_rate(total_dropped=0, total_valid_candidates=0)
        assert r["quote_hallucination_rate"] == 0.0

    def test_drop_class_breakdown(self, engine):
        r = engine.compute_quote_hallucination_rate(
            total_dropped=4, total_valid_candidates=6,
            drop_classes={"ellipsis_stitch": 3, "unmatched": 1},
            pass2_drop_classes={"case": 1},
        )
        assert r["quote_hallucination_rate"] == 0.4
        assert r["unmatched_quote_rate"] == 0.1          # 1 / (6+4)
        assert r["drop_classes"] == {"ellipsis_stitch": 3, "unmatched": 1}
        assert r["pass2_drop_classes"] == {"case": 1}

    def test_unmatched_rate_zero_without_candidates(self, engine):
        r = engine.compute_quote_hallucination_rate(0, 0, drop_classes={})
        assert r["unmatched_quote_rate"] == 0.0


class TestJudgeReliability:
    def test_rates(self, engine):
        r = engine.compute_judge_reliability(
            decision_paths={"empty_codebook": 1, "llm": 8, "llm_failed": 2},
            merge_target_unresolved=1,
            judge_merge_verdicts=4,
        )
        assert r["judge_failure_rate"] == 0.2            # 2 / (8+2)
        assert r["judge_failed"] == 2
        assert r["judge_calls"] == 10
        assert r["merge_target_unresolved_rate"] == 0.25 # 1 / 4

    def test_zero_denominators(self, engine):
        r = engine.compute_judge_reliability({"empty_codebook": 3}, 0, 0)
        assert r["judge_failure_rate"] == 0.0
        assert r["merge_target_unresolved_rate"] == 0.0


class TestAmbiguousOccurrences:
    def test_rate(self, engine):
        r = engine.compute_ambiguous_occurrences(
            {"first_free": 2, "first_fallback": 1}, accepted_quotes_total=10,
        )
        assert r["ambiguous_occurrence_rate"] == 0.3
        assert r["first_free"] == 2 and r["first_fallback"] == 1

    def test_zero_accepted(self, engine):
        r = engine.compute_ambiguous_occurrences({}, accepted_quotes_total=0)
        assert r["ambiguous_occurrence_rate"] == 0.0


class TestMergeRate:
    def test_overall_rate(self, engine):
        r = engine.compute_merge_rate(
            [{"batch_num": 1, "new_candidates": 4, "merges": 1}]
        )
        assert r["overall_rate"] == 0.25
        assert r["total_merges"] == 1
        assert len(r["per_batch"]) == 1


class TestCoderConfidence:
    def test_mean_and_low_count(self, engine):
        r = engine.compute_coder_confidence([0.9, 0.8, 0.5, 0.4])
        assert r["total_new_ics"] == 4
        assert r["mean_confidence"] == pytest.approx(0.65, abs=1e-6)
        assert r["low_confidence_count"] == 2   # 0.5 and 0.4 are < 0.6

    def test_empty(self, engine):
        r = engine.compute_coder_confidence([])
        assert r["mean_confidence"] is None
        assert r["total_new_ics"] == 0


# ── DB-backed metrics ─────────────────────────────────────────────────────────

class TestSpanIntegrity:
    def test_all_quotes_verified(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_span_integrity()
        assert r["total_quotes"] == 2
        assert r["verified"] == 2
        assert r["span_integrity"] == 1.0
        assert r["failed"] == 0

    def test_empty_db_is_one(self, engine):
        assert engine.compute_span_integrity()["span_integrity"] == 1.0


class TestExtractionDensity:
    def test_density_and_drop_rate(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_extraction_density(
            total_dropped=1, total_valid_candidates=3
        )
        assert r["total_segments"] == 1
        assert 0.0 < r["distribution"]["mean"] <= 1.0
        assert r["drop_rate"]["overall_rate"] == 0.25   # 1 / (3+1)


class TestICConcentration:
    def test_singletons(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_ic_concentration()
        # 3 active ICs; ic_001 and ic_003 have 1 quote each, ic_002 has 0
        assert r["total_ics"] == 3
        assert r["singletons"] == 2


class TestCrossReviewConvergence:
    def test_single_doc_unconfirmed(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_cross_review_convergence()
        # all quotes come from one document -> no IC confirmed by 2+ docs
        assert r["confirmed_ratio"] == 0.0
        assert r["mean_docs_per_ic"] >= 0.0


class TestQuoteCoveragePerIC:
    def test_structure(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_quote_coverage_per_ic()
        assert "per_ic" in r
        assert r["total_ic_segment_pairs"] == 2   # ic_001/seg_001 and ic_003/seg_001


class TestComputeAll:
    def test_returns_expected_keys(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_all(
            its_history=[],
            total_dropped=1,
            total_candidates=5,
            new_ic_confidences=[0.7, 0.9],
        )
        for key in [
            "span_integrity", "judge_reliability", "ambiguous_occurrences",
            "extraction_density", "quote_hallucination_rate", "ic_concentration",
            "merge_rate", "its_history", "cross_review_convergence",
            "coder_confidence", "quote_coverage", "coder_reuse",
        ]:
            assert key in r
        assert "grounding" not in r

    def test_compute_all_passes_p0_counters(self, populated_db):
        engine = L1MetricsEngine(populated_db)
        r = engine.compute_all(
            its_history=[],
            total_dropped=1, total_candidates=3,
            decision_paths={"llm": 3, "llm_failed": 1},
            merge_target_unresolved=1, judge_merge_verdicts=2,
            grounding_drop_classes={"unmatched": 1},
            pass2_stats={"drop_classes": {"case": 1}},
            ambiguous_occurrences={"first_free": 1, "first_fallback": 0},
            accepted_quotes_total=4,
        )
        assert r["judge_reliability"]["judge_failure_rate"] == 0.25
        assert r["judge_reliability"]["merge_target_unresolved_rate"] == 0.5
        assert r["quote_hallucination_rate"]["unmatched_quote_rate"] == 0.25
        assert r["quote_hallucination_rate"]["pass2_drop_classes"] == {"case": 1}
        assert r["ambiguous_occurrences"]["ambiguous_occurrence_rate"] == 0.25
