"""Historical RCA provider protocol."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import HistoricalRCAContext


@runtime_checkable
class HistoricalRCAProvider(Protocol):
    """Contract for searching prior RCA reports for similar incidents."""

    async def search_history(
        self,
        queries: list[str],
        *,
        current_incident_id: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalRCAContext]:
        """Search prior RCA reports using focused incident-memory queries."""
        ...
