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
    assert result.impact == (
        "Affected service: conversational_rag. Affected area: summary flow."
    )
    assert result.evidence_ids == ["ev-log-1", "ev-code-1", "ev-kb-1"]
    assert result.confidence_score >= state.confidence_threshold
    assert result.confidence_score < 1.0
    assert result.low_confidence_warning is None
    assert result.open_questions == []
    assert result.selected_hypothesis_id == "H1"
    assert "src/rag/router.py:40-45" in result.root_cause
    assert result.log_findings == [
        "app.log shows runtime signal: TypeError in route_query"
    ]
    assert result.code_findings == [
        (
            "src/rag/router.py:40-45 contains implementation context relevant "
            "to the incident."
        )
    ]
    assert result.knowledge_base_findings == [
        (
            "README.md documents expected behavior relevant to the incident: "
            "The router returns a structured response."
        )
    ]
    assert result.metadata == {"evidence_count": "3", "dynamic_workflow": "true"}


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
    assert llm.prompt is not None
    assert "Allowed evidence IDs: ev-log-1, ev-code-1, ev-kb-1" in llm.prompt


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
    assert "rca_writer" not in result.metadata


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
    assert "rca_writer" not in result.metadata


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
            code_findings=[
                "evidence-src/rag/router.py:1-20 shows the failing code path."
            ],
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
    assert "rca_writer" not in result.metadata


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
    assert "rca_writer" not in result.metadata


@pytest.mark.asyncio
async def test_rca_writer_agent_falls_back_when_llm_fails() -> None:
    state = make_state()
    add_evidence(state)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    llm = FakeRCAWriterLLM(should_fail=True)

    result = await RCAWriterAgent(llm_client=llm).run(state)

    assert result.title == "RCA for Summary route fails"
    assert result.metadata == {"evidence_count": "3", "dynamic_workflow": "true"}


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
    assert "rca_writer" not in result.metadata


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
