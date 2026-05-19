"""Code investigator agent that turns supervisor code-search decisions into evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision


class CodeInvestigatorInput(StrictBaseModel):
    """Input for a code investigation requested by the supervisor."""

    decision: AgentDecision
    limit: int = Field(default=5, ge=1)


class CodeInvestigatorAgent(BaseAgent[CodeInvestigatorInput, list[EvidenceItem]]):
    """
    Retrieves code context selected by the supervisor and returns code evidence.
    """

    name = "code_investigator_agent"

    def __init__(self, code_context_provider: CodeContextProvider) -> None:
        self._code_context_provider = code_context_provider

    async def _run(self, input_data: CodeInvestigatorInput) -> list[EvidenceItem]:
        queries = self._queries_from_decision(input_data.decision)
        contexts = await self._code_context_provider.search_code(
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
