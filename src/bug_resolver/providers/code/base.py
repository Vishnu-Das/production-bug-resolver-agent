"""Code context provider protocol for retrieving source evidence."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import CodeContext


@runtime_checkable
class CodeContextProvider(Protocol):
    """Contract for retrieving relevant code context."""

    async def search_code(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeContext]:
        """Search code context using one or more focused queries."""
        ...
