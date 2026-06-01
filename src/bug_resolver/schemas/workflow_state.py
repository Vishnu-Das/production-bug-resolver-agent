"""Mutable investigation state passed through the dynamic workflow."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.evaluation import EvidenceEvaluationResult
from bug_resolver.schemas.incident import Incident
from bug_resolver.schemas.errors import WorkflowErrorInfo
from bug_resolver.schemas.orchestration import (
    AgentDecision,
    AgentExecutionRecord,
    AgentName,
    AgentRunStatus,
    GuardrailDecision,
    InvestigationStatus,
    InvestigationStep,
    InvestigationTrace,
)
from bug_resolver.schemas.rca import RCAReport
from bug_resolver.schemas.reports import ReportSaveResult
from bug_resolver.schemas.patch_suggestion import PatchSuggestion
from bug_resolver.schemas.solution import SolutionRecommendation
from bug_resolver.utils.ids import new_error_id


class _ErrorLikeProtocol:
    code: str
    message: str
    component: str
    recoverable: bool
    suggested_action: str | None
    context: dict[str, str]


def _default_allowed_agent_names() -> list[AgentName]:
    return [
        AgentName.LOG_INVESTIGATOR,
        AgentName.CODE_INVESTIGATOR,
        AgentName.GRAPH_INVESTIGATOR,
        AgentName.HISTORICAL_RCA_INVESTIGATOR,
        AgentName.KNOWLEDGE_BASE_INVESTIGATOR,
        AgentName.EVIDENCE_EVALUATOR,
        AgentName.RCA_WRITER,
        AgentName.SOLUTION_RECOMMENDER,
        AgentName.PATCH_SUGGESTER,
        AgentName.REPORT_WRITER,
        AgentName.FINISH,
        AgentName.PATCH_GENERATOR,
    ]


class WorkflowState(StrictBaseModel):
    """Investigation state shared across supervisor, guardrails, and agents."""

    incident: Incident

    investigation_status: InvestigationStatus = InvestigationStatus.CREATED

    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    evidence_evaluation: EvidenceEvaluationResult | None = None
    rca_report: RCAReport | None = None
    solution_recommendation: SolutionRecommendation | None = None
    patch_suggestion: PatchSuggestion | None = None
    report_save_result: ReportSaveResult | None = None
    final_report_path: Path | None = None
    report_artifact_paths: list[Path] = Field(default_factory=list)

    current_decision: AgentDecision | None = None
    trace: InvestigationTrace = Field(default_factory=InvestigationTrace)
    agent_invocation_counts: dict[AgentName, int] = Field(default_factory=dict)

    replan_count: int = Field(default=0, ge=0)
    max_replans: int = Field(default=2, ge=0)
    max_steps: int = Field(default=12, ge=1)
    max_agent_invocations_per_agent: int = Field(default=3, ge=1)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    minimum_evidence_count_before_rca: int = Field(default=2, ge=0)
    allowed_agent_names: list[AgentName] = Field(default_factory=_default_allowed_agent_names)

    low_confidence: bool = False
    errors: list[str] = Field(default_factory=list)
    error_events: list[WorkflowErrorInfo] = Field(default_factory=list)

    def can_replan(self) -> bool:
        return self.replan_count < self.max_replans

    def increment_replan(self) -> None:
        if not self.can_replan():
            raise ValueError("max replan count exceeded")
        self.replan_count += 1

    def can_take_step(self) -> bool:
        return len(self.trace.steps) < self.max_steps

    def can_invoke_agent(self, agent_name: AgentName) -> bool:
        invocation_count = self.agent_invocation_counts.get(agent_name, 0)
        return invocation_count < self.max_agent_invocations_per_agent

    def record_decision(self, decision: AgentDecision) -> None:
        self.current_decision = decision
        self.trace.decisions.append(decision)

    def record_guardrail_decision(self, decision: GuardrailDecision) -> None:
        self.trace.guardrail_decisions.append(decision)

    def record_agent_execution(self, record: AgentExecutionRecord) -> None:
        self.trace.agent_executions.append(record)
        if record.status in {
            AgentRunStatus.RUNNING,
            AgentRunStatus.SUCCEEDED,
            AgentRunStatus.FAILED,
        }:
            self.agent_invocation_counts[record.agent_name] = (
                self.agent_invocation_counts.get(record.agent_name, 0) + 1
            )

    def add_investigation_step(self, step: InvestigationStep) -> None:
        if not self.can_take_step():
            self.investigation_status = InvestigationStatus.MAX_STEPS_REACHED
            raise ValueError("max investigation steps exceeded")
        self.trace.steps.append(step)

    def add_evidence(self, evidence: EvidenceItem) -> None:
        self.evidence_items.append(evidence)

    def has_minimum_evidence_for_rca(self) -> bool:
        return len(self.evidence_items) >= self.minimum_evidence_count_before_rca

    def mark_low_confidence(self) -> None:
        self.low_confidence = True
        self.investigation_status = InvestigationStatus.LOW_CONFIDENCE

    def add_error(
        self,
        error: str | WorkflowErrorInfo | _ErrorLikeProtocol,
        *,
        recoverable: bool | None = None,
        component: str | None = None,
        suggested_action: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        error_info = self._to_error_info(
            error,
            recoverable=recoverable,
            component=component,
            suggested_action=suggested_action,
            context=context,
        )
        self.error_events.append(error_info)
        self.errors.append(error_info.message)
        if not error_info.recoverable:
            self.investigation_status = InvestigationStatus.FAILED

    def _to_error_info(
        self,
        error: str | WorkflowErrorInfo | _ErrorLikeProtocol,
        *,
        recoverable: bool | None,
        component: str | None,
        suggested_action: str | None,
        context: dict[str, str] | None,
    ) -> WorkflowErrorInfo:
        if isinstance(error, WorkflowErrorInfo):
            return error

        if isinstance(error, str):
            return WorkflowErrorInfo(
                error_id=new_error_id(),
                code="workflow_error",
                message=error,
                component=component or "workflow",
                recoverable=False if recoverable is None else recoverable,
                suggested_action=suggested_action,
                context=context or {},
            )

        merged_context = {
            **getattr(error, "context", {}),
            **(context or {}),
        }
        return WorkflowErrorInfo(
            error_id=new_error_id(),
            code=getattr(error, "code", "workflow_error"),
            message=getattr(error, "message", str(error)),
            component=component or getattr(error, "component", "workflow"),
            recoverable=(
                getattr(error, "recoverable", False)
                if recoverable is None
                else recoverable
            ),
            suggested_action=suggested_action
            or getattr(error, "suggested_action", None),
            context=merged_context,
        )
