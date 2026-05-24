"""Signal expansion rules used for RCA evidence and finding selection."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

from bug_resolver.schemas import EvidenceSourceType, WorkflowState
from bug_resolver.signals.evidence_selection_signals import (
    DEFAULT_SIGNAL_PROFILES,
    DEFAULT_STOPWORDS,
    SignalProfile,
)


class EvidenceSelectionRules:
    """Builds configurable evidence-selection signals from workflow state."""

    def __init__(
        self,
        *,
        signal_profiles: Sequence[SignalProfile] = DEFAULT_SIGNAL_PROFILES,
        stopwords: Collection[str] = DEFAULT_STOPWORDS,
    ) -> None:
        self.signal_profiles = tuple(signal_profiles)
        self.stopwords = frozenset(stopwords)

    def selection_signals(self, state: WorkflowState) -> set[str]:
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
        tokens = self.tokens(combined_text)
        signals = tokens - self.stopwords

        for profile in self.signal_profiles:
            if tokens & profile.triggers:
                signals.update(profile.expansions)

        return signals

    def tokens(self, value: str) -> set[str]:
        raw_tokens = set(re.findall(r"[a-z0-9_]+", value.lower()))
        split_tokens = {
            token_part
            for token in raw_tokens
            for token_part in token.split("_")
            if token_part
        }
        return raw_tokens | split_tokens
