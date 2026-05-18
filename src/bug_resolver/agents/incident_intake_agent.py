from __future__ import annotations

from bug_resolver.agents.base import BaseAgent
from bug_resolver.schemas import Incident
from bug_resolver.schemas.common import IncidentSeverity, IncidentStatus
from bug_resolver.schemas.incident_intake import IncidentIntakeRequest
from bug_resolver.utils.ids import new_incident_id


class IncidentIntakeAgent(BaseAgent[IncidentIntakeRequest, Incident]):
    """
    Converts raw incident input into a structured Incident.

    This agent is intentionally deterministic for now.
    No LLM is needed for the first version because intake should be reliable,
    cheap, and easy to test.
    """

    name = "incident_intake_agent"

    async def _run(self, input_data: IncidentIntakeRequest) -> Incident:
        description = self._normalize_text(input_data.description)

        return Incident(
            incident_id=input_data.incident_id or new_incident_id(),
            title=self._build_title(input_data.title, description),
            description=description,
            severity=input_data.severity or IncidentSeverity.UNKNOWN,
            status=IncidentStatus.NEW,
            affected_service=input_data.affected_service,
            affected_area=input_data.affected_area,
            reporter=input_data.reporter,
            raw_input=input_data.raw_input or input_data.description,
            metadata=input_data.metadata,
        )

    def _build_title(self, title: str | None, description: str) -> str:
        if title:
            return self._normalize_text(title)

        first_sentence = description.split(".", maxsplit=1)[0].strip()
        if len(first_sentence) <= 80:
            return first_sentence

        return f"{first_sentence[:77].rstrip()}..."

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.split())