"""Incident-term extraction rules used for evidence ranking and RCA selection."""

from __future__ import annotations

import re
from collections.abc import Collection

from bug_resolver.schemas import EvidenceSourceType, WorkflowState


DEFAULT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "service",
        "that",
        "the",
        "this",
        "to",
        "with",
    }
)


class EvidenceSelectionRules:
    """Build incident-grounded terms from workflow state."""

    def __init__(
        self,
        *,
        stopwords: Collection[str] = DEFAULT_STOPWORDS,
    ) -> None:
        self.stopwords = frozenset(stopwords)

    def selection_terms(self, state: WorkflowState) -> set[str]:
        values = [
            state.incident.title,
            state.incident.description,
            state.incident.affected_service or "",
            state.incident.affected_area or "",
            *state.incident.metadata.values(),
        ]
        values.extend(
            evidence.content
            for evidence in state.evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        )

        if state.evidence_evaluation is not None:
            values.append(state.evidence_evaluation.reason)
            values.extend(state.evidence_evaluation.missing_evidence)

        combined_text = "\n".join(value for value in values if value).lower()
        return self.tokens(combined_text) - self.stopwords

    def tokens(self, value: str) -> set[str]:
        raw_tokens = set(re.findall(r"[a-z0-9_]+", value.lower()))
        split_tokens = {
            token_part
            for token in raw_tokens
            for token_part in token.split("_")
            if token_part
        }
        return raw_tokens | split_tokens
