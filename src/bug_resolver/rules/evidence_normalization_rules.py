"""Deterministic cleanup rules for raw retrieval evidence candidates."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from bug_resolver.schemas import EvidenceCandidate


class EvidenceNormalizationRules:
    """Normalize provider output without changing its evidence identity."""

    def normalize_candidate(
        self,
        candidate: EvidenceCandidate,
    ) -> EvidenceCandidate | None:
        """Return a cleaned candidate or drop unusable defensive input."""
        content = self.normalize_content(candidate.content)
        if not content:
            return None

        metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
        candidate_data: dict[str, Any] = {
            **candidate.model_dump(),
            "content": content,
            "file_path": self.normalize_file_path(candidate.file_path),
            "matched_terms": self.normalize_matched_terms(candidate.matched_terms),
            "metadata": metadata,
        }

        try:
            return EvidenceCandidate.model_validate(candidate_data)
        except ValidationError:
            return None

    def normalize_file_path(self, file_path: str | None) -> str | None:
        """Normalize separators while preserving repo-relative path semantics."""
        if file_path is None:
            return None

        normalized_path = file_path.strip().replace("\\", "/")
        while normalized_path.startswith("./"):
            normalized_path = normalized_path[2:]
        return normalized_path or None

    def normalize_matched_terms(self, terms: list[str]) -> list[str]:
        """Trim and stably deduplicate matched terms."""
        normalized_terms: list[str] = []
        seen: set[str] = set()
        for term in terms:
            normalized_term = term.strip()
            if not normalized_term or normalized_term in seen:
                continue
            seen.add(normalized_term)
            normalized_terms.append(normalized_term)
        return normalized_terms

    def normalize_content(self, content: str) -> str:
        """Trim blank edge lines without rewriting source text."""
        lines = content.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)
