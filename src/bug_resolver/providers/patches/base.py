"""Provider contract for safe patch generation file context."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PatchContextProvider(Protocol):
    """Read exact target-repository file contents for patch suggestions."""

    async def read_file(self, file_path: str) -> str | None:
        """Return file text for a repo-relative path, or None when unavailable."""
        ...
