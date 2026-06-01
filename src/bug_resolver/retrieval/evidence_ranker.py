"""Coordinator for deterministic retrieval evidence scoring and ranking."""

from __future__ import annotations

from bug_resolver.rules.evidence_scoring_rules import EvidenceScoringRules
from bug_resolver.rules.ranked_evidence_selection_rules import (
    RankedEvidenceSelectionRules,
)
from bug_resolver.schemas import (
    EvidenceCandidate,
    IncidentFacts,
    RankedEvidence,
    RetrievalEvidenceEvaluationResult,
    RetrievalEvidenceSourceType,
)
from bug_resolver.utils.observability import traceable


class EvidenceRanker:
    """Rank retrieval evidence and summarize whether it is sufficient for RCA."""

    _DIRECT_CODE_TYPES = {
        RetrievalEvidenceSourceType.FILE_CONTEXT,
        RetrievalEvidenceSourceType.CODE_EXACT,
        RetrievalEvidenceSourceType.CODE_STRUCTURAL,
        RetrievalEvidenceSourceType.CODE_GRAPH,
    }

    def __init__(
        self,
        scoring_rules: EvidenceScoringRules | None = None,
        selection_rules: RankedEvidenceSelectionRules | None = None,
    ) -> None:
        self._scoring_rules = scoring_rules or EvidenceScoringRules()
        self._selection_rules = selection_rules or RankedEvidenceSelectionRules()

    def rank(
        self,
        candidates: list[EvidenceCandidate],
        facts: IncidentFacts,
    ) -> list[RankedEvidence]:
        """Score and rank candidates by descending final score with stable ties."""
        scored_candidates = [
            (
                index,
                candidate,
                self._scoring_rules.score_candidate(
                    candidate,
                    facts,
                    all_candidates=candidates,
                ),
            )
            for index, candidate in enumerate(candidates)
        ]
        scored_candidates.sort(key=lambda item: (-item[2].final_score, item[0]))

        return [
            RankedEvidence(
                candidate=candidate,
                score=score,
                rank=rank,
                supporting_candidate_ids=self._supporting_candidate_ids(candidate),
            )
            for rank, (_, candidate, score) in enumerate(scored_candidates, start=1)
        ]

    @traceable(name="incident_driven_context.rank_evidence", run_type="chain")
    def evaluate(
        self,
        candidates: list[EvidenceCandidate],
        facts: IncidentFacts,
        *,
        max_selected: int = 8,
        minimum_score: float = 0.35,
    ) -> RetrievalEvidenceEvaluationResult:
        """Select strong evidence and summarize remaining evidence gaps."""
        if max_selected < 1:
            raise ValueError("max_selected must be greater than zero")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("minimum_score must be between zero and one")

        ranked_evidence = self.rank(candidates, facts)
        selected_evidence = self._selection_rules.select(
            ranked_evidence,
            max_selected=max_selected,
            minimum_score=minimum_score,
        )
        selected_source_types = {
            evidence.candidate.source_type for evidence in selected_evidence
        }
        has_runtime_evidence = RetrievalEvidenceSourceType.LOG in selected_source_types
        has_direct_code_evidence = bool(selected_source_types & self._DIRECT_CODE_TYPES)
        has_supporting_kb_evidence = (
            RetrievalEvidenceSourceType.KNOWLEDGE_BASE in selected_source_types
        )
        has_graph_support = RetrievalEvidenceSourceType.CODE_GRAPH in selected_source_types
        sufficient_for_rca = bool(selected_evidence) and (
            has_runtime_evidence or has_direct_code_evidence
        )
        missing_evidence = self._missing_evidence(
            selected_evidence,
            has_runtime_evidence=has_runtime_evidence,
            has_direct_code_evidence=has_direct_code_evidence,
        )
        warnings = self._warnings(selected_evidence, sufficient_for_rca=sufficient_for_rca)

        return RetrievalEvidenceEvaluationResult(
            ranked_evidence=ranked_evidence,
            selected_evidence=selected_evidence,
            has_runtime_evidence=has_runtime_evidence,
            has_direct_code_evidence=has_direct_code_evidence,
            has_supporting_kb_evidence=has_supporting_kb_evidence,
            has_graph_support=has_graph_support,
            sufficient_for_rca=sufficient_for_rca,
            confidence=self._confidence(selected_evidence),
            missing_evidence=missing_evidence,
            warnings=warnings,
        )

    def _supporting_candidate_ids(self, candidate: EvidenceCandidate) -> list[str]:
        values = candidate.metadata.get("merged_candidate_ids")
        if not isinstance(values, list):
            return []
        return [
            value
            for value in values
            if isinstance(value, str) and value != candidate.candidate_id
        ]

    def _missing_evidence(
        self,
        selected_evidence: list[RankedEvidence],
        *,
        has_runtime_evidence: bool,
        has_direct_code_evidence: bool,
    ) -> list[str]:
        missing_evidence: list[str] = []
        if not has_direct_code_evidence:
            missing_evidence.append("No direct code evidence selected")
        if not has_runtime_evidence:
            missing_evidence.append("No runtime/log evidence selected")
        if selected_evidence and all(
            evidence.candidate.source_type == RetrievalEvidenceSourceType.CODE_SEMANTIC
            for evidence in selected_evidence
        ):
            missing_evidence.append("Only weak semantic evidence selected")
        return missing_evidence

    def _warnings(
        self,
        selected_evidence: list[RankedEvidence],
        *,
        sufficient_for_rca: bool,
    ) -> list[str]:
        warnings: list[str] = []
        if not selected_evidence:
            warnings.append("No evidence met the minimum selection score")
        elif len(selected_evidence) == 1:
            warnings.append("Selected evidence is thin; corroborating context is recommended")
        if selected_evidence and selected_evidence[0].score.final_score < 0.50:
            warnings.append("Selected evidence has low deterministic confidence")
        if not sufficient_for_rca:
            warnings.append("Evidence is insufficient for RCA")
        return warnings

    def _confidence(self, selected_evidence: list[RankedEvidence]) -> float:
        if not selected_evidence:
            return 0.0
        top_scores = [evidence.score.final_score for evidence in selected_evidence[:3]]
        return max(0.0, min(1.0, sum(top_scores) / len(top_scores)))
