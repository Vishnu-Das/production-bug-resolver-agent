from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.rca_rules import RCARules
from bug_resolver.schemas import (
    CodeContext,
    Hypothesis,
    Incident,
    KnowledgeContext,
    LogAnalysisResult,
    RCAReport,
)
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.utils.ids import new_rca_report_id


class RCAInput(StrictBaseModel):
    incident: Incident
    log_analysis: LogAnalysisResult
    hypotheses: list[Hypothesis] = Field(..., min_length=1)
    code_contexts: list[CodeContext] = Field(default_factory=list)
    knowledge_contexts: list[KnowledgeContext] = Field(default_factory=list)


class RCAAgent(BaseAgent[RCAInput, RCAReport]):
    """
    Coordinates RCA report generation.

    Current version is deterministic:
    - selects strongest hypothesis
    - builds structured RCAReport
    - keeps evidence IDs attached
    - marks low-confidence reports clearly
    """

    name = "rca_agent"

    def __init__(self, rules: RCARules | None = None) -> None:
        self._rules = rules or RCARules()

    async def _run(self, input_data: RCAInput) -> RCAReport:
        selected_hypothesis = self._rules.select_strongest_hypothesis(
            input_data.hypotheses
        )

        return RCAReport(
            report_id=new_rca_report_id(),
            incident_id=input_data.incident.incident_id,
            title=self._rules.build_title(input_data.incident),
            incident_summary=self._rules.build_incident_summary(input_data.incident),
            impact=self._rules.build_impact(input_data.incident),
            symptoms=self._rules.build_symptoms(
                incident=input_data.incident,
                log_analysis=input_data.log_analysis,
            ),
            log_findings=self._rules.build_log_findings(input_data.log_analysis),
            code_findings=self._rules.build_code_findings(input_data.code_contexts),
            knowledge_base_findings=self._rules.build_knowledge_base_findings(
                input_data.knowledge_contexts
            ),
            hypotheses_considered=self._rules.build_hypotheses_considered(
                input_data.hypotheses
            ),
            selected_hypothesis_id=selected_hypothesis.hypothesis_id,
            root_cause=selected_hypothesis.suspected_root_cause,
            technical_explanation=self._rules.build_technical_explanation(
                selected_hypothesis=selected_hypothesis,
                log_analysis=input_data.log_analysis,
            ),
            evidence_ids=selected_hypothesis.supporting_evidence_ids,
            confidence_score=selected_hypothesis.confidence_score,
            confidence_reason=self._rules.build_confidence_reason(selected_hypothesis),
            immediate_fix=self._rules.build_immediate_fix(selected_hypothesis),
            long_term_prevention=self._rules.build_long_term_prevention(),
            tests_to_add=self._rules.build_tests_to_add(
                incident=input_data.incident,
                selected_hypothesis=selected_hypothesis,
            ),
            open_questions=self._rules.build_open_questions(selected_hypothesis),
            low_confidence_warning=self._rules.build_low_confidence_warning(
                selected_hypothesis
            ),
            metadata={
                "selected_hypothesis_status": selected_hypothesis.status.value,
            },
        )