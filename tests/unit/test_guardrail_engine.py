"""Tests for deterministic routing guardrails around supervisor decisions."""

import pytest

from bug_resolver.rules import GuardrailEngine
from bug_resolver.schemas import (
    AgentDecision,
    AgentExecutionRecord,
    AgentName,
    AgentRunStatus,
    EvidenceItem,
    EvidenceEvaluationResult,
    EvidenceSourceType,
    Incident,
    InvestigationStep,
    RCAReport,
    SolutionRecommendation,
    WorkflowState,
)


def make_state(**overrides: object) -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Bug",
            description="Something failed",
        ),
        **overrides,
    )


def make_decision(agent_name: AgentName = AgentName.LOG_INVESTIGATOR) -> AgentDecision:
    return AgentDecision(
        decision_id="decision-1",
        next_agent=agent_name,
        reason="Runtime evidence is missing.",
        queries=["INC-001 logs"],
        expected_evidence=["exception type"],
    )


def test_guardrail_engine_allows_valid_decision() -> None:
    engine = GuardrailEngine()
    state = make_state()
    decision = make_decision()

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True
    assert result.violated_rules == []
    assert result.reason == "Routing to log_investigator is allowed."
    assert result.guardrail_id.startswith("GRD-")


def test_guardrail_engine_rejects_disallowed_agent() -> None:
    engine = GuardrailEngine()
    state = make_state(allowed_agent_names=[AgentName.LOG_INVESTIGATOR])
    decision = make_decision(AgentName.CODE_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "unknown_or_disallowed_agent" in result.violated_rules
    assert result.fallback_next_agent == AgentName.LOG_INVESTIGATOR


def test_guardrail_engine_rejects_when_max_steps_reached() -> None:
    engine = GuardrailEngine()
    state = make_state(max_steps=1)
    state.add_investigation_step(
        InvestigationStep(
            step_number=1,
            agent_name=AgentName.LOG_INVESTIGATOR,
        )
    )
    decision = make_decision(AgentName.CODE_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "max_steps_reached" in result.violated_rules


def test_guardrail_engine_rejects_when_agent_invocation_limit_reached() -> None:
    engine = GuardrailEngine()
    state = make_state(max_agent_invocations_per_agent=1)
    state.record_agent_execution(
        AgentExecutionRecord(
            execution_id="execution-1",
            agent_name=AgentName.LOG_INVESTIGATOR,
            status=AgentRunStatus.SUCCEEDED,
        )
    )
    decision = make_decision(AgentName.LOG_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "max_agent_invocations_reached" in result.violated_rules


def test_guardrail_engine_rejects_repeated_agent_call_without_new_reason() -> None:
    engine = GuardrailEngine()
    state = make_state()
    decision = make_decision(AgentName.LOG_INVESTIGATOR)
    state.record_decision(decision)

    repeated_decision = make_decision(AgentName.LOG_INVESTIGATOR)
    repeated_decision.decision_id = "decision-2"

    result = engine.validate_decision(state=state, decision=repeated_decision)

    assert result.allowed is False
    assert "repeated_agent_call_without_new_reason" in result.violated_rules


def test_guardrail_engine_allows_repeated_agent_call_with_new_reason() -> None:
    engine = GuardrailEngine()
    state = make_state()
    state.record_decision(make_decision(AgentName.LOG_INVESTIGATOR))

    decision = AgentDecision(
        decision_id="decision-2",
        next_agent=AgentName.LOG_INVESTIGATOR,
        reason="New trace id was discovered.",
        queries=["trace-123 logs"],
        expected_evidence=["request timeline"],
    )

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True


def test_guardrail_engine_allows_forced_repeated_control_agent_call() -> None:
    engine = GuardrailEngine()
    state = make_state()

    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in router",
        )
    )

    first_decision = AgentDecision(
        decision_id="decision-1",
        next_agent=AgentName.EVIDENCE_EVALUATOR,
        reason="Evaluate evidence after latest investigation step.",
        queries=[],
        expected_evidence=[],
        metadata={"forced_by_workflow": "true"},
    )
    state.record_decision(first_decision)

    repeated_decision = AgentDecision(
        decision_id="decision-2",
        next_agent=AgentName.EVIDENCE_EVALUATOR,
        reason="Evaluate evidence after latest investigation step.",
        queries=[],
        expected_evidence=[],
        metadata={"forced_by_workflow": "true"},
    )

    result = engine.validate_decision(state=state, decision=repeated_decision)

    assert result.allowed is True
    assert "repeated_agent_call_without_new_reason" not in result.violated_rules


def test_guardrail_engine_allows_forced_control_agent_after_invocation_limit() -> None:
    engine = GuardrailEngine()
    state = make_state(max_agent_invocations_per_agent=1)
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in router",
        )
    )
    state.record_agent_execution(
        AgentExecutionRecord(
            execution_id="execution-1",
            agent_name=AgentName.EVIDENCE_EVALUATOR,
            status=AgentRunStatus.SUCCEEDED,
        )
    )

    decision = AgentDecision(
        decision_id="decision-2",
        next_agent=AgentName.EVIDENCE_EVALUATOR,
        reason="Evaluate evidence after latest investigation step.",
        queries=[],
        expected_evidence=[],
        metadata={"forced_by_workflow": "true"},
    )

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True
    assert "max_agent_invocations_reached" not in result.violated_rules


def test_guardrail_engine_routes_to_code_when_evaluation_says_code_is_missing() -> None:
    engine = GuardrailEngine()
    state = make_state()
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
            evidence_id="ev-kb-1",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="README.md",
            content="Router docs.",
        )
    )
    state.evidence_evaluation = EvidenceEvaluationResult(
        evaluation_id="eval-1",
        incident_id="INC-001",
        confidence_score=0.7,
        retry_required=True,
        missing_evidence=["Implementation code evidence is missing."],
        reason="Evidence is incomplete; supervisor should replan for more evidence.",
    )

    decision = make_decision(AgentName.LOG_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "missing_code_evidence_should_route_to_code" in result.violated_rules
    assert result.fallback_next_agent == AgentName.CODE_INVESTIGATOR


def test_guardrail_engine_allows_kb_when_code_is_missing_but_no_kb_evidence_exists() -> None:
    engine = GuardrailEngine()
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in router",
        )
    )
    state.evidence_evaluation = EvidenceEvaluationResult(
        evaluation_id="eval-1",
        incident_id="INC-001",
        confidence_score=0.7,
        retry_required=True,
        missing_evidence=["Implementation code evidence is missing."],
        reason="Expected behavior documentation could clarify the next step.",
    )

    decision = make_decision(AgentName.KNOWLEDGE_BASE_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True
    assert "missing_code_evidence_should_route_to_code" not in result.violated_rules


def test_guardrail_engine_blocks_repeated_kb_when_code_is_still_missing() -> None:
    engine = GuardrailEngine()
    state = make_state()
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
            evidence_id="ev-kb-1",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="README.md",
            content="Router docs.",
        )
    )
    state.evidence_evaluation = EvidenceEvaluationResult(
        evaluation_id="eval-1",
        incident_id="INC-001",
        confidence_score=0.7,
        retry_required=True,
        missing_evidence=["Implementation code evidence is missing."],
        reason="Code evidence is still required after knowledge-base context.",
    )

    decision = make_decision(AgentName.KNOWLEDGE_BASE_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "missing_code_evidence_should_route_to_code" in result.violated_rules
    assert result.fallback_next_agent == AgentName.CODE_INVESTIGATOR


def test_guardrail_engine_blocks_rca_without_minimum_evidence() -> None:
    engine = GuardrailEngine()
    state = make_state(minimum_evidence_count_before_rca=2)
    decision = make_decision(AgentName.RCA_WRITER)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "runtime_evidence_required_first" in result.violated_rules
    assert "minimum_evidence_not_met_for_rca" in result.violated_rules
    assert result.fallback_next_agent == AgentName.LOG_INVESTIGATOR


def test_guardrail_engine_allows_rca_with_minimum_evidence() -> None:
    engine = GuardrailEngine()
    state = make_state(minimum_evidence_count_before_rca=2)
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
    decision = make_decision(AgentName.RCA_WRITER)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True


def test_guardrail_engine_blocks_solution_without_rca() -> None:
    engine = GuardrailEngine()
    state = make_state()
    decision = make_decision(AgentName.SOLUTION_RECOMMENDER)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "runtime_evidence_required_first" in result.violated_rules
    assert "solution_requires_rca" in result.violated_rules
    assert result.fallback_next_agent == AgentName.LOG_INVESTIGATOR


def test_guardrail_engine_blocks_report_without_rca_and_solution() -> None:
    engine = GuardrailEngine()
    state = make_state()
    decision = make_decision(AgentName.REPORT_WRITER)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "runtime_evidence_required_first" in result.violated_rules
    assert "report_requires_rca" in result.violated_rules
    assert "report_requires_solution" in result.violated_rules
    assert result.fallback_next_agent == AgentName.LOG_INVESTIGATOR


def test_guardrail_engine_allows_report_after_rca_and_solution() -> None:
    engine = GuardrailEngine()
    state = make_state()
    state.rca_report = RCAReport(
        report_id="rca-1",
        incident_id="INC-001",
        title="RCA for bug",
        incident_summary="Something failed.",
        symptoms=["HTTP 500"],
        log_findings=["TypeError in logs"],
        code_findings=["Router expects dict"],
        knowledge_base_findings=["Docs describe routing"],
        hypotheses_considered=["Schema mismatch"],
        selected_hypothesis_id="hyp-1",
        root_cause="Router received the wrong response shape.",
        technical_explanation="Runtime and code evidence point to a schema mismatch.",
        evidence_ids=["ev-log-1", "ev-code-1"],
        confidence_score=0.85,
        confidence_reason="Log and code evidence agree.",
    )
    state.solution_recommendation = SolutionRecommendation(
        recommendation_id="sol-1",
        incident_id="INC-001",
        rca_report_id="rca-1",
        summary="Normalize router response handling.",
        immediate_steps=["Validate response shape"],
        long_term_steps=["Use structured output"],
        tests_to_add=["Add schema mismatch regression test"],
        monitoring_improvements=["Log invalid response shape"],
        confidence_score=0.8,
        evidence_ids=["ev-code-1"],
    )
    decision = make_decision(AgentName.REPORT_WRITER)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True


def test_guardrail_engine_blocks_finish_without_report_or_low_confidence() -> None:
    engine = GuardrailEngine()
    state = make_state()
    decision = AgentDecision(
        decision_id="decision-finish",
        next_agent=AgentName.FINISH,
        reason="Stop.",
        should_continue=False,
    )

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is False
    assert "runtime_evidence_required_first" in result.violated_rules
    assert "finish_requires_report_or_low_confidence" in result.violated_rules
    assert result.fallback_next_agent == AgentName.LOG_INVESTIGATOR


def test_guardrail_engine_allows_finish_for_low_confidence_state() -> None:
    engine = GuardrailEngine()
    state = make_state()
    state.mark_low_confidence()
    decision = AgentDecision(
        decision_id="decision-finish",
        next_agent=AgentName.FINISH,
        reason="Stop with low-confidence output.",
        should_continue=False,
    )

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True


def test_guardrail_engine_allows_investigation_when_max_replans_reached_but_steps_available() -> (
    None
):
    engine = GuardrailEngine()
    state = make_state(max_replans=0)
    state.evidence_evaluation = EvidenceEvaluationResult(
        evaluation_id="eval-1",
        incident_id="INC-001",
        confidence_score=0.4,
        retry_required=True,
        missing_evidence=["Need code evidence."],
        reason="Evidence is weak.",
    )
    decision = make_decision(AgentName.CODE_INVESTIGATOR)

    result = engine.validate_decision(state=state, decision=decision)

    assert result.allowed is True
    assert "max_replans_reached" not in result.violated_rules


def test_guardrail_engine_has_no_llm_dependency() -> None:
    engine = GuardrailEngine()

    with pytest.raises(TypeError):
        GuardrailEngine(llm_client=object())  # type: ignore[call-arg]

    assert not hasattr(engine, "llm_client")
