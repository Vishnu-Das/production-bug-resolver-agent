"""Tests for JSON and Markdown report persistence."""

import json

import pytest

from bug_resolver.providers.reports.file_report_store import FileReportStore
from bug_resolver.schemas import PatchSuggestion
from bug_resolver.schemas.rca import RCAReport
from bug_resolver.schemas.solution import SolutionRecommendation


@pytest.mark.asyncio
async def test_file_report_store_saves_markdown_and_json(tmp_path):
    report = RCAReport(
        report_id="RCA-001",
        incident_id="INC-001",
        title="Summary Query 500 Error RCA",
        incident_summary="Users are getting 500 errors when asking summary questions.",
        impact="Summary queries fail for users.",
        symptoms=[
            "500 error",
            "KeyError in summary flow",
        ],
        log_findings=[
            "Application raised KeyError: output",
        ],
        code_findings=[
            "Summary flow expects response['output']",
        ],
        graph_findings=[
            "src/rag/service.py:answer_question shows structural code relationship: calls route_query.",
        ],
        knowledge_base_findings=[
            "README says summary queries are supported",
        ],
        historical_findings=[
            "Prior incident INC-000 had a similar router contract mismatch.",
        ],
        hypotheses_considered=[
            "LLM response shape mismatch",
            "Vector store retrieval failure",
        ],
        selected_hypothesis_id="HYP-001",
        root_cause="The summary response expected an output key that was missing.",
        technical_explanation=(
            "The application accessed response['output'], but the returned "
            "response payload did not contain that key."
        ),
        evidence_ids=[
            "log-1",
            "code-1",
        ],
        confidence_score=0.87,
        confidence_reason="Logs and code point to the same missing key.",
        immediate_fix="Use the correct response key and add validation.",
        long_term_prevention="Introduce structured response schemas for LLM outputs.",
        tests_to_add=[
            "Test summary flow when LLM response is missing output key",
        ],
        open_questions=[],
        metadata={
            "environment": "local-test",
            "rca_writer": "llm",
            "llm_output_validated": "true",
            "fallback_used": "false",
        },
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(report)

    markdown_path = tmp_path / "incidents" / "INC-001" / "rca.md"
    json_path = tmp_path / "incidents" / "INC-001" / "rca.json"

    assert result == [markdown_path, json_path]
    assert json_path.exists()
    assert markdown_path.exists()

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    saved_markdown = markdown_path.read_text(encoding="utf-8")

    assert saved_json["report_id"] == "RCA-001"
    assert saved_json["incident_id"] == "INC-001"
    assert saved_json["title"] == "Summary Query 500 Error RCA"
    assert (
        saved_json["root_cause"] == "The summary response expected an output key that was missing."
    )
    assert saved_json["confidence_score"] == 0.87
    assert saved_json["metadata"]["environment"] == "local-test"

    assert "# Summary Query 500 Error RCA" in saved_markdown
    assert "# Summary Query 500 Error RCA\n\n## Incident Summary" in saved_markdown
    assert "## Incident Summary" in saved_markdown
    assert "Users are getting 500 errors when asking summary questions." in saved_markdown
    assert "## Final Root Cause" in saved_markdown
    assert "The summary response expected an output key that was missing." in saved_markdown
    assert "## Technical Explanation" in saved_markdown
    assert "Application raised KeyError: output" in saved_markdown
    assert "## Graph Findings" in saved_markdown
    assert "calls route_query" in saved_markdown
    assert "## Historical Findings" in saved_markdown
    assert "Prior incident INC-000" in saved_markdown
    assert "## Generation Details" in saved_markdown
    assert "- writer: llm" in saved_markdown
    assert "- llm_output_validated: true" in saved_markdown
    assert "- fallback_used: false" in saved_markdown
    assert "- environment: local-test" in saved_markdown
    assert "# Summary Query 500 Error RCA ## Incident Summary" not in saved_markdown


@pytest.mark.asyncio
async def test_file_report_store_saves_solution_markdown_when_solution_is_provided(
    tmp_path,
):
    report = RCAReport(
        report_id="RCA-001",
        incident_id="INC-001",
        title="RCA",
        incident_summary="Summary.",
        root_cause="Root cause.",
        technical_explanation="Technical explanation.",
        confidence_score=0.9,
        confidence_reason="Enough evidence exists.",
    )
    solution = SolutionRecommendation(
        recommendation_id="SOL-001",
        incident_id="INC-001",
        rca_report_id="RCA-001",
        summary="Fix the router output contract.",
        immediate_steps=["Normalize unsupported router strategies."],
        long_term_steps=["Keep router schema and prompt in sync."],
        tests_to_add=["Add routing regression test."],
        monitoring_improvements=["Track unsupported router strategies."],
        risk_notes=["Validate with production-like prompts."],
        confidence_score=0.85,
        evidence_ids=["evidence-src/rag/routing/llm.py:1-80"],
        metadata={
            "solution_writer": "deterministic_fallback",
            "llm_output_validated": "false",
            "fallback_used": "true",
            "fallback_reason": "llm_call_failed",
        },
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(report, solution=solution)

    markdown_path = tmp_path / "incidents" / "INC-001" / "rca.md"
    json_path = tmp_path / "incidents" / "INC-001" / "rca.json"
    solution_json_path = tmp_path / "incidents" / "INC-001" / "solution.json"
    solution_markdown_path = tmp_path / "incidents" / "INC-001" / "solution.md"

    assert result == [
        markdown_path,
        json_path,
        solution_json_path,
        solution_markdown_path,
    ]
    assert solution_json_path.exists()
    assert solution_markdown_path.exists()

    saved_solution_markdown = solution_markdown_path.read_text(encoding="utf-8")
    assert "# Solution Recommendation for INC-001" in saved_solution_markdown
    assert "# Solution Recommendation for INC-001\n\n## Summary" in saved_solution_markdown
    assert "Fix the router output contract." in saved_solution_markdown
    assert "- Normalize unsupported router strategies." in saved_solution_markdown
    assert "- src/rag/routing/llm.py:1-80" in saved_solution_markdown
    assert "## Generation Details" in saved_solution_markdown
    assert "- writer: deterministic_fallback" in saved_solution_markdown
    assert "- llm_output_validated: false" in saved_solution_markdown
    assert "- fallback_used: true" in saved_solution_markdown
    assert "- fallback_reason: llm_call_failed" in saved_solution_markdown
    assert "- recommendation_id: SOL-001" in saved_solution_markdown


@pytest.mark.asyncio
async def test_file_report_store_saves_patch_markdown_when_patch_plan_is_provided(
    tmp_path,
):
    report = RCAReport(
        report_id="RCA-010",
        incident_id="INC-010",
        title="RCA",
        incident_summary="Summary.",
        root_cause="Root cause.",
        technical_explanation="Technical explanation.",
        confidence_score=0.9,
        confidence_reason="Enough evidence exists.",
    )
    solution = SolutionRecommendation(
        recommendation_id="SOL-010",
        incident_id="INC-010",
        rca_report_id="RCA-010",
        summary="Fix duplicate upload handling.",
        confidence_score=0.85,
    )
    patch_suggestion = PatchSuggestion(
        suggestion_id="PATCH-010",
        incident_id="INC-010",
        rca_report_id="RCA-010",
        solution_recommendation_id="SOL-010",
        summary="Use content hash as upload identity.",
        affected_files=["src/services/upload_service.py"],
        behavior_changes=["Use content hash instead of filename for duplicate detection."],
        tests_to_add=["Add same-content different-filename upload regression test."],
        validation_commands=["Run upload service tests."],
        risk_notes=["Human approval is required."],
        confidence_score=0.85,
        evidence_ids=["evidence-src/services/upload_service.py:handle_file_upload"],
        metadata={
            "patch_suggestion_writer": "deterministic",
            "analyze_only": "true",
            "target_repo_modified": "false",
        },
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(
        report,
        solution=solution,
        patch_suggestion=patch_suggestion,
    )

    patch_json_path = tmp_path / "incidents" / "INC-010" / "patch.json"
    patch_markdown_path = tmp_path / "incidents" / "INC-010" / "patch.md"

    assert patch_json_path in result
    assert patch_markdown_path in result
    saved_patch_json = json.loads(patch_json_path.read_text(encoding="utf-8"))
    saved_patch_markdown = patch_markdown_path.read_text(encoding="utf-8")

    assert saved_patch_json["suggestion_id"] == "PATCH-010"
    assert "# Patch Suggestion for INC-010" in saved_patch_markdown
    assert "## Affected Files" in saved_patch_markdown
    assert "- src/services/upload_service.py" in saved_patch_markdown
    assert "Human approval required: True" in saved_patch_markdown
    assert "Target repository modified: false" in saved_patch_markdown


@pytest.mark.asyncio
async def test_file_report_store_displays_symbol_evidence_ids(tmp_path):
    report = RCAReport(
        report_id="RCA-005",
        incident_id="INC-005",
        title="Symbol RCA",
        incident_summary="Summary.",
        root_cause="Root cause.",
        technical_explanation="Technical explanation.",
        confidence_score=0.9,
        confidence_reason="Enough evidence exists.",
        evidence_ids=[
            "evidence-src/reranker.py:CrossEncoderReranker.rerank",
            "evidence-src/services/upload_service.py:handle_file_upload",
        ],
    )
    solution = SolutionRecommendation(
        recommendation_id="SOL-005",
        incident_id="INC-005",
        rca_report_id="RCA-005",
        summary="Fix symbol evidence.",
        immediate_steps=["Inspect symbol-specific code paths."],
        long_term_steps=["Keep evidence display symbol-aware."],
        tests_to_add=["Assert symbol evidence display."],
        monitoring_improvements=["Track evidence quality."],
        risk_notes=[],
        confidence_score=0.85,
        evidence_ids=report.evidence_ids,
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(report, solution=solution)

    saved_rca_markdown = result[0].read_text(encoding="utf-8")
    saved_solution_markdown = result[3].read_text(encoding="utf-8")

    assert "- src/reranker.py:CrossEncoderReranker.rerank" in saved_rca_markdown
    assert "- src/services/upload_service.py:handle_file_upload" in saved_rca_markdown
    assert "- src/reranker.py:CrossEncoderReranker.rerank" in saved_solution_markdown
    assert "- src/services/upload_service.py:handle_file_upload" in saved_solution_markdown


@pytest.mark.asyncio
async def test_file_report_store_renders_none_for_empty_sections(tmp_path):
    report = RCAReport(
        report_id="RCA-002",
        incident_id="INC-002",
        title="Minimal RCA",
        incident_summary="Minimal incident summary.",
        root_cause="Minimal root cause.",
        technical_explanation="Minimal technical explanation.",
        confidence_score=0.9,
        confidence_reason="Enough evidence exists.",
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(report)

    saved_markdown = result[0].read_text(encoding="utf-8")

    assert "## Symptoms" in saved_markdown
    assert "- None" in saved_markdown
    assert "## Impact" in saved_markdown
    assert "Not specified" in saved_markdown
    assert "## Low Confidence Warning" in saved_markdown
    assert "None" in saved_markdown


@pytest.mark.asyncio
async def test_file_report_store_renders_multiline_list_items_as_fenced_blocks(tmp_path):
    report = RCAReport(
        report_id="RCA-004",
        incident_id="INC-004",
        title="Multiline RCA",
        incident_summary="Summary.",
        symptoms=[
            "Runtime error\nTraceback (most recent call last):\nValueError: boom",
        ],
        root_cause="Root cause.",
        technical_explanation="Technical explanation.",
        confidence_score=0.9,
        confidence_reason="Enough evidence exists.",
    )

    store = FileReportStore(reports_dir=tmp_path)

    result = await store.save_report(report)

    saved_markdown = result[0].read_text(encoding="utf-8")

    assert "- Runtime error" in saved_markdown
    assert "```text\nTraceback (most recent call last):\nValueError: boom\n```" in saved_markdown


@pytest.mark.asyncio
async def test_file_report_store_can_overwrite_existing_report(tmp_path):
    first_report = RCAReport(
        report_id="RCA-003",
        incident_id="INC-003",
        title="First RCA",
        incident_summary="First summary.",
        root_cause="First root cause.",
        technical_explanation="First technical explanation.",
        confidence_score=0.9,
        confidence_reason="First confidence reason.",
    )

    second_report = RCAReport(
        report_id="RCA-003",
        incident_id="INC-003",
        title="Updated RCA",
        incident_summary="Updated summary.",
        root_cause="Updated root cause.",
        technical_explanation="Updated technical explanation.",
        confidence_score=0.95,
        confidence_reason="Updated confidence reason.",
    )

    store = FileReportStore(reports_dir=tmp_path)

    first_result = await store.save_report(first_report)
    second_result = await store.save_report(second_report)

    assert first_result == second_result

    saved_json = json.loads(second_result[1].read_text(encoding="utf-8"))
    saved_markdown = second_result[0].read_text(encoding="utf-8")

    assert saved_json["title"] == "Updated RCA"
    assert saved_json["root_cause"] == "Updated root cause."
    assert "# Updated RCA" in saved_markdown
    assert "Updated technical explanation." in saved_markdown
