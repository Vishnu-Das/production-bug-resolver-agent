"""Local filesystem provider for source context around incident locations."""

from __future__ import annotations

import hashlib
from pathlib import Path

from bug_resolver.providers.retrieval.base import FileContextProvider
from bug_resolver.schemas import (
    EvidenceCandidate,
    FileContextRequest,
    RetrievalEvidenceSourceType,
)
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class LocalFileContextProvider(FileContextProvider):
    """Read bounded source snippets while preventing access outside the target repo."""

    _DEFAULT_MAX_LINES = 120

    def __init__(
        self,
        repo_path: Path | str,
        *,
        retriever_name: str = "file_context",
    ) -> None:
        self._repo_path = Path(repo_path).resolve()
        self._retriever_name = retriever_name

    @traceable(name="file_context.read_context", run_type="retriever")
    async def read_context(
        self,
        requests: list[FileContextRequest],
    ) -> list[EvidenceCandidate]:
        """Read one deterministic, line-numbered snippet for each valid request."""
        candidates: list[EvidenceCandidate] = []
        seen_requests: set[tuple[str, int | None, int, int]] = set()

        for request in requests:
            resolved_path = self._resolve_request_path(request.file_path)
            if resolved_path is None or not resolved_path.is_file():
                logger.info("file context skipped unavailable path file_path=%s", request.file_path)
                continue

            relative_path = resolved_path.relative_to(self._repo_path).as_posix()
            request_key = (
                relative_path,
                request.line_number,
                request.before_lines,
                request.after_lines,
            )
            if request_key in seen_requests:
                continue
            seen_requests.add(request_key)

            try:
                content = resolved_path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                logger.warning(
                    "file context failed to read file_path=%s error=%s",
                    relative_path,
                    error,
                )
                continue

            lines = content.splitlines()
            if not lines:
                logger.info("file context skipped empty file file_path=%s", relative_path)
                continue

            start_line, end_line = self._line_range(request, total_lines=len(lines))
            selected_lines = lines[start_line - 1 : end_line]
            snippet = "\n".join(
                f"{line_number}: {line}"
                for line_number, line in enumerate(selected_lines, start=start_line)
            )
            metadata: dict[str, str | int] = {
                "before_lines": request.before_lines,
                "after_lines": request.after_lines,
                "reason": request.reason,
            }
            if request.line_number is not None:
                metadata["requested_line_number"] = request.line_number

            candidates.append(
                EvidenceCandidate(
                    candidate_id=self._candidate_id(relative_path, start_line, end_line),
                    source_type=RetrievalEvidenceSourceType.FILE_CONTEXT,
                    retriever_name=self._retriever_name,
                    content=snippet,
                    file_path=relative_path,
                    start_line=start_line,
                    end_line=end_line,
                    metadata=metadata,
                )
            )

        return candidates

    def _resolve_request_path(self, file_path: str) -> Path | None:
        normalized_path = file_path.replace("\\", "/").strip()
        if not normalized_path:
            return None

        requested_path = Path(normalized_path)
        resolved_path = (
            requested_path.resolve()
            if requested_path.is_absolute()
            else (self._repo_path / requested_path).resolve()
        )
        if not self._is_within_repo(resolved_path):
            logger.warning("file context rejected traversal file_path=%s", file_path)
            return None

        return resolved_path

    def _is_within_repo(self, resolved_path: Path) -> bool:
        try:
            resolved_path.relative_to(self._repo_path)
        except ValueError:
            return False
        return True

    def _line_range(
        self,
        request: FileContextRequest,
        *,
        total_lines: int,
    ) -> tuple[int, int]:
        if request.line_number is None:
            return 1, min(total_lines, self._DEFAULT_MAX_LINES)

        return (
            max(1, request.line_number - request.before_lines),
            min(total_lines, request.line_number + request.after_lines),
        )

    def _candidate_id(self, file_path: str, start_line: int, end_line: int) -> str:
        identity = f"file_context:{file_path}:{start_line}:{end_line}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()
        return f"EVID-FILE-{digest}"
