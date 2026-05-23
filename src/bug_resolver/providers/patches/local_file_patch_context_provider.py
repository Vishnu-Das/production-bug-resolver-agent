"""Local filesystem provider for exact patch-generation file context."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.providers.patches.base import PatchContextProvider
from bug_resolver.utils.observability import get_logger, traceable


logger = get_logger(__name__)


class LocalFilePatchContextProvider(PatchContextProvider):
    """Read repo-relative files while blocking traversal outside the target repo."""

    def __init__(self, target_repo_path: str | Path) -> None:
        self._target_repo_path = Path(target_repo_path).resolve()

    @traceable(name="patch_context.read_file", run_type="retriever")
    async def read_file(self, file_path: str) -> str | None:
        normalized_path = file_path.replace("\\", "/").strip()
        requested_path = Path(normalized_path)

        if not normalized_path or requested_path.is_absolute():
            logger.warning("patch context rejected invalid path file_path=%s", file_path)
            return None

        resolved_path = (self._target_repo_path / requested_path).resolve()
        if not self._is_within_target_repo(resolved_path):
            logger.warning("patch context rejected traversal file_path=%s", file_path)
            return None

        if not resolved_path.is_file():
            logger.info("patch context missing file file_path=%s", normalized_path)
            return None

        content = resolved_path.read_text(encoding="utf-8")
        logger.info(
            "patch context loaded file file_path=%s chars=%s",
            normalized_path,
            len(content),
        )
        return content

    def _is_within_target_repo(self, resolved_path: Path) -> bool:
        try:
            resolved_path.relative_to(self._target_repo_path)
        except ValueError:
            return False

        return True
