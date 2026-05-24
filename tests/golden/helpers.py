"""Golden investigation test helpers."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.agents import (
    CodeGraphInvestigatorAgent,
    CodeInvestigatorAgent,
    EvidenceEvaluatorAgent,
    KnowledgeBaseInvestigatorAgent,
    LogInvestigatorAgent,
    PatchSuggestionAgent,
    RCAWriterAgent,
    ReportWriterAgent,
    SolutionRecommendationAgent,
)
from bug_resolver.providers.incident.file_incident_provider import FileIncidentProvider
from bug_resolver.providers.knowledge.local_knowledge_base_provider import (
    LocalKnowledgeBaseProvider,
)
from bug_resolver.providers.logs.file_log_provider import FileLogProvider
from bug_resolver.providers.reports.file_report_store import FileReportStore
from bug_resolver.rules import GuardrailEngine
from bug_resolver.rules.code_context_ranking_rules import CodeContextRankingRules
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    CodeContext,
    CodeGraphContext,
    WorkflowState,
)
from bug_resolver.workflows.dynamic_bug_resolution_graph import (
    DynamicBugResolutionGraphWorkflow,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_DIR = REPO_ROOT / "sample_data"


class GoldenSupervisorAgent:
    """Yield planned decisions so golden tests are deterministic and LLM-free."""

    def __init__(self, decisions: list[AgentDecision]) -> None:
        self.decisions = decisions
        self.call_count = 0
        self.seen_states: list[WorkflowState] = []

    async def run(self, state: WorkflowState) -> AgentDecision:
        self.seen_states.append(state.model_copy(deep=True))

        if self.call_count >= len(self.decisions):
            return AgentDecision(
                decision_id=f"golden-finish-{self.call_count}",
                next_agent=AgentName.FINISH,
                reason="Golden investigation has no more planned supervisor decisions.",
                queries=[],
                expected_evidence=[],
                should_continue=False,
            )

        decision = self.decisions[self.call_count]
        self.call_count += 1
        return decision


class GoldenCodeContextProvider:
    """Return incident-specific code contexts without FAISS or embeddings."""

    def __init__(self, contexts: list[CodeContext]) -> None:
        self.contexts = contexts
        self.queries_seen: list[list[str]] = []

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.queries_seen.append(queries)
        return self.contexts[:limit]


class RankedGoldenCodeContextProvider:
    """Return production-ranked golden code contexts from a noisy candidate set."""

    def __init__(self, contexts: list[CodeContext]) -> None:
        self.contexts = contexts
        self.queries_seen: list[list[str]] = []
        self.ranking_rules = CodeContextRankingRules()

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        self.queries_seen.append(queries)
        return self.ranking_rules.rank_contexts(
            self.contexts,
            queries=queries,
            limit=limit,
            mode="implementation",
        )


class GoldenCodeGraphProvider:
    """Return incident-specific structural graph contexts."""

    def __init__(self, contexts: list[CodeGraphContext]) -> None:
        self.contexts = contexts
        self.queries_seen: list[list[str]] = []

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        self.queries_seen.append(queries)
        return self.contexts[:limit]


def decision(
    decision_id: str,
    agent_name: AgentName,
    queries: list[str],
    *,
    reason: str | None = None,
) -> AgentDecision:
    """Create a stable supervisor decision for golden tests."""
    return AgentDecision(
        decision_id=decision_id,
        next_agent=agent_name,
        reason=reason or f"Collect {agent_name.value} evidence.",
        queries=queries,
        expected_evidence=["evidence relevant to the current incident"],
        should_continue=True,
    )


def build_golden_graph_workflow(
    *,
    supervisor: GoldenSupervisorAgent,
    code_contexts: list[CodeContext],
    graph_contexts: list[CodeGraphContext],
    report_dir: Path,
    rank_code_contexts: bool = False,
    include_patch_plan: bool = False,
) -> DynamicBugResolutionGraphWorkflow:
    """Build the graph workflow using real sample data and deterministic providers."""
    code_context_provider = (
        RankedGoldenCodeContextProvider(code_contexts)
        if rank_code_contexts
        else GoldenCodeContextProvider(code_contexts)
    )
    return DynamicBugResolutionGraphWorkflow(
        incident_provider=FileIncidentProvider(SAMPLE_DATA_DIR / "incidents"),
        supervisor_agent=supervisor,  # type: ignore[arg-type]
        guardrail_engine=GuardrailEngine(),
        log_investigator_agent=LogInvestigatorAgent(
            FileLogProvider(SAMPLE_DATA_DIR / "logs")
        ),
        code_investigator_agent=CodeInvestigatorAgent(
            code_context_provider
        ),
        code_graph_investigator_agent=CodeGraphInvestigatorAgent(
            GoldenCodeGraphProvider(graph_contexts)
        ),
        knowledge_base_investigator_agent=KnowledgeBaseInvestigatorAgent(
            LocalKnowledgeBaseProvider(SAMPLE_DATA_DIR / "knowledge_base")
        ),
        evidence_evaluator_agent=EvidenceEvaluatorAgent(),
        rca_writer_agent=RCAWriterAgent(),
        solution_recommendation_agent=SolutionRecommendationAgent(),
        patch_suggestion_agent=PatchSuggestionAgent() if include_patch_plan else None,
        report_writer_agent=ReportWriterAgent(FileReportStore(report_dir)),
        max_steps=12,
        max_replans=3,
        minimum_evidence_count_before_rca=2,
        include_patch_plan=include_patch_plan,
    )


def code_context(
    *,
    context_id: str,
    file_path: str,
    snippet: str,
    function_name: str | None = None,
    class_name: str | None = None,
    relevance_score: float = 0.9,
) -> CodeContext:
    """Create symbol-aware code context for a golden incident."""
    return CodeContext(
        context_id=context_id,
        file_path=file_path,
        snippet=snippet,
        function_name=function_name,
        class_name=class_name,
        line_start=1,
        line_end=20,
        relevance_score=relevance_score,
    )


def graph_context(
    *,
    context_id: str,
    file_path: str,
    relative_path: str,
    symbol_name: str,
    qualified_symbol: str,
    content: str,
    calls: list[str] | None = None,
    called_by: list[str] | None = None,
    config_keys: list[str] | None = None,
    config_readers: list[str] | None = None,
) -> CodeGraphContext:
    """Create structural graph context for a golden incident."""
    return CodeGraphContext(
        context_id=context_id,
        file_path=file_path,
        relative_path=relative_path,
        symbol_name=symbol_name,
        symbol_type="function",
        qualified_symbol=qualified_symbol,
        line_start=1,
        line_end=20,
        calls=calls or [],
        called_by=called_by or [],
        config_keys=config_keys or [],
        config_readers=config_readers or [],
        content=content,
        relevance_score=0.9,
    )
