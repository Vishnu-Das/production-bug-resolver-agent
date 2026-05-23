"""Tests for analyze-only patch suggestion generation."""

from __future__ import annotations

import pytest

from bug_resolver.agents import PatchSuggestionAgent, PatchSuggestionInput
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


def build_solution() -> SolutionRecommendation:
    return SolutionRecommendation(
        recommendation_id="SOL-010",
        incident_id="INC-010",
        rca_report_id="RCA-010",
        summary="Use content hash for duplicate upload handling.",
        immediate_steps=[
            "Update upload duplicate detection to compare content hash values.",
        ],
        tests_to_add=[
            "Add integration test for duplicate uploads with different filenames.",
        ],
        risk_notes=["Validate behavior for legitimate document revisions."],
        confidence_score=0.8,
        evidence_ids=[
            "evidence-src/services/upload_service.py:handle_file_upload",
            "historical-INC-007",
        ],
    )


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
    assert result.affected_files == [
        "src/services/upload_service.py",
        "src/helpers/deduplication.py",
    ]
    assert "Use content hash as upload identity before ingestion." in result.behavior_changes
    assert (
        "Add integration test for duplicate uploads with different filenames."
        in result.tests_to_add
    )
    assert result.confidence_score == 0.8
    assert result.metadata == {
        "patch_suggestion_writer": "deterministic",
        "analyze_only": "true",
        "target_repo_modified": "false",
    }
    assert "historical-INC-007" in result.evidence_ids
    assert any("Human approval is required" in risk for risk in result.risk_notes)
