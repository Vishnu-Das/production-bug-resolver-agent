"""Log provider protocol for retrieving incident-specific runtime logs."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import LogEntry


@runtime_checkable
class LogProvider(Protocol):
    """Contract for loading logs related to an incident."""

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        """Fetch logs for the given incident."""
        ...
