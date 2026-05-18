from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.evidence_evaluation_rules import EvidenceEvaluationRules
from bug_resolver.schemas import EvidenceEvaluationResult, RCAReport
from bug_resolver.utils.ids import new_evaluation_id


class EvidenceEvaluatorAgent(BaseAgent[RCAReport, EvidenceEvaluationResult]):
    """
    Coordinates RCA evidence evaluation.

    Current version is deterministic:
    - checks confidence threshold
    - checks required evidence sections
    - decides whether retry is required
    - generates improved retrieval queries
    """

    name = "evidence_evaluator_agent"

    def __init__(self, rules: EvidenceEvaluationRules | None = None) -> None:
        self._rules = rules or EvidenceEvaluationRules()

    async def _run(self, input_data: RCAReport) -> EvidenceEvaluationResult:
        retry_required = self._rules.retry_required(input_data)

        return EvidenceEvaluationResult(
            evaluation_id=new_evaluation_id(),
            incident_id=input_data.incident_id,
            confidence_score=input_data.confidence_score,
            retry_required=retry_required,
            missing_evidence=self._rules.missing_evidence(input_data),
            conflicting_evidence=self._rules.conflicting_evidence(input_data),
            improved_code_queries=(
                self._rules.improved_code_queries(input_data)
                if retry_required
                else []
            ),
            improved_knowledge_queries=(
                self._rules.improved_knowledge_queries(input_data)
                if retry_required
                else []
            ),
            reason=self._rules.reason(
                rca_report=input_data,
                retry_required=retry_required,
            ),
        )