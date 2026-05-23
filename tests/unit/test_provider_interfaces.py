"""Tests that provider protocols are satisfied by runtime-compatible fakes."""

from pathlib import Path

import pytest

from bug_resolver.embeddings import EmbeddingClient
from bug_resolver.llm import LLMClient
from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.providers.incident import IncidentProvider
from bug_resolver.providers.knowledge import KnowledgeBaseProvider
from bug_resolver.providers.logs import LogProvider
from bug_resolver.providers.reports import ReportStore
from bug_resolver.schemas import (
    CodeContext,
    Incident,
    KnowledgeContext,
    LogEntry,
    RCAReport,
)


class DummyIncidentProvider:
    async def get_incident(self, incident_id: str) -> Incident:
        return Incident(
            incident_id=incident_id,
            title="Dummy incident",
            description="Dummy incident description",
        )


class DummyLogProvider:
    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        return []


class DummyCodeContextProvider:
    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        return []


class DummyKnowledgeBaseProvider:
    async def search_knowledge(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[KnowledgeContext]:
        return []


class DummyReportStore:
    async def save_report(
        self,
        report: RCAReport,
        *,
        solution=None,
        patch_suggestion=None,
    ) -> list[Path]:
        return [Path("reports/incidents/INC-001/rca.md")]

    async def get_report(self, incident_id: str) -> RCAReport | None:
        return None


class DummyLLMClient:
    async def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        return "dummy response"

    async def generate_structured(
        self,
        prompt: str,
        output_schema,
        *,
        system_prompt: str | None = None,
    ):
        return output_schema()


class DummyEmbeddingClient:
    async def embed_text(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_dummy_providers_satisfy_runtime_protocols() -> None:
    assert isinstance(DummyIncidentProvider(), IncidentProvider)
    assert isinstance(DummyLogProvider(), LogProvider)
    assert isinstance(DummyCodeContextProvider(), CodeContextProvider)
    assert isinstance(DummyKnowledgeBaseProvider(), KnowledgeBaseProvider)
    assert isinstance(DummyReportStore(), ReportStore)
    assert isinstance(DummyLLMClient(), LLMClient)
    assert isinstance(DummyEmbeddingClient(), EmbeddingClient)


@pytest.mark.asyncio
async def test_embedding_client_contract() -> None:
    client: EmbeddingClient = DummyEmbeddingClient()

    single_embedding = await client.embed_text("hello")
    batch_embeddings = await client.embed_texts(["hello", "world"])

    assert single_embedding == [0.1, 0.2, 0.3]
    assert batch_embeddings == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
