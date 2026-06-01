"""Tests for deterministic retrieval evidence ranking and evaluation."""

from __future__ import annotations

from bug_resolver.retrieval.evidence_ranker import EvidenceRanker
from bug_resolver.schemas import (
    EvidenceCandidate,
    IncidentFacts,
    RetrievalEvidenceSourceType,
    StackFrame,
)


def _facts() -> IncidentFacts:
    return IncidentFacts(
        incident_id="INC-001",
        summary="Request fails with TypeError",
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
        metadata=metadata or {},
    )


def _strong_candidate(candidate_id: str = "strong") -> EvidenceCandidate:
    return _candidate(
        candidate_id,
        source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
        content="42: def handle_request():\n43:     raise TypeError('bad input')",
        file_path="src/app.py",
        start_line=35,
        end_line=50,
    )


def _weak_semantic_candidate(candidate_id: str = "semantic") -> EvidenceCandidate:
    return _candidate(
        candidate_id,
        source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
        content="Background maintenance schedule",
        file_path="src/maintenance.py",
    )


def test_ranker_sorts_by_final_score() -> None:
    ranked = EvidenceRanker().rank([_weak_semantic_candidate(), _strong_candidate()], _facts())

    assert ranked[0].candidate.candidate_id == "strong"
    assert ranked[0].rank == 1


def test_ranker_assigns_stable_ranks() -> None:
    ranked = EvidenceRanker().rank(
        [_strong_candidate(), _weak_semantic_candidate(), _strong_candidate("second")],
        _facts(),
    )

    assert [evidence.rank for evidence in ranked] == [1, 2, 3]
    assert [evidence.candidate.candidate_id for evidence in ranked[:2]] == [
        "strong",
        "second",
    ]


def test_evaluate_selects_top_candidates() -> None:
    result = EvidenceRanker().evaluate(
        [_strong_candidate(), _strong_candidate("second"), _weak_semantic_candidate()],
        _facts(),
        max_selected=1,
        minimum_score=0.35,
    )

    assert len(result.selected_evidence) == 1
    assert result.selected_evidence[0].candidate.candidate_id == "strong"
    assert result.selected_evidence[0].score.final_score >= 0.35


def test_evaluate_sets_flags() -> None:
    candidates = [
        _strong_candidate(),
        _candidate(
            "kb",
            source_type=RetrievalEvidenceSourceType.KNOWLEDGE_BASE,
            content="TypeError request troubleshooting notes",
        ),
        _candidate(
            "graph",
            source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
            content="handle_request caller raises TypeError",
            metadata={"graph_distance": 1},
        ),
    ]

    result = EvidenceRanker().evaluate(candidates, _facts(), minimum_score=0.0)

    assert result.has_direct_code_evidence is True
    assert result.has_supporting_kb_evidence is True
    assert result.has_graph_support is True
    assert result.sufficient_for_rca is True


def test_evaluate_reports_missing_evidence() -> None:
    result = EvidenceRanker().evaluate([_weak_semantic_candidate()], _facts())

    assert result.sufficient_for_rca is False
    assert result.selected_evidence == []
    assert "No direct code evidence selected" in result.missing_evidence
    assert "No runtime/log evidence selected" in result.missing_evidence
    assert "Evidence is insufficient for RCA" in result.warnings


def test_evaluate_reports_only_semantic_selected() -> None:
    candidate = _candidate(
        "semantic",
        source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
        content="TypeError request failure",
    )

    result = EvidenceRanker().evaluate([candidate], _facts(), minimum_score=0.0)

    assert "Only weak semantic evidence selected" in result.missing_evidence


def test_evaluate_confidence_uses_top_selected_scores() -> None:
    result = EvidenceRanker().evaluate(
        [_strong_candidate(), _strong_candidate("second")],
        _facts(),
    )

    expected_confidence = sum(
        evidence.score.final_score for evidence in result.selected_evidence[:3]
    ) / len(result.selected_evidence[:3])
    assert result.confidence == expected_confidence
    assert 0.0 <= result.confidence <= 1.0


def test_ranker_exposes_merged_supporting_candidate_ids() -> None:
    candidate = _strong_candidate().model_copy(
        update={"metadata": {"merged_candidate_ids": ["strong", "exact-match"]}}
    )

    ranked = EvidenceRanker().rank([candidate], _facts())

    assert ranked[0].supporting_candidate_ids == ["exact-match"]
