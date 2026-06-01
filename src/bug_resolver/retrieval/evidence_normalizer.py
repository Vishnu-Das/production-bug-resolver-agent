"""Coordinator for deterministic retrieval evidence normalization."""

from __future__ import annotations

from bug_resolver.rules.evidence_normalization_rules import EvidenceNormalizationRules
from bug_resolver.schemas import EvidenceCandidate
from bug_resolver.utils.observability import traceable


class EvidenceNormalizer:
    """Apply defensive cleanup to raw provider evidence."""

    def __init__(self, rules: EvidenceNormalizationRules | None = None) -> None:
        self._rules = rules or EvidenceNormalizationRules()

    @traceable(name="incident_driven_context.normalize_evidence", run_type="chain")
    def normalize(
        self,
        candidates: list[EvidenceCandidate],
    ) -> list[EvidenceCandidate]:
        """Return valid normalized candidates in first-seen order."""
        normalized_candidates: list[EvidenceCandidate] = []
        for candidate in candidates:
            normalized_candidate = self._rules.normalize_candidate(candidate)
            if normalized_candidate is not None:
                normalized_candidates.append(normalized_candidate)
        return normalized_candidates
