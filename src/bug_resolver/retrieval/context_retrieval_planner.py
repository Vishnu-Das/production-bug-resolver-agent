"""Coordinator for deterministic context retrieval planning."""

from __future__ import annotations

from bug_resolver.rules.retrieval_planning_rules import RetrievalPlanningRules
from bug_resolver.schemas import IncidentFacts, RetrievalPlan


class ContextRetrievalPlanner:
    """Turn grounded incident facts into an executable retrieval plan."""

    def __init__(self, rules: RetrievalPlanningRules | None = None) -> None:
        self._rules = rules or RetrievalPlanningRules()

    def plan(self, facts: IncidentFacts) -> RetrievalPlan:
        """Create a plan without executing any retrieval request."""
        return self._rules.build_plan(facts)
