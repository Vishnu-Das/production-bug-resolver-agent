"""Repo-agnostic deterministic scoring rules for retrieval evidence candidates."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from bug_resolver.schemas import (
    EvidenceCandidate,
    EvidenceScoreBreakdown,
    IncidentFacts,
    RetrievalEvidenceSourceType,
    StackFrame,
)


class EvidenceScoringRules:
    """Score retrieval evidence using incident-grounded, repo-agnostic features."""

    _SOURCE_STRENGTH = {
        RetrievalEvidenceSourceType.LOG: 0.90,
        RetrievalEvidenceSourceType.FILE_CONTEXT: 0.85,
        RetrievalEvidenceSourceType.CODE_EXACT: 0.75,
        RetrievalEvidenceSourceType.CODE_STRUCTURAL: 0.70,
        RetrievalEvidenceSourceType.CODE_GRAPH: 0.65,
        RetrievalEvidenceSourceType.CODE_SEMANTIC: 0.45,
        RetrievalEvidenceSourceType.KNOWLEDGE_BASE: 0.40,
    }
    _NOISY_PATH_PARTS = {
        "tests",
        "test",
        "eval",
        "examples",
        "example",
        "demo",
        "notebooks",
        "scripts",
        "debug",
        "inspector",
        "__pycache__",
        ".venv",
        "node_modules",
    }
    _SUPPORT_CONTEXT_TERMS = {
        "test",
        "tests",
        "testing",
        "eval",
        "evaluation",
        "example",
        "examples",
        "demo",
        "debug",
        "inspector",
        "notebook",
        "notebooks",
        "script",
        "scripts",
    }

    def score_candidate(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        *,
        all_candidates: list[EvidenceCandidate] | None = None,
    ) -> EvidenceScoreBreakdown:
        """Return a bounded score breakdown for one evidence candidate."""
        reasons: list[str] = []
        source_strength = self._SOURCE_STRENGTH[candidate.source_type]
        reasons.append(
            f"Source type {candidate.source_type.value} has "
            f"{self._strength_label(source_strength)} source strength"
        )

        directness = self._directness(candidate, facts, reasons)
        incident_term_overlap = self._incident_term_overlap(candidate, facts)
        if incident_term_overlap > 0.0:
            reasons.append("Candidate overlaps incident-grounded terms")

        exact_error_match = self._exact_error_match(candidate, facts, reasons)
        file_path_match = self._file_path_match(candidate, facts, reasons)
        symbol_match = self._symbol_match(candidate, facts, reasons)
        stack_trace_proximity = self._stack_trace_proximity(candidate, facts, reasons)
        line_proximity = self._line_proximity(candidate, facts, reasons)
        graph_distance_score = self._graph_distance_score(candidate, reasons)
        multi_source_agreement = self._multi_source_agreement(candidate, reasons)
        recency_relevance = self._recency_relevance(candidate, reasons)
        semantic_only_penalty = self._semantic_only_penalty(
            candidate,
            incident_term_overlap,
            multi_source_agreement,
            reasons,
        )
        noise_penalty = self._noise_penalty(candidate, facts, reasons)

        positive_score = (
            0.20 * source_strength
            + 0.25 * directness
            + 0.15 * incident_term_overlap
            + 0.15 * exact_error_match
            + 0.10 * file_path_match
            + 0.10 * symbol_match
            + 0.10 * stack_trace_proximity
            + 0.05 * line_proximity
            + 0.05 * graph_distance_score
            + 0.05 * multi_source_agreement
            + 0.05 * recency_relevance
        )
        final_score = self._clamp(
            positive_score - 0.10 * semantic_only_penalty - 0.10 * noise_penalty
        )

        return EvidenceScoreBreakdown(
            source_strength=source_strength,
            directness=directness,
            incident_term_overlap=incident_term_overlap,
            exact_error_match=exact_error_match,
            file_path_match=file_path_match,
            symbol_match=symbol_match,
            stack_trace_proximity=stack_trace_proximity,
            line_proximity=line_proximity,
            graph_distance_score=graph_distance_score,
            multi_source_agreement=multi_source_agreement,
            recency_relevance=recency_relevance,
            semantic_only_penalty=semantic_only_penalty,
            noise_penalty=noise_penalty,
            final_score=final_score,
            reasons=reasons,
        )

    def _directness(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        candidate_text = self._candidate_text(candidate)
        direct_values = [
            *facts.exception_types,
            *facts.config_like_terms,
            *facts.log_key_terms,
            *facts.event_terms,
            *facts.candidate_symbols,
            *facts.quoted_terms,
            *(str(code) for code in facts.status_codes),
        ]
        matches = self._matching_values(candidate_text, direct_values)
        if matches:
            reasons.append(f"Candidate directly contains incident term {matches[0]}")
        structured_matches = self._matching_values(
            candidate_text,
            [*facts.log_key_terms, *facts.event_terms],
        )
        if structured_matches:
            reasons.append(
                f"Candidate contains structured runtime anchor {structured_matches[0]}"
            )
            return min(1.0, 0.70 + 0.30 * (len(structured_matches) - 1))
        return self._fraction(len(matches), len(self._unique_strings(direct_values)))

    def _incident_term_overlap(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
    ) -> float:
        incident_tokens = self._incident_tokens(facts)
        if not incident_tokens:
            return 0.0
        candidate_tokens = self._tokens(self._candidate_text(candidate))
        overlap = self._fraction(len(candidate_tokens & incident_tokens), len(incident_tokens))
        structured_matches = self._matching_values(
            self._candidate_text(candidate),
            [*facts.log_key_terms, *facts.event_terms],
        )
        structured_overlap = (
            min(1.0, 0.60 + 0.15 * (len(structured_matches) - 1))
            if structured_matches
            else 0.0
        )
        return max(overlap, structured_overlap)

    def _exact_error_match(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        values = [*facts.exception_types, *facts.error_terms]
        matches = self._matching_values(self._candidate_text(candidate), values)
        if matches:
            reasons.append(f"Candidate contains error term {matches[0]}")
        return 1.0 if matches else 0.0

    def _file_path_match(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        if candidate.file_path is None:
            return 0.0
        for frame in facts.stack_frames:
            if self._normalized_path(candidate.file_path) == self._normalized_path(frame.file_path):
                reasons.append(f"Candidate file matches stack trace file {frame.file_path}")
                return 1.0
        return 0.0

    def _symbol_match(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        symbols = self._unique_strings(
            [
                *facts.candidate_symbols,
                *(frame.function_name for frame in facts.stack_frames if frame.function_name),
                *(frame.class_name for frame in facts.stack_frames if frame.class_name),
            ]
        )
        matches = self._matching_values(self._candidate_text(candidate), symbols)
        if matches:
            reasons.append(f"Candidate contains incident symbol {matches[0]}")
            return 1.0
        return 0.0

    def _stack_trace_proximity(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        matching_frames = self._matching_stack_frames(candidate, facts)
        if not matching_frames:
            return 0.0

        for frame in matching_frames:
            if frame.line_number is not None and self._contains_line(candidate, frame.line_number):
                reasons.append(f"Candidate line range contains stack trace line {frame.line_number}")
                return 1.0
        return 0.65

    def _line_proximity(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        distances = [
            self._distance_to_range(candidate, frame.line_number)
            for frame in self._matching_stack_frames(candidate, facts)
            if frame.line_number is not None
        ]
        if not distances:
            return 0.0

        minimum_distance = min(distances)
        if minimum_distance == 0:
            reasons.append("Candidate is at the stack trace line")
            return 1.0
        if minimum_distance <= 20:
            reasons.append("Candidate is within 20 lines of the stack trace")
            return 0.65
        if minimum_distance <= 50:
            reasons.append("Candidate is within 50 lines of the stack trace")
            return 0.35
        return 0.0

    def _graph_distance_score(
        self,
        candidate: EvidenceCandidate,
        reasons: list[str],
    ) -> float:
        graph_distance = self._metadata_int(candidate.metadata, "graph_distance")
        if graph_distance is None:
            return 0.0
        if graph_distance <= 0:
            score = 1.0
        elif graph_distance == 1:
            score = 0.80
        elif graph_distance == 2:
            score = 0.55
        else:
            score = 0.20
        reasons.append(f"Candidate graph distance is {graph_distance}")
        return score

    def _multi_source_agreement(
        self,
        candidate: EvidenceCandidate,
        reasons: list[str],
    ) -> float:
        retrieved_by = self._metadata_strings(candidate.metadata, "retrieved_by")
        source_types = self._metadata_strings(candidate.metadata, "source_types")
        agreement_count = max(len(set(retrieved_by)), len(set(source_types)))
        if agreement_count <= 1:
            return 0.0

        reasons.append("Candidate was retrieved by multiple sources")
        return min(1.0, 0.35 * (agreement_count - 1))

    def _recency_relevance(
        self,
        candidate: EvidenceCandidate,
        reasons: list[str],
    ) -> float:
        raw_value = candidate.metadata.get("recency_relevance")
        if not isinstance(raw_value, (int, float)):
            return 0.0
        score = self._clamp(float(raw_value))
        if score > 0.0:
            reasons.append("Candidate metadata indicates recent change relevance")
        return score

    def _semantic_only_penalty(
        self,
        candidate: EvidenceCandidate,
        incident_term_overlap: float,
        multi_source_agreement: float,
        reasons: list[str],
    ) -> float:
        if (
            candidate.source_type == RetrievalEvidenceSourceType.CODE_SEMANTIC
            and incident_term_overlap == 0.0
            and multi_source_agreement == 0.0
        ):
            reasons.append("Semantic-only candidate has weak incident overlap")
            return 1.0
        return 0.0

    def _noise_penalty(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
        reasons: list[str],
    ) -> float:
        path_parts = set(self._normalized_path(candidate.file_path or "").split("/"))
        if not path_parts & self._NOISY_PATH_PARTS:
            return 0.0
        if self._incident_tokens(facts) & self._SUPPORT_CONTEXT_TERMS:
            return 0.0

        reasons.append("Candidate path appears to be test/eval/demo/debug support context")
        return 1.0

    def _candidate_text(self, candidate: EvidenceCandidate) -> str:
        return " ".join(
            value
            for value in [
                candidate.content,
                candidate.file_path or "",
                candidate.symbol_name or "",
                *candidate.matched_terms,
            ]
            if value
        )

    def _incident_tokens(self, facts: IncidentFacts) -> set[str]:
        return self._tokens(
            " ".join(
                value
                for value in [
                    facts.summary,
                    facts.description or "",
                    *facts.error_terms,
                    *facts.exception_types,
                    *facts.candidate_symbols,
                    *facts.quoted_terms,
                    *facts.config_like_terms,
                    *facts.log_key_terms,
                    *facts.event_terms,
                ]
                if value
            )
        )

    def _tokens(self, value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[A-Za-z0-9_]+", value.casefold())
            if len(token) >= 3
        }

    def _matching_values(self, text: str, values: Iterable[str]) -> list[str]:
        normalized_text = text.casefold()
        return [
            value
            for value in self._unique_strings(values)
            if value and value.casefold() in normalized_text
        ]

    def _matching_stack_frames(
        self,
        candidate: EvidenceCandidate,
        facts: IncidentFacts,
    ) -> list[StackFrame]:
        if candidate.file_path is None:
            return []
        candidate_path = self._normalized_path(candidate.file_path)
        return [
            frame
            for frame in facts.stack_frames
            if candidate_path == self._normalized_path(frame.file_path)
        ]

    def _contains_line(self, candidate: EvidenceCandidate, line_number: int) -> bool:
        return (
            candidate.start_line is not None
            and candidate.end_line is not None
            and candidate.start_line <= line_number <= candidate.end_line
        )

    def _distance_to_range(self, candidate: EvidenceCandidate, line_number: int) -> int:
        if candidate.start_line is None or candidate.end_line is None:
            return 1_000_000
        if self._contains_line(candidate, line_number):
            return 0
        return min(abs(candidate.start_line - line_number), abs(candidate.end_line - line_number))

    def _normalized_path(self, value: str) -> str:
        return value.replace("\\", "/").removeprefix("./").casefold()

    def _metadata_int(self, metadata: dict[str, Any], key: str) -> int | None:
        value = metadata.get(key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    def _metadata_strings(self, metadata: dict[str, Any], key: str) -> list[str]:
        values = metadata.get(key)
        if not isinstance(values, list):
            return []
        return [value for value in values if isinstance(value, str)]

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen:
                continue
            seen.add(normalized_value)
            unique_values.append(normalized_value)
        return unique_values

    def _fraction(self, numerator: int, denominator: int) -> float:
        if denominator == 0:
            return 0.0
        return min(1.0, numerator / denominator)

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, value))

    def _strength_label(self, source_strength: float) -> str:
        if source_strength >= 0.75:
            return "strong"
        if source_strength >= 0.60:
            return "moderate"
        return "supporting"
