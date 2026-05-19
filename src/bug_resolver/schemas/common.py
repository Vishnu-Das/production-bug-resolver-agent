from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveInt = Annotated[int, Field(ge=1)]


class StrictBaseModel(BaseModel):
    """Base model for all project schemas.

    We forbid unknown fields so invalid LLM/provider outputs fail fast.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class IncidentStatus(StrEnum):
    NEW = "new"
    INVESTIGATING = "investigating"
    ANALYZED = "analyzed"
    CLOSED = "closed"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class EvidenceSourceType(StrEnum):
    LOG = "log"
    CODE = "code"
    KNOWLEDGE_BASE = "knowledge_base"
    GRAPH = "graph"
    WEB = "web"
    HISTORICAL_RCA = "historical_rca"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    SELECTED = "selected"
    REJECTED = "rejected"


