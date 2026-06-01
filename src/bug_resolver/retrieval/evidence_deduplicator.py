"""Coordinator for deterministic retrieval evidence deduplication."""

from __future__ import annotations

from bug_resolver.rules.evidence_deduplication_rules import EvidenceDeduplicationRules
from bug_resolver.schemas import EvidenceCandidate
from bug_resolver.utils.observability import traceable


class EvidenceDeduplicator:
    """Merge duplicate and overlapping retrieval evidence candidates."""

    def __init__(self, rules: EvidenceDeduplicationRules | None = None) -> None:
        self._rules = rules or EvidenceDeduplicationRules()

    @traceable(name="incident_driven_context.deduplicate_evidence", run_type="chain")
    def deduplicate(
        self,
        candidates: list[EvidenceCandidate],
    ) -> list[EvidenceCandidate]:
        """Return deduplicated candidates in stable first-seen order."""
        return self._rules.deduplicate(candidates)
