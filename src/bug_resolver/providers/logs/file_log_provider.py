"""File-backed log provider for local sample and CLI investigations."""

import asyncio
import json
from pathlib import Path
from typing import Any

from bug_resolver.schemas import LogEntry


class FileLogProvider:
    """Loads incident logs from local JSON files.

    Expected file format:
        sample_data/logs/INC-001.json

    The JSON file should contain a list of log entries.
    """

    def __init__(self, logs_dir: str | Path) -> None:
        self.logs_dir = Path(logs_dir)

    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        logs_file = self.logs_dir / f"{incident_id}.json"

        if not logs_file.exists():
            raise FileNotFoundError(
                f"Log file not found for incident_id={incident_id}: {logs_file}"
            )

        raw_json = await asyncio.to_thread(
            logs_file.read_text,
            encoding="utf-8",
        )

        raw_logs = json.loads(raw_json)

        if not isinstance(raw_logs, list):
            raise ValueError(
                f"Expected logs file to contain a JSON list, got {type(raw_logs).__name__}"
            )

        return [self._parse_log_entry(raw_log) for raw_log in raw_logs]

    def _parse_log_entry(self, raw_log: Any) -> LogEntry:
        if not isinstance(raw_log, dict):
            raise ValueError(
                f"Expected each log entry to be a JSON object, got {type(raw_log).__name__}"
            )

        return LogEntry.model_validate(raw_log)
