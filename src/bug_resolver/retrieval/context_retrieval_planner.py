"""Coordinator for deterministic context retrieval planning."""

from __future__ import annotations

from bug_resolver.rules.retrieval_planning_rules import RetrievalPlanningRules
from bug_resolver.schemas import IncidentFacts, RetrievalPlan
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable

logger = get_logger(__name__)


class ContextRetrievalPlanner:
    """Turn grounded incident facts into an executable retrieval plan."""

    def __init__(self, rules: RetrievalPlanningRules | None = None) -> None:
        self._rules = rules or RetrievalPlanningRules()

    @traceable(name="incident_driven_context.plan_retrieval", run_type="chain")
    def plan(self, facts: IncidentFacts) -> RetrievalPlan:
        """Create a plan without executing any retrieval request."""
        plan = self._rules.build_plan(facts)
        logger.info(
            "retrieval plan built incident_id=%s anchors=%s file_context=%s exact=%s "
            "structural=%s semantic=%s graph=%s kb=%s",
            facts.incident_id,
            len(plan.anchors),
            len(plan.file_context_requests),
            len(plan.exact_queries),
            len(plan.structural_queries),
            len(plan.semantic_queries),
            len(plan.graph_expansion_requests),
            len(plan.kb_queries),
        )
        log_debug_payload(
            logger,
            "retrieval plan details",
            payload=self._debug_summary(plan),
        )
        return plan

    def _debug_summary(self, plan: RetrievalPlan) -> dict[str, object]:
        safe_exact_source_hints = {
            "exception_type",
            "config_like_term",
            "log_key_term",
            "event_term",
            "candidate_symbol",
        }
        return {
            "anchor_counts": {
                anchor_type: sum(
                    anchor.anchor_type == anchor_type for anchor in plan.anchors
                )
                for anchor_type in sorted({anchor.anchor_type for anchor in plan.anchors})
            },
            "exact_queries": [
                {
                    "query": query.query,
                    "purpose": query.purpose,
                    "priority": query.priority,
                    "source_hint": query.source_hint,
                }
                for query in plan.exact_queries
                if query.source_hint in safe_exact_source_hints
            ],
            "structural_queries": [query.query for query in plan.structural_queries],
            "semantic_query_count": len(plan.semantic_queries),
            "kb_query_count": len(plan.kb_queries),
            "file_context_requests": [
                {
                    "file_path": request.file_path,
                    "line_number": request.line_number,
                }
                for request in plan.file_context_requests
            ],
            "graph_expansion_requests": [
                {
                    "file_path": request.file_path,
                    "symbol_name": request.symbol_name,
                    "line_number": request.line_number,
                    "max_depth": request.max_depth,
                }
                for request in plan.graph_expansion_requests
            ],
        }
