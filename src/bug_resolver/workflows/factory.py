"""Factory for wiring CLI settings into the dynamic investigation workflow."""

from __future__ import annotations

from bug_resolver.agents import (
    CodeGraphInvestigatorAgent,
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    HistoricalRCAInvestigatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    PatchSuggestionAgent,
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
from bug_resolver.providers.graph import PythonASTCodeGraphProvider
from bug_resolver.providers.history import FileHistoricalRCAProvider
from bug_resolver.providers.incident.file_incident_provider import FileIncidentProvider
from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)
from bug_resolver.providers.logs.file_log_provider import FileLogProvider
from bug_resolver.providers.reports.file_report_store import FileReportStore
from bug_resolver.rules import GuardrailEngine
from bug_resolver.workflows.dynamic_bug_resolution_workflow import (
    DynamicBugResolutionWorkflow,
)
from bug_resolver.workflows.workflow_dependencies import load_or_build_code_index


async def build_dynamic_workflow(
    settings: AppSettings,
    *,
    include_patch_plan: bool = False,
) -> DynamicBugResolutionWorkflow:
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
    vector_store = await load_or_build_code_index(
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
        code_graph_investigator_agent=CodeGraphInvestigatorAgent(
            PythonASTCodeGraphProvider(settings.target_repo_path)
        ),
        historical_rca_investigator_agent=HistoricalRCAInvestigatorAgent(
            FileHistoricalRCAProvider(settings.historical_rca_dir)
        ),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            LocalKnowledgeBaseProvider(settings.knowledge_base_dir)
        ),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(llm_client=llm_client),
        solution_recommendation_agent=SolutionRecommendationAgent(llm_client=llm_client),
        patch_suggestion_agent=PatchSuggestionAgent(),
        report_writer_agent=ReportWriterAgent(FileReportStore(settings.reports_dir)),
        max_steps=settings.max_investigation_steps,
        max_replans=settings.max_retries,
        confidence_threshold=settings.confidence_threshold,
        include_patch_plan=include_patch_plan,
    )


