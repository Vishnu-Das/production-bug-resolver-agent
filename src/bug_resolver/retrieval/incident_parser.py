"""Coordinator for deterministic incident fact parsing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bug_resolver.rules.incident_parsing_rules import IncidentParsingRules
from bug_resolver.schemas import Incident, IncidentFacts, LogEntry
from bug_resolver.utils.observability import get_logger, traceable

logger = get_logger(__name__)


class IncidentParser:
    """Parse incident and runtime text into grounded retrieval facts."""

    def __init__(self, rules: IncidentParsingRules | None = None) -> None:
        self._rules = rules or IncidentParsingRules()

    @traceable(name="incident_driven_context.parse_facts", run_type="parser")
    def parse(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str | None = None,
        log_texts: Sequence[str] | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> IncidentFacts:
        runtime_texts = log_texts or ()
        texts = self._texts(
            summary=summary,
            description=description,
            log_texts=runtime_texts,
            metadata=metadata or {},
        )
        stack_frames = self._rules.extract_stack_frames(texts)

        facts = IncidentFacts(
            incident_id=incident_id,
            summary=summary,
            description=description,
            error_terms=self._rules.extract_error_terms(texts),
            exception_types=self._rules.extract_exception_types(texts),
            stack_frames=stack_frames,
            status_codes=self._rules.extract_status_codes(texts),
            trace_ids=self._rules.extract_trace_ids(texts),
            request_ids=self._rules.extract_request_ids(texts),
            candidate_symbols=self._rules.extract_candidate_symbols(
                texts,
                stack_frames=stack_frames,
            ),
            quoted_terms=self._rules.extract_quoted_terms(texts),
            config_like_terms=self._rules.extract_config_like_terms(texts),
            log_key_terms=self._rules.extract_log_key_terms(runtime_texts),
            event_terms=self._rules.extract_event_terms(runtime_texts),
        )
        logger.info(
            "incident facts parsed incident_id=%s runtime_texts=%s stack_frames=%s "
            "exceptions=%s log_keys=%s events=%s symbols=%s",
            incident_id,
            len(runtime_texts),
            len(facts.stack_frames),
            len(facts.exception_types),
            len(facts.log_key_terms),
            len(facts.event_terms),
            len(facts.candidate_symbols),
        )
        return facts

    def parse_incident(
        self,
        incident: Incident,
        logs: Sequence[LogEntry] | None = None,
    ) -> IncidentFacts:
        log_entries = logs or ()
        facts = self.parse(
            incident_id=incident.incident_id,
            summary=incident.title,
            description=incident.description,
            log_texts=[
                value
                for log in log_entries
                for value in self._log_texts(log)
            ],
            metadata={
                **incident.metadata,
                **({"raw_input": incident.raw_input} if incident.raw_input else {}),
            },
        )

        return facts.model_copy(
            update={
                "trace_ids": self._rules.unique(
                    [
                        *facts.trace_ids,
                        *(log.trace_id for log in log_entries if log.trace_id),
                    ]
                ),
                "request_ids": self._rules.unique(
                    [
                        *facts.request_ids,
                        *(log.request_id for log in log_entries if log.request_id),
                    ]
                ),
            }
        )

    def _texts(
        self,
        *,
        summary: str,
        description: str | None,
        log_texts: Sequence[str],
        metadata: Mapping[str, str],
    ) -> list[str]:
        return [
            value
            for value in (
                summary,
                description or "",
                *(f"{key}={value}" for key, value in metadata.items()),
                *log_texts,
            )
            if value
        ]

    def _log_texts(self, log: LogEntry) -> list[str]:
        return [
            value
            for value in (
                log.message,
                log.raw or "",
                *(f"{key}={value}" for key, value in log.metadata.items()),
            )
            if value
        ]
