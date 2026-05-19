"""Tests for incident intake normalization."""

from __future__ import annotations

import pytest

from bug_resolver.agents import IncidentIntakeAgent
from bug_resolver.schemas import Incident, IncidentIntakeRequest
from bug_resolver.schemas.common import IncidentSeverity, IncidentStatus


@pytest.mark.asyncio
async def test_incident_intake_agent_creates_structured_incident() -> None:
    agent = IncidentIntakeAgent()
    request = IncidentIntakeRequest(
        incident_id="INC-001",
        description="Users get 500 error while asking summary questions.",
        severity="HIGH",
        affected_service="conversational_rag",
        affected_area="summary flow",
        reporter="cli",
        metadata={"source": "manual_test"},
    )

    incident = await agent.run(request)

    assert isinstance(incident, Incident)
    assert incident.incident_id == "INC-001"
    assert incident.title == "Users get 500 error while asking summary questions"
    assert incident.description == "Users get 500 error while asking summary questions."
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.status == IncidentStatus.NEW
    assert incident.affected_service == "conversational_rag"
    assert incident.affected_area == "summary flow"
    assert incident.reporter == "cli"
    assert incident.raw_input == request.description
    assert incident.metadata == {"source": "manual_test"}


@pytest.mark.asyncio
async def test_incident_intake_agent_generates_incident_id_when_missing() -> None:
    agent = IncidentIntakeAgent()
    request = IncidentIntakeRequest(
        description="Chat endpoint fails for document summary queries.",
    )

    incident = await agent.run(request)

    assert incident.incident_id.startswith("INC-")
    assert incident.status == IncidentStatus.NEW
    assert incident.severity == IncidentSeverity.UNKNOWN


@pytest.mark.asyncio
async def test_incident_intake_agent_uses_explicit_title_when_provided() -> None:
    agent = IncidentIntakeAgent()
    request = IncidentIntakeRequest(
        incident_id="INC-002",
        title="Summary query failure",
        description="Users get error while asking document summary questions.",
    )

    incident = await agent.run(request)

    assert incident.title == "Summary query failure"


@pytest.mark.asyncio
async def test_incident_intake_agent_normalizes_description_whitespace() -> None:
    agent = IncidentIntakeAgent()
    request = IncidentIntakeRequest(
        incident_id="INC-003",
        description="Users    get     500 error\nwhile asking summary questions.",
    )

    incident = await agent.run(request)

    assert incident.description == "Users get 500 error while asking summary questions."
