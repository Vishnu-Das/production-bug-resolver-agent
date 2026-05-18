from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field

from bug_resolver.schemas.common import (
    IncidentSeverity,
    IncidentStatus,
    StrictBaseModel,
)


class Incident(StrictBaseModel):
    incident_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)

    severity: IncidentSeverity = IncidentSeverity.UNKNOWN
    status: IncidentStatus = IncidentStatus.NEW

    affected_service: str | None = None
    affected_area: str | None = None
    reporter: str | None = None

    raw_input: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, str] = Field(default_factory=dict)