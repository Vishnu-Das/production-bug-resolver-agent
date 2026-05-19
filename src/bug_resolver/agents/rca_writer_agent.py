from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.rca_rules import RCARules
from bug_resolver.schemas import RCAReport, WorkflowState
from bug_resolver.utils.ids import new_rca_report_id


class RCAWriterAgent(BaseAgent[WorkflowState, RCAReport]):
    """Writes an evidence-backed RCA from dynamic investigation state."""

    name = "rca_writer_agent"

    def __init__(self, rules: RCARules | None = None) -> None:
        self._rules = rules or RCARules()

    async def _run(self, input_data: WorkflowState) -> RCAReport:
        return RCAReport(
            report_id=new_rca_report_id(),
            incident_id=input_data.incident.incident_id,
            title=self._rules.build_title(input_data),
            incident_summary=self._rules.build_incident_summary(input_data),
            impact=self._rules.build_impact(input_data),
            symptoms=self._rules.build_symptoms(input_data),
            log_findings=self._rules.build_log_findings(input_data),
            code_findings=self._rules.build_code_findings(input_data),
            knowledge_base_findings=self._rules.build_knowledge_base_findings(input_data),
            hypotheses_considered=self._rules.build_hypotheses_considered(input_data),
            selected_hypothesis_id=None,
            root_cause=self._rules.build_root_cause(input_data),
            technical_explanation=self._rules.build_technical_explanation(input_data),
            evidence_ids=self._rules.evidence_ids(input_data),
            confidence_score=self._rules.confidence_score(input_data),
            confidence_reason=self._rules.confidence_reason(input_data),
            immediate_fix=self._rules.immediate_fix(input_data),
            long_term_prevention=self._rules.long_term_prevention(),
            tests_to_add=self._rules.tests_to_add(input_data),
            open_questions=self._rules.open_questions(input_data),
            low_confidence_warning=self._rules.low_confidence_warning(input_data),
            metadata={
                "evidence_count": str(len(input_data.evidence_items)),
                "dynamic_workflow": "true",
            },
        )

    def _validate_input(self, input_data: WorkflowState) -> None:
        super()._validate_input(input_data)

        if not input_data.evidence_items:
            raise ValueError(f"{self.name} requires evidence before writing an RCA.")

        if input_data.evidence_evaluation is None:
            raise ValueError(f"{self.name} requires evidence evaluation before RCA.")
