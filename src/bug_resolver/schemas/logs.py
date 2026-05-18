from __future__ import annotations

from datetime import datetime

from pydantic import Field

from bug_resolver.schemas.common import LogLevel, StrictBaseModel
from bug_resolver.schemas.evidence import EvidenceItem


class StackTraceFrame(StrictBaseModel):
    file_path: str | None = None
    function_name: str | None = None
    line_number: int | None = Field(default=None, ge=1)
    raw_frame: str = Field(..., min_length=1)


class LogEntry(StrictBaseModel):
    log_id: str = Field(..., min_length=1)

    message: str = Field(..., min_length=1)
    level: LogLevel = LogLevel.UNKNOWN

    timestamp: datetime | None = None
    service_name: str | None = None
    environment: str | None = None

    request_id: str | None = None
    trace_id: str | None = None

    raw: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class LogAnalysisResult(StrictBaseModel):
    summary: str = Field(..., min_length=1)

    exception_type: str | None = None
    exception_message: str | None = None

    stack_trace: list[StackTraceFrame] = Field(default_factory=list)
    suspected_file_paths: list[str] = Field(default_factory=list)
    suspected_function_names: list[str] = Field(default_factory=list)

    request_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)

    likely_failure_point: str | None = None
    evidence_items: list[EvidenceItem] = Field(default_factory=list)