"""Factory for wiring settings into the LangGraph investigation workflow."""

from __future__ import annotations

from bug_resolver.agents import (
    CodeGraphInvestigatorAgent,
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    HistoricalRCAInvestigatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    PatchGeneratorAgent,
    PatchSuggestionAgent,
    RCAWriterAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
    SupervisorAgent,
)
from bug_resolver.config.settings import AppSettings
from bug_resolver.embeddings.openai_embedding_client import OpenAIEmbeddingClient
from bug_resolver.errors import ConfigurationError
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
from bug_resolver.providers.patches import LocalFilePatchContextProvider
from bug_resolver.providers.reports.file_report_store import FileReportStore
from bug_resolver.rules import CodeQueryRules, GuardrailEngine
from bug_resolver.utils.observability import configure_langsmith_tracing
from bug_resolver.workflows.dynamic_bug_resolution_graph import (
    DynamicBugResolutionGraphWorkflow,
)
from bug_resolver.workflows.workflow_dependencies import (
    load_or_build_code_index,
)


async def build_dynamic_graph_workflow(
    settings: AppSettings,
    *,
    include_patch_plan: bool = False,
    include_patch_diff: bool = False,
) -> DynamicBugResolutionGraphWorkflow:
    """Build the fully wired LangGraph workflow for future CLI investigations."""
    configure_langsmith_tracing(
        enabled=settings.langsmith_tracing,
        api_key=settings.langsmith_api_key,
        project=settings.langsmith_project,
        endpoint=settings.langsmith_endpoint,
    )
    if not settings.openai_api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY is required to run investigations.",
            component="settings",
            suggested_action="Set OPENAI_API_KEY in .env before running investigations.",
        )

    supervisor_llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.supervisor_model,
    )
    rca_writer_llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.rca_writer_model,
    )
    solution_recommender_llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.solution_recommender_model,
    )
    patch_suggestion_llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.patch_suggestion_model,
    )
    patch_generator_llm_client = OpenAILLMClient(
        api_key=settings.openai_api_key,
        model=settings.patch_generator_model,
    )
    embedding_client = OpenAIEmbeddingClient(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector_store = await load_or_build_code_index(
        settings=settings,
        embedding_client=embedding_client,
    )

    return DynamicBugResolutionGraphWorkflow(
        incident_provider=FileIncidentProvider(settings.incidents_dir),
        supervisor_agent=SupervisorAgent(supervisor_llm_client),
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(FileLogProvider(settings.logs_dir)),
        code_investigator_agent=CodeInvestigatorAgent(
            FAISSCodeContextProvider(
                vector_store=vector_store,
                embedding_client=embedding_client,
            ),
            code_query_rules=CodeQueryRules(),
        ),
        code_graph_investigator_agent=CodeGraphInvestigatorAgent(
            PythonASTCodeGraphProvider(settings.target_repo_path),
            code_query_rules=CodeQueryRules(),
        ),
        historical_rca_investigator_agent=HistoricalRCAInvestigatorAgent(
            FileHistoricalRCAProvider(settings.historical_rca_dir)
        ),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            LocalKnowledgeBaseProvider(settings.knowledge_base_dir)
        ),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(llm_client=rca_writer_llm_client),
        solution_recommendation_agent=SolutionRecommendationAgent(
            llm_client=solution_recommender_llm_client,
        ),
        patch_suggestion_agent=PatchSuggestionAgent(
            llm_client=patch_suggestion_llm_client,
        ),
        patch_generator_agent=PatchGeneratorAgent(
            llm_client=patch_generator_llm_client,
            patch_context_provider=LocalFilePatchContextProvider(settings.target_repo_path),
        ),
        report_writer_agent=ReportWriterAgent(FileReportStore(settings.reports_dir)),
        max_steps=settings.max_investigation_steps,
        max_replans=settings.max_retries,
        confidence_threshold=settings.confidence_threshold,
        include_patch_plan=include_patch_plan,
        include_patch_diff=include_patch_diff,
    )
