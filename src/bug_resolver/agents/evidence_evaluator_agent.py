"""Evidence evaluator agent that decides whether the investigation has enough signal."""

from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.evidence_evaluation_rules import EvidenceEvaluationRules
from bug_resolver.schemas import EvidenceEvaluationResult, WorkflowState
from bug_resolver.utils.ids import new_evaluation_id


class EvidenceEvaluatorAgent(BaseAgent[WorkflowState, EvidenceEvaluationResult]):
    """
    Evaluates collected investigation evidence before RCA writing.
    """

    name = "evidence_evaluator_agent"

    def __init__(self, rules: EvidenceEvaluationRules | None = None) -> None:
        self._rules = rules or EvidenceEvaluationRules()

    async def _run(self, input_data: WorkflowState) -> EvidenceEvaluationResult:
        confidence_score = self._rules.confidence_score(input_data)
        can_write_rca = self._rules.can_write_rca(input_data, confidence_score)
        retry_required = self._rules.retry_required(input_data, can_write_rca)

        return EvidenceEvaluationResult(
            evaluation_id=new_evaluation_id(),
            incident_id=input_data.incident.incident_id,
            confidence_score=confidence_score,
            retry_required=retry_required,
            can_write_rca=can_write_rca,
            missing_evidence=self._rules.missing_evidence(input_data),
            conflicting_evidence=self._rules.conflicting_evidence(input_data),
            improved_code_queries=(
                self._rules.improved_code_queries(input_data) if retry_required else []
            ),
            improved_knowledge_queries=(
                self._rules.improved_knowledge_queries(input_data) if retry_required else []
            ),
            reason=self._rules.reason(
                can_write_rca=can_write_rca,
                retry_required=retry_required,
            ),
        )
