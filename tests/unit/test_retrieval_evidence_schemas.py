"""Tests for incident-driven retrieval and ranked-evidence schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bug_resolver.schemas import (
    EvidenceCandidate,
    EvidenceScoreBreakdown,
    FileContextRequest,
    GraphExpansionRequest,
    IncidentFacts,
    RankedEvidence,
    RetrievalAnchor,
    RetrievalEvidenceEvaluationResult,
    RetrievalEvidenceSourceType,
    RetrievalPlan,
    RetrievalQuery,
    StackFrame,
)


def test_incident_facts_defaults() -> None:
    facts = IncidentFacts(
        incident_id="INC-001",
        summary="Request fails with TypeError",
    )

    assert facts.description is None
    assert facts.error_terms == []
    assert facts.exception_types == []
    assert facts.stack_frames == []
    assert facts.status_codes == []
    assert facts.trace_ids == []
    assert facts.request_ids == []
    assert facts.candidate_symbols == []
    assert facts.quoted_terms == []
    assert facts.config_like_terms == []
    assert facts.log_key_terms == []
    assert facts.event_terms == []


def test_incident_facts_accepts_stack_frames() -> None:
    facts = IncidentFacts(
        incident_id="INC-001",
        summary="Request fails",
        stack_frames=[
            StackFrame(
                file_path="src/app.py",
                line_number=42,
                function_name="handle_request",
                class_name="App",
            )
        ],
    )

    assert facts.stack_frames[0].file_path == "src/app.py"
    assert facts.stack_frames[0].line_number == 42


def test_retrieval_plan_defaults() -> None:
    plan = RetrievalPlan()

    assert plan.anchors == []
    assert plan.exact_queries == []
    assert plan.structural_queries == []
    assert plan.semantic_queries == []
    assert plan.file_context_requests == []
    assert plan.graph_expansion_requests == []
    assert plan.kb_queries == []


def test_retrieval_plan_accepts_all_request_types() -> None:
    plan = RetrievalPlan(
        anchors=[
            RetrievalAnchor(
                value="TypeError",
                anchor_type="exception_type",
                source="log",
            )
        ],
        exact_queries=[
            RetrievalQuery(
                query="TypeError handle_request",
                purpose="exact_error_lookup",
                priority=10,
                source_hint="log",
            )
        ],
        file_context_requests=[
            FileContextRequest(
                file_path="src/app.py",
                line_number=42,
                reason="Stack trace frame",
            )
        ],
        graph_expansion_requests=[
            GraphExpansionRequest(
                file_path="src/app.py",
                symbol_name="handle_request",
                reason="Find callers",
            )
        ],
    )

    assert plan.anchors[0].confidence == 1.0
    assert plan.exact_queries[0].priority == 10
    assert plan.file_context_requests[0].before_lines == 40
    assert plan.file_context_requests[0].after_lines == 40
    assert plan.graph_expansion_requests[0].max_depth == 1


def test_graph_expansion_request_requires_an_anchor() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        GraphExpansionRequest(reason="Find related code")


def test_graph_expansion_request_accepts_file_path_anchor() -> None:
    request = GraphExpansionRequest(
        file_path="src/app.py",
        reason="Find related code",
    )

    assert request.file_path == "src/app.py"


def test_graph_expansion_request_accepts_symbol_name_anchor() -> None:
    request = GraphExpansionRequest(
        symbol_name="handle_request",
        reason="Find related code",
    )

    assert request.symbol_name == "handle_request"


def test_graph_expansion_request_accepts_line_number_anchor() -> None:
    request = GraphExpansionRequest(
        line_number=10,
        reason="Find related code",
    )

    assert request.line_number == 10


def test_evidence_candidate_supports_code_metadata() -> None:
    candidate = EvidenceCandidate(
        candidate_id="cand-1",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        retriever_name="ripgrep",
        content="def handle_request(): ...",
        file_path="src/app.py",
        start_line=10,
        end_line=20,
        symbol_name="handle_request",
        symbol_type="function",
        matched_terms=["handle_request", "TypeError"],
        retrieval_query="handle_request TypeError",
        metadata={"language": "python", "score": 0.91},
    )

    assert candidate.source_type == RetrievalEvidenceSourceType.CODE_EXACT
    assert candidate.metadata["language"] == "python"
    assert candidate.metadata["score"] == 0.91
    assert candidate.matched_terms == ["handle_request", "TypeError"]


def test_evidence_candidate_validates_line_range() -> None:
    with pytest.raises(ValidationError, match="end_line"):
        EvidenceCandidate(
            candidate_id="cand-1",
            source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
            retriever_name="file_context",
            content="context",
            start_line=20,
            end_line=10,
        )


def test_evidence_score_breakdown_defaults() -> None:
    score = EvidenceScoreBreakdown()

    assert score.source_strength == 0.0
    assert score.directness == 0.0
    assert score.incident_term_overlap == 0.0
    assert score.exact_error_match == 0.0
    assert score.file_path_match == 0.0
    assert score.symbol_match == 0.0
    assert score.stack_trace_proximity == 0.0
    assert score.line_proximity == 0.0
    assert score.graph_distance_score == 0.0
    assert score.multi_source_agreement == 0.0
    assert score.recency_relevance == 0.0
    assert score.semantic_only_penalty == 0.0
    assert score.noise_penalty == 0.0
    assert score.final_score == 0.0
    assert score.reasons == []


def test_ranked_evidence_wraps_candidate_and_score() -> None:
    candidate = EvidenceCandidate(
        candidate_id="cand-1",
        source_type=RetrievalEvidenceSourceType.LOG,
        retriever_name="log_provider",
        content="TypeError in request handler",
    )
    score = EvidenceScoreBreakdown(
        source_strength=0.8,
        final_score=0.9,
        reasons=["Runtime evidence"],
    )

    ranked = RankedEvidence(
        candidate=candidate,
        score=score,
        rank=1,
        supporting_candidate_ids=["cand-2"],
    )

    assert ranked.candidate.candidate_id == "cand-1"
    assert ranked.score.final_score == 0.9
    assert ranked.rank == 1
    assert ranked.supporting_candidate_ids == ["cand-2"]


def test_evidence_evaluation_result_defaults() -> None:
    result = RetrievalEvidenceEvaluationResult()

    assert result.ranked_evidence == []
    assert result.selected_evidence == []
    assert result.has_runtime_evidence is False
    assert result.has_direct_code_evidence is False
    assert result.has_supporting_kb_evidence is False
    assert result.has_graph_support is False
    assert result.sufficient_for_rca is False
    assert result.confidence == 0.0
    assert result.missing_evidence == []
    assert result.warnings == []
