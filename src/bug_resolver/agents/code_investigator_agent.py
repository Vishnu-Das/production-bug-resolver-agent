"""Code investigator agent that turns supervisor code-search decisions into evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.rules.code_query_rules import CodeQueryRules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision
from bug_resolver.utils.observability import get_logger, log_debug_payload


logger = get_logger(__name__)


class CodeInvestigatorInput(StrictBaseModel):
    """Input for a code investigation requested by the supervisor."""

    decision: AgentDecision
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1)


class CodeInvestigatorAgent(BaseAgent[CodeInvestigatorInput, list[EvidenceItem]]):
    """
    Retrieves code context selected by the supervisor and returns code evidence.
    """

    name = "code_investigator_agent"

    def __init__(
        self,
        code_context_provider: CodeContextProvider,
        code_query_rules: CodeQueryRules | None = None,
    ) -> None:
        self._code_context_provider = code_context_provider
        self._code_query_rules = code_query_rules or CodeQueryRules()

    async def _run(self, input_data: CodeInvestigatorInput) -> list[EvidenceItem]:
        queries = self._queries_from_input(input_data)
        logger.info(
            "code investigator search decision_id=%s query_count=%s limit=%s",
            input_data.decision.decision_id,
            len(queries),
            input_data.limit,
        )
        log_debug_payload(logger, "code investigator queries", payload=queries)
        contexts = await self._code_context_provider.search_code(
            queries,
            limit=input_data.limit,
        )

        evidence_items = [context.to_evidence_item() for context in contexts]
        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        logger.info(
            "code investigator evidence decision_id=%s count=%s ids=%s",
            input_data.decision.decision_id,
            len(evidence_items),
            [evidence.evidence_id for evidence in evidence_items],
        )
        return evidence_items

    def _queries_from_decision(self, decision: AgentDecision) -> list[str]:
        return self._code_query_rules.enrich_queries(decision)

    def _queries_from_input(self, input_data: CodeInvestigatorInput) -> list[str]:
        return self._code_query_rules.enrich_queries(
            input_data.decision,
            evidence_items=input_data.evidence_items,
        )
