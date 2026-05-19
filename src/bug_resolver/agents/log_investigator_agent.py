from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.logs import LogProvider
from bug_resolver.rules.log_analysis_rules import LogAnalysisRules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision


class LogInvestigatorInput(StrictBaseModel):
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
        logs = await self._log_provider.get_logs(input_data.incident_id)
        if not logs:
            return []

        evidence_items = self._rules.build_evidence_items(logs)
        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        return evidence_items
