"""Local exact text search provider for incident-grounded repository queries."""

from __future__ import annotations

import hashlib
from pathlib import Path

from bug_resolver.providers.retrieval.base import ExactSearchProvider
from bug_resolver.schemas import (
    EvidenceCandidate,
    RetrievalEvidenceSourceType,
    RetrievalQuery,
)
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class LocalExactSearchProvider(ExactSearchProvider):
    """Search repository text files for bounded, case-insensitive exact matches."""

    _EXCLUDED_DIRECTORY_NAMES = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "storage",
        "reports",
    }

    def __init__(
        self,
        repo_path: Path | str,
        *,
        retriever_name: str = "exact_search",
        max_file_size_bytes: int = 1_000_000,
        context_before_lines: int = 3,
        context_after_lines: int = 3,
        max_results_per_query: int = 20,
        max_total_results: int = 100,
    ) -> None:
        if max_file_size_bytes < 1:
            raise ValueError("max_file_size_bytes must be greater than zero")
        if context_before_lines < 0 or context_after_lines < 0:
            raise ValueError("context line counts must not be negative")
        if max_results_per_query < 1 or max_total_results < 1:
            raise ValueError("result limits must be greater than zero")

        self._repo_path = Path(repo_path).resolve()
        self._retriever_name = retriever_name
        self._max_file_size_bytes = max_file_size_bytes
        self._context_before_lines = context_before_lines
        self._context_after_lines = context_after_lines
        self._max_results_per_query = max_results_per_query
        self._max_total_results = max_total_results

    @traceable(name="exact_search.search_exact", run_type="retriever")
    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Return raw exact-match candidates without scoring or ranking them."""
        if not self._repo_path.is_dir():
            return []

        candidates: list[EvidenceCandidate] = []
        seen_candidates: set[tuple[str, int, int, str]] = set()
        files = self._text_files()

        for query in self._deduplicate_queries(queries):
            query_result_count = 0
            normalized_query = query.query.casefold()

            for file_path, lines in files:
                for match_line, line in enumerate(lines, start=1):
                    if normalized_query not in line.casefold():
                        continue

                    start_line = max(1, match_line - self._context_before_lines)
                    end_line = min(len(lines), match_line + self._context_after_lines)
                    relative_path = file_path.relative_to(self._repo_path).as_posix()
                    candidate_key = (relative_path, start_line, end_line, query.query)
                    if candidate_key in seen_candidates:
                        continue
                    seen_candidates.add(candidate_key)

                    candidates.append(
                        EvidenceCandidate(
                            candidate_id=self._candidate_id(
                                relative_path,
                                start_line,
                                end_line,
                                query.query,
                            ),
                            source_type=RetrievalEvidenceSourceType.CODE_EXACT,
                            retriever_name=self._retriever_name,
                            content=self._snippet(lines, start_line, end_line),
                            file_path=relative_path,
                            start_line=start_line,
                            end_line=end_line,
                            matched_terms=[query.query],
                            retrieval_query=query.query,
                            metadata=self._metadata(query, match_line),
                        )
                    )
                    query_result_count += 1
                    if len(candidates) >= self._max_total_results:
                        return candidates
                    if query_result_count >= self._max_results_per_query:
                        break
                if query_result_count >= self._max_results_per_query:
                    break

        return candidates

    def _text_files(self) -> list[tuple[Path, list[str]]]:
        text_files: list[tuple[Path, list[str]]] = []
        for file_path in sorted(self._repo_path.rglob("*")):
            if self._should_skip(file_path):
                continue

            try:
                raw_content = file_path.read_bytes()
            except OSError as error:
                logger.warning("exact search failed to read file_path=%s error=%s", file_path, error)
                continue

            if self._is_likely_binary(raw_content):
                continue

            content = raw_content.decode("utf-8", errors="replace")
            text_files.append((file_path, content.splitlines()))

        return text_files

    def _should_skip(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return True
        if any(part in self._EXCLUDED_DIRECTORY_NAMES for part in file_path.parts):
            return True
        try:
            return file_path.stat().st_size > self._max_file_size_bytes
        except OSError:
            return True

    def _is_likely_binary(self, content: bytes) -> bool:
        if not content:
            return False
        if b"\x00" in content:
            return True

        sample = content[:4096]
        control_characters = sum(
            byte < 32 and byte not in {9, 10, 13}
            for byte in sample
        )
        return control_characters / len(sample) > 0.05

    def _deduplicate_queries(self, queries: list[RetrievalQuery]) -> list[RetrievalQuery]:
        unique_queries: list[RetrievalQuery] = []
        seen: set[str] = set()
        for query in queries:
            normalized_query = query.query.strip().casefold()
            if not normalized_query or normalized_query in seen:
                continue
            seen.add(normalized_query)
            unique_queries.append(query)
        return unique_queries

    def _snippet(self, lines: list[str], start_line: int, end_line: int) -> str:
        return "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(lines[start_line - 1 : end_line], start=start_line)
        )

    def _metadata(self, query: RetrievalQuery, match_line: int) -> dict[str, str | int]:
        metadata: dict[str, str | int] = {
            "purpose": query.purpose,
            "priority": query.priority,
            "match_line": match_line,
        }
        if query.source_hint is not None:
            metadata["source_hint"] = query.source_hint
        return metadata

    def _candidate_id(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        query: str,
    ) -> str:
        identity = f"code_exact:{file_path}:{start_line}:{end_line}:{query}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        return f"EVID-EXACT-{digest}"
