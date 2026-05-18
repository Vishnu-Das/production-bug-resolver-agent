from __future__ import annotations

import pytest

from bug_resolver.agents import LogAnalysisAgent
from bug_resolver.schemas import LogEntry
from bug_resolver.schemas.common import EvidenceSourceType, LogLevel


@pytest.mark.asyncio
async def test_log_analysis_agent_extracts_exception_and_stack_trace() -> None:
    agent = LogAnalysisAgent()
    logs = [
        LogEntry(
            log_id="log-001",
            level=LogLevel.ERROR,
            message="Application error",
            raw=(
                "Traceback (most recent call last):\n"
                '  File "src/rag/router.py", line 42, in route_query\n'
                "    return router.route(query)\n"
                '  File "src/rag/llm.py", line 18, in route\n'
                "    return response['output']\n"
                "KeyError: 'output'"
            ),
            request_id="req-123",
            trace_id="trace-456",
            service_name="conversational_rag",
            environment="test",
        )
    ]

    result = await agent.run(logs)

    assert result.exception_type == "KeyError"
    assert result.exception_message == "'output'"
    assert len(result.stack_trace) == 2

    assert result.stack_trace[0].file_path == "src/rag/router.py"
    assert result.stack_trace[0].line_number == 42
    assert result.stack_trace[0].function_name == "route_query"

    assert result.stack_trace[1].file_path == "src/rag/llm.py"
    assert result.stack_trace[1].line_number == 18
    assert result.stack_trace[1].function_name == "route"

    assert result.suspected_file_paths == [
        "src/rag/router.py",
        "src/rag/llm.py",
    ]
    assert result.suspected_function_names == [
        "route_query",
        "route",
    ]
    assert result.request_ids == ["req-123"]
    assert result.trace_ids == ["trace-456"]
    assert result.likely_failure_point == "src/rag/llm.py:18 in route"
    assert "KeyError" in result.summary
    assert "'output'" in result.summary


@pytest.mark.asyncio
async def test_log_analysis_agent_creates_log_evidence_items() -> None:
    agent = LogAnalysisAgent()
    logs = [
        LogEntry(
            log_id="log-001",
            level=LogLevel.ERROR,
            message="Something failed",
            raw="ValueError: Invalid input",
        ),
        LogEntry(
            log_id="log-002",
            level=LogLevel.INFO,
            message="Request completed",
        ),
    ]

    result = await agent.run(logs)

    assert len(result.evidence_items) == 2
    assert result.evidence_items[0].source_type == EvidenceSourceType.LOG
    assert result.evidence_items[0].source_name == "log-001"
    assert result.evidence_items[0].content == "ValueError: Invalid input"
    assert result.evidence_items[0].confidence == 1.0

    assert result.evidence_items[1].source_type == EvidenceSourceType.LOG
    assert result.evidence_items[1].source_name == "log-002"
    assert result.evidence_items[1].content == "Request completed"


@pytest.mark.asyncio
async def test_log_analysis_agent_extracts_request_and_trace_ids_from_text() -> None:
    agent = LogAnalysisAgent()
    logs = [
        LogEntry(
            log_id="log-001",
            level=LogLevel.ERROR,
            message="request_id=req-abc trace_id=trace-xyz RuntimeError: Failed",
        ),
    ]

    result = await agent.run(logs)

    assert result.request_ids == ["req-abc"]
    assert result.trace_ids == ["trace-xyz"]
    assert result.exception_type == "RuntimeError"
    assert result.exception_message == "Failed"


@pytest.mark.asyncio
async def test_log_analysis_agent_handles_logs_without_exception() -> None:
    agent = LogAnalysisAgent()
    logs = [
        LogEntry(
            log_id="log-001",
            level=LogLevel.INFO,
            message="User submitted a query",
        )
    ]

    result = await agent.run(logs)

    assert result.exception_type is None
    assert result.exception_message is None
    assert result.stack_trace == []
    assert result.suspected_file_paths == []
    assert result.suspected_function_names == []
    assert result.likely_failure_point is None
    assert "No explicit exception" in result.summary


@pytest.mark.asyncio
async def test_log_analysis_agent_rejects_empty_log_list() -> None:
    agent = LogAnalysisAgent()

    with pytest.raises(ValueError, match="received no logs"):
        await agent.run([])