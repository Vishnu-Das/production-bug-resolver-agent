"""Code graph investigator agent for AST-derived structural evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.graph import CodeGraphProvider
from bug_resolver.rules.code_query_rules import CodeQueryRules
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision
from bug_resolver.utils.observability import get_logger, log_debug_payload


logger = get_logger(__name__)


class CodeGraphInvestigatorInput(StrictBaseModel):
    """Input for a structural code graph investigation."""

    decision: AgentDecision
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1)


class CodeGraphInvestigatorAgent(
    BaseAgent[CodeGraphInvestigatorInput, list[EvidenceItem]]
):
    """Retrieves AST-derived relationships between local Python symbols."""

    name = "code_graph_investigator_agent"

    def __init__(
        self,
        code_graph_provider: CodeGraphProvider,
        code_query_rules: CodeQueryRules | None = None,
    ) -> None:
        self._code_graph_provider = code_graph_provider
        self._code_query_rules = code_query_rules or CodeQueryRules()

    async def _run(self, input_data: CodeGraphInvestigatorInput) -> list[EvidenceItem]:
        queries = self._queries_from_input(input_data)
        logger.info(
            "code graph investigator search decision_id=%s query_count=%s limit=%s",
            input_data.decision.decision_id,
            len(queries),
            input_data.limit,
        )
        log_debug_payload(logger, "code graph investigator queries", payload=queries)
        contexts = await self._code_graph_provider.search_graph(
            queries,
            limit=input_data.limit,
        )

        evidence_items = [context.to_evidence_item() for context in contexts]
        for evidence in evidence_items:
            evidence.metadata["agent_name"] = self.name
            evidence.metadata["decision_id"] = input_data.decision.decision_id

        logger.info(
            "code graph investigator evidence decision_id=%s count=%s ids=%s",
            input_data.decision.decision_id,
            len(evidence_items),
            [evidence.evidence_id for evidence in evidence_items],
        )
        return evidence_items

    def _queries_from_input(self, input_data: CodeGraphInvestigatorInput) -> list[str]:
        return self._code_query_rules.enrich_queries(
            input_data.decision,
            evidence_items=input_data.evidence_items,
            mode="implementation",
        )
