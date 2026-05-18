from __future__ import annotations

from pydantic import Field, field_validator

from bug_resolver.schemas.common import IncidentSeverity, StrictBaseModel


class IncidentIntakeRequest(StrictBaseModel):
    """
    Input model for IncidentIntakeAgent.

    This represents raw incident input coming from CLI now,
    and later from Jira, GitHub Issues, files, or other providers.
    """

    description: str = Field(..., min_length=1)
    incident_id: str | None = None
    title: str | None = None
    severity: IncidentSeverity = IncidentSeverity.UNKNOWN
    affected_service: str | None = None
    affected_area: str | None = None
    reporter: str | None = None
    raw_input: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value