"""Tests for repo-agnostic deterministic retrieval evidence scoring."""

from __future__ import annotations

from bug_resolver.rules.evidence_scoring_rules import EvidenceScoringRules
from bug_resolver.schemas import (
    EvidenceCandidate,
    IncidentFacts,
    RetrievalEvidenceSourceType,
    StackFrame,
)


def _facts(*, summary: str = "Request fails with TypeError") -> IncidentFacts:
    return IncidentFacts(
        incident_id="INC-001",
        summary=summary,
        exception_types=["TypeError"],
        candidate_symbols=["handle_request"],
        stack_frames=[
            StackFrame(
                file_path="src/app.py",
                line_number=42,
                function_name="handle_request",
            )
        ],
    )


def _candidate(
    candidate_id: str,
    *,
    source_type: RetrievalEvidenceSourceType,
    content: str,
    file_path: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    symbol_name: str | None = None,
    metadata: dict[str, object] | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        candidate_id=candidate_id,
        source_type=source_type,
        retriever_name=source_type.value,
        content=content,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        symbol_name=symbol_name,
        metadata=metadata or {},
    )


def test_file_context_on_stack_trace_line_scores_high() -> None:
    candidate = _candidate(
        "stack-context",
        source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
        content="42: def handle_request():\n43:     raise TypeError('bad input')",
        file_path="src/app.py",
        start_line=35,
        end_line=50,
        symbol_name="handle_request",
    )

    score = EvidenceScoringRules().score_candidate(candidate, _facts())

    assert score.final_score > 0.7
    assert any("stack trace file src/app.py" in reason for reason in score.reasons)
    assert any("stack trace line 42" in reason for reason in score.reasons)
    assert any("error term TypeError" in reason for reason in score.reasons)
    assert any("incident symbol handle_request" in reason for reason in score.reasons)


def test_unrelated_semantic_candidate_scores_low() -> None:
    candidate = _candidate(
        "semantic",
        source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
        content="Background maintenance schedule",
        file_path="src/maintenance.py",
    )

    score = EvidenceScoringRules().score_candidate(candidate, _facts())

    assert score.final_score < 0.2
    assert score.semantic_only_penalty == 1.0


def test_exact_exception_match_scores_above_weak_kb() -> None:
    exact_candidate = _candidate(
        "exact",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content="raise TypeError('bad input')",
        file_path="src/service.py",
    )
    kb_candidate = _candidate(
        "kb",
        source_type=RetrievalEvidenceSourceType.KNOWLEDGE_BASE,
        content="General operational documentation",
    )
    rules = EvidenceScoringRules()

    exact_score = rules.score_candidate(exact_candidate, _facts())
    kb_score = rules.score_candidate(kb_candidate, _facts())

    assert exact_score.final_score > kb_score.final_score


def test_multi_source_agreement_boosts_candidate() -> None:
    candidate = _candidate(
        "merged",
        source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
        content="raise TypeError('bad input')",
        metadata={
            "retrieved_by": ["file_context", "exact_search"],
            "source_types": ["file_context", "code_exact"],
        },
    )

    score = EvidenceScoringRules().score_candidate(candidate, _facts())

    assert score.multi_source_agreement > 0.0
    assert "Candidate was retrieved by multiple sources" in score.reasons


def test_noise_path_penalty_applies_to_tests() -> None:
    candidate = _candidate(
        "test-context",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content="raise TypeError('bad input')",
        file_path="tests/test_app.py",
    )

    score = EvidenceScoringRules().score_candidate(candidate, _facts())

    assert score.noise_penalty == 1.0


def test_noise_path_not_penalized_for_test_incident() -> None:
    candidate = _candidate(
        "test-context",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content="raise TypeError('bad input')",
        file_path="tests/test_app.py",
    )

    score = EvidenceScoringRules().score_candidate(
        candidate,
        _facts(summary="Test failure raises TypeError"),
    )

    assert score.noise_penalty == 0.0


def test_graph_distance_scores() -> None:
    near_candidate = _candidate(
        "near",
        source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
        content="Related caller",
        metadata={"graph_distance": 1},
    )
    far_candidate = _candidate(
        "far",
        source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
        content="Distant caller",
        metadata={"graph_distance": 3},
    )
    rules = EvidenceScoringRules()

    near_score = rules.score_candidate(near_candidate, _facts())
    far_score = rules.score_candidate(far_candidate, _facts())

    assert near_score.graph_distance_score > far_score.graph_distance_score


def test_structured_runtime_anchor_scores_above_unrelated_candidate() -> None:
    facts = IncidentFacts(
        incident_id="INC-STRUCTURED-001",
        summary="Worker produced duplicate records",
        log_key_terms=["record_fingerprint"],
        event_terms=["duplicate_record_detected"],
    )
    matching_candidate = _candidate(
        "matching",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content=(
            "record_fingerprint = fingerprint(payload)\n"
            'logger.warning("duplicate_record_detected=true")'
        ),
        file_path="src/worker.py",
    )
    unrelated_candidate = _candidate(
        "unrelated",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content="def healthy_task():\n    return True",
        file_path="src/healthy.py",
    )
    rules = EvidenceScoringRules()

    matching_score = rules.score_candidate(matching_candidate, facts)
    unrelated_score = rules.score_candidate(unrelated_candidate, facts)

    assert matching_score.final_score > unrelated_score.final_score
    assert matching_score.directness == 1.0
    assert matching_score.incident_term_overlap >= 0.60
    assert any("structured runtime anchor" in reason for reason in matching_score.reasons)


def test_multiple_structured_runtime_anchors_score_above_single_anchor() -> None:
    facts = IncidentFacts(
        incident_id="INC-STRUCTURED-002",
        summary="Worker produced duplicate records",
        log_key_terms=["record_fingerprint"],
        event_terms=["duplicate_record_detected"],
    )
    single_anchor_candidate = _candidate(
        "single",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content="record_fingerprint = fingerprint(payload)",
        file_path="src/helper.py",
    )
    multiple_anchor_candidate = _candidate(
        "multiple",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        content=(
            "record_fingerprint = fingerprint(payload)\n"
            'logger.warning("duplicate_record_detected=true")'
        ),
        file_path="src/worker.py",
    )
    rules = EvidenceScoringRules()

    single_score = rules.score_candidate(single_anchor_candidate, facts)
    multiple_score = rules.score_candidate(multiple_anchor_candidate, facts)

    assert multiple_score.incident_term_overlap > single_score.incident_term_overlap
    assert multiple_score.final_score > single_score.final_score
    assert multiple_score.final_score > 0.5
