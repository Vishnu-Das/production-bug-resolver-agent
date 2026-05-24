"""Structured workflow error records."""

from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import StrictBaseModel


class WorkflowErrorInfo(StrictBaseModel):
    """User-facing error detail preserved on WorkflowState."""

    error_id: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    component: str = Field(..., min_length=1)
    recoverable: bool = False
    suggested_action: str | None = None
    context: dict[str, str] = Field(default_factory=dict)
