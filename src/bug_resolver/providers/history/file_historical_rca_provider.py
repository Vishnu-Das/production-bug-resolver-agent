"""File-backed historical RCA provider."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bug_resolver.providers.history.base import HistoricalRCAProvider
from bug_resolver.schemas import HistoricalRCAContext
from bug_resolver.utils.observability import get_logger, log_debug_payload, traceable


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
logger = get_logger(__name__)
STOPWORDS = frozenset(
    {
        "a",
        "after",
        "and",
        "are",
        "as",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "with",
        "users",
    }
)


class FileHistoricalRCAProvider(HistoricalRCAProvider):
    """Search saved RCA JSON reports with deterministic token overlap."""

    def __init__(self, reports_dir: str | Path) -> None:
        self.reports_dir = Path(reports_dir)

    @traceable(name="historical_rca.search", run_type="retriever")
    async def search_history(
        self,
        queries: list[str],
        *,
        current_incident_id: str | None = None,
        limit: int = 5,
    ) -> list[HistoricalRCAContext]:
        query_tokens = self._tokens(" ".join(queries))
        if not query_tokens:
            return []

        logger.info(
            "historical rca search started query_count=%s current_incident_id=%s limit=%s",
            len(queries),
            current_incident_id,
            limit,
        )
        log_debug_payload(logger, "historical rca search queries", payload=queries)
        candidates: list[tuple[float, HistoricalRCAContext]] = []
        for report_path in self._report_paths():
            report_data = self._load_report(report_path)
            if report_data is None:
                continue

            incident_id = str(report_data.get("incident_id", ""))
            if current_incident_id and incident_id == current_incident_id:
                continue

            context = self._context_from_report(report_data, report_path, query_tokens)
            if context.relevance_score <= 0:
                continue
            candidates.append((context.relevance_score, context))

        ranked = sorted(
            candidates,
            key=lambda item: (
                item[0],
                item[1].confidence_score,
                item[1].incident_id,
            ),
            reverse=True,
        )
        contexts = [context for _, context in ranked[:limit]]
        logger.info(
            "historical rca search finished candidates=%s returned=%s",
            len(candidates),
            len(contexts),
        )
        log_debug_payload(
            logger,
            "historical rca returned contexts",
            payload=[
                {
                    "context_id": context.context_id,
                    "incident_id": context.incident_id,
                    "score": context.relevance_score,
                    "matched_signals": context.matched_signals,
                }
                for context in contexts
            ],
        )
        return contexts

    def _report_paths(self) -> list[Path]:
        if not self.reports_dir.exists():
            return []

        return sorted(self.reports_dir.glob("incidents/*/rca.json"))

    def _load_report(self, report_path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return value if isinstance(value, dict) else None

    def _context_from_report(
        self,
        report_data: dict[str, Any],
        report_path: Path,
        query_tokens: set[str],
    ) -> HistoricalRCAContext:
        searchable_text = self._searchable_text(report_data)
        report_tokens = self._tokens(searchable_text)
        matched_signals = sorted(query_tokens & report_tokens)
        relevance_score = min(len(matched_signals) / max(len(query_tokens), 1), 1.0)

        incident_id = str(report_data.get("incident_id", "unknown"))
        title = str(report_data.get("title") or f"RCA for {incident_id}")
        root_cause = str(report_data.get("root_cause") or "Root cause unavailable.")
        confidence_score = float(report_data.get("confidence_score") or 0.0)

        return HistoricalRCAContext(
            context_id=f"historical-{incident_id}",
            incident_id=incident_id,
            title=title,
            root_cause=root_cause,
            confidence_score=confidence_score,
            report_path=str(report_path),
            matched_signals=matched_signals,
            content=(
                f"Similar prior incident {incident_id}: {title}. "
                f"Prior RCA root cause: {root_cause}"
            ),
            relevance_score=round(relevance_score, 3),
        )

    def _searchable_text(self, report_data: dict[str, Any]) -> str:
        values: list[str] = []
        for key in (
            "title",
            "incident_summary",
            "root_cause",
            "technical_explanation",
            "confidence_reason",
            "immediate_fix",
        ):
            value = report_data.get(key)
            if isinstance(value, str):
                values.append(value)

        for key in (
            "symptoms",
            "log_findings",
            "code_findings",
            "graph_findings",
            "knowledge_base_findings",
            "historical_findings",
            "hypotheses_considered",
            "tests_to_add",
        ):
            value = report_data.get(key)
            if isinstance(value, list):
                values.extend(str(item) for item in value)

        return "\n".join(values)

    def _tokens(self, value: str) -> set[str]:
        raw_tokens = set(TOKEN_PATTERN.findall(value.lower()))
        split_tokens = {
            token_part
            for token in raw_tokens
            for token_part in token.split("_")
            if token_part
        }
        return (raw_tokens | split_tokens) - STOPWORDS
