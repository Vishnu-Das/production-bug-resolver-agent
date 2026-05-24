"""Log investigator agent that retrieves incident logs as evidence."""

from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.logs import LogProvider
from bug_resolver.rules.log_analysis_rules import LogAnalysisRules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision
from bug_resolver.utils.observability import get_logger, log_debug_payload


logger = get_logger(__name__)


class LogInvestigatorInput(StrictBaseModel):
    """Input for a log search requested by the supervisor."""

    incident_id: str
    decision: AgentDecision


class LogInvestigatorAgent(BaseAgent[LogInvestigatorInput, list[EvidenceItem]]):
    """
    Retrieves incident logs and converts runtime signals into evidence.
    """

    name = "log_investigator_agent"

    def __init__(
        self,
        log_provider: LogProvider,
        rules: LogAnalysisRules | None = None,
    ) -> None:
        self._log_provider = log_provider
        self._rules = rules or LogAnalysisRules()

    async def _run(self, input_data: LogInvestigatorInput) -> list[EvidenceItem]:
        logger.info(
            "log investigator search incident_id=%s decision_id=%s",
            input_data.incident_id,
            input_data.decision.decision_id,
        )
        logs = await self._log_provider.get_logs(input_data.incident_id)
        if not logs:
            return []
        log_debug_payload(logger, "log investigator retrieved logs", payload=logs)

        evidence_items = self._rules.build_evidence_items(logs)
        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        logger.info(
            "log investigator evidence decision_id=%s count=%s ids=%s",
            input_data.decision.decision_id,
            len(evidence_items),
            [evidence.evidence_id for evidence in evidence_items],
        )
        return evidence_items
