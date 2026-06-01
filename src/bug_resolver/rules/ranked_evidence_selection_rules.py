"""Deterministic selection rules for ranked retrieval evidence."""

from __future__ import annotations

from bug_resolver.schemas import RankedEvidence, RetrievalEvidenceSourceType


class RankedEvidenceSelectionRules:
    """Select strong evidence while retaining useful structural corroboration."""

    _DIRECT_SOURCE_TYPES = {
        RetrievalEvidenceSourceType.FILE_CONTEXT,
        RetrievalEvidenceSourceType.CODE_EXACT,
    }
    _REPLACEABLE_SUPPORT_TYPES = {
        RetrievalEvidenceSourceType.CODE_SEMANTIC,
        RetrievalEvidenceSourceType.KNOWLEDGE_BASE,
    }

    def select(
        self,
        ranked_evidence: list[RankedEvidence],
        *,
        max_selected: int,
        minimum_score: float,
    ) -> list[RankedEvidence]:
        """Return bounded evidence with graph support when it can replace weaker context."""
        eligible_evidence = [
            evidence
            for evidence in ranked_evidence
            if evidence.score.final_score >= minimum_score
        ]
        selected_evidence = eligible_evidence[:max_selected]
        graph_evidence = self._preferred_graph_evidence(
            ranked_evidence=ranked_evidence,
            eligible_evidence=eligible_evidence,
        )
        if graph_evidence is None:
            return selected_evidence

        selected_graph_evidence = next(
            (
                evidence
                for evidence in selected_evidence
                if evidence.candidate.source_type
                == RetrievalEvidenceSourceType.CODE_GRAPH
            ),
            None,
        )
        if selected_graph_evidence is not None:
            if selected_graph_evidence.candidate.candidate_id == graph_evidence.candidate.candidate_id:
                return selected_evidence
            return self._rank_order(
                [
                    evidence
                    for evidence in selected_evidence
                    if evidence.candidate.candidate_id
                    != selected_graph_evidence.candidate.candidate_id
                ]
                + [graph_evidence]
            )

        if len(selected_evidence) < max_selected:
            return self._rank_order([*selected_evidence, graph_evidence])

        replaceable_evidence = [
            evidence
            for evidence in selected_evidence
            if evidence.candidate.source_type in self._REPLACEABLE_SUPPORT_TYPES
        ]
        if not replaceable_evidence:
            return selected_evidence

        replaced_evidence = replaceable_evidence[-1]
        return self._rank_order(
            [
                evidence
                for evidence in selected_evidence
                if evidence.candidate.candidate_id
                != replaced_evidence.candidate.candidate_id
            ]
            + [graph_evidence]
        )

    def _preferred_graph_evidence(
        self,
        *,
        ranked_evidence: list[RankedEvidence],
        eligible_evidence: list[RankedEvidence],
    ) -> RankedEvidence | None:
        owner_paths = {
            self._normalized_path(evidence.candidate.file_path)
            for evidence in eligible_evidence
            if evidence.candidate.source_type in self._DIRECT_SOURCE_TYPES
            and evidence.candidate.file_path
        }
        owner_graph_evidence = [
            evidence
            for evidence in ranked_evidence
            if evidence.candidate.source_type == RetrievalEvidenceSourceType.CODE_GRAPH
            and self._normalized_path(evidence.candidate.file_path) in owner_paths
        ]
        if owner_graph_evidence:
            return owner_graph_evidence[0]

        return next(
            (
                evidence
                for evidence in eligible_evidence
                if evidence.candidate.source_type
                == RetrievalEvidenceSourceType.CODE_GRAPH
            ),
            None,
        )

    def _normalized_path(self, path: str | None) -> str:
        return (path or "").replace("\\", "/").lower()

    def _rank_order(self, evidence_items: list[RankedEvidence]) -> list[RankedEvidence]:
        return sorted(evidence_items, key=lambda evidence: evidence.rank)
