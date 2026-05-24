"""File-backed incident provider for local sample and CLI investigations."""

import asyncio
from pathlib import Path

from bug_resolver.schemas import Incident
from bug_resolver.utils.observability import get_logger, traceable


logger = get_logger(__name__)


class FileIncidentProvider:
    """Loads incident data from local JSON files.

    Expected file format:
        sample_data/incidents/INC-001.json
    """

    def __init__(self, incidents_dir: str | Path) -> None:
        self.incidents_dir = Path(incidents_dir)

    @traceable(name="incident.load", run_type="retriever")
    async def get_incident(self, incident_id: str) -> Incident:
        incident_file = self.incidents_dir / f"{incident_id}.json"
        logger.info("loading incident incident_id=%s path=%s", incident_id, incident_file)

        if not incident_file.exists():
            raise FileNotFoundError(
                f"Incident file not found for incident_id={incident_id}: {incident_file}"
            )

        raw_json = await asyncio.to_thread(
            incident_file.read_text,
            encoding="utf-8",
        )

        incident = Incident.model_validate_json(raw_json)
        logger.info(
            "loaded incident incident_id=%s severity=%s service=%s",
            incident.incident_id,
            incident.severity,
            incident.affected_service,
        )
        return incident
