"""Factory for wiring CLI settings into the dynamic investigation workflow."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.agents import (
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    RCAWriterAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
    SupervisorAgent,
)
from bug_resolver.config.settings import AppSettings
from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient
from bug_resolver.llm.openai_llm_client import OpenAILLMClient
from bug_resolver.providers.code.faiss_code_context_provider import (
    FAISSCodeContextProvider,
)
from bug_resolver.providers.incident.file_incident_provider import FileIncidentProvider
from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)
from bug_resolver.providers.logs.file_log_provider import FileLogProvider
from bug_resolver.providers.reports.file_report_store import FileReportStore
from bug_resolver.retrieval.code_chunker import SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.retrieval.code_indexer import CodeIndexer
from bug_resolver.retrieval.faiss_vector_store import FAISSVectorStore
from bug_resolver.rules import GuardrailEngine
from bug_resolver.workflows.dynamic_bug_resolution_workflow import (
    DynamicBugResolutionWorkflow,
)


async def build_dynamic_workflow(settings: AppSettings) -> DynamicBugResolutionWorkflow:
    """Build the fully wired dynamic workflow for CLI investigations."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required to run investigations.")

    llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,
    )
    embedding_client = OpenAIEmbeddingClient(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector_store = await _load_or_build_code_index(
        settings=settings,
        embedding_client=embedding_client,
    )

    return DynamicBugResolutionWorkflow(
        incident_provider=FileIncidentProvider(settings.incidents_dir),
        supervisor_agent=SupervisorAgent(llm_client),
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(FileLogProvider(settings.logs_dir)),
        code_investigator_agent=CodeInvestigatorAgent(
            FAISSCodeContextProvider(
                vector_store=vector_store,
                embedding_client=embedding_client,
            )
        ),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            LocalKnowledgeBaseProvider(settings.knowledge_base_dir)
        ),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(llm_client=llm_client),
        solution_recommendation_agent=SolutionRecommendationAgent(llm_client=llm_client),
        report_writer_agent=ReportWriterAgent(FileReportStore(settings.reports_dir)),
        max_replans=settings.max_retries,
        confidence_threshold=settings.confidence_threshold,
    )


async def _load_or_build_code_index(
    *,
    settings: AppSettings,
    embedding_client: OpenAIEmbeddingClient,
) -> FAISSVectorStore:
    index_path = settings.faiss_index_dir / "code.index"
    metadata_path = settings.faiss_index_dir / "code_metadata.json"

    if index_path.exists() and metadata_path.exists():
        return FAISSVectorStore.load(
            index_path=index_path,
            metadata_path=metadata_path,
        )

    _ensure_path_exists(settings.target_repo_path, "target repository")

    indexer = CodeIndexer(
        file_loader=CodeFileLoader(settings.target_repo_path),
        chunker=SimpleCodeChunker(),
        embedding_client=embedding_client,
    )
    vector_store = await indexer.build_index()
    vector_store.save(index_path=index_path, metadata_path=metadata_path)
    return vector_store


def _ensure_path_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Configured {label} path does not exist: {path}")
