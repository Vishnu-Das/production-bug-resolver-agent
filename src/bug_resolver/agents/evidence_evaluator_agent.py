"""Evidence evaluator agent that decides whether enough evidence was collected."""

from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.rules.evidence_evaluation_rules import EvidenceEvaluationRules
from bug_resolver.schemas import EvidenceEvaluationResult, WorkflowState
from bug_resolver.utils.ids import new_evaluation_id
from bug_resolver.utils.observability import get_logger, log_debug_payload


logger = get_logger(__name__)


class EvidenceEvaluatorAgent(BaseAgent[WorkflowState, EvidenceEvaluationResult]):
    """
    Evaluates collected investigation evidence before RCA writing.
    """

    name = "evidence_evaluator_agent"

    def __init__(self, rules: EvidenceEvaluationRules | None = None) -> None:
        self._rules = rules or EvidenceEvaluationRules()

    async def _run(self, input_data: WorkflowState) -> EvidenceEvaluationResult:
        logger.info(
            "evidence evaluation started incident_id=%s evidence_count=%s replan_count=%s",
            input_data.incident.incident_id,
            len(input_data.evidence_items),
            input_data.replan_count,
        )
        confidence_score = self._rules.confidence_score(input_data)
        can_write_rca = self._rules.can_write_rca(input_data, confidence_score)
        retry_required = self._rules.retry_required(input_data, can_write_rca)

        result = EvidenceEvaluationResult(
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
                state=input_data,
                can_write_rca=can_write_rca,
                retry_required=retry_required,
            ),
        )
        logger.info(
            "evidence evaluation finished evaluation_id=%s confidence=%s can_write_rca=%s retry_required=%s missing_count=%s",
            result.evaluation_id,
            result.confidence_score,
            result.can_write_rca,
            result.retry_required,
            len(result.missing_evidence),
        )
        log_debug_payload(logger, "evidence evaluation result", payload=result)
        return result
