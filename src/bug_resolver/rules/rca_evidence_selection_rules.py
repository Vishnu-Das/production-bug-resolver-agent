"""Focused RCA evidence selection rules."""

from __future__ import annotations

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
from bug_resolver.rules.evidence_formatting_rules import EvidenceFormattingRules
from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, WorkflowState


class RCAEvidenceSelectionRules:
    """Select the strongest evidence IDs and findings for RCA prose."""

    def __init__(
        self,
        evidence_selection_rules: EvidenceSelectionRules | None = None,
        code_path_rules: CodeEvidencePathRules | None = None,
        formatter: EvidenceFormattingRules | None = None,
    ) -> None:
        self.evidence_selection_rules = evidence_selection_rules or EvidenceSelectionRules()
        self.code_path_rules = code_path_rules or CodeEvidencePathRules()
        self.formatter = formatter or EvidenceFormattingRules()

    def evidence_ids(self, state: WorkflowState) -> list[str]:
        selected_evidence = [
            *self.evidence_for_source(state, EvidenceSourceType.LOG),
            *self.selected_evidence_for_source(state, EvidenceSourceType.CODE, max_items=3),
            *self.selected_evidence_for_source(state, EvidenceSourceType.GRAPH, max_items=2),
            *self.selected_evidence_for_source(
                state,
                EvidenceSourceType.KNOWLEDGE_BASE,
                max_items=2,
            ),
        ]

        evidence_ids = self.formatter.unique(
            [evidence.evidence_id for evidence in selected_evidence]
        )
        if evidence_ids:
            return evidence_ids

        return [evidence.evidence_id for evidence in state.evidence_items]

    def selected_evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
        *,
        max_items: int,
    ) -> list[EvidenceItem]:
        evidence_items = self.evidence_for_source(state, source_type)
        if len(evidence_items) <= 1:
            return evidence_items

        signals = self.evidence_selection_rules.selection_signals(state)
        if not signals:
            return evidence_items

        scored_items = [
            (
                self.evidence_relevance_score(evidence, signals),
                self.evidence_signal_score(evidence, signals),
                evidence,
            )
            for evidence in evidence_items
        ]
        strongest_signal_score = max(signal_score for _, signal_score, _ in scored_items)

        if strongest_signal_score <= 0:
            return evidence_items

        signal_ratio = 0.65 if source_type == EvidenceSourceType.KNOWLEDGE_BASE else 0.5
        minimum_signal_score = max(1.0, strongest_signal_score * signal_ratio)
        ranked_items = sorted(
            scored_items,
            key=lambda item: (
                item[0],
                item[1],
                item[2].relevance_score or 0.0,
                self.formatter.display_path(item[2].file_path or item[2].source_name).lower(),
                item[2].line_start or 0,
                item[2].evidence_id,
            ),
            reverse=True,
        )
        selected_items = [
            evidence
            for score, signal_score, evidence in ranked_items
            if score > 0 and signal_score >= minimum_signal_score
        ][:max_items]

        if not selected_items:
            return evidence_items

        if source_type in {EvidenceSourceType.CODE, EvidenceSourceType.GRAPH}:
            return self._prefer_primary_code_evidence(selected_items, signals)

        return selected_items

    def evidence_for_source(
        self,
        state: WorkflowState,
        source_type: EvidenceSourceType,
    ) -> list[EvidenceItem]:
        return [
            evidence for evidence in state.evidence_items if evidence.source_type == source_type
        ]

    def evidence_relevance_score(
        self,
        evidence: EvidenceItem,
        signals: set[str],
    ) -> float:
        score = self.evidence_signal_score(evidence, signals)
        score += (evidence.relevance_score or 0.0) * 0.5

        if evidence.source_type == EvidenceSourceType.CODE:
            score += self._code_finding_penalty(
                self.formatter.display_path(evidence.file_path or evidence.source_name).lower(),
                signals,
            )
        if evidence.source_type == EvidenceSourceType.GRAPH:
            score += self._graph_finding_penalty(
                self.formatter.display_path(evidence.file_path or evidence.source_name).lower(),
                signals,
            )

        return score

    def evidence_signal_score(
        self,
        evidence: EvidenceItem,
        signals: set[str],
    ) -> float:
        path = self.formatter.display_path(evidence.file_path or evidence.source_name).lower()
        path_source_tokens = self.evidence_selection_rules.tokens(
            f"{path} {evidence.source_name}"
        )
        content_tokens = self.evidence_selection_rules.tokens(
            " ".join(
                [
                    evidence.content,
                    *evidence.metadata.values(),
                ]
            )
        )

        path_score = len(path_source_tokens & signals) * 3.0
        content_score = min(len(content_tokens & signals), 10) * 1.0

        return path_score + content_score

    def _prefer_primary_code_evidence(
        self,
        evidence_items: list[EvidenceItem],
        signals: set[str],
    ) -> list[EvidenceItem]:
        primary_items = [
            evidence
            for evidence in evidence_items
            if self.code_path_rules.is_allowed_support_path(
                self.formatter.display_path(evidence.file_path or evidence.source_name).lower(),
                signals,
            )
        ]

        return primary_items or evidence_items

    def _code_finding_penalty(self, path: str, signals: set[str]) -> float:
        penalty = 0.0

        penalty += self.code_path_rules.support_adjustment(
            path,
            signals,
            penalty=-2.0,
            mention_bonus=0.5,
        )

        if path.endswith("__init__.py"):
            penalty -= 2.0
        if path.endswith((".json", ".yml", ".yaml", ".md")):
            penalty -= 1.5

        return penalty

    def _graph_finding_penalty(self, path: str, signals: set[str]) -> float:
        penalty = 0.0

        penalty += self.code_path_rules.support_adjustment(
            path,
            signals,
            penalty=-8.0,
            mention_bonus=0.5,
        )

        if path.startswith("src/"):
            penalty += 2.0
        if path.endswith("__init__.py"):
            penalty -= 2.0

        return penalty
