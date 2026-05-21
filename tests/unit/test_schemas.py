"""Tests for schema validation and workflow state invariants."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from bug_resolver.schemas import (
    AgentDecision,
    AgentExecutionRecord,
    AgentName,
    AgentRunStatus,
    CodeContext,
    EvidenceItem,
    EvidenceSourceType,
    GuardrailDecision,
    Hypothesis,
    Incident,
    IncidentSeverity,
    InvestigationStatus,
    InvestigationStep,
    KnowledgeContext,
    LogAnalysisResult,
    LogEntry,
    LogLevel,
    RCAReport,
    SolutionRecommendation,
    ToolCallResult,
    WorkflowState,
)


def test_incident_schema_accepts_minimum_valid_fields() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Summary query returns 500",
        description="Users see 500 when asking for document summary.",
        severity=IncidentSeverity.HIGH,
    )

    assert incident.incident_id == "INC-001"
    assert incident.severity == IncidentSeverity.HIGH


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Incident(
            incident_id="INC-001",
            title="Bug",
            description="Something failed",
            unknown_field="not allowed",
        )


def test_log_entry_schema() -> None:
    log = LogEntry(
        log_id="log-1",
        level=LogLevel.ERROR,
        message="KeyError: output",
        service_name="conversational-rag",
        request_id="req-123",
    )

    assert log.level == LogLevel.ERROR
    assert log.request_id == "req-123"


def test_evidence_item_validates_confidence_score() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="Traceback...",
            confidence=1.5,
        )


def test_evidence_item_validates_line_range() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="ev-1",
            source_type=EvidenceSourceType.CODE,
            source_name="src/app.py",
            file_path="src/app.py",
            line_start=20,
            line_end=10,
            content="broken code",
        )


def test_code_context_can_convert_to_evidence_item() -> None:
    context = CodeContext(
        context_id="code-1",
        file_path="src/search.py",
        function_name="search_and_summarize",
        line_start=10,
        line_end=30,
        snippet="def search_and_summarize(...): ...",
        relevance_score=0.91,
    )

    evidence = context.to_evidence_item()

    assert evidence.source_type == EvidenceSourceType.CODE
    assert evidence.file_path == "src/search.py"
    assert evidence.line_start == 10
    assert evidence.relevance_score == 0.91
    assert evidence.metadata["function_name"] == "search_and_summarize"
    assert evidence.metadata["qualified_symbol"] == "search_and_summarize"


def test_code_context_evidence_metadata_includes_class_and_qualified_symbol() -> None:
    context = CodeContext(
        context_id="src/reranker.py:CrossEncoderReranker.rerank",
        file_path="src/reranker.py",
        class_name="CrossEncoderReranker",
        function_name="rerank",
        line_start=10,
        line_end=30,
        snippet="def rerank(...): ...",
        metadata={"symbol_type": "method"},
    )

    evidence = context.to_evidence_item()

    assert evidence.evidence_id == "evidence-src/reranker.py:CrossEncoderReranker.rerank"
    assert evidence.metadata["class_name"] == "CrossEncoderReranker"
    assert evidence.metadata["function_name"] == "rerank"
    assert evidence.metadata["qualified_symbol"] == "CrossEncoderReranker.rerank"
    assert evidence.metadata["symbol_type"] == "method"


def test_knowledge_context_can_convert_to_evidence_item() -> None:
    context = KnowledgeContext(
        context_id="kb-1",
        document_name="README.md",
        section_title="Retrieval flow",
        content="The app retrieves documents before answer generation.",
        relevance_score=0.8,
    )

    evidence = context.to_evidence_item()

    assert evidence.source_type == EvidenceSourceType.KNOWLEDGE_BASE
    assert evidence.source_name == "README.md"


def test_log_analysis_result_schema() -> None:
    evidence = EvidenceItem(
        evidence_id="ev-log-1",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="KeyError: output",
        confidence=0.9,
    )

    result = LogAnalysisResult(
        summary="Application failed while reading output key.",
        exception_type="KeyError",
        exception_message="output",
        suspected_file_paths=["src/client.py"],
        suspected_function_names=["get_openai_response"],
        evidence_items=[evidence],
    )

    assert result.exception_type == "KeyError"
    assert result.evidence_items[0].evidence_id == "ev-log-1"


def test_hypothesis_requires_valid_confidence() -> None:
    with pytest.raises(ValidationError):
        Hypothesis(
            hypothesis_id="hyp-1",
            title="Invalid confidence",
            description="Confidence cannot exceed 1.",
            suspected_root_cause="Bad confidence score",
            confidence_score=1.2,
        )


def test_low_confidence_rca_requires_open_questions() -> None:
    with pytest.raises(ValidationError):
        RCAReport(
            report_id="rca-1",
            incident_id="INC-001",
            title="Low confidence RCA",
            incident_summary="Something failed",
            root_cause="Not enough evidence",
            technical_explanation="Evidence is missing",
            confidence_score=0.5,
            confidence_reason="Only logs were available",
        )


def test_valid_rca_report_schema() -> None:
    report = RCAReport(
        report_id="rca-1",
        incident_id="INC-001",
        title="KeyError in response handling",
        incident_summary="Users get 500 during summary generation.",
        symptoms=["HTTP 500"],
        log_findings=["KeyError: output"],
        code_findings=["Code expects output key"],
        knowledge_base_findings=["README describes summary flow"],
        hypotheses_considered=["Response schema mismatch"],
        selected_hypothesis_id="hyp-1",
        root_cause="The app reads a missing output key from the LLM response.",
        technical_explanation="The response object does not contain the expected key.",
        evidence_ids=["ev-log-1", "ev-code-1"],
        confidence_score=0.82,
        confidence_reason="Logs and code point to the same failure.",
    )

    assert report.confidence_score == 0.82
    assert report.evidence_ids == ["ev-log-1", "ev-code-1"]


def test_solution_recommendation_schema() -> None:
    solution = SolutionRecommendation(
        recommendation_id="sol-1",
        incident_id="INC-001",
        rca_report_id="rca-1",
        summary="Normalize LLM response handling.",
        immediate_steps=["Guard missing output key"],
        long_term_steps=["Use structured response model"],
        tests_to_add=["Add test for missing output key"],
        monitoring_improvements=["Log response schema mismatch"],
        confidence_score=0.8,
        evidence_ids=["ev-code-1"],
    )

    assert solution.tests_to_add == ["Add test for missing output key"]


def test_workflow_state_retry_helpers() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(incident=incident, max_replans=2)

    assert state.can_replan() is True

    state.increment_replan()
    state.increment_replan()

    assert state.replan_count == 2
    assert state.can_replan() is False

    with pytest.raises(ValueError):
        state.increment_replan()


def test_workflow_state_accepts_report_path() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(
        incident=incident,
        final_report_path=Path("reports/incidents/INC-001/rca.md"),
    )

    assert state.final_report_path == Path("reports/incidents/INC-001/rca.md")


def test_agent_decision_rejects_invalid_agent_name() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            decision_id="decision-1",
            next_agent="not_registered",
            reason="Invalid route",
        )


def test_agent_decision_finish_must_stop_workflow() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            decision_id="decision-1",
            next_agent=AgentName.FINISH,
            reason="Investigation is complete.",
            should_continue=True,
        )


def test_guardrail_decision_requires_fallback_or_rule_when_blocked() -> None:
    with pytest.raises(ValidationError):
        GuardrailDecision(
            guardrail_id="guardrail-1",
            allowed=False,
            reason="RCA writer is blocked.",
        )


def test_workflow_state_records_dynamic_investigation_trace() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(incident=incident)

    decision = AgentDecision(
        decision_id="decision-1",
        next_agent=AgentName.LOG_INVESTIGATOR,
        reason="Runtime evidence is missing.",
        queries=["INC-001 logs"],
        expected_evidence=["exception type"],
    )
    guardrail = GuardrailDecision(
        guardrail_id="guardrail-1",
        allowed=True,
        reason="Log investigation is allowed.",
    )
    execution = AgentExecutionRecord(
        execution_id="execution-1",
        agent_name=AgentName.LOG_INVESTIGATOR,
        status=AgentRunStatus.SUCCEEDED,
        decision_id="decision-1",
        evidence_ids=["ev-log-1"],
    )
    step = InvestigationStep(
        step_number=state.trace.next_step_number(),
        agent_name=AgentName.LOG_INVESTIGATOR,
        run_status=AgentRunStatus.SUCCEEDED,
        decision_id="decision-1",
        guardrail_id="guardrail-1",
        execution_id="execution-1",
        evidence_ids=["ev-log-1"],
    )

    state.record_decision(decision)
    state.record_guardrail_decision(guardrail)
    state.record_agent_execution(execution)
    state.add_investigation_step(step)

    assert state.current_decision == decision
    assert state.trace.decisions == [decision]
    assert state.trace.guardrail_decisions == [guardrail]
    assert state.trace.agent_executions == [execution]
    assert state.trace.steps == [step]
    assert state.agent_invocation_counts[AgentName.LOG_INVESTIGATOR] == 1


def test_workflow_state_enforces_max_steps() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(incident=incident, max_steps=1)

    state.add_investigation_step(
        InvestigationStep(
            step_number=1,
            agent_name=AgentName.LOG_INVESTIGATOR,
        )
    )

    with pytest.raises(ValueError):
        state.add_investigation_step(
            InvestigationStep(
                step_number=2,
                agent_name=AgentName.CODE_INVESTIGATOR,
            )
        )

    assert state.investigation_status == InvestigationStatus.MAX_STEPS_REACHED


def test_failed_tool_call_result_requires_error() -> None:
    with pytest.raises(ValidationError):
        ToolCallResult(
            tool_call_id="tool-1",
            tool_name="search_logs",
            succeeded=False,
        )


def test_failed_agent_execution_requires_error() -> None:
    with pytest.raises(ValidationError):
        AgentExecutionRecord(
            execution_id="execution-1",
            agent_name=AgentName.CODE_INVESTIGATOR,
            status=AgentRunStatus.FAILED,
        )


def test_workflow_state_tracks_evidence_threshold() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(incident=incident, minimum_evidence_count_before_rca=2)

    assert state.has_minimum_evidence_for_rca() is False

    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in router",
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-code-1",
            source_type=EvidenceSourceType.CODE,
            source_name="router.py",
            content="Router expects a dict response.",
            file_path="src/router.py",
            line_start=12,
            line_end=20,
        )
    )

    assert state.has_minimum_evidence_for_rca() is True


def test_workflow_state_marks_low_confidence() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(incident=incident)

    state.mark_low_confidence()

    assert state.low_confidence is True
    assert state.investigation_status == InvestigationStatus.LOW_CONFIDENCE


def test_workflow_state_enforces_agent_invocation_limit() -> None:
    incident = Incident(
        incident_id="INC-001",
        title="Bug",
        description="Something failed",
    )
    state = WorkflowState(
        incident=incident,
        max_agent_invocations_per_agent=1,
    )

    assert state.can_invoke_agent(AgentName.LOG_INVESTIGATOR) is True

    state.record_agent_execution(
        AgentExecutionRecord(
            execution_id="execution-1",
            agent_name=AgentName.LOG_INVESTIGATOR,
            status=AgentRunStatus.SUCCEEDED,
        )
    )

    assert state.can_invoke_agent(AgentName.LOG_INVESTIGATOR) is False
