"""Tests for the LangGraph workflow factory wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from bug_resolver.config.settings import AppSettings
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore
from bug_resolver.workflows.dynamic_bug_resolution_graph import (
    DynamicBugResolutionGraphWorkflow,
)
from bug_resolver.workflows.dynamic_bug_resolution_workflow import (
    DynamicBugResolutionWorkflow,
)
import bug_resolver.workflows.factory as workflow_factory
import bug_resolver.workflows.graph_factory as graph_factory


@pytest.mark.asyncio
async def test_build_dynamic_graph_workflow_wires_graph_workflow(monkeypatch, tmp_path) -> None:
    """Build the graph workflow with a fake vector store and no OpenAI calls."""

    async def fake_load_or_build_code_index(*, settings, embedding_client):
        assert settings.target_repo_path == tmp_path
        assert embedding_client is not None
        return FAISSVectorStore(dimension=2)

    monkeypatch.setattr(
        graph_factory,
        "load_or_build_code_index",
        fake_load_or_build_code_index,
    )

    settings = AppSettings(
        OPENAI_API_KEY="test-key",
        LLM_MODEL="default-model",
        SUPERVISOR_LLM_MODEL="supervisor-model",
        RCA_WRITER_LLM_MODEL="rca-model",
        SOLUTION_RECOMMENDER_LLM_MODEL="solution-model",
        PATCH_SUGGESTION_LLM_MODEL="patch-plan-model",
        PATCH_GENERATOR_LLM_MODEL="patch-diff-model",
        target_repo_path=tmp_path,
        incidents_dir=tmp_path / "incidents",
        logs_dir=tmp_path / "logs",
        reports_dir=tmp_path / "reports",
        faiss_index_dir=tmp_path / "faiss",
        knowledge_base_dir=tmp_path / "knowledge_base",
        MAX_INVESTIGATION_STEPS=18,
    )

    workflow = await graph_factory.build_dynamic_graph_workflow(settings)

    assert isinstance(workflow, DynamicBugResolutionGraphWorkflow)
    assert workflow._max_steps == 18
    assert workflow._supervisor_agent._llm_client.model == "supervisor-model"
    assert workflow._rca_writer_agent._llm_client.model == "rca-model"
    assert (
        workflow._solution_recommendation_agent._llm_client.model
        == "solution-model"
    )
    assert workflow._patch_suggestion_agent._llm_client.model == "patch-plan-model"
    assert workflow._patch_generator_agent._llm_client.model == "patch-diff-model"


@pytest.mark.asyncio
async def test_build_dynamic_workflow_uses_role_specific_models(
    monkeypatch,
    tmp_path,
) -> None:
    """Build the manual workflow with role-specific LLM clients."""

    async def fake_load_or_build_code_index(*, settings, embedding_client):
        assert settings.target_repo_path == tmp_path
        assert embedding_client is not None
        return FAISSVectorStore(dimension=2)

    monkeypatch.setattr(
        workflow_factory,
        "load_or_build_code_index",
        fake_load_or_build_code_index,
    )

    settings = AppSettings(
        OPENAI_API_KEY="test-key",
        LLM_MODEL="default-model",
        SUPERVISOR_LLM_MODEL="supervisor-model",
        RCA_WRITER_LLM_MODEL="rca-model",
        SOLUTION_RECOMMENDER_LLM_MODEL="solution-model",
        PATCH_SUGGESTION_LLM_MODEL="patch-plan-model",
        PATCH_GENERATOR_LLM_MODEL="patch-diff-model",
        target_repo_path=tmp_path,
        incidents_dir=tmp_path / "incidents",
        logs_dir=tmp_path / "logs",
        reports_dir=tmp_path / "reports",
        faiss_index_dir=tmp_path / "faiss",
        knowledge_base_dir=tmp_path / "knowledge_base",
    )

    workflow = await workflow_factory.build_dynamic_workflow(settings)

    assert isinstance(workflow, DynamicBugResolutionWorkflow)
    assert workflow._supervisor_agent._llm_client.model == "supervisor-model"
    assert workflow._rca_writer_agent._llm_client.model == "rca-model"
    assert (
        workflow._solution_recommendation_agent._llm_client.model
        == "solution-model"
    )
    assert workflow._patch_suggestion_agent._llm_client.model == "patch-plan-model"
    assert workflow._patch_generator_agent._llm_client.model == "patch-diff-model"


@pytest.mark.asyncio
async def test_build_dynamic_graph_workflow_requires_openai_api_key(tmp_path: Path) -> None:
    settings = AppSettings(
        OPENAI_API_KEY="",
        target_repo_path=tmp_path,
        incidents_dir=tmp_path / "incidents",
        logs_dir=tmp_path / "logs",
        reports_dir=tmp_path / "reports",
        faiss_index_dir=tmp_path / "faiss",
        knowledge_base_dir=tmp_path / "knowledge_base",
    )

    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        await graph_factory.build_dynamic_graph_workflow(settings)
