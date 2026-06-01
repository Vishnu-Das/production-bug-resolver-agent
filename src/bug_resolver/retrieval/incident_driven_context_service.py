"""Coordinator for incident-driven retrieval and deterministic evidence evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter

from bug_resolver.rules.owner_graph_expansion_rules import OwnerGraphExpansionRules
from bug_resolver.retrieval.context_retrieval_planner import ContextRetrievalPlanner
from bug_resolver.retrieval.evidence_deduplicator import EvidenceDeduplicator
from bug_resolver.retrieval.evidence_normalizer import EvidenceNormalizer
from bug_resolver.retrieval.evidence_ranker import EvidenceRanker
from bug_resolver.retrieval.incident_parser import IncidentParser
from bug_resolver.retrieval.parallel_context_retriever import ParallelContextRetriever
from bug_resolver.schemas import (
    EvidenceCandidate,
    GraphExpansionRequest,
    Incident,
    IncidentDrivenContextResult,
    IncidentFacts,
    LogEntry,
    RetrievalBatchResult,
    RetrievalEvidenceEvaluationResult,
    RetrievalPlan,
)
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable

logger = get_logger(__name__)


class IncidentDrivenContextService:
    """Coordinate parsing, retrieval, cleanup, and evidence evaluation."""

    def __init__(
        self,
        context_retriever: ParallelContextRetriever,
        *,
        incident_parser: IncidentParser | None = None,
        retrieval_planner: ContextRetrievalPlanner | None = None,
        evidence_normalizer: EvidenceNormalizer | None = None,
        evidence_deduplicator: EvidenceDeduplicator | None = None,
        evidence_ranker: EvidenceRanker | None = None,
        owner_graph_expansion_rules: OwnerGraphExpansionRules | None = None,
    ) -> None:
        self._incident_parser = incident_parser or IncidentParser()
        self._retrieval_planner = retrieval_planner or ContextRetrievalPlanner()
        self._context_retriever = context_retriever
        self._evidence_normalizer = evidence_normalizer or EvidenceNormalizer()
        self._evidence_deduplicator = evidence_deduplicator or EvidenceDeduplicator()
        self._evidence_ranker = evidence_ranker or EvidenceRanker()
        self._owner_graph_expansion_rules = (
            owner_graph_expansion_rules or OwnerGraphExpansionRules()
        )

    @traceable(name="incident_driven_context.build", run_type="retriever")
    async def build_context(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str | None = None,
        log_texts: Sequence[str] | None = None,
        metadata: Mapping[str, str] | None = None,
        max_selected: int = 8,
        minimum_score: float = 0.35,
    ) -> IncidentDrivenContextResult:
        """Parse raw incident text and build ranked retrieval context."""
        facts = self._incident_parser.parse(
            incident_id=incident_id,
            summary=summary,
            description=description,
            log_texts=log_texts,
            metadata=metadata,
        )
        return await self.build_context_from_facts(
            facts,
            max_selected=max_selected,
            minimum_score=minimum_score,
        )

    @traceable(name="incident_driven_context.build_for_incident", run_type="retriever")
    async def build_context_for_incident(
        self,
        incident: Incident,
        logs: Sequence[LogEntry] | None = None,
        *,
        max_selected: int = 8,
        minimum_score: float = 0.35,
    ) -> IncidentDrivenContextResult:
        """Parse existing incident schemas and build ranked retrieval context."""
        facts = self._incident_parser.parse_incident(incident, logs)
        return await self.build_context_from_facts(
            facts,
            max_selected=max_selected,
            minimum_score=minimum_score,
        )

    @traceable(name="incident_driven_context.evaluate", run_type="chain")
    async def build_context_from_facts(
        self,
        facts: IncidentFacts,
        *,
        max_selected: int = 8,
        minimum_score: float = 0.35,
    ) -> IncidentDrivenContextResult:
        """Execute retrieval and deterministic evaluation for parsed facts."""
        started_at = perf_counter()
        logger.info("incident-driven context build started incident_id=%s", facts.incident_id)
        retrieval_plan = self._retrieval_planner.plan(facts)
        retrieval_batch = await self._context_retriever.retrieve(retrieval_plan)
        normalized_candidates, deduplicated_candidates, evaluation = (
            self._evaluate_candidates(
                retrieval_batch,
                facts,
                max_selected=max_selected,
                minimum_score=minimum_score,
            )
        )
        owner_graph_requests = self._owner_graph_requests(
            retrieval_plan,
            evaluation,
            minimum_score=minimum_score,
        )
        if owner_graph_requests:
            logger.info(
                "owner graph expansion started incident_id=%s requests=%s",
                facts.incident_id,
                len(owner_graph_requests),
            )
            owner_graph_batch = await self._context_retriever.retrieve(
                RetrievalPlan(graph_expansion_requests=owner_graph_requests)
            )
            retrieval_plan = retrieval_plan.model_copy(
                update={
                    "graph_expansion_requests": [
                        *retrieval_plan.graph_expansion_requests,
                        *owner_graph_requests,
                    ]
                }
            )
            retrieval_batch = self._merge_batches(retrieval_batch, owner_graph_batch)
            normalized_candidates, deduplicated_candidates, evaluation = (
                self._evaluate_candidates(
                    retrieval_batch,
                    facts,
                    max_selected=max_selected,
                    minimum_score=minimum_score,
                )
            )
            logger.info(
                "owner graph expansion finished incident_id=%s candidates=%s",
                facts.incident_id,
                len(owner_graph_batch.candidates),
            )
        logger.info(
            "incident-driven context build finished incident_id=%s raw=%s normalized=%s "
            "deduplicated=%s ranked=%s selected=%s direct_code=%s sufficient_for_rca=%s "
            "confidence=%.3f failed_retrievers=%s duration_ms=%.2f",
            facts.incident_id,
            len(retrieval_batch.candidates),
            len(normalized_candidates),
            len(deduplicated_candidates),
            len(evaluation.ranked_evidence),
            len(evaluation.selected_evidence),
            evaluation.has_direct_code_evidence,
            evaluation.sufficient_for_rca,
            evaluation.confidence,
            retrieval_batch.failed_retrievers,
            (perf_counter() - started_at) * 1000,
        )
        log_debug_payload(
            logger,
            "incident-driven context selected evidence",
            payload=[
                {
                    "rank": evidence.rank,
                    "candidate_id": evidence.candidate.candidate_id,
                    "source_type": evidence.candidate.source_type,
                    "file_path": evidence.candidate.file_path,
                    "symbol_name": evidence.candidate.symbol_name,
                    "matched_terms": evidence.candidate.matched_terms,
                    "score": evidence.score.final_score,
                    "reasons": evidence.score.reasons,
                }
                for evidence in evaluation.selected_evidence
            ],
        )

        return IncidentDrivenContextResult(
            facts=facts,
            retrieval_plan=retrieval_plan,
            raw_candidates=retrieval_batch.candidates,
            normalized_candidates=normalized_candidates,
            deduplicated_candidates=deduplicated_candidates,
            evaluation=evaluation,
            retrieval_warnings=retrieval_batch.warnings,
            failed_retrievers=retrieval_batch.failed_retrievers,
        )

    def _evaluate_candidates(
        self,
        retrieval_batch: RetrievalBatchResult,
        facts: IncidentFacts,
        *,
        max_selected: int,
        minimum_score: float,
    ) -> tuple[
        list[EvidenceCandidate],
        list[EvidenceCandidate],
        RetrievalEvidenceEvaluationResult,
    ]:
        normalized_candidates = self._evidence_normalizer.normalize(
            retrieval_batch.candidates
        )
        deduplicated_candidates = self._evidence_deduplicator.deduplicate(
            normalized_candidates
        )
        evaluation = self._evidence_ranker.evaluate(
            deduplicated_candidates,
            facts,
            max_selected=max_selected,
            minimum_score=minimum_score,
        )
        return normalized_candidates, deduplicated_candidates, evaluation

    def _owner_graph_requests(
        self,
        retrieval_plan: RetrievalPlan,
        evaluation: RetrievalEvidenceEvaluationResult,
        *,
        minimum_score: float,
    ) -> list[GraphExpansionRequest]:
        if retrieval_plan.graph_expansion_requests:
            return []
        return self._owner_graph_expansion_rules.build_requests(
            evaluation.ranked_evidence,
            minimum_score=minimum_score,
        )

    def _merge_batches(
        self,
        initial_batch: RetrievalBatchResult,
        owner_graph_batch: RetrievalBatchResult,
    ) -> RetrievalBatchResult:
        return RetrievalBatchResult(
            candidates=[*initial_batch.candidates, *owner_graph_batch.candidates],
            warnings=self._unique_strings(
                [*initial_batch.warnings, *owner_graph_batch.warnings]
            ),
            failed_retrievers=self._unique_strings(
                [
                    *initial_batch.failed_retrievers,
                    *owner_graph_batch.failed_retrievers,
                ]
            ),
            failures=[*initial_batch.failures, *owner_graph_batch.failures],
        )

    def _unique_strings(self, values: Sequence[str]) -> list[str]:
        return list(dict.fromkeys(values))
