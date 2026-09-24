"""
Tests for Phase 2 — second pass (omitted-text audit).

Covers:
  - build_omitted_view: complement wrapping (before/between/after), raw
    boundaries, no overlapping/empty tags.
  - DEDUP overlap gate: a recovered quote overlapping a pass-1 span is dropped.
  - Recovered evidence flows the full track (grounding → judge → accepted).
  - Two-point density: density_pass1 ≤ density_pass2; density_delta.
  - SecondPassResult parsing with reasoning BEFORE the decision fields (CoT order).

All fixtures are synthetic (invented English text) — no slices of real data.
"""

import pytest
from unittest.mock import MagicMock

from src.core.db import Database, DocumentRepo, SegmentRepo
from src.core.models import (
    ComparatorOutput,
    ComparatorRecommendation,
    Document,
    ICCandidate,
    OmissionType,
    OmittedFragmentAssessment,
    RawICCandidate,
    SecondPassResult,
    Segment,
)
from src.eval.l1_metrics import L1MetricsEngine
from src.extraction.omitted import build_omitted_view
from src.extraction.orchestrator import Layer1Orchestrator


# Synthetic review with three clearly separable clauses.
REVIEW = "The combat is sluggish and clunky. The story was fine. Loading times are far too long."


# ── build_omitted_view ────────────────────────────────────────────────────────

class TestBuildOmittedView:
    def test_middle_extraction_wraps_before_and_after(self):
        quote = "The story was fine"
        s = REVIEW.index(quote)
        view = build_omitted_view(REVIEW, [(s, s + len(quote))])
        assert view == (
            f"<omitted>{REVIEW[:s]}</omitted>"
            f"{quote}"
            f"<omitted>{REVIEW[s + len(quote):]}</omitted>"
        )
        # The extracted fragment appears as plain text (not inside a tag).
        assert f"<omitted>{quote}</omitted>" not in view

    def test_no_spans_wraps_whole_text(self):
        assert build_omitted_view(REVIEW, []) == f"<omitted>{REVIEW}</omitted>"

    def test_full_coverage_has_no_tags(self):
        view = build_omitted_view(REVIEW, [(0, len(REVIEW))])
        assert "<omitted>" not in view
        assert view == REVIEW

    def test_raw_boundaries_mid_word(self):
        # A span ending mid-word is honoured verbatim (raw boundaries).
        view = build_omitted_view("abcdef", [(0, 3)])
        assert view == "abc<omitted>def</omitted>"

    def test_overlapping_and_adjacent_spans_merge_no_empty_tags(self):
        # Overlapping (1,3)+(2,4) and the leading/trailing gaps.
        view = build_omitted_view("abcdef", [(1, 3), (2, 4)])
        assert view == "<omitted>a</omitted>bcd<omitted>ef</omitted>"
        assert "<omitted></omitted>" not in view

    def test_adjacent_spans_leave_no_gap(self):
        view = build_omitted_view("abcdef", [(0, 2), (2, 4)])
        assert view == "abcd<omitted>ef</omitted>"


# ── SecondPassResult parsing / field order ────────────────────────────────────

class TestSecondPassParsing:
    def test_reasoning_precedes_decision_fields(self):
        fields = list(OmittedFragmentAssessment.model_fields)
        assert fields.index("reasoning") < fields.index("omission_type")
        assert fields.index("reasoning") < fields.index("contains_evidence")
        assert fields.index("reasoning") < fields.index("recovered_evidence")

    def test_parse_from_dict(self):
        result = SecondPassResult.model_validate({
            "segment_id": "seg_1",
            "fragments": [
                {
                    "omitted_text": "Loading times are far too long",
                    "reasoning": "This clause carries a concrete performance complaint.",
                    "omission_type": "accidental",
                    "contains_evidence": True,
                    "recovered_evidence": [
                        {
                            "ic_name": "loading_times_too_long",
                            "definition": "Player complains loading times are excessive",
                            "quote_text": "Loading times are far too long",
                            "confidence": 0.9,
                        }
                    ],
                },
                {
                    "omitted_text": " The story was fine. ",
                    "reasoning": "Filler — no specific experiential content.",
                    "omission_type": "deliberate",
                    "contains_evidence": False,
                },
            ],
        })
        assert len(result.fragments) == 2
        assert result.fragments[0].omission_type is OmissionType.ACCIDENTAL
        assert result.fragments[0].recovered_evidence[0].quote_text == "Loading times are far too long"
        assert result.fragments[1].recovered_evidence is None


# ── Two-point density metric ──────────────────────────────────────────────────

class TestDensityPasses:
    def test_pass2_geq_pass1_and_delta(self):
        db = Database(":memory:")
        db.init_schema()
        eng = L1MetricsEngine(db)
        snaps = [
            {"segment_id": "s1", "char_count": 100, "density_pass1": 0.40,
             "density_pass2": 0.65, "recovered": True},
            {"segment_id": "s2", "char_count": 80, "density_pass1": 0.50,
             "density_pass2": 0.50, "recovered": False},
        ]
        out = eng.compute_density_passes(snaps)
        assert out["density_pass1"] <= out["density_pass2"]
        assert out["density_delta"] == pytest.approx((0.25 + 0.0) / 2, abs=1e-6)
        assert out["recovery_rate"] == pytest.approx(0.5, abs=1e-6)
        assert out["reviews_with_recovery"] == 1

    def test_empty_snapshots(self):
        db = Database(":memory:")
        db.init_schema()
        out = L1MetricsEngine(db).compute_density_passes([])
        assert out["density_delta"] is None
        assert out["total_reviews"] == 0

    def test_omission_ratio(self):
        db = Database(":memory:")
        db.init_schema()
        out = L1MetricsEngine(db).compute_omission_stats(
            {"deliberate": 3, "accidental": 1, "fragments_total": 4}
        )
        assert out["accidental_omission_ratio"] == pytest.approx(0.25, abs=1e-6)
        assert out["deliberate_omission_ratio"] == pytest.approx(0.75, abs=1e-6)


# ── Orchestrator pass-2 integration (DEDUP + full track) ──────────────────────

class TestPass2Integration:
    @pytest.fixture
    def segment(self):
        return Segment(
            id="seg_p2",
            document_id="doc_p2",
            canonical_text=REVIEW,
            original_text=REVIEW,
            char_count=len(REVIEW),
            segment_index=0,
            content_hash="hash",
        )

    @pytest.fixture
    def orch(self, db, segment):
        DocumentRepo(db).insert(Document(id="doc_p2", raw_text="x"))
        SegmentRepo(db).insert(segment)

        config = MagicMock()
        config.processing.batch_size = 15
        config.processing.its_saturation_threshold = 0.02
        config.processing.its_consecutive_batches = 3
        config.processing.similarity_prefilter_k = 5

        o = Layer1Orchestrator(MagicMock(), db, config)
        o.coder_agent = MagicMock()
        o.coder_agent.last_drop_counts = {}
        o.coder_agent.last_drops = {}
        o.comparator = MagicMock()
        o.second_pass_agent = MagicMock()
        o.embedding_service = MagicMock()
        o.embedding_service.embed_texts_batch.side_effect = (
            lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
        )

        def fake_embed_ic(ic):
            ic.embedding_json = [0.1, 0.2, 0.3]
            return ic
        o.embedding_service.embed_ic.side_effect = fake_embed_ic
        o.embedding_service.embed_quote.side_effect = lambda q: q

        # Judge always says NEW (empty top-k) — both passes accept.
        o.comparator.evaluate.return_value = (
            ComparatorOutput(
                recommendation=ComparatorRecommendation.NEW,
                reasoning="Distinct concept.",
            ),
            [],
            {"decision_path": "empty_codebook", "max_sim": None, "llm_recommendation": None},
        )
        return o

    def _pass1_candidate(self):
        quote = "The combat is sluggish and clunky"
        s = REVIEW.index(quote)
        return ICCandidate(
            ic_name="combat_sluggish",
            definition="Player finds the combat sluggish and clunky",
            quote_text=quote,
            span_start=s,
            span_end=s + len(quote),
            confidence=0.9,
            existing_code_match=None,
        )

    def test_recovered_evidence_flows_full_track(self, orch, segment):
        """Pass-2 recovered quote in an omitted region → grounded → judged → accepted."""
        orch.coder_agent.process_batch.return_value = {segment.id: [self._pass1_candidate()]}
        orch.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id=segment.id,
            fragments=[
                OmittedFragmentAssessment(
                    omitted_text="Loading times are far too long",
                    reasoning="Concrete performance complaint missed by pass 1.",
                    omission_type=OmissionType.ACCIDENTAL,
                    contains_evidence=True,
                    recovered_evidence=[
                        RawICCandidate(
                            ic_name="loading_times_too_long",
                            definition="Player complains loading times are excessive",
                            quote_text="Loading times are far too long",
                            confidence=0.9,
                        )
                    ],
                )
            ],
        )

        result = orch.run([segment], enable_hil=False)

        # Two NEW ICs: one from each pass.
        assert result["new_ics_created"] == 2
        # Judge consulted for both the pass-1 and the recovered pass-2 candidate.
        assert orch.comparator.evaluate.call_count == 2
        ps = result["pass2_stats"]
        assert ps["accidental"] == 1
        assert ps["recovered_candidates"] == 1
        assert ps["recovered_accepted"] == 1
        assert ps["overlap_drops"] == 0
        # density_pass2 strictly greater (pass-2 added coverage).
        snap = result["density_snapshots"][0]
        assert snap["density_pass2"] > snap["density_pass1"]
        assert snap["recovered"] is True

    def test_dedup_overlap_drops_recovered(self, orch, segment):
        """A recovered quote overlapping a pass-1 span is dropped, never judged."""
        orch.coder_agent.process_batch.return_value = {segment.id: [self._pass1_candidate()]}
        # Recovered quote overlaps the pass-1 span ("combat is sluggish" ⊂ pass-1 quote).
        orch.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id=segment.id,
            fragments=[
                OmittedFragmentAssessment(
                    omitted_text="combat is sluggish",
                    reasoning="Looks codeable but overlaps already-extracted evidence.",
                    omission_type=OmissionType.ACCIDENTAL,
                    contains_evidence=True,
                    recovered_evidence=[
                        RawICCandidate(
                            ic_name="combat_dupe",
                            definition="Duplicate of the combat complaint",
                            quote_text="combat is sluggish",
                            confidence=0.8,
                        )
                    ],
                )
            ],
        )

        result = orch.run([segment], enable_hil=False)

        # Only the pass-1 IC survives; the overlapping recovery is dropped.
        assert result["new_ics_created"] == 1
        assert orch.comparator.evaluate.call_count == 1  # recovered never reached the judge
        ps = result["pass2_stats"]
        assert ps["overlap_drops"] == 1
        assert ps["recovered_accepted"] == 0
        snap = result["density_snapshots"][0]
        assert snap["density_pass2"] == snap["density_pass1"]
        assert snap["recovered"] is False

    def test_grounding_gate_drops_hallucinated_recovery(self, orch, segment):
        """A recovered quote not present verbatim is dropped by the grounding gate."""
        orch.coder_agent.process_batch.return_value = {segment.id: [self._pass1_candidate()]}
        orch.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id=segment.id,
            fragments=[
                OmittedFragmentAssessment(
                    omitted_text="Loading times are far too long",
                    reasoning="Hallucinated paraphrase, not a verbatim substring.",
                    omission_type=OmissionType.ACCIDENTAL,
                    contains_evidence=True,
                    recovered_evidence=[
                        RawICCandidate(
                            ic_name="loading_paraphrase",
                            definition="Paraphrase not present in the text",
                            quote_text="loading is way too slow",  # not verbatim
                            confidence=0.7,
                        )
                    ],
                )
            ],
        )

        result = orch.run([segment], enable_hil=False)

        assert result["new_ics_created"] == 1
        ps = result["pass2_stats"]
        assert ps["recovered_candidates"] == 1
        assert ps["recovered_hallucinated"] == 1
        assert ps["recovered_accepted"] == 0
        assert ps["drop_classes"] == {"unmatched": 1}

    def test_pass2_hits_second_occurrence_instead_of_overlap_drop(self, db):
        """A repeated phrase recovered in pass 2 lands on the free occurrence."""
        text = "The combat is bad. The story was fine. The combat is bad."
        seg = Segment(
            id="seg_dup2", document_id="doc_dup2", canonical_text=text,
            original_text=text, char_count=len(text), segment_index=0,
            content_hash="hash_dup2",
        )
        DocumentRepo(db).insert(Document(id="doc_dup2", raw_text="x"))
        SegmentRepo(db).insert(seg)

        config = MagicMock()
        config.processing.batch_size = 15
        config.processing.its_saturation_threshold = 0.02
        config.processing.its_consecutive_batches = 3
        config.processing.similarity_prefilter_k = 5
        o = Layer1Orchestrator(MagicMock(), db, config)
        o.coder_agent = MagicMock()
        o.coder_agent.last_drop_counts = {}
        o.coder_agent.last_drops = {}
        o.comparator = MagicMock()
        o.second_pass_agent = MagicMock()
        o.embedding_service = MagicMock()
        o.embedding_service.embed_texts_batch.side_effect = (
            lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
        )

        def fake_embed_ic(ic):
            ic.embedding_json = [0.1, 0.2, 0.3]
            return ic
        o.embedding_service.embed_ic.side_effect = fake_embed_ic
        o.comparator.evaluate.return_value = (
            ComparatorOutput(recommendation=ComparatorRecommendation.NEW,
                             reasoning="Distinct concept."),
            [],
            {"decision_path": "empty_codebook", "max_sim": None, "llm_recommendation": None},
        )

        o.coder_agent.process_batch.return_value = {seg.id: [ICCandidate(
            ic_name="combat_bad", definition="Player criticises the combat",
            quote_text="The combat is bad", span_start=0, span_end=17,
            confidence=0.9, n_occurrences=2, occurrence_resolution="first_free",
        )]}
        o.second_pass_agent.assess_omitted.return_value = SecondPassResult(
            segment_id=seg.id,
            fragments=[OmittedFragmentAssessment(
                omitted_text="The combat is bad.",
                reasoning="Repeated complaint at the end of the review.",
                omission_type=OmissionType.ACCIDENTAL,
                contains_evidence=True,
                recovered_evidence=[RawICCandidate(
                    ic_name="combat_bad_repeat",
                    definition="Player repeats the combat complaint",
                    quote_text="The combat is bad", confidence=0.8,
                )],
            )],
        )

        result = o.run([seg], enable_hil=False)

        ps = result["pass2_stats"]
        assert ps["overlap_drops"] == 0
        assert ps["recovered_accepted"] == 1
        assert result["ambiguous_occurrences"] == {"first_free": 2, "first_fallback": 0}
        assert result["accepted_quotes_total"] == 2
