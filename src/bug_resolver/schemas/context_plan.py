from __future__ import annotations

from pydantic import Field

from bug_resolver.schemas.common import StrictBaseModel


class ContextPlan(StrictBaseModel):
    plan_id: str = Field(..., min_length=1)

    code_search_queries: list[str] = Field(default_factory=list)
    knowledge_search_queries: list[str] = Field(default_factory=list)

    files_to_prioritize: list[str] = Field(default_factory=list)
    functions_to_prioritize: list[str] = Field(default_factory=list)

    missing_evidence_hints: list[str] = Field(default_factory=list)

    retry_reason: str | None = None
    generated_from: str | None = None

    metadata: dict[str, str] = Field(default_factory=dict)