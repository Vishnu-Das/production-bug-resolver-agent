from pathlib import Path

import pytest
from pydantic import ValidationError

from bug_resolver.schemas import (
    CodeContext,
    ContextPlan,
    EvidenceItem,
    EvidenceSourceType,
    Hypothesis,
    Incident,
    IncidentSeverity,
    KnowledgeContext,
    LogAnalysisResult,
    LogEntry,
    LogLevel,
    RCAReport,
    SolutionRecommendation,
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


def test_context_plan_schema() -> None:
    plan = ContextPlan(
        plan_id="plan-1",
        code_search_queries=["KeyError output get_openai_response"],
        knowledge_search_queries=["response output format"],
        files_to_prioritize=["src/client.py"],
    )

    assert plan.code_search_queries
    assert plan.files_to_prioritize == ["src/client.py"]


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
    state = WorkflowState(incident=incident, max_retries=2)

    assert state.can_retry() is True

    state.increment_retry()
    state.increment_retry()

    assert state.retry_count == 2
    assert state.can_retry() is False

    with pytest.raises(ValueError):
        state.increment_retry()


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