"""Deterministic owner-file graph expansion rules."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from bug_resolver.schemas import (
    GraphExpansionRequest,
    RankedEvidence,
    RetrievalEvidenceSourceType,
)


class OwnerGraphExpansionRules:
    """Build a shallow second graph pass from ranked implementation owners."""

    _OWNER_SOURCE_TYPES = {
        RetrievalEvidenceSourceType.FILE_CONTEXT,
        RetrievalEvidenceSourceType.CODE_EXACT,
        RetrievalEvidenceSourceType.CODE_STRUCTURAL,
        RetrievalEvidenceSourceType.CODE_SEMANTIC,
    }
    _CODE_SUFFIXES = {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".scala",
        ".swift",
        ".ts",
        ".tsx",
    }
    _NOISY_PATH_PARTS = {
        "demo",
        "eval",
        "example",
        "examples",
        "notebooks",
        "scripts",
        "test",
        "tests",
    }

    def build_requests(
        self,
        ranked_evidence: Iterable[RankedEvidence],
        *,
        existing_requests: Iterable[GraphExpansionRequest] = (),
        max_requests: int = 3,
        minimum_score: float = 0.35,
    ) -> list[GraphExpansionRequest]:
        """Return bounded owner-file requests not already covered by the plan."""
        if max_requests < 1:
            raise ValueError("max_requests must be greater than zero")
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("minimum_score must be between zero and one")

        existing_paths = {
            self._normalized_path(request.file_path)
            for request in existing_requests
            if request.file_path
        }
        requests: list[GraphExpansionRequest] = []
        seen_paths = set(existing_paths)
        for evidence in ranked_evidence:
            candidate = evidence.candidate
            file_path = candidate.file_path
            if (
                evidence.score.final_score < minimum_score
                or candidate.source_type not in self._OWNER_SOURCE_TYPES
                or not file_path
                or not self._is_code_file(file_path)
            ):
                continue

            normalized_path = self._normalized_path(file_path)
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            requests.append(
                GraphExpansionRequest(
                    file_path=file_path,
                    symbol_name=candidate.symbol_name,
                    line_number=candidate.start_line,
                    max_depth=1,
                    reason=f"Expand graph context from ranked implementation owner {file_path}",
                )
            )
            if len(requests) >= max_requests:
                break

        return requests

    def _is_code_file(self, file_path: str) -> bool:
        normalized_path = self._normalized_path(file_path)
        path = PurePosixPath(normalized_path)
        return (
            path.suffix.casefold() in self._CODE_SUFFIXES
            and not set(path.parts) & self._NOISY_PATH_PARTS
        )

    def _normalized_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").removeprefix("./").casefold()
