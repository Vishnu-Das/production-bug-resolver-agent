"""Schemas for supervisor routing, guardrails, and investigation traces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from bug_resolver.schemas.common import StrictBaseModel


class AgentName(StrEnum):
    """Allowed supervisor routes and workflow control agents."""

    LOG_INVESTIGATOR = "log_investigator"
    CODE_INVESTIGATOR = "code_investigator"
    KNOWLEDGE_BASE_INVESTIGATOR = "knowledge_base_investigator"
    EVIDENCE_EVALUATOR = "evidence_evaluator"
    RCA_WRITER = "rca_writer"
    SOLUTION_RECOMMENDER = "solution_recommender"
    REPORT_WRITER = "report_writer"
    WEB_SEARCH_INVESTIGATOR = "web_search_investigator"
    GRAPH_INVESTIGATOR = "graph_investigator"
    HISTORICAL_RCA_INVESTIGATOR = "historical_rca_investigator"
    PATCH_SUGGESTER = "patch_suggester"
    FINISH = "finish"


class InvestigationStatus(StrEnum):
    """Top-level workflow status values exposed by the CLI."""

    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_EVIDENCE = "waiting_for_evidence"
    READY_FOR_RCA = "ready_for_rca"
    LOW_CONFIDENCE = "low_confidence"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_STEPS_REACHED = "max_steps_reached"


class AgentRunStatus(StrEnum):
    """Execution status values for individual agent runs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class AgentDecision(StrictBaseModel):
    """Supervisor routing decision with reason and optional search queries."""

    decision_id: str = Field(..., min_length=1)
    next_agent: AgentName
    reason: str = Field(..., min_length=1)
    queries: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)
    should_continue: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_finish_decision(self) -> AgentDecision:
        if self.next_agent == AgentName.FINISH and self.should_continue:
            raise ValueError("finish decisions must set should_continue to false")
        return self


class GuardrailDecision(StrictBaseModel):
    """Deterministic validation result for a supervisor decision."""

    guardrail_id: str = Field(..., min_length=1)
    allowed: bool
    reason: str = Field(..., min_length=1)
    fallback_next_agent: AgentName | None = None
    violated_rules: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_blocked_decision_has_fallback_or_rules(self) -> GuardrailDecision:
        if not self.allowed and self.fallback_next_agent is None and not self.violated_rules:
            raise ValueError(
                "blocked guardrail decisions must include a fallback route or violated rules"
            )
        return self


class ToolCallRequest(StrictBaseModel):
    """Trace record for a requested provider/tool call."""

    tool_call_id: str = Field(..., min_length=1)
    agent_name: AgentName
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class ToolCallResult(StrictBaseModel):
    """Trace record for a completed provider/tool call."""

    tool_call_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    succeeded: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @model_validator(mode="after")
    def validate_failed_result_has_error(self) -> ToolCallResult:
        if not self.succeeded and not self.error:
            raise ValueError("failed tool call results must include an error")
        return self


class AgentExecutionRecord(StrictBaseModel):
    """Trace record for an agent invocation."""

    execution_id: str = Field(..., min_length=1)
    agent_name: AgentName
    status: AgentRunStatus = AgentRunStatus.PENDING
    decision_id: str | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tool_calls: list[ToolCallResult] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_failed_run_has_error(self) -> AgentExecutionRecord:
        if self.status == AgentRunStatus.FAILED and not self.error:
            raise ValueError("failed agent execution records must include an error")
        return self


class InvestigationStep(StrictBaseModel):
    """Human-readable workflow step shown in investigation traces."""

    step_number: int = Field(..., ge=1)
    agent_name: AgentName
    run_status: AgentRunStatus = AgentRunStatus.PENDING
    decision_id: str | None = None
    guardrail_id: str | None = None
    execution_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class InvestigationTrace(StrictBaseModel):
    """Accumulated routing, guardrail, and execution trace."""

    steps: list[InvestigationStep] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    guardrail_decisions: list[GuardrailDecision] = Field(default_factory=list)
    agent_executions: list[AgentExecutionRecord] = Field(default_factory=list)

    def next_step_number(self) -> int:
        return len(self.steps) + 1
