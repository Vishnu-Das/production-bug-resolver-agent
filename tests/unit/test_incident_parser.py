"""Tests for deterministic incident fact parsing."""

from __future__ import annotations

from bug_resolver.retrieval.incident_parser import IncidentParser
from bug_resolver.schemas import Incident, LogEntry


def test_incident_parser_extracts_python_stack_frame() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-001",
        summary="Request processing failed",
        log_texts=[
            """Traceback (most recent call last):
  File "src/app.py", line 42, in handle_request
    result = service.run()
TypeError: 'NoneType' object is not iterable"""
        ],
    )

    assert facts.stack_frames[0].file_path == "src/app.py"
    assert facts.stack_frames[0].line_number == 42
    assert facts.stack_frames[0].function_name == "handle_request"
    assert "TypeError" in facts.exception_types
    assert "handle_request" in facts.candidate_symbols


def test_incident_parser_extracts_path_line_pattern() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-002",
        summary="Payment processing failed",
        log_texts=["ERROR src/services/payment.py:88 in charge_card failed"],
    )

    assert facts.stack_frames[0].file_path == "src/services/payment.py"
    assert facts.stack_frames[0].line_number == 88
    assert facts.stack_frames[0].function_name == "charge_card"


def test_incident_parser_extracts_status_codes() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-003",
        summary="Search request failed",
        log_texts=["Request returned HTTP 503 for /api/search"],
    )

    assert facts.status_codes == [503]


def test_incident_parser_extracts_trace_and_request_ids() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-004",
        summary="Request failed",
        log_texts=["trace_id=abc123 requestId=req-456 X-Request-ID: req-789"],
    )

    assert facts.trace_ids == ["abc123"]
    assert facts.request_ids == ["req-456", "req-789"]


def test_incident_parser_extracts_quoted_terms() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-005",
        summary='User reports "search results are empty" after deployment',
    )

    assert facts.quoted_terms == ["search results are empty"]


def test_incident_parser_extracts_config_like_terms() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-006",
        summary="Environment configuration is missing",
        log_texts=["Missing RERANKING_MODEL_NAME in environment"],
    )

    assert facts.config_like_terms == ["RERANKING_MODEL_NAME"]


def test_incident_parser_extracts_structured_log_keys() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-STRUCTURED-001",
        summary="Worker produced duplicate records",
        log_texts=[
            'content_hash="abc123" dedupe_key="record:abc123" '
            "processed_uploads_match=true"
        ],
    )

    assert facts.log_key_terms == [
        "content_hash",
        "dedupe_key",
        "processed_uploads_match",
    ]


def test_incident_parser_extracts_json_log_keys() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-STRUCTURED-002",
        summary="Runtime event was recorded",
        log_texts=['{"event": "cache_refresh_failed", "content_hash": "abc123"}'],
    )

    assert facts.log_key_terms == ["event", "content_hash"]


def test_incident_parser_extracts_event_values_and_runtime_snake_case_terms() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-STRUCTURED-003",
        summary="Runtime workflow changed",
        log_texts=[
            "event=cache_refresh_failed action=indexing_started "
            "name=document_uploaded processed_uploads_match=true"
        ],
    )

    assert facts.event_terms == [
        "cache_refresh_failed",
        "indexing_started",
        "document_uploaded",
        "processed_uploads_match",
    ]


def test_incident_parser_deduplicates_structured_terms_and_avoids_noisy_values() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-STRUCTURED-004",
        summary="Runtime workflow changed",
        log_texts=[
            "request_id=req_123 trace_id=trace_456 event=cache_refresh_failed "
            'filename="guide.pdf" digest="aabbccddeeff00112233445566778899" '
            "correlation_id=123e4567-e89b-12d3-a456-426614174000 "
            "cache_refresh_failed=true",
            "event=cache_refresh_failed",
        ],
    )

    assert facts.log_key_terms == [
        "event",
        "filename",
        "digest",
        "cache_refresh_failed",
    ]
    assert facts.event_terms == ["cache_refresh_failed"]
    assert "request_id" not in facts.log_key_terms
    assert "trace_id" not in facts.log_key_terms
    assert "req_123" not in facts.event_terms
    assert "trace_456" not in facts.event_terms
    assert "guide.pdf" not in facts.event_terms
    assert "aabbccddeeff00112233445566778899" not in facts.event_terms
    assert "123e4567-e89b-12d3-a456-426614174000" not in facts.event_terms


def test_incident_parser_extracts_candidate_symbols_from_text() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-007",
        summary="BillingService fails while calling payment.charge_card()",
    )

    assert "BillingService" in facts.candidate_symbols
    assert "payment.charge_card" in facts.candidate_symbols
    assert "charge_card" in facts.candidate_symbols


def test_incident_parser_does_not_treat_runtime_modules_or_filenames_as_symbols() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-STRUCTURED-005",
        summary="Runtime workflow changed",
        log_texts=['service.worker filename="guide.pdf" worker.step_started=true'],
    )

    assert facts.candidate_symbols == []


def test_incident_parser_deduplicates_preserving_order() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-008",
        summary="TypeError while calling handle_request()",
        log_texts=[
            "TypeError: failed in handle_request()",
            "TypeError: failed in handle_request()",
            "ValueError: invalid input",
        ],
    )

    assert facts.exception_types == ["TypeError", "ValueError"]
    assert facts.error_terms == [
        "TypeError while calling handle_request()",
        "TypeError: failed in handle_request()",
        "ValueError: invalid input",
    ]
    assert facts.candidate_symbols.count("handle_request") == 1


def test_incident_parser_handles_empty_logs() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-009",
        summary="Background job is delayed",
        description="The job has not completed yet.",
        log_texts=[],
    )

    assert facts.incident_id == "INC-009"
    assert facts.summary == "Background job is delayed"
    assert facts.description == "The job has not completed yet."
    assert facts.stack_frames == []


def test_incident_parser_supports_existing_incident_and_log_entry_schemas() -> None:
    facts = IncidentParser().parse_incident(
        Incident(
            incident_id="INC-010",
            title="Request processing failed",
            description="A request cannot be completed.",
        ),
        [
            LogEntry(
                log_id="log-1",
                message="Request failed",
                raw='File "src/handlers/api.py", line 17, in process_request',
                trace_id="trace-10",
                request_id="request-10",
            )
        ],
    )

    assert facts.stack_frames[0].file_path == "src/handlers/api.py"
    assert facts.trace_ids == ["trace-10"]
    assert facts.request_ids == ["request-10"]


def test_incident_parser_is_repo_agnostic() -> None:
    facts = IncidentParser().parse(
        incident_id="INC-011",
        summary="Worker execution failed",
        log_texts=[
            'File "src/workers/task_runner.py", line 21, in execute_task\n'
            "TimeoutError: operation timed out"
        ],
    )

    assert facts.stack_frames[0].file_path == "src/workers/task_runner.py"
    assert facts.exception_types == ["TimeoutError"]
    assert "execute_task" in facts.candidate_symbols
