"""Tests for ranked implementation-owner graph expansion rules."""

from bug_resolver.rules import OwnerGraphExpansionRules
from bug_resolver.schemas import (
    EvidenceCandidate,
    EvidenceScoreBreakdown,
    GraphExpansionRequest,
    RankedEvidence,
    RetrievalEvidenceSourceType,
)


def ranked_evidence(
    candidate_id: str,
    file_path: str,
    *,
    score: float = 0.6,
    source_type: RetrievalEvidenceSourceType = RetrievalEvidenceSourceType.CODE_EXACT,
    symbol_name: str | None = None,
    start_line: int | None = None,
) -> RankedEvidence:
    return RankedEvidence(
        candidate=EvidenceCandidate(
            candidate_id=candidate_id,
            source_type=source_type,
            retriever_name="exact_search",
            content="def handle_request(): return service.run()",
            file_path=file_path,
            symbol_name=symbol_name,
            start_line=start_line,
        ),
        score=EvidenceScoreBreakdown(final_score=score),
        rank=1,
    )


def test_owner_graph_expansion_builds_shallow_request_from_ranked_code_owner() -> None:
    requests = OwnerGraphExpansionRules().build_requests(
        [
            ranked_evidence(
                "owner-1",
                "src/app.py",
                symbol_name="handle_request",
                start_line=42,
            )
        ]
    )

    assert requests == [
        GraphExpansionRequest(
            file_path="src/app.py",
            symbol_name="handle_request",
            line_number=42,
            max_depth=1,
            reason="Expand graph context from ranked implementation owner src/app.py",
        )
    ]


def test_owner_graph_expansion_skips_support_paths_and_non_code_files() -> None:
    requests = OwnerGraphExpansionRules().build_requests(
        [
            ranked_evidence("test-owner", "tests/test_app.py"),
            ranked_evidence("docs-owner", "docs/app.md"),
            ranked_evidence("source-owner", "src/app.py"),
        ]
    )

    assert [request.file_path for request in requests] == ["src/app.py"]


def test_owner_graph_expansion_deduplicates_paths_and_existing_requests() -> None:
    requests = OwnerGraphExpansionRules().build_requests(
        [
            ranked_evidence("owner-1", "./src\\app.py"),
            ranked_evidence("owner-2", "src/app.py"),
            ranked_evidence("owner-3", "src/service.py"),
        ],
        existing_requests=[
            GraphExpansionRequest(
                file_path="src/app.py",
                reason="Already planned",
            )
        ],
    )

    assert [request.file_path for request in requests] == ["src/service.py"]


def test_owner_graph_expansion_respects_score_and_request_limits() -> None:
    requests = OwnerGraphExpansionRules().build_requests(
        [
            ranked_evidence("weak", "src/weak.py", score=0.34),
            ranked_evidence("first", "src/first.py"),
            ranked_evidence("second", "src/second.py"),
        ],
        max_requests=1,
        minimum_score=0.35,
    )

    assert [request.file_path for request in requests] == ["src/first.py"]
