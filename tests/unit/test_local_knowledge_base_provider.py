from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)

import pytest


@pytest.mark.asyncio
async def test_local_knowledge_base_provider_returns_matching_docs(tmp_path):
    docs_dir = tmp_path / "knowledge_base"
    docs_dir.mkdir()

    readme = docs_dir / "README.md"
    readme.write_text(
        "The application supports summary queries using a retrieval pipeline.",
        encoding="utf-8",
    )

    provider = LocalKnowledgeBaseProvider(knowledge_base_dir=docs_dir)

    results = await provider.search_knowledge(["summary queries"])

    assert len(results) == 1
    assert results[0].document_name == "README.md"
    assert "summary queries" in results[0].content
    assert results[0].relevance_score > 0


@pytest.mark.asyncio
async def test_local_knowledge_base_provider_returns_empty_list_for_no_queries(tmp_path):
    docs_dir = tmp_path / "knowledge_base"
    docs_dir.mkdir()

    provider = LocalKnowledgeBaseProvider(knowledge_base_dir=docs_dir)

    results = await provider.search_knowledge([])

    assert results == []


@pytest.mark.asyncio
async def test_local_knowledge_base_provider_returns_empty_list_for_missing_directory(tmp_path):
    docs_dir = tmp_path / "missing_knowledge_base"

    provider = LocalKnowledgeBaseProvider(knowledge_base_dir=docs_dir)

    results = await provider.search_knowledge(["summary"])

    assert results == []


@pytest.mark.asyncio
async def test_local_knowledge_base_provider_ignores_unsupported_files(tmp_path):
    docs_dir = tmp_path / "knowledge_base"
    docs_dir.mkdir()

    unsupported_file = docs_dir / "notes.json"
    unsupported_file.write_text(
        '{"content": "summary queries"}',
        encoding="utf-8",
    )

    provider = LocalKnowledgeBaseProvider(knowledge_base_dir=docs_dir)

    results = await provider.search_knowledge(["summary queries"])

    assert results == []


@pytest.mark.asyncio
async def test_local_knowledge_base_provider_respects_max_results(tmp_path):
    docs_dir = tmp_path / "knowledge_base"
    docs_dir.mkdir()

    for index in range(3):
        doc = docs_dir / f"doc_{index}.md"
        doc.write_text(
            f"summary query document {index}",
            encoding="utf-8",
        )

    provider = LocalKnowledgeBaseProvider(
        knowledge_base_dir=docs_dir,
        max_results=2,
    )

    results = await provider.search_knowledge(["summary query"])

    assert len(results) == 2