from __future__ import annotations

from pathlib import Path

from pydantic import Field

from bug_resolver.schemas.code_context import CodeContext
from bug_resolver.schemas.common import StrictBaseModel, WorkflowStatus
from bug_resolver.schemas.context_plan import ContextPlan
from bug_resolver.schemas.evaluation import EvidenceEvaluationResult
from bug_resolver.schemas.hypothesis import Hypothesis
from bug_resolver.schemas.incident import Incident
from bug_resolver.schemas.knowledge_context import KnowledgeContext
from bug_resolver.schemas.logs import LogAnalysisResult, LogEntry
from bug_resolver.schemas.rca import RCAReport
from bug_resolver.schemas.solution import SolutionRecommendation


class WorkflowState(StrictBaseModel):
    incident: Incident

    raw_logs: list[str] = Field(default_factory=list)
    parsed_logs: list[LogEntry] = Field(default_factory=list)

    log_analysis: LogAnalysisResult | None = None
    context_plan: ContextPlan | None = None

    code_context: list[CodeContext] = Field(default_factory=list)
    knowledge_context: list[KnowledgeContext] = Field(default_factory=list)

    hypotheses: list[Hypothesis] = Field(default_factory=list)
    rca_report: RCAReport | None = None
    evidence_evaluation: EvidenceEvaluationResult | None = None
    solution_recommendation: SolutionRecommendation | None = None

    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=0)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    final_report_path: Path | None = None
    errors: list[str] = Field(default_factory=list)

    status: WorkflowStatus = WorkflowStatus.CREATED

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        if not self.can_retry():
            raise ValueError("max retry count exceeded")
        self.retry_count += 1

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.status = WorkflowStatus.FAILED