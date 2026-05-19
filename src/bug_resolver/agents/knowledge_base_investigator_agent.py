"""Knowledge-base investigator agent that retrieves documentation context as evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.knowledge import KnowledgeBaseProvider
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision


class KnowledgeBaseInvestigatorInput(StrictBaseModel):
    """Input for a documentation search requested by the supervisor."""

    decision: AgentDecision
    limit: int = Field(default=5, ge=1)


class KnowledgeBaseInvestigatorAgent(BaseAgent[KnowledgeBaseInvestigatorInput, list[EvidenceItem]]):
    """
    Retrieves README/docs/design context selected by the supervisor as evidence.
    """

    name = "knowledge_base_investigator_agent"

    def __init__(self, knowledge_base_provider: KnowledgeBaseProvider) -> None:
        self._knowledge_base_provider = knowledge_base_provider

    async def _run(self, input_data: KnowledgeBaseInvestigatorInput) -> list[EvidenceItem]:
        queries = self._queries_from_decision(input_data.decision)
        contexts = await self._knowledge_base_provider.search_knowledge(
            queries,
            limit=input_data.limit,
        )

        evidence_items = [context.to_evidence_item() for context in contexts]
        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        return evidence_items

    def _queries_from_decision(self, decision: AgentDecision) -> list[str]:
        if decision.queries:
            return decision.queries

        return [decision.reason]
