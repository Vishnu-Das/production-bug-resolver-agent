"""Schema for generated RCA reports."""

from __future__ import annotations

from pydantic import Field, model_validator

from bug_resolver.schemas.common import ConfidenceScore, StrictBaseModel


class RCAReport(StrictBaseModel):
    """Evidence-backed root cause analysis report."""

    report_id: str = Field(..., min_length=1)
    incident_id: str = Field(..., min_length=1)

    title: str = Field(..., min_length=1)

    incident_summary: str = Field(..., min_length=1)
    impact: str | None = None
    symptoms: list[str] = Field(default_factory=list)

    log_findings: list[str] = Field(default_factory=list)
    code_findings: list[str] = Field(default_factory=list)
    graph_findings: list[str] = Field(default_factory=list)
    knowledge_base_findings: list[str] = Field(default_factory=list)
    historical_findings: list[str] = Field(default_factory=list)

    hypotheses_considered: list[str] = Field(default_factory=list)
    selected_hypothesis_id: str | None = None

    root_cause: str = Field(..., min_length=1)
    technical_explanation: str = Field(..., min_length=1)

    evidence_ids: list[str] = Field(default_factory=list)

    confidence_score: ConfidenceScore
    confidence_reason: str = Field(..., min_length=1)

    immediate_fix: str | None = None
    long_term_prevention: str | None = None
    tests_to_add: list[str] = Field(default_factory=list)

    open_questions: list[str] = Field(default_factory=list)
    low_confidence_warning: str | None = None

    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_low_confidence_report(self) -> RCAReport:
        if self.confidence_score < 0.75 and not self.open_questions:
            raise ValueError("low-confidence RCA reports must include open_questions")
        return self
