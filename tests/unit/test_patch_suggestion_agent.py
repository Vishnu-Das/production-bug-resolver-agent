"""Tests for analyze-only patch suggestion generation."""

from __future__ import annotations

import pytest

from bug_resolver.agents import PatchSuggestionAgent, PatchSuggestionInput
from bug_resolver.agents.patch_suggestion_agent import PatchSuggestionNarrativeOutput
from bug_resolver.schemas import RCAReport, SolutionRecommendation


def build_rca_report() -> RCAReport:
    return RCAReport(
        report_id="RCA-010",
        incident_id="INC-010",
        title="RCA for duplicate uploads",
        incident_summary="Duplicate records appeared after upload.",
        root_cause="Upload duplicate detection used filename identity instead of content hash.",
        technical_explanation="Logs and code evidence show same content under two filenames.",
        evidence_ids=[
            "EVID-LOG-001",
            "evidence-src/services/upload_service.py:handle_file_upload",
            "evidence-src/helpers/deduplication.py:deduplicate_docs",
            "historical-INC-007",
        ],
        confidence_score=0.85,
        confidence_reason="Logs and code support the RCA.",
        immediate_fix="Use content hash as upload identity before ingestion.",
        tests_to_add=["Add same-content different-filename upload test."],
        open_questions=["Should duplicate uploads be rejected or linked?"],
    )


def build_rca_report_with_graph_context() -> RCAReport:
    report = build_rca_report()
    return report.model_copy(
        update={
            "evidence_ids": [
                *report.evidence_ids,
                "graph-src/rag/service.py:stream_response",
                "graph-src/ui/chat.py:handle_chat_input",
                "graph-tests/rag/test_service.py:test_stream_response",
            ],
        }
    )


def build_solution() -> SolutionRecommendation:
    return SolutionRecommendation(
        recommendation_id="SOL-010",
        incident_id="INC-010",
        rca_report_id="RCA-010",
        summary="Use content hash for duplicate upload handling.",
        immediate_steps=[
            "Update upload duplicate detection to compare content hash values.",
            "Run upload regression tests.",
            "Validate duplicate upload metrics after deployment.",
        ],
        tests_to_add=[
            "Add integration test for duplicate uploads with different filenames.",
        ],
        risk_notes=["Validate behavior for legitimate document revisions."],
        confidence_score=0.8,
        evidence_ids=[
            "EVID-LOG-001",
            "kb-upload-ingestion",
            "evidence-src/services/upload_service.py:handle_file_upload",
            "historical-INC-007",
        ],
    )


class FakeLLMClient:
    def __init__(self, output: PatchSuggestionNarrativeOutput) -> None:
        self.output = output
        self.prompt = ""
        self.system_prompt = ""

    async def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "unused"

    async def generate_structured(self, prompt, output_schema, *, system_prompt=None):
        self.prompt = prompt
        self.system_prompt = system_prompt or ""
        return self.output


@pytest.mark.asyncio
async def test_patch_suggestion_agent_builds_analyze_only_patch_plan() -> None:
    agent = PatchSuggestionAgent()

    result = await agent.run(
        PatchSuggestionInput(
            rca_report=build_rca_report(),
            solution_recommendation=build_solution(),
        )
    )

    assert result.suggestion_id.startswith("PATCH-")
    assert result.incident_id == "INC-010"
    assert result.rca_report_id == "RCA-010"
    assert result.solution_recommendation_id == "SOL-010"
    assert result.human_approval_required is True
    assert result.analyze_only is True
    assert result.target_repo_modified is False
    assert result.file_patches == []
    assert result.test_patches == []
    assert result.affected_files == [
        "src/services/upload_service.py",
        "src/helpers/deduplication.py",
    ]
    assert "Use content hash as upload identity before ingestion." in result.behavior_changes
    assert "Run upload regression tests." not in result.behavior_changes
    assert (
        "Validate duplicate upload metrics after deployment."
        not in result.behavior_changes
    )
    assert result.behavior_changes.count(
        "Update upload duplicate detection to compare content hash values."
    ) == 1
    assert (
        "Add integration test for duplicate uploads with different filenames."
        in result.tests_to_add
    )
    assert result.confidence_score == 0.8
    assert result.metadata == {
        "patch_suggestion_writer": "deterministic",
        "analyze_only": "true",
        "target_repo_modified": "false",
        "supporting_context_files": "",
    }
    assert "historical-INC-007" in result.evidence_ids
    assert result.open_questions == ["Should duplicate uploads be rejected or linked?"]
    assert any("Human approval is required" in risk for risk in result.risk_notes)
    assert not any("Should duplicate uploads" in risk for risk in result.risk_notes)


@pytest.mark.asyncio
async def test_patch_suggestion_agent_keeps_graph_context_out_of_affected_files() -> None:
    agent = PatchSuggestionAgent()

    result = await agent.run(
        PatchSuggestionInput(
            rca_report=build_rca_report_with_graph_context(),
            solution_recommendation=build_solution(),
        )
    )

    assert result.affected_files == [
        "src/services/upload_service.py",
        "src/helpers/deduplication.py",
    ]
    assert result.metadata["supporting_context_files"] == (
        "src/rag/service.py, src/ui/chat.py"
    )


@pytest.mark.asyncio
async def test_patch_suggestion_agent_uses_llm_for_narrative_only() -> None:
    llm_client = FakeLLMClient(
        PatchSuggestionNarrativeOutput(
            summary="Review the upload dedupe owner and update content-hash handling.",
            behavior_changes=["Use content hash as the upload duplicate identity."],
            tests_to_add=["Add duplicate-content upload regression coverage."],
            risk_notes=["Confirm revised upload behavior with product owners."],
            open_questions=["Should duplicate content be rejected or linked?"],
            warnings=["No code has been modified by this analyze-only plan."],
        )
    )
    agent = PatchSuggestionAgent(llm_client=llm_client)

    result = await agent.run(
        PatchSuggestionInput(
            rca_report=build_rca_report(),
            solution_recommendation=build_solution(),
        )
    )

    assert result.summary == "Review the upload dedupe owner and update content-hash handling."
    assert result.behavior_changes == ["Use content hash as the upload duplicate identity."]
    assert result.tests_to_add == ["Add duplicate-content upload regression coverage."]
    assert result.affected_files == [
        "src/services/upload_service.py",
        "src/helpers/deduplication.py",
    ]
    assert result.evidence_ids == [
        "EVID-LOG-001",
        "evidence-src/services/upload_service.py:handle_file_upload",
        "evidence-src/helpers/deduplication.py:deduplicate_docs",
        "historical-INC-007",
        "kb-upload-ingestion",
    ]
    assert result.metadata["patch_suggestion_writer"] == "hybrid_llm"
    assert result.metadata["llm_output_validated"] == "true"
    assert result.metadata["fallback_used"] == "false"
    assert "Patchable owner files:" in llm_client.prompt


@pytest.mark.asyncio
async def test_patch_suggestion_agent_rejects_llm_completion_claims() -> None:
    agent = PatchSuggestionAgent(
        llm_client=FakeLLMClient(
            PatchSuggestionNarrativeOutput(
                summary="We fixed the upload dedupe bug.",
                behavior_changes=["Use content hash."],
                tests_to_add=["Add tests."],
                risk_notes=[],
                open_questions=[],
            )
        )
    )

    result = await agent.run(
        PatchSuggestionInput(
            rca_report=build_rca_report(),
            solution_recommendation=build_solution(),
        )
    )

    assert result.summary.startswith("Analyze-only patch plan")
    assert result.metadata["patch_suggestion_writer"] == "deterministic_fallback"
    assert result.metadata["fallback_reason"] == "forbidden_completion_claim"
