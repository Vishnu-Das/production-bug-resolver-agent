from __future__ import annotations

import pytest

from bug_resolver.agents import ContextPlanningAgent, ContextPlanningInput
from bug_resolver.schemas import Incident, LogAnalysisResult, StackTraceFrame
from bug_resolver.schemas.common import IncidentSeverity, IncidentStatus


@pytest.mark.asyncio
async def test_context_planning_agent_creates_plan_from_incident_and_logs() -> None:
    agent = ContextPlanningAgent()

    incident = Incident(
        incident_id="INC-001",
        title="Summary query fails",
        description="Users get 500 error while asking document summary questions.",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.NEW,
        affected_service="conversational_rag",
        affected_area="summary flow",
    )

    log_analysis = LogAnalysisResult(
        summary="Found KeyError: 'output'.",
        exception_type="KeyError",
        exception_message="'output'",
        stack_trace=[
            StackTraceFrame(
                file_path="src/rag/llm.py",
                line_number=18,
                function_name="route",
                raw_frame='File "src/rag/llm.py", line 18, in route',
            )
        ],
        suspected_file_paths=["src/rag/llm.py"],
        suspected_function_names=["route"],
        likely_failure_point="src/rag/llm.py:18 in route",
    )

    result = await agent.run(
        ContextPlanningInput(
            incident=incident,
            log_analysis=log_analysis,
        )
    )

    assert result.plan_id.startswith("CTX-")
    assert "Summary query fails" in result.code_search_queries
    assert "Users get 500 error while asking document summary questions." in result.code_search_queries
    assert "KeyError" in result.code_search_queries
    assert "'output'" in result.code_search_queries
    assert "src/rag/llm.py" in result.code_search_queries
    assert "route" in result.code_search_queries
    assert "src/rag/llm.py route" in result.code_search_queries

    assert "conversational_rag" in result.knowledge_search_queries
    assert "summary flow" in result.knowledge_search_queries
    assert "KeyError troubleshooting" in result.knowledge_search_queries
    assert "'output' expected behavior" in result.knowledge_search_queries

    assert result.files_to_prioritize == ["src/rag/llm.py"]
    assert result.functions_to_prioritize == ["route"]
    assert result.missing_evidence_hints == []
    assert result.generated_from == "incident+exception+stack_trace+suspected_files+suspected_functions"
    assert result.metadata == {"incident_id": "INC-001"}


@pytest.mark.asyncio
async def test_context_planning_agent_adds_missing_evidence_hints() -> None:
    agent = ContextPlanningAgent()

    incident = Incident(
        incident_id="INC-002",
        title="Chat fails",
        description="Chat endpoint fails intermittently.",
    )

    log_analysis = LogAnalysisResult(
        summary="No explicit exception or stack trace was found.",
    )

    result = await agent.run(
        ContextPlanningInput(
            incident=incident,
            log_analysis=log_analysis,
        )
    )

    assert "No exception type was found in logs." in result.missing_evidence_hints
    assert "No exception message was found in logs." in result.missing_evidence_hints
    assert "No stack trace frames were found in logs." in result.missing_evidence_hints
    assert "No suspected source files were identified from logs." in result.missing_evidence_hints
    assert "No suspected function names were identified from logs." in result.missing_evidence_hints
    assert "Incident affected area was not provided." in result.missing_evidence_hints
    assert result.generated_from == "incident"


@pytest.mark.asyncio
async def test_context_planning_agent_includes_retry_context() -> None:
    agent = ContextPlanningAgent()

    incident = Incident(
        incident_id="INC-003",
        title="Router output missing",
        description="Router response does not contain output key.",
        affected_area="routing",
    )

    log_analysis = LogAnalysisResult(
        summary="Found KeyError.",
        exception_type="KeyError",
        exception_message="'output'",
    )

    result = await agent.run(
        ContextPlanningInput(
            incident=incident,
            log_analysis=log_analysis,
            retry_reason="RCA confidence below threshold.",
            previous_missing_evidence_hints=[
                "Need caller context for route function.",
            ],
        )
    )

    assert result.retry_reason == "RCA confidence below threshold."
    assert "Need caller context for route function." in result.missing_evidence_hints
    assert result.metadata == {"incident_id": "INC-003"}


@pytest.mark.asyncio
async def test_context_planning_agent_deduplicates_queries() -> None:
    agent = ContextPlanningAgent()

    incident = Incident(
        incident_id="INC-004",
        title="KeyError",
        description="KeyError",
        affected_area="KeyError",
    )

    log_analysis = LogAnalysisResult(
        summary="Found KeyError.",
        exception_type="KeyError",
        exception_message="KeyError",
        suspected_file_paths=["src/rag/llm.py", "src/rag/llm.py"],
        suspected_function_names=["route", "route"],
    )

    result = await agent.run(
        ContextPlanningInput(
            incident=incident,
            log_analysis=log_analysis,
        )
    )

    assert result.code_search_queries.count("KeyError") == 1
    assert result.files_to_prioritize == ["src/rag/llm.py"]
    assert result.functions_to_prioritize == ["route"]