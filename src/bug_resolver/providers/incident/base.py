from typing import Protocol, runtime_checkable

from bug_resolver.schemas import Incident


@runtime_checkable
class IncidentProvider(Protocol):
    """Contract for loading incidents from CLI, files, Jira, GitHub Issues, etc."""

    async def get_incident(self, incident_id: str) -> Incident:
        """Fetch a structured incident by id."""
        ...