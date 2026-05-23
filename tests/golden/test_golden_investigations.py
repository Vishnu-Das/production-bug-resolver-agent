"""Golden graph-workflow investigations for realistic demo incidents."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bug_resolver.schemas import AgentName, EvidenceSourceType, InvestigationStatus
from helpers import (
    GoldenSupervisorAgent,
    build_golden_graph_workflow,
    code_context,
    decision,
    graph_context,
)


def assert_report_files_exist(report_dir: Path, incident_id: str) -> None:
    """Assert Markdown and JSON reports were persisted for an incident."""
    incident_report_dir = report_dir / "incidents" / incident_id

    assert (incident_report_dir / "rca.md").exists()
    assert (incident_report_dir / "rca.json").exists()
    assert (incident_report_dir / "solution.md").exists()
    assert (incident_report_dir / "solution.json").exists()


def report_json(report_dir: Path, incident_id: str) -> dict:
    """Load generated RCA JSON for broad signal assertions."""
    return json.loads(
        (report_dir / "incidents" / incident_id / "rca.json").read_text(
            encoding="utf-8"
        )
    )


def source_types(state) -> set[EvidenceSourceType]:
    """Return collected evidence source types."""
    return {evidence.source_type for evidence in state.evidence_items}


@pytest.mark.asyncio
async def test_inc_007_upload_dedup_golden_investigation(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    supervisor = GoldenSupervisorAgent(
        [
            decision("golden-007-log", AgentName.LOG_INVESTIGATOR, ["INC-007 logs"]),
            decision(
                "golden-007-kb",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["upload ingestion content hash deduplication expectations"],
            ),
            decision(
                "golden-007-code",
                AgentName.CODE_INVESTIGATOR,
                ["upload content_hash filename deduplicate documents"],
            ),
            decision(
                "golden-007-graph",
                AgentName.GRAPH_INVESTIGATOR,
                ["which upload request path calls deduplication"],
            ),
        ]
    )
    workflow = build_golden_graph_workflow(
        supervisor=supervisor,
        report_dir=report_dir,
        code_contexts=[
            code_context(
                context_id="src/services/upload_service.py:handle_file_upload",
                file_path="src/services/upload_service.py",
                function_name="handle_file_upload",
                snippet=(
                    "handle_file_upload computes content_hash but checks "
                    "processed_uploads by filename before ingestion."
                ),
            ),
            code_context(
                context_id="src/helpers/deduplication.py:deduplicate_docs",
                file_path="src/helpers/deduplication.py",
                function_name="deduplicate_docs",
                snippet="deduplicate_docs should compare stable content identity.",
            ),
        ],
        graph_contexts=[
            graph_context(
                context_id="src/services/upload_service.py:handle_file_upload",
                file_path="src/services/upload_service.py",
                relative_path="src/services/upload_service.py",
                symbol_name="handle_file_upload",
                qualified_symbol="handle_file_upload",
                calls=["deduplicate_docs", "ingest_single_document"],
                called_by=["upload_document"],
                content=(
                    "handle_file_upload is called by the upload request path "
                    "and calls deduplicate_docs before document ingestion."
                ),
            )
        ],
    )

    state = await workflow.run("INC-007")
    generated_report = report_json(report_dir, "INC-007")
    combined_rca_text = " ".join(
        [
            generated_report["root_cause"],
            generated_report["technical_explanation"],
            " ".join(generated_report["code_findings"]),
            " ".join(generated_report["knowledge_base_findings"]),
        ]
    ).lower()

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert source_types(state) >= {
        EvidenceSourceType.LOG,
        EvidenceSourceType.KNOWLEDGE_BASE,
        EvidenceSourceType.CODE,
        EvidenceSourceType.GRAPH,
    }
    assert_report_files_exist(report_dir, "INC-007")
    assert "content" in combined_rca_text
    assert "filename" in combined_rca_text
    assert "dedup" in combined_rca_text
    assert any(
        step.agent_name == AgentName.KNOWLEDGE_BASE_INVESTIGATOR
        for step in state.trace.steps
    )
    assert any(step.agent_name == AgentName.GRAPH_INVESTIGATOR for step in state.trace.steps)


@pytest.mark.asyncio
async def test_inc_008_reranker_config_golden_investigation(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    supervisor = GoldenSupervisorAgent(
        [
            decision("golden-008-log", AgentName.LOG_INVESTIGATOR, ["INC-008 logs"]),
            decision(
                "golden-008-kb",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["reranking configuration RERANKING_MODEL_NAME fallback expectations"],
            ),
            decision(
                "golden-008-code",
                AgentName.CODE_INVESTIGATOR,
                ["reranker_model scores order_changed RERANKING_MODEL_NAME"],
            ),
            decision(
                "golden-008-graph",
                AgentName.GRAPH_INVESTIGATOR,
                ["which function reads RERANKING_MODEL_NAME and caller chain"],
            ),
        ]
    )
    workflow = build_golden_graph_workflow(
        supervisor=supervisor,
        report_dir=report_dir,
        code_contexts=[
            code_context(
                context_id="src/reranker.py:rerank_documents",
                file_path="src/reranker.py",
                function_name="rerank_documents",
                snippet=(
                    "rerank_documents returns documents unchanged when "
                    "reranker_model is None and scores remain neutral."
                ),
            ),
            code_context(
                context_id="src/reranker.py:load_reranker",
                file_path="src/reranker.py",
                function_name="load_reranker",
                snippet="load_reranker reads RERANKING_MODEL_NAME before loading the model.",
            ),
        ],
        graph_contexts=[
            graph_context(
                context_id="src/reranker.py:rerank_documents",
                file_path="src/reranker.py",
                relative_path="src/reranker.py",
                symbol_name="rerank_documents",
                qualified_symbol="rerank_documents",
                calls=["load_reranker"],
                called_by=["stream_response"],
                config_keys=["RERANKING_MODEL_NAME"],
                config_readers=["load_reranker"],
                content=(
                    "rerank_documents uses config from load_reranker, which "
                    "reads RERANKING_MODEL_NAME."
                ),
            )
        ],
    )

    state = await workflow.run("INC-008")
    generated_report = report_json(report_dir, "INC-008")
    combined_rca_text = " ".join(
        [
            generated_report["root_cause"],
            generated_report["technical_explanation"],
            " ".join(generated_report["graph_findings"]),
            " ".join(generated_report["evidence_ids"]),
        ]
    ).lower()

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert source_types(state) >= {
        EvidenceSourceType.LOG,
        EvidenceSourceType.KNOWLEDGE_BASE,
        EvidenceSourceType.CODE,
        EvidenceSourceType.GRAPH,
    }
    assert_report_files_exist(report_dir, "INC-008")
    assert "reranker" in combined_rca_text
    assert "reranking_model_name".lower() in combined_rca_text
    assert "order" in combined_rca_text or "neutral" in combined_rca_text
    assert any(step.agent_name == AgentName.GRAPH_INVESTIGATOR for step in state.trace.steps)


@pytest.mark.asyncio
async def test_inc_009_structural_graph_golden_investigation(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports"
    supervisor = GoldenSupervisorAgent(
        [
            decision("golden-009-log", AgentName.LOG_INVESTIGATOR, ["INC-009 logs"]),
            decision(
                "golden-009-code",
                AgentName.CODE_INVESTIGATOR,
                ["rerank_documents_with_scores load_reranker RERANKING_MODEL_NAME"],
            ),
            decision(
                "golden-009-graph",
                AgentName.GRAPH_INVESTIGATOR,
                ["caller chain for rerank_documents_with_scores"],
            ),
            decision(
                "golden-009-kb",
                AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
                ["reranking configuration expected behavior"],
            ),
        ]
    )
    workflow = build_golden_graph_workflow(
        supervisor=supervisor,
        report_dir=report_dir,
        code_contexts=[
            code_context(
                context_id="src/reranker.py:rerank_documents_with_scores",
                file_path="src/reranker.py",
                function_name="rerank_documents_with_scores",
                snippet=(
                    "rerank_documents_with_scores uses reranker_model initialized "
                    "from load_reranker and returns neutral scores when missing."
                ),
            ),
            code_context(
                context_id="src/reranker.py:load_reranker",
                file_path="src/reranker.py",
                function_name="load_reranker",
                snippet="load_reranker reads RERANKING_MODEL_NAME.",
            ),
        ],
        graph_contexts=[
            graph_context(
                context_id="src/reranker.py:rerank_documents_with_scores",
                file_path="src/reranker.py",
                relative_path="src/reranker.py",
                symbol_name="rerank_documents_with_scores",
                qualified_symbol="rerank_documents_with_scores",
                calls=["load_reranker"],
                called_by=["process_documents_with_scores"],
                config_keys=["RERANKING_MODEL_NAME"],
                config_readers=["load_reranker"],
                content=(
                    "rerank_documents_with_scores calls load_reranker and is "
                    "called by process_documents_with_scores."
                ),
            )
        ],
    )

    state = await workflow.run("INC-009")
    generated_report = report_json(report_dir, "INC-009")
    graph_findings = " ".join(generated_report["graph_findings"]).lower()

    assert state.investigation_status == InvestigationStatus.COMPLETED
    assert source_types(state) >= {
        EvidenceSourceType.LOG,
        EvidenceSourceType.CODE,
        EvidenceSourceType.GRAPH,
        EvidenceSourceType.KNOWLEDGE_BASE,
    }
    assert_report_files_exist(report_dir, "INC-009")
    assert "rerank_documents_with_scores" in graph_findings
    assert "load_reranker" in graph_findings
    assert "reranking_model_name".lower() in graph_findings
    assert any(
        step.agent_name == AgentName.GRAPH_INVESTIGATOR
        for step in state.trace.steps
    )
