"""End-to-end tests for deterministic incident-driven context retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.providers.retrieval import (
    LocalExactSearchProvider,
    LocalFileContextProvider,
)
from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import RetrievalEvidenceSourceType


def _write_file(repo_path: Path, relative_path: str, content: str) -> None:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _build_service(repo_path: Path) -> IncidentDrivenContextService:
    return IncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=LocalFileContextProvider(repo_path),
            exact_search_provider=LocalExactSearchProvider(repo_path),
        )
    )


@pytest.mark.asyncio
async def test_incident_driven_pipeline_finds_generic_source_owner(tmp_path: Path) -> None:
    repo_path = tmp_path / "tmp_repo"
    _write_file(
        repo_path,
        "src/service.py",
        "\n".join(
            [
                "from .config import DEFAULT_TIMEOUT",
                "",
                "",
                "def handle_request(payload):",
                "    if payload is None:",
                '        raise TypeError("payload cannot be None")',
                "    timeout = get_timeout()",
                '    return {"ok": True, "timeout": timeout}',
                "",
                "",
                "def get_timeout():",
                "    return DEFAULT_TIMEOUT",
            ]
        ),
    )
    _write_file(repo_path, "src/config.py", "DEFAULT_TIMEOUT = 30\n")
    _write_file(
        repo_path,
        "tests/test_service.py",
        "\n".join(
            [
                "from src.service import handle_request",
                "",
                "",
                "def test_handle_request_none():",
                "    try:",
                "        handle_request(None)",
                "    except TypeError:",
                "        pass",
            ]
        ),
    )
    _write_file(
        repo_path,
        "README.md",
        "# Service behavior\nRequests with valid payloads should return ok responses.\n",
    )

    result = await _build_service(repo_path).build_context(
        incident_id="INC-GENERIC-001",
        summary='Users report "request fails for empty payload" after deployment.',
        description="The service returns HTTP 500 for empty payload requests.",
        log_texts=[
            "\n".join(
                [
                    "Traceback (most recent call last):",
                    '  File "src/service.py", line 4, in handle_request',
                    '    raise TypeError("payload cannot be None")',
                    "TypeError: payload cannot be None",
                    "request_id=req-123 trace_id=trace-456",
                    "HTTP 500 returned for /request",
                ]
            )
        ],
    )

    assert "TypeError" in result.facts.exception_types
    assert any(
        frame.file_path == "src/service.py"
        and frame.line_number == 4
        and frame.function_name == "handle_request"
        for frame in result.facts.stack_frames
    )
    assert 500 in result.facts.status_codes
    assert "req-123" in result.facts.request_ids
    assert "trace-456" in result.facts.trace_ids
    assert "request fails for empty payload" in result.facts.quoted_terms

    assert any(
        request.file_path == "src/service.py" and request.line_number == 4
        for request in result.retrieval_plan.file_context_requests
    )
    exact_queries = {query.query for query in result.retrieval_plan.exact_queries}
    assert "TypeError" in exact_queries
    assert "handle_request" in exact_queries
    assert result.retrieval_plan.semantic_queries
    assert result.retrieval_plan.kb_queries

    assert any(
        candidate.source_type == RetrievalEvidenceSourceType.FILE_CONTEXT
        and candidate.file_path == "src/service.py"
        for candidate in result.raw_candidates
    )
    assert any(
        candidate.source_type == RetrievalEvidenceSourceType.CODE_EXACT
        and candidate.file_path == "src/service.py"
        for candidate in result.raw_candidates
    )
    assert len(result.deduplicated_candidates) <= len(result.raw_candidates)
    assert len(
        {candidate.candidate_id for candidate in result.deduplicated_candidates}
    ) == len(result.deduplicated_candidates)

    assert result.evaluation.selected_evidence
    top_evidence = result.evaluation.selected_evidence[0]
    assert top_evidence.candidate.file_path == "src/service.py"
    assert top_evidence.candidate.source_type in {
        RetrievalEvidenceSourceType.FILE_CONTEXT,
        RetrievalEvidenceSourceType.CODE_EXACT,
    }
    assert top_evidence.score.final_score > 0.5
    assert any("stack trace file src/service.py" in reason for reason in top_evidence.score.reasons)
    assert any("error term TypeError" in reason for reason in top_evidence.score.reasons)
    assert any("stack trace line 4" in reason for reason in top_evidence.score.reasons)

    ranked_test_evidence = [
        evidence
        for evidence in result.evaluation.ranked_evidence
        if evidence.candidate.file_path == "tests/test_service.py"
    ]
    assert all(
        evidence.score.final_score < top_evidence.score.final_score
        for evidence in ranked_test_evidence
    )

    assert result.evaluation.has_direct_code_evidence is True
    assert result.evaluation.sufficient_for_rca is True
    assert 0.0 <= result.evaluation.confidence <= 1.0
    assert "No direct code evidence selected" not in result.evaluation.missing_evidence


@pytest.mark.asyncio
async def test_incident_driven_pipeline_marks_weak_when_no_matching_files(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tmp_repo"
    _write_file(repo_path, "src/other.py", "def healthy_task():\n    return 'ok'\n")

    result = await _build_service(repo_path).build_context(
        incident_id="INC-GENERIC-002",
        summary="Background request fails",
        description="The implementation owner has not been identified.",
        log_texts=[
            "\n".join(
                [
                    "Traceback (most recent call last):",
                    '  File "src/missing.py", line 99, in process_request',
                    "ValueError: invalid payload",
                ]
            )
        ],
    )

    assert result.raw_candidates == []
    assert result.evaluation.selected_evidence == []
    assert result.evaluation.has_direct_code_evidence is False
    assert result.evaluation.sufficient_for_rca is False
    assert "No direct code evidence selected" in result.evaluation.missing_evidence
    assert "Evidence is insufficient for RCA" in result.evaluation.warnings


@pytest.mark.asyncio
async def test_incident_driven_pipeline_selects_structured_log_owner_without_stack_trace(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tmp_repo"
    _write_file(
        repo_path,
        "src/processor.py",
        "\n".join(
            [
                "def process_record(record_fingerprint):",
                "    if already_processed(record_fingerprint):",
                '        log_event("duplicate_record_detected")',
                "        return False",
                "    return True",
            ]
        ),
    )

    result = await _build_service(repo_path).build_context(
        incident_id="INC-GENERIC-003",
        summary="Duplicate records appear after processing",
        description="The same record appears more than once.",
        log_texts=[
            "event=duplicate_record_detected record_fingerprint=abc123 "
            "request_id=req-123"
        ],
    )

    assert "record_fingerprint" in result.facts.log_key_terms
    assert "duplicate_record_detected" in result.facts.event_terms
    assert {query.query for query in result.retrieval_plan.exact_queries} >= {
        "record_fingerprint",
        "duplicate_record_detected",
    }
    assert result.evaluation.selected_evidence
    top_evidence = result.evaluation.selected_evidence[0]
    assert top_evidence.candidate.file_path == "src/processor.py"
    assert top_evidence.candidate.source_type == RetrievalEvidenceSourceType.CODE_EXACT
    assert top_evidence.score.final_score >= 0.35
    assert any(
        "structured runtime anchor" in reason for reason in top_evidence.score.reasons
    )
    assert result.evaluation.has_direct_code_evidence is True
