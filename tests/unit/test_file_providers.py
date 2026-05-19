"""Tests for local incident and log file providers."""

import json

import pytest

from bug_resolver.providers.incident import FileIncidentProvider
from bug_resolver.providers.logs import FileLogProvider
from bug_resolver.schemas import Incident, LogEntry


@pytest.mark.asyncio
async def test_file_incident_provider_loads_incident(tmp_path) -> None:
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()

    incident = Incident(
        incident_id="INC-001",
        title="Users get 500 error",
        description="Users get 500 error while asking summary questions.",
    )

    incident_file = incidents_dir / "INC-001.json"
    incident_file.write_text(
        incident.model_dump_json(),
        encoding="utf-8",
    )

    provider = FileIncidentProvider(incidents_dir)

    loaded_incident = await provider.get_incident("INC-001")

    assert loaded_incident == incident


@pytest.mark.asyncio
async def test_file_incident_provider_raises_for_missing_file(tmp_path) -> None:
    provider = FileIncidentProvider(tmp_path)

    with pytest.raises(FileNotFoundError):
        await provider.get_incident("INC-404")


@pytest.mark.asyncio
async def test_file_log_provider_loads_logs(tmp_path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    log_entry = LogEntry(
        log_id="LOG-001",
        message="Something failed",
        level="error",
    )

    logs_file = logs_dir / "INC-001.json"
    logs_file.write_text(
        json.dumps([log_entry.model_dump(mode="json")]),
        encoding="utf-8",
    )

    provider = FileLogProvider(logs_dir)

    loaded_logs = await provider.get_logs("INC-001")

    assert loaded_logs == [log_entry]


@pytest.mark.asyncio
async def test_file_log_provider_raises_for_missing_file(tmp_path) -> None:
    provider = FileLogProvider(tmp_path)

    with pytest.raises(FileNotFoundError):
        await provider.get_logs("INC-404")


@pytest.mark.asyncio
async def test_file_log_provider_rejects_non_list_json(tmp_path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    logs_file = logs_dir / "INC-001.json"
    logs_file.write_text(
        json.dumps({"message": "This should have been inside a list"}),
        encoding="utf-8",
    )

    provider = FileLogProvider(logs_dir)

    with pytest.raises(ValueError, match="Expected logs file to contain a JSON list"):
        await provider.get_logs("INC-001")
