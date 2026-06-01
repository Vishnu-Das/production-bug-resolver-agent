"""Tests for LLM-first RCA generation and deterministic fallback behavior."""

from __future__ import annotations

import pytest

from bug_resolver.agents import EvidenceEvaluatorAgent, RCAWriterAgent, RCAWriterOutput
from bug_resolver.schemas import (
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    WorkflowState,
)


class FakeRCAWriterLLM:
    def __init__(
        self,
        output: RCAWriterOutput | None = None,
        *,
        should_fail: bool = False,
    ) -> None:
        self.output = output
        self.should_fail = should_fail
        self.prompt: str | None = None
        self.system_prompt: str | None = None

    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        raise AssertionError("RCAWriterAgent should request structured output")

    async def generate_structured(
        self,
        prompt: str,
        output_schema,
        *,
        system_prompt: str | None = None,
    ):
        self.prompt = prompt
        self.system_prompt = system_prompt

        if self.should_fail:
            raise ValueError("LLM failed")

        assert output_schema is RCAWriterOutput
        assert self.output is not None
        return self.output


def make_state() -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Summary route fails",
            description="Users get 500 errors when asking summary questions.",
            affected_service="conversational_rag",
            affected_area="summary flow",
        )
    )


def add_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log-1",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content="TypeError in route_query",
            confidence=1.0,
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-code-1",
            source_type=EvidenceSourceType.CODE,
            source_name="C:\\Users\\vishn\\repo\\src\\rag\\router.py",
            file_path="C:\\Users\\vishn\\repo\\src\\rag\\router.py",
            line_start=40,
            line_end=45,
            content="def route_query(...): return response['output']",
            relevance_score=0.9,
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-kb-1",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="README.md",
            content="The router returns a structured response.",
            relevance_score=0.8,
        )
    )


def add_graph_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-graph-1",
            source_type=EvidenceSourceType.GRAPH,
            source_name="src/rag/router.py",
            file_path="src/rag/router.py",
            line_start=40,
            line_end=45,
            content="src/rag/router.py:route_query calls parse_router_response.",
            relevance_score=0.9,
            metadata={
                "qualified_symbol": "route_query",
                "calls": "parse_router_response",
                "called_by": "answer_question",
            },
        )
    )


def add_direct_source_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-code-exact",
            source_type=EvidenceSourceType.CODE,
            source_name="src/rag/router.py",
            file_path="src/rag/router.py",
            line_start=42,
            line_end=43,
            content="42: if response is None:\n43:     return fallback_response",
            relevance_score=0.85,
            metadata={
                "retrieval_source_type": "code_exact",
                "rank": "2",
            },
        )
    )


def add_supporting_code_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-code-support",
            source_type=EvidenceSourceType.CODE,
            source_name="C:\\Users\\vishn\\repo\\src\\rag\\retrieval\\fusion\\strategy.py",
            file_path="C:\\Users\\vishn\\repo\\src\\rag\\retrieval\\fusion\\strategy.py",
            line_start=19,
            line_end=40,
            content="def deduplicate_retrieved_docs(...): deduplicate retrieved documents",
            relevance_score=0.5,
        )
    )


@pytest.mark.asyncio
async def test_rca_writer_agent_generates_report_from_dynamic_evidence() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)

    result = await RCAWriterAgent().run(state)

    assert result.report_id.startswith("RCA-")
    assert result.incident_id == "INC-001"
    assert result.title == "RCA for Summary route fails"
    assert "Users get 500 errors" in result.incident_summary
    assert result.impact == ("Affected service: conversational_rag. Affected area: summary flow.")
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1"]
    assert result.confidence_score >= state.confidence_threshold
    assert result.confidence_score < 1.0
    assert result.low_confidence_warning is None
    assert result.open_questions == []
    assert result.selected_hypothesis_id == "H1"
    assert "src/rag/router.py:40-45" in result.root_cause
    assert result.log_findings == ["app.log shows runtime evidence: TypeError in route_query"]
    assert result.code_findings == [
        ("src/rag/router.py:40-45 contains implementation context relevant to the incident.")
    ]
    assert result.knowledge_base_findings == [
        (
            "README.md documents expected behavior relevant to the incident: "
            "The router returns a structured response."
        )
    ]
    assert result.metadata == {
        "evidence_count": "3",
        "dynamic_workflow": "true",
        "rca_writer": "deterministic_fallback",
        "llm_output_validated": "false",
        "fallback_used": "true",
        "fallback_reason": "llm_client_not_configured",
    }


@pytest.mark.asyncio
async def test_rca_writer_agent_can_generate_llm_backed_report() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="LLM RCA for summary route failure",
            incident_summary="The summary route failed for users.",
            impact="Users saw failed summary responses.",
            symptoms=["500 during summary flow"],
            log_findings=["Log evidence shows TypeError in route_query."],
            code_findings=["Code evidence shows router output access."],
            knowledge_base_findings=["README describes structured router output."],
            hypotheses_considered=["H1: Router output contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Router output contract mismatch caused the failure.",
            technical_explanation=(
                "The log and code evidence show the route_query path expected "
                "a different response shape."
            ),
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.78,
            confidence_reason="Log and code evidence agree.",
            immediate_fix="Normalize router response shape before access.",
            long_term_prevention="Add structured router response validation.",
            tests_to_add=["Add regression test for malformed router output."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.report_id.startswith("RCA-")
    assert result.incident_id == "INC-001"
    assert result.title == "LLM RCA for summary route failure"
    assert result.evidence_ids == ["ev-log-1", "ev-code-1"]
    assert result.root_cause == "Router output contract mismatch caused the failure."
    assert result.metadata["rca_writer"] == "llm"
    assert result.metadata["llm_output_validated"] == "true"
    assert result.metadata["fallback_used"] == "false"
    assert "fallback_reason" not in result.metadata
    assert llm.prompt is not None
    assert "Allowed evidence IDs: ev-log-1, ev-code-1, ev-kb-1" in llm.prompt


@pytest.mark.asyncio
async def test_rca_writer_agent_preserves_code_evidence_when_llm_code_findings_exist() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="LLM RCA for summary route failure",
            incident_summary="The summary route failed for users.",
            impact="Users saw failed summary responses.",
            symptoms=["500 during summary flow"],
            log_findings=["Log evidence shows TypeError in route_query."],
            code_findings=["src/rag/router.py:40-45 shows router output access."],
            knowledge_base_findings=["README describes structured router output."],
            hypotheses_considered=["H1: Router output contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Router output contract mismatch caused the failure.",
            technical_explanation=(
                "The log and code findings show the route_query path expected "
                "a different response shape."
            ),
            evidence_ids=["ev-log-1", "ev-kb-1"],
            confidence_score=0.78,
            confidence_reason="Log, code, and knowledge-base evidence agree.",
            immediate_fix="Normalize router response shape before access.",
            long_term_prevention="Add structured router response validation.",
            tests_to_add=["Add regression test for malformed router output."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.metadata["rca_writer"] == "llm"
    assert result.metadata["fallback_used"] == "false"
    assert result.evidence_ids == ["ev-log-1", "ev-kb-1", "ev-code-1"]


@pytest.mark.asyncio
async def test_rca_writer_agent_accepts_collected_evidence_not_in_deterministic_selection() -> None:
    state = make_state()
    add_evidence(state)
    add_supporting_code_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="LLM RCA for duplicate retrieval context",
            incident_summary="The summary route failed for users.",
            impact="Users saw failed summary responses.",
            symptoms=["500 during summary flow"],
            log_findings=["Log evidence shows TypeError in route_query."],
            code_findings=[
                "src/rag/router.py:40-45 shows router output access.",
                "src/rag/retrieval/fusion/strategy.py:19-40 is supporting retrieval context.",
            ],
            knowledge_base_findings=["README describes structured router output."],
            hypotheses_considered=["H1: Router output contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Router output contract mismatch caused the failure.",
            technical_explanation=(
                "The log, owner code, and supporting retrieval context agree."
            ),
            evidence_ids=["ev-log-1", "ev-code-1", "ev-code-support"],
            confidence_score=0.78,
            confidence_reason="Log and collected code evidence agree.",
            immediate_fix="Normalize router response shape before access.",
            long_term_prevention="Add structured router response validation.",
            tests_to_add=["Add regression test for malformed router output."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.metadata["rca_writer"] == "llm"
    assert result.metadata["fallback_used"] == "false"
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-code-support"]


@pytest.mark.asyncio
async def test_rca_writer_agent_preserves_graph_evidence_when_llm_graph_findings_exist() -> None:
    state = make_state()
    add_evidence(state)
    add_graph_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="LLM RCA for summary route failure",
            incident_summary="The summary route failed for users.",
            impact="Users saw failed summary responses.",
            symptoms=["500 during summary flow"],
            log_findings=["Log evidence shows TypeError in route_query."],
            code_findings=["src/rag/router.py:40-45 shows router output access."],
            graph_findings=[
                "src/rag/router.py:route_query is called by answer_question."
            ],
            knowledge_base_findings=["README describes structured router output."],
            hypotheses_considered=["H1: Router output contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Router output contract mismatch caused the failure.",
            technical_explanation=(
                "The log, code, and graph findings show the route_query path "
                "expected a different response shape."
            ),
            evidence_ids=["ev-log-1", "ev-code-1", "ev-kb-1"],
            confidence_score=0.78,
            confidence_reason="Log, code, graph, and knowledge-base evidence agree.",
            immediate_fix="Normalize router response shape before access.",
            long_term_prevention="Add structured router response validation.",
            tests_to_add=["Add regression test for malformed router output."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.metadata["rca_writer"] == "llm"
    assert result.graph_findings == [
        "src/rag/router.py:route_query is called by answer_question."
    ]
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1", "ev-graph-1"]


@pytest.mark.asyncio
async def test_rca_writer_agent_preserves_direct_source_snippet_with_graph_context() -> None:
    state = make_state()
    add_evidence(state)
    add_direct_source_evidence(state)
    add_graph_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="LLM RCA for summary route failure",
            incident_summary="The summary route failed for users.",
            impact="Users saw failed summary responses.",
            symptoms=["500 during summary flow"],
            log_findings=["Log evidence shows TypeError in route_query."],
            code_findings=["src/rag/router.py:42-43 shows the implementation condition."],
            graph_findings=[
                "src/rag/router.py:route_query is called by answer_question."
            ],
            knowledge_base_findings=["README describes structured router output."],
            hypotheses_considered=["H1: Router output contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Router output contract mismatch caused the failure.",
            technical_explanation=(
                "The implementation condition and graph owner context explain the failure."
            ),
            evidence_ids=["ev-log-1", "ev-code-1", "ev-kb-1", "ev-graph-1"],
            confidence_score=0.78,
            confidence_reason="Log, code, graph, and knowledge-base evidence agree.",
            immediate_fix="Normalize router response shape before access.",
            long_term_prevention="Add structured router response validation.",
            tests_to_add=["Add regression test for malformed router output."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.metadata["rca_writer"] == "llm"
    assert result.evidence_ids == [
        "ev-log-1",
        "ev-code-1",
        "ev-kb-1",
        "ev-graph-1",
        "ev-code-exact",
    ]


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_confidence_exceeds_baseline() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Overconfident RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["Code finding"],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=1.0,
            confidence_reason="Too confident.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "llm_call_failed"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_claims_fix_was_done() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["Code finding"],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.75,
            confidence_reason="Evidence is enough.",
            immediate_fix="We fixed the router response handling.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "forbidden_completion_claim"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_leaks_internal_evidence_path() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["evidence-src/rag/router.py:1-20 shows the failing code path."],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.75,
            confidence_reason="Evidence is enough.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "internal_evidence_prefix_in_prose"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_puts_evidence_id_in_prose() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["Code finding"],
            knowledge_base_findings=["EVIDENCE-README describes expected routing behavior."],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.75,
            confidence_reason="Evidence is enough.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "invalid_evidence_id"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_log_finding_is_in_code_findings() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["Log evidence shows request_id=req-1 returned warning output."],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H1",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.75,
            confidence_reason="Evidence is enough.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "llm_call_failed"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_selected_hypothesis_is_missing() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Summary.",
            impact=None,
            symptoms=["Symptom"],
            log_findings=["Log finding"],
            code_findings=["Code finding"],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Contract mismatch."],
            selected_hypothesis_id="H2",
            root_cause="Contract mismatch.",
            technical_explanation="Evidence suggests a contract mismatch.",
            evidence_ids=["ev-log-1", "ev-code-1"],
            confidence_score=0.75,
            confidence_reason="Evidence is enough.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "selected_hypothesis_id_not_found"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_fails() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(should_fail=True)

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["llm_output_validated"] == "false"
    assert result.metadata["fallback_used"] == "true"
    assert result.metadata["fallback_reason"] == "llm_call_failed"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_references_unknown_evidence() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Bad summary.",
            impact=None,
            symptoms=["Bad symptom"],
            log_findings=[],
            code_findings=[],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Unknown."],
            selected_hypothesis_id="H1",
            root_cause="Unknown evidence caused the issue.",
            technical_explanation="Unknown evidence was used.",
            evidence_ids=["not-collected"],
            confidence_score=0.8,
            confidence_reason="Bad evidence.",
            immediate_fix=None,
            long_term_prevention=None,
            tests_to_add=[],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1"]
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "invalid_evidence_id"


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_mixes_unknown_evidence_with_valid_ids() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(
        RCAWriterOutput(
            title="Bad RCA",
            incident_summary="Bad summary.",
            impact=None,
            symptoms=["Bad symptom"],
            log_findings=["Log finding"],
            code_findings=["Code finding"],
            knowledge_base_findings=[],
            hypotheses_considered=["H1: Unknown."],
            selected_hypothesis_id="H1",
            root_cause="Unknown evidence caused the issue.",
            technical_explanation="Unknown evidence was used.",
            evidence_ids=["ev-log-1", "not-collected"],
            confidence_score=0.75,
            confidence_reason="Bad evidence.",
            immediate_fix="Validate response shape.",
            long_term_prevention="Add contracts.",
            tests_to_add=["Add regression test."],
            open_questions=[],
            low_confidence_warning=None,
        )
    )

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1"]
    assert result.metadata["rca_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "invalid_evidence_id"


@pytest.mark.asyncio
async def test_rca_writer_agent_requires_evidence() -> None:
    state = make_state()

    with pytest.raises(ValueError, match="requires evidence before writing an RCA"):
        await RCAWriterAgent().run(state)


@pytest.mark.asyncio
async def test_rca_writer_agent_requires_evidence_evaluation() -> None:
    state = make_state()
    add_evidence(state)

    with pytest.raises(ValueError, match="requires evidence evaluation before RCA"):
        await RCAWriterAgent().run(state)


def test_rca_writer_agent_allows_evidence_backed_prose() -> None:
    output = RCAWriterOutput(
        title="Evidence-backed RCA",
        incident_summary="This is an evidence-backed explanation.",
        impact=None,
        symptoms=[],
        log_findings=[],
        code_findings=[],
        knowledge_base_findings=[],
        hypotheses_considered=["H1: Validate the implementation contract."],
        selected_hypothesis_id="H1",
        root_cause="Evidence-backed analysis points to a contract mismatch.",
        technical_explanation="The evidence-backed conclusion uses collected context.",
        evidence_ids=["ev-log-1"],
        confidence_score=0.5,
        confidence_reason="Evidence-backed analysis is available.",
        tests_to_add=["Add a regression test."],
        open_questions=[],
    )

    assert not RCAWriterAgent()._contains_evidence_id_in_prose(output)
