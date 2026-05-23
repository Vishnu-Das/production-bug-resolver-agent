"""Tests that bundled sample incidents, logs, and knowledge base remain usable."""

from pathlib import Path

import pytest

from bug_resolver.providers.incident.file_incident_provider import FileIncidentProvider
from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)
from bug_resolver.providers.logs.file_log_provider import FileLogProvider


SAMPLE_DATA_DIR = Path("sample_data")


@pytest.mark.asyncio
async def test_sample_incidents_and_logs_are_loadable() -> None:
    incident_provider = FileIncidentProvider(SAMPLE_DATA_DIR / "incidents")
    log_provider = FileLogProvider(SAMPLE_DATA_DIR / "logs")

    for incident_id in [
        "INC-001",
        "INC-002",
        "INC-003",
        "INC-004",
        "INC-006",
        "INC-007",
        "INC-008",
        "INC-009",
        "INC-010",
    ]:
        incident = await incident_provider.get_incident(incident_id)
        logs = await log_provider.get_logs(incident_id)

        assert incident.incident_id == incident_id
        assert incident.description
        assert len(logs) >= 1
        assert all(log.raw for log in logs)


@pytest.mark.asyncio
async def test_sample_knowledge_base_covers_new_incident_themes() -> None:
    provider = LocalKnowledgeBaseProvider(SAMPLE_DATA_DIR / "knowledge_base")

    retrieval_context = await provider.search_knowledge(
        ["unsupported retrieval strategy semantic"],
        limit=3,
    )
    selected_document_context = await provider.search_knowledge(
        ["selected document Transformer Notes parent_child"],
        limit=3,
    )
    upload_context = await provider.search_knowledge(
        ["duplicate upload processed_uploads stale document"],
        limit=3,
    )
    summary_context = await provider.search_knowledge(
        ["summary-style queries document-level retrieval semantic chunk search"],
        limit=3,
    )
    content_hash_context = await provider.search_knowledge(
        ["content hash duplicate filename upload citations"],
        limit=3,
    )
    reranker_context = await provider.search_knowledge(
        ["RERANKING_MODEL_NAME missing reranker silent bypass retrieval quality"],
        limit=3,
    )

    assert any(context.document_name == "retrieval-strategies.md" for context in retrieval_context)
    assert any(
        context.document_name == "selected-document-routing.md"
        for context in selected_document_context
    )
    assert any(context.document_name == "upload-ingestion.md" for context in upload_context)
    assert any(
        context.document_name == "query-routing-expectations.md" for context in summary_context
    )
    assert any(context.document_name == "upload-ingestion.md" for context in content_hash_context)
    assert any(
        context.document_name == "reranking-configuration.md" for context in reranker_context
    )
