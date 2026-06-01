"""Code investigator agent that turns supervisor code-search decisions into evidence."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.agents.base import BaseAgent
from bug_resolver.providers.code import CodeContextProvider
from bug_resolver.rules.code_query_rules import CodeQueryRules
from bug_resolver.rules.ranked_evidence_conversion_rules import (
    RankedEvidenceConversionRules,
)
from bug_resolver.retrieval.incident_driven_context_service import (
    IncidentDrivenContextService,
)
from bug_resolver.schemas import Incident
from bug_resolver.schemas.common import EvidenceSourceType
from bug_resolver.schemas.common import StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision
from bug_resolver.utils.observability import get_logger, log_debug_payload


logger = get_logger(__name__)


class CodeInvestigatorInput(StrictBaseModel):
    """Input for a code investigation requested by the supervisor."""

    decision: AgentDecision
    incident: Incident | None = None
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
        *,
        incident_driven_context_service: IncidentDrivenContextService | None = None,
        ranked_evidence_conversion_rules: RankedEvidenceConversionRules | None = None,
    ) -> None:
        self._code_context_provider = code_context_provider
        self._code_query_rules = code_query_rules or CodeQueryRules()
        self._incident_driven_context_service = incident_driven_context_service
        self._ranked_evidence_conversion_rules = (
            ranked_evidence_conversion_rules or RankedEvidenceConversionRules()
        )

    async def _run(self, input_data: CodeInvestigatorInput) -> list[EvidenceItem]:
        if (
            self._incident_driven_context_service is not None
            and input_data.incident is not None
        ):
            return await self._run_incident_driven(input_data)

        return await self._run_legacy(input_data)

    async def _run_incident_driven(
        self,
        input_data: CodeInvestigatorInput,
    ) -> list[EvidenceItem]:
        incident = input_data.incident
        if incident is None:
            return await self._run_legacy(input_data)

        log_texts = [
            evidence.content
            for evidence in input_data.evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        ]
        metadata = {
            **incident.metadata,
            **({"raw_input": incident.raw_input} if incident.raw_input else {}),
        }
        context_service = self._incident_driven_context_service
        if context_service is None:
            return await self._run_legacy(input_data)

        result = await context_service.build_context(
            incident_id=incident.incident_id,
            summary=incident.title,
            description=incident.description,
            log_texts=log_texts,
            metadata=metadata,
            max_selected=input_data.limit,
        )
        evidence_items = self._ranked_evidence_conversion_rules.convert_selected(
            result,
            agent_name=self.name,
            decision_id=input_data.decision.decision_id,
        )
        logger.info(
            "incident-driven code investigator evidence decision_id=%s selected=%s "
            "failed_retrievers=%s",
            input_data.decision.decision_id,
            len(evidence_items),
            result.failed_retrievers,
        )
        log_debug_payload(
            logger,
            "incident-driven code investigator evaluation",
            payload=result.evaluation,
        )
        return evidence_items

    async def _run_legacy(self, input_data: CodeInvestigatorInput) -> list[EvidenceItem]:
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
        return self._code_query_rules.enrich_queries(decision, mode="implementation")

    def _queries_from_input(self, input_data: CodeInvestigatorInput) -> list[str]:
        return self._code_query_rules.enrich_queries(
            input_data.decision,
            evidence_items=input_data.evidence_items,
            mode="implementation",
        )
