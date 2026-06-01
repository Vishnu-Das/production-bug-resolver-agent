"""Golden regression for ranked context retrieval using a checked-in sample incident."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bug_resolver.agents import (
    CodeInvestigatorAgent,
    CodeInvestigatorInput,
    EvidenceEvaluatorAgent,
    LogInvestigatorAgent,
    LogInvestigatorInput,
    RCAWriterAgent,
    ReportWriterAgent,
    ReportWriterInput,
    SolutionRecommendationAgent,
)
from bug_resolver.prompts import RCAPromptBuilder
from bug_resolver.providers.graph import PythonASTCodeGraphProvider
from bug_resolver.providers.incident import FileIncidentProvider
from bug_resolver.providers.knowledge import LocalKnowledgeBaseProvider
from bug_resolver.providers.logs import FileLogProvider
from bug_resolver.providers.reports import FileReportStore
from bug_resolver.providers.retrieval import (
    CodeGraphExpansionAdapter,
    KnowledgeSearchAdapter,
    LocalExactSearchProvider,
    LocalFileContextProvider,
)
from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    AgentDecision,
    AgentName,
    IncidentDrivenContextResult,
    RetrievalEvidenceSourceType,
    WorkflowState,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_DIR = REPO_ROOT / "sample_data"
NOISY_TEST_MARKER = "NOISY_TEST_ONLY_CONTEXT"


class FailIfCalledCodeContextProvider:
    """Prove the incident-driven branch does not fall back to legacy Code RAG."""

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[object]:
        raise AssertionError(
            f"legacy code context provider should not be called: {queries=} {limit=}"
        )


class RecordingIncidentDrivenContextService(IncidentDrivenContextService):
    """Retain retrieval diagnostics while exercising the agent integration."""

    last_result: IncidentDrivenContextResult | None = None

    async def build_context(self, **kwargs: Any) -> IncidentDrivenContextResult:
        self.last_result = await super().build_context(**kwargs)
        return self.last_result


def _decision(decision_id: str, next_agent: AgentName) -> AgentDecision:
    return AgentDecision(
        decision_id=decision_id,
        next_agent=next_agent,
        reason=f"Collect {next_agent.value} evidence for the sample incident.",
    )


def _write_file(repo_path: Path, relative_path: str, content: str) -> None:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _source_with_lines(
    total_lines: int,
    replacements: dict[int, str],
) -> str:
    lines = ["# fixture padding"] * total_lines
    for line_number, value in replacements.items():
        lines[line_number - 1] = value
    return "\n".join(lines) + "\n"


def _build_target_repo(repo_path: Path) -> None:
    _write_file(
        repo_path,
        "src/rag/service.py",
        _source_with_lines(
            70,
            {
                51: "def resolve_retrieval_strategy(router, user_input, selected_document):",
                52: "    if not user_input:",
                53: '        raise ValueError("query is required")',
                54: "    selected_document = selected_document or None",
                55: (
                    "    router_result = router.route("
                    "query=user_input, selected_document=selected_document)"
                ),
                56: "    return router_result.strategy",
            },
        ),
    )
    _write_file(
        repo_path,
        "src/rag/routing/llm.py",
        _source_with_lines(
            95,
            {
                76: "class LLMRouterStrategy:",
                77: "    def route(self, query, selected_document=None):",
                78: "        result = self._route_result(query)",
                79: '        if result.strategy not in {"parent_child", "fusion"}:',
                80: '            explanation = "unsupported strategy"',
                81: "            log_message = explanation",
                82: '            raise ValueError(f"Invalid strategy: {result.strategy}")',
                83: "        return result",
                85: "    def _route_result(self, query):",
                86: "        return query",
            },
        ),
    )
    _write_file(
        repo_path,
        "tests/rag/routing/test_router_factory.py",
        "\n".join(
            [
                f'NOISY_MARKER = "{NOISY_TEST_MARKER}"',
                "",
                "def test_route_rejects_invalid_strategy():",
                '    raise ValueError("Invalid strategy in fixture test")',
            ]
        ),
    )


def _build_service(repo_path: Path) -> RecordingIncidentDrivenContextService:
    return RecordingIncidentDrivenContextService(
        ParallelContextRetriever(
            file_context_provider=LocalFileContextProvider(repo_path),
            exact_search_provider=LocalExactSearchProvider(repo_path),
            code_graph_provider=CodeGraphExpansionAdapter(
                PythonASTCodeGraphProvider(repo_path)
            ),
            knowledge_search_provider=KnowledgeSearchAdapter(
                LocalKnowledgeBaseProvider(SAMPLE_DATA_DIR / "knowledge_base")
            ),
        )
    )


@pytest.mark.asyncio
async def test_inc_001_selects_ranked_owner_evidence_for_rca(tmp_path: Path) -> None:
    repo_path = tmp_path / "target_repo"
    _build_target_repo(repo_path)
    incident = await FileIncidentProvider(SAMPLE_DATA_DIR / "incidents").get_incident(
        "INC-001"
    )
    log_evidence = await LogInvestigatorAgent(
        FileLogProvider(SAMPLE_DATA_DIR / "logs")
    ).run(
        LogInvestigatorInput(
            incident_id=incident.incident_id,
            decision=_decision("decision-log", AgentName.LOG_INVESTIGATOR),
        )
    )
    context_service = _build_service(repo_path)
    code_evidence = await CodeInvestigatorAgent(
        FailIfCalledCodeContextProvider(),  # type: ignore[arg-type]
        incident_driven_context_service=context_service,
    ).run(
        CodeInvestigatorInput(
            decision=_decision("decision-code", AgentName.CODE_INVESTIGATOR),
            incident=incident,
            evidence_items=log_evidence,
            limit=2,
        )
    )

    result = context_service.last_result
    assert result is not None
    assert result.evaluation.sufficient_for_rca is True
    assert result.evaluation.has_direct_code_evidence is True
    assert 0.0 < result.evaluation.confidence <= 1.0
    assert len(result.raw_candidates) > len(result.evaluation.selected_evidence)
    assert len(code_evidence) == len(result.evaluation.selected_evidence)

    top_evidence = result.evaluation.selected_evidence[0]
    assert top_evidence.candidate.file_path in {
        "src/rag/service.py",
        "src/rag/routing/llm.py",
    }
    assert top_evidence.candidate.source_type in {
        RetrievalEvidenceSourceType.FILE_CONTEXT,
        RetrievalEvidenceSourceType.CODE_EXACT,
    }
    assert top_evidence.score.final_score > 0.7
    route_evidence = next(
        evidence
        for evidence in result.evaluation.selected_evidence
        if evidence.candidate.file_path == "src/rag/routing/llm.py"
    )
    assert any(
        "stack trace file src/rag/routing/llm.py" in reason
        for reason in route_evidence.score.reasons
    )
    assert any(
        "stack trace line 82" in reason for reason in route_evidence.score.reasons
    )
    assert any(
        "error term ValueError" in reason for reason in route_evidence.score.reasons
    )

    ranked_test_evidence = [
        evidence
        for evidence in result.evaluation.ranked_evidence
        if evidence.candidate.file_path == "tests/rag/routing/test_router_factory.py"
    ]
    assert ranked_test_evidence
    assert all(
        evidence.score.final_score < top_evidence.score.final_score
        for evidence in ranked_test_evidence
    )

    state = WorkflowState(incident=incident)
    for evidence in [*log_evidence, *code_evidence]:
        state.add_evidence(evidence)
    state.evidence_evaluation = await EvidenceEvaluatorAgent().run(state)
    report = await RCAWriterAgent().run(state)
    prompt = RCAPromptBuilder().build_user_prompt(state, report)

    assert "Ranked Evidence:" in prompt
    assert "Why it matters:" in prompt
    assert "raw_candidates" not in prompt
    assert NOISY_TEST_MARKER not in prompt
    assert NOISY_TEST_MARKER not in report.model_dump_json()
    assert "signal" not in prompt.lower()
    assert "signal" not in report.model_dump_json().lower()
    assert all("score" in evidence.metadata for evidence in code_evidence)
    assert all("score_reasons" in evidence.metadata for evidence in code_evidence)

    solution = await SolutionRecommendationAgent().run(report)
    report_paths = await ReportWriterAgent(FileReportStore(tmp_path / "reports")).run(
        ReportWriterInput(report=report, solution=solution)
    )
    assert report_paths
    assert all(path.exists() for path in report_paths)
    assert (tmp_path / "reports" / "incidents" / "INC-001" / "rca.json").exists()
    assert (tmp_path / "reports" / "incidents" / "INC-001" / "solution.json").exists()
    saved_report = json.loads(
        (tmp_path / "reports" / "incidents" / "INC-001" / "rca.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved_report["incident_id"] == "INC-001"
