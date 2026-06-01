"""Tests for deterministic retrieval evidence deduplication."""

from __future__ import annotations

from bug_resolver.retrieval.evidence_deduplicator import EvidenceDeduplicator
from bug_resolver.schemas import EvidenceCandidate, RetrievalEvidenceSourceType


def _candidate(
    candidate_id: str,
    *,
    source_type: RetrievalEvidenceSourceType = RetrievalEvidenceSourceType.CODE_EXACT,
    retriever_name: str = "exact_search",
    content: str = "raise TypeError('bad input')",
    file_path: str | None = "src/app.py",
    start_line: int | None = None,
    end_line: int | None = None,
    symbol_name: str | None = None,
    matched_terms: list[str] | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        candidate_id=candidate_id,
        source_type=source_type,
        retriever_name=retriever_name,
        content=content,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        symbol_name=symbol_name,
        matched_terms=matched_terms or [],
    )


def test_evidence_deduplicator_merges_same_candidate_id() -> None:
    candidates = [
        _candidate("candidate-1", matched_terms=["TypeError"]),
        _candidate("candidate-1", retriever_name="second_route", matched_terms=["bad input"]),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert len(deduplicated) == 1
    assert deduplicated[0].candidate_id == "candidate-1"
    assert deduplicated[0].matched_terms == ["TypeError", "bad input"]
    assert deduplicated[0].metadata["merged_count"] == 2


def test_evidence_deduplicator_merges_overlapping_same_file_ranges() -> None:
    wider_content = "\n".join(f"{line}: source line {line}" for line in range(40, 61))
    candidates = [
        _candidate(
            "file-context",
            source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
            retriever_name="file_context",
            content=wider_content,
            start_line=40,
            end_line=60,
        ),
        _candidate(
            "exact-match",
            content="\n".join(f"{line}: source line {line}" for line in range(45, 56)),
            start_line=45,
            end_line=55,
            matched_terms=["TypeError"],
        ),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert len(deduplicated) == 1
    candidate = deduplicated[0]
    assert candidate.candidate_id == "file-context"
    assert candidate.start_line == 40
    assert candidate.end_line == 60
    assert candidate.content == wider_content
    assert candidate.matched_terms == ["TypeError"]
    assert candidate.metadata["merged_candidate_ids"] == ["file-context", "exact-match"]
    assert candidate.metadata["retrieved_by"] == ["file_context", "exact_search"]
    assert candidate.metadata["source_types"] == ["file_context", "code_exact"]
    assert candidate.metadata["merged_count"] == 2


def test_evidence_deduplicator_keeps_non_overlapping_ranges_separate() -> None:
    candidates = [
        _candidate("first", content="first region", start_line=10, end_line=20),
        _candidate("second", content="second region", start_line=80, end_line=90),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert [candidate.candidate_id for candidate in deduplicated] == ["first", "second"]


def test_evidence_deduplicator_merges_same_file_same_symbol_without_ranges() -> None:
    candidates = [
        _candidate("first", symbol_name="handle_request", content="definition"),
        _candidate("second", symbol_name="handle_request", content="usage"),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert len(deduplicated) == 1
    assert deduplicated[0].symbol_name == "handle_request"
    assert deduplicated[0].metadata["merged_count"] == 2


def test_evidence_deduplicator_merges_identical_content() -> None:
    candidates = [
        _candidate("first", file_path="src/app.py", content="shared source"),
        _candidate(
            "second",
            retriever_name="semantic_code",
            source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
            file_path="src/service.py",
            content="shared source",
        ),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert len(deduplicated) == 1
    assert deduplicated[0].metadata["retrieved_by"] == ["exact_search", "semantic_code"]
    assert deduplicated[0].metadata["source_types"] == ["code_exact", "code_semantic"]


def test_evidence_deduplicator_preserves_first_seen_order() -> None:
    candidates = [
        _candidate("first", content="shared source"),
        _candidate("duplicate", retriever_name="second_route", content="shared source"),
        _candidate("third", file_path="src/other.py", content="different source"),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert [candidate.candidate_id for candidate in deduplicated] == ["first", "third"]


def test_evidence_deduplicator_does_not_merge_different_files_with_different_content() -> None:
    candidates = [
        _candidate("first", file_path="src/app.py", content="first source"),
        _candidate("second", file_path="src/service.py", content="second source"),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert [candidate.candidate_id for candidate in deduplicated] == ["first", "second"]


def test_evidence_deduplicator_keeps_distant_identical_same_file_ranges_separate() -> None:
    candidates = [
        _candidate("first", content="return value", start_line=10, end_line=20),
        _candidate("second", content="return value", start_line=80, end_line=90),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert [candidate.candidate_id for candidate in deduplicated] == ["first", "second"]


def test_evidence_deduplicator_keeps_graph_summary_separate_from_source_snippet() -> None:
    candidates = [
        _candidate(
            "exact-source",
            content="19: if filename in processed_records:\n20:     return",
            start_line=16,
            end_line=22,
        ),
        _candidate(
            "graph-owner",
            source_type=RetrievalEvidenceSourceType.CODE_GRAPH,
            retriever_name="code_graph_expansion",
            content="Graph context: handle_request calls process_record",
            start_line=10,
            end_line=40,
            symbol_name="handle_request",
        ),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert [candidate.candidate_id for candidate in deduplicated] == [
        "exact-source",
        "graph-owner",
    ]
    assert deduplicated[0].content == (
        "19: if filename in processed_records:\n20:     return"
    )
    assert deduplicated[1].content == "Graph context: handle_request calls process_record"


def test_evidence_deduplicator_prefers_exact_source_over_semantic_summary() -> None:
    candidates = [
        _candidate(
            "semantic",
            source_type=RetrievalEvidenceSourceType.CODE_SEMANTIC,
            retriever_name="semantic_code_search",
            content="A much longer semantic explanation of the implementation behavior",
            start_line=10,
            end_line=40,
            symbol_name="handle_request",
        ),
        _candidate(
            "exact-source",
            content="19: if filename in processed_records:",
            start_line=19,
            end_line=19,
            symbol_name="handle_request",
        ),
    ]

    deduplicated = EvidenceDeduplicator().deduplicate(candidates)

    assert len(deduplicated) == 1
    assert deduplicated[0].content == "19: if filename in processed_records:"
