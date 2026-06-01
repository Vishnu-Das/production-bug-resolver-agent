"""Deterministic merge rules for overlapping retrieval evidence candidates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bug_resolver.schemas import EvidenceCandidate, RetrievalEvidenceSourceType


class EvidenceDeduplicationRules:
    """Merge corroborating evidence while preserving first-seen identity and order."""

    _SOURCE_SNIPPET_PRIORITY = {
        RetrievalEvidenceSourceType.FILE_CONTEXT: 2,
        RetrievalEvidenceSourceType.CODE_EXACT: 1,
    }

    def deduplicate(
        self,
        candidates: list[EvidenceCandidate],
    ) -> list[EvidenceCandidate]:
        """Merge duplicate candidates into the earliest compatible candidate."""
        deduplicated_candidates: list[EvidenceCandidate] = []
        for candidate in candidates:
            for index, existing_candidate in enumerate(deduplicated_candidates):
                if self.should_merge(existing_candidate, candidate):
                    deduplicated_candidates[index] = self.merge(existing_candidate, candidate)
                    break
            else:
                deduplicated_candidates.append(candidate)
        return deduplicated_candidates

    def should_merge(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> bool:
        """Return whether two candidates represent the same evidence region."""
        if first.candidate_id == second.candidate_id:
            return True

        if self._mixes_graph_and_non_graph(first, second):
            return False

        if first.file_path is not None and first.file_path == second.file_path:
            if self._ranges_overlap(first, second):
                return True
            if first.symbol_name and first.symbol_name == second.symbol_name:
                return True
            if self._has_disjoint_ranges(first, second):
                return False

        return self._content_identity(first) == self._content_identity(second)

    def merge(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> EvidenceCandidate:
        """Merge corroborating candidates into the stable first identity."""
        same_file = first.file_path is not None and first.file_path == second.file_path
        start_line = self._merged_start_line(first, second) if same_file else first.start_line
        end_line = self._merged_end_line(first, second) if same_file else first.end_line
        metadata = self._merged_metadata(first, second)

        return first.model_copy(
            update={
                "content": self._preferred_content(first, second),
                "start_line": start_line,
                "end_line": end_line,
                "symbol_name": first.symbol_name or second.symbol_name,
                "symbol_type": first.symbol_type or second.symbol_type,
                "matched_terms": self._unique_strings(
                    [*first.matched_terms, *second.matched_terms]
                ),
                "metadata": metadata,
            }
        )

    def _ranges_overlap(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> bool:
        if (
            first.start_line is None
            or first.end_line is None
            or second.start_line is None
            or second.end_line is None
        ):
            return False
        return first.start_line <= second.end_line and second.start_line <= first.end_line

    def _has_disjoint_ranges(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> bool:
        return (
            first.start_line is not None
            and first.end_line is not None
            and second.start_line is not None
            and second.end_line is not None
            and not self._ranges_overlap(first, second)
        )

    def _content_identity(self, candidate: EvidenceCandidate) -> str:
        return candidate.content.strip()

    def _merged_start_line(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> int | None:
        values = [line for line in (first.start_line, second.start_line) if line is not None]
        return min(values) if values else None

    def _merged_end_line(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> int | None:
        values = [line for line in (first.end_line, second.end_line) if line is not None]
        return max(values) if values else None

    def _preferred_content(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> str:
        preferred_source_snippet = self._preferred_source_snippet(first, second)
        if preferred_source_snippet is not None:
            return preferred_source_snippet.content
        if self._contains_range(first, second):
            return first.content
        if self._contains_range(second, first):
            return second.content
        if len(second.content) > len(first.content):
            return second.content
        return first.content

    def _mixes_graph_and_non_graph(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> bool:
        graph_type = RetrievalEvidenceSourceType.CODE_GRAPH
        return (first.source_type == graph_type) != (second.source_type == graph_type)

    def _preferred_source_snippet(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> EvidenceCandidate | None:
        first_priority = self._SOURCE_SNIPPET_PRIORITY.get(first.source_type, 0)
        second_priority = self._SOURCE_SNIPPET_PRIORITY.get(second.source_type, 0)
        if first_priority == second_priority == 0:
            return None
        if first_priority > second_priority:
            return first
        if second_priority > first_priority:
            return second
        return None

    def _contains_range(
        self,
        outer: EvidenceCandidate,
        inner: EvidenceCandidate,
    ) -> bool:
        return (
            outer.file_path is not None
            and outer.file_path == inner.file_path
            and outer.start_line is not None
            and outer.end_line is not None
            and inner.start_line is not None
            and inner.end_line is not None
            and outer.start_line <= inner.start_line
            and outer.end_line >= inner.end_line
        )

    def _merged_metadata(
        self,
        first: EvidenceCandidate,
        second: EvidenceCandidate,
    ) -> dict[str, Any]:
        metadata = {**second.metadata, **first.metadata}
        metadata["merged_candidate_ids"] = self._unique_strings(
            [
                *self._metadata_strings(first.metadata, "merged_candidate_ids"),
                first.candidate_id,
                *self._metadata_strings(second.metadata, "merged_candidate_ids"),
                second.candidate_id,
            ]
        )
        metadata["retrieved_by"] = self._unique_strings(
            [
                *self._metadata_strings(first.metadata, "retrieved_by"),
                first.retriever_name,
                *self._metadata_strings(second.metadata, "retrieved_by"),
                second.retriever_name,
            ]
        )
        metadata["source_types"] = self._unique_strings(
            [
                *self._metadata_strings(first.metadata, "source_types"),
                first.source_type.value,
                *self._metadata_strings(second.metadata, "source_types"),
                second.source_type.value,
            ]
        )
        metadata["merged_count"] = self._merged_count(first) + self._merged_count(second)
        return metadata

    def _merged_count(self, candidate: EvidenceCandidate) -> int:
        merged_count = candidate.metadata.get("merged_count")
        return merged_count if isinstance(merged_count, int) else 1

    def _metadata_strings(self, metadata: dict[str, Any], key: str) -> list[str]:
        values = metadata.get(key)
        if not isinstance(values, list):
            return []
        return [value for value in values if isinstance(value, str)]

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values
