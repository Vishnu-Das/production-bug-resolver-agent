"""Historical RCA investigator agent for incident-memory evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.history import HistoricalRCAProvider
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision


class HistoricalRCAInvestigatorInput(StrictBaseModel):
    """Input for searching prior RCA reports."""

    incident_id: str = Field(..., min_length=1)
    decision: AgentDecision
    limit: int = Field(default=5, ge=1)


class HistoricalRCAInvestigatorAgent(
    BaseAgent[HistoricalRCAInvestigatorInput, list[EvidenceItem]]
):
    """Retrieves similar prior RCA reports as supporting historical context."""

    name = "historical_rca_investigator_agent"

    def __init__(self, historical_rca_provider: HistoricalRCAProvider) -> None:
        self._historical_rca_provider = historical_rca_provider

    async def _run(
        self,
        input_data: HistoricalRCAInvestigatorInput,
    ) -> list[EvidenceItem]:
        queries = input_data.decision.queries or [input_data.decision.reason]
        contexts = await self._historical_rca_provider.search_history(
            queries,
            current_incident_id=input_data.incident_id,
            limit=input_data.limit,
        )
        evidence_items = [context.to_evidence_item() for context in contexts]

        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        return evidence_items
