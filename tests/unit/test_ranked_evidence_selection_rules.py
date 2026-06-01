"""Tests for structural-support preservation during ranked evidence selection."""

from bug_resolver.rules import RankedEvidenceSelectionRules
from bug_resolver.schemas import (
    EvidenceCandidate,
    EvidenceScoreBreakdown,
    RankedEvidence,
    RetrievalEvidenceSourceType,
)


def ranked_evidence(
    candidate_id: str,
    source_type: RetrievalEvidenceSourceType,
    *,
    rank: int,
    score: float,
    file_path: str | None = None,
) -> RankedEvidence:
    return RankedEvidence(
        candidate=EvidenceCandidate(
            candidate_id=candidate_id,
            source_type=source_type,
            retriever_name=source_type.value,
            content=f"{candidate_id} context",
            file_path=file_path,
        ),
        score=EvidenceScoreBreakdown(final_score=score),
        rank=rank,
    )


def test_selection_retains_graph_support_over_semantic_only_context() -> None:
    selected = RankedEvidenceSelectionRules().select(
        [
            ranked_evidence(
                "exact",
                RetrievalEvidenceSourceType.CODE_EXACT,
                rank=1,
                score=0.9,
            ),
            ranked_evidence(
                "semantic",
                RetrievalEvidenceSourceType.CODE_SEMANTIC,
                rank=2,
                score=0.8,
            ),
            ranked_evidence(
                "graph",
                RetrievalEvidenceSourceType.CODE_GRAPH,
                rank=3,
                score=0.7,
            ),
        ],
        max_selected=2,
        minimum_score=0.35,
    )

    assert [evidence.candidate.candidate_id for evidence in selected] == [
        "exact",
        "graph",
    ]


def test_selection_does_not_displace_direct_code_for_graph_support() -> None:
    selected = RankedEvidenceSelectionRules().select(
        [
            ranked_evidence(
                "file",
                RetrievalEvidenceSourceType.FILE_CONTEXT,
                rank=1,
                score=0.9,
            ),
            ranked_evidence(
                "exact",
                RetrievalEvidenceSourceType.CODE_EXACT,
                rank=2,
                score=0.8,
            ),
            ranked_evidence(
                "graph",
                RetrievalEvidenceSourceType.CODE_GRAPH,
                rank=3,
                score=0.7,
            ),
        ],
        max_selected=2,
        minimum_score=0.35,
    )

    assert [evidence.candidate.candidate_id for evidence in selected] == [
        "file",
        "exact",
    ]


def test_selection_ignores_graph_support_below_minimum_score() -> None:
    selected = RankedEvidenceSelectionRules().select(
        [
            ranked_evidence(
                "semantic",
                RetrievalEvidenceSourceType.CODE_SEMANTIC,
                rank=1,
                score=0.8,
            ),
            ranked_evidence(
                "graph",
                RetrievalEvidenceSourceType.CODE_GRAPH,
                rank=2,
                score=0.2,
            ),
        ],
        max_selected=1,
        minimum_score=0.35,
    )

    assert [evidence.candidate.candidate_id for evidence in selected] == ["semantic"]


def test_selection_prefers_graph_context_for_direct_source_owner_path() -> None:
    selected = RankedEvidenceSelectionRules().select(
        [
            ranked_evidence(
                "exact-owner",
                RetrievalEvidenceSourceType.CODE_EXACT,
                rank=1,
                score=0.9,
                file_path="src/services/processor.py",
            ),
            ranked_evidence(
                "graph-downstream",
                RetrievalEvidenceSourceType.CODE_GRAPH,
                rank=2,
                score=0.8,
                file_path="src/ui/renderer.py",
            ),
            ranked_evidence(
                "semantic",
                RetrievalEvidenceSourceType.CODE_SEMANTIC,
                rank=3,
                score=0.7,
            ),
            ranked_evidence(
                "graph-owner",
                RetrievalEvidenceSourceType.CODE_GRAPH,
                rank=4,
                score=0.2,
                file_path="src/services/processor.py",
            ),
        ],
        max_selected=3,
        minimum_score=0.35,
    )

    assert [evidence.candidate.candidate_id for evidence in selected] == [
        "exact-owner",
        "semantic",
        "graph-owner",
    ]
