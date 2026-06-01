"""Tests for ranked-evidence RCA prompt construction."""

from __future__ import annotations

from bug_resolver.prompts import RCAPromptBuilder
from bug_resolver.schemas import (
    EvidenceEvaluationResult,
    EvidenceItem,
    EvidenceSourceType,
    Incident,
    RCAReport,
    WorkflowState,
)


def make_report(*, evidence_ids: list[str]) -> RCAReport:
    return RCAReport(
        report_id="RCA-001",
        incident_id="INC-001",
        title="Request failure",
        incident_summary="A request failed.",
        root_cause="The strongest ranked code evidence identifies the likely cause.",
        technical_explanation="Do not expose unselected evidence from this baseline.",
        evidence_ids=evidence_ids,
        confidence_score=0.8,
        confidence_reason="Ranked evidence is available.",
    )


def make_state() -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Request fails with TypeError",
            description="Users receive an error response.",
        ),
        evidence_evaluation=EvidenceEvaluationResult(
            evaluation_id="evaluation-1",
            incident_id="INC-001",
            confidence_score=0.72,
            can_write_rca=True,
            reason="Direct implementation evidence was selected.",
        ),
    )


def add_ranked_code_evidence(state: WorkflowState) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="selected-code",
            source_type=EvidenceSourceType.CODE,
            source_name="src/app.py",
            file_path="src/app.py",
            line_start=35,
            line_end=50,
            content="42: def handle_request():\n43:     raise TypeError('bad input')",
            relevance_score=0.91,
            metadata={
                "retrieval_source_type": "file_context",
                "retriever_name": "file_context",
                "rank": "1",
                "score": "0.91",
                "symbol_name": "handle_request",
                "score_reasons": (
                    '["Candidate file matches stack trace file src/app.py", '
                    '"Candidate line range contains stack trace line 42", '
                    '"Candidate contains exception TypeError"]'
                ),
                "retrieval_sufficient_for_rca": "false",
                "retrieval_confidence": "0.42",
                "retrieval_missing_evidence": '["No runtime/log evidence selected"]',
                "retrieval_evaluation_warnings": (
                    '["Selected evidence is thin; corroborating context is recommended"]'
                ),
                "retrieval_warnings": '["exact_search retrieval failed"]',
            },
        )
    )


def test_rca_prompt_includes_ranked_evidence_scores_and_reasons() -> None:
    state = make_state()
    add_ranked_code_evidence(state)

    prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["selected-code"]),
    )

    assert "Ranked Evidence:" in prompt
    assert "1. [file_context | score=0.91]" in prompt
    assert "Display path: src/app.py:35-50" in prompt
    assert "Symbol: handle_request" in prompt
    assert "Candidate line range contains stack trace line 42" in prompt


def test_rca_prompt_does_not_include_raw_unselected_candidates() -> None:
    state = make_state()
    add_ranked_code_evidence(state)
    state.add_evidence(
        EvidenceItem(
            evidence_id="raw-unselected",
            source_type=EvidenceSourceType.CODE,
            source_name="tests/test_app.py",
            content="RAW_UNSELECTED_CONTENT",
        )
    )

    prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["selected-code"]),
    )

    assert "selected-code" in prompt
    assert "raw-unselected" not in prompt
    assert "RAW_UNSELECTED_CONTENT" not in prompt
    assert "Do not expose unselected evidence from this baseline." not in prompt


def test_rca_prompt_includes_missing_evidence_warnings() -> None:
    state = make_state()
    add_ranked_code_evidence(state)

    prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["selected-code"]),
    )

    assert "Evidence Evaluation:" in prompt
    assert "- sufficient_for_rca: false" in prompt
    assert "- confidence: 0.42" in prompt
    assert "No runtime/log evidence selected" in prompt
    assert "Selected evidence is thin; corroborating context is recommended" in prompt
    assert "exact_search retrieval failed" in prompt


def test_rca_prompt_makes_evidence_boundary_explicit() -> None:
    system_prompt = RCAPromptBuilder().build_system_prompt()
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="kb-1",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="docs/api.md",
            content="Requests should return a validated response.",
        )
    )
    user_prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["kb-1"]),
    )

    assert "Every RCA claim must be backed by one or more ranked evidence items." in (
        system_prompt
    )
    assert (
        "Treat knowledge base evidence as supporting expected behavior, not as proof "
        "of implementation behavior."
    ) in user_prompt


def test_prompt_builder_handles_legacy_evidence_without_score_metadata() -> None:
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="legacy-code",
            source_type=EvidenceSourceType.CODE,
            source_name="src/legacy.py",
            file_path="src/legacy.py",
            content="def handle_request(): ...",
        )
    )

    prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["legacy-code"]),
    )

    assert "1. [code]" in prompt
    assert "Display path: src/legacy.py" in prompt
    assert "def handle_request(): ..." in prompt
    assert "Why it matters:" not in prompt


def test_rca_prompt_preserves_source_snippet_and_graph_owner_summary() -> None:
    state = make_state()
    state.add_evidence(
        EvidenceItem(
            evidence_id="exact-source",
            source_type=EvidenceSourceType.CODE,
            source_name="src/app.py",
            file_path="src/app.py",
            line_start=19,
            line_end=20,
            content="19: if filename in processed_records:\n20:     return",
            metadata={
                "retrieval_source_type": "code_exact",
                "retriever_name": "exact_search",
                "rank": "1",
                "score": "0.91",
            },
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="graph-owner",
            source_type=EvidenceSourceType.GRAPH,
            source_name="src/app.py",
            file_path="src/app.py",
            line_start=10,
            line_end=40,
            content="Graph context: handle_request calls process_record",
            metadata={
                "retrieval_source_type": "code_graph",
                "retriever_name": "code_graph_expansion",
                "rank": "2",
                "score": "0.72",
            },
        )
    )

    prompt = RCAPromptBuilder().build_user_prompt(
        state,
        make_report(evidence_ids=["exact-source", "graph-owner"]),
    )

    assert "19: if filename in processed_records:" in prompt
    assert "Graph context: handle_request calls process_record" in prompt
    assert "[code_exact | score=0.91]" in prompt
    assert "[code_graph | score=0.72]" in prompt
