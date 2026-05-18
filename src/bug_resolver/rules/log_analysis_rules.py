from __future__ import annotations

import re
from uuid import uuid4

from bug_resolver.schemas import EvidenceItem, LogEntry, StackTraceFrame
from bug_resolver.schemas.common import EvidenceSourceType


class LogAnalysisRules:
    """
    Deterministic rules for extracting useful debugging signals from logs.

    This class keeps parsing rules outside the agent so the agent remains thin.
    Later, we can replace or extend these rules without changing agent flow.
    """

    _stack_frame_pattern = re.compile(
        r'File "(?P<file_path>[^"]+)", line (?P<line_number>\d+), in (?P<function_name>[^\s]+)'
    )

    _exception_pattern = re.compile(
        r"(?P<exception_type>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)):\s*(?P<exception_message>.+)"
    )

    _request_id_pattern = re.compile(
        r"(?:request_id|requestId|request-id)[=:]\s*(?P<value>[A-Za-z0-9\-_.]+)"
    )

    _trace_id_pattern = re.compile(
        r"(?:trace_id|traceId|trace-id)[=:]\s*(?P<value>[A-Za-z0-9\-_.]+)"
    )

    def extract_stack_trace(self, logs: list[LogEntry]) -> list[StackTraceFrame]:
        frames: list[StackTraceFrame] = []

        for log in logs:
            text = self.log_text(log)

            for match in self._stack_frame_pattern.finditer(text):
                frames.append(
                    StackTraceFrame(
                        file_path=match.group("file_path"),
                        line_number=int(match.group("line_number")),
                        function_name=match.group("function_name"),
                        raw_frame=match.group(0),
                    )
                )

        return frames

    def extract_exception(self, logs: list[LogEntry]) -> tuple[str | None, str | None]:
        for log in reversed(logs):
            text = self.log_text(log)

            matches = list(self._exception_pattern.finditer(text))
            if not matches:
                continue

            match = matches[-1]
            return (
                match.group("exception_type"),
                match.group("exception_message").strip(),
            )

        return None, None

    def extract_request_ids(self, logs: list[LogEntry]) -> list[str]:
        values: list[str] = []

        for log in logs:
            if log.request_id:
                values.append(log.request_id)

            values.extend(
                match.group("value")
                for match in self._request_id_pattern.finditer(self.log_text(log))
            )

        return self.unique(values)

    def extract_trace_ids(self, logs: list[LogEntry]) -> list[str]:
        values: list[str] = []

        for log in logs:
            if log.trace_id:
                values.append(log.trace_id)

            values.extend(
                match.group("value")
                for match in self._trace_id_pattern.finditer(self.log_text(log))
            )

        return self.unique(values)

    def build_evidence_items(self, logs: list[LogEntry]) -> list[EvidenceItem]:
        return [
            EvidenceItem(
                evidence_id=f"EVID-LOG-{uuid4().hex[:8].upper()}",
                source_type=EvidenceSourceType.LOG,
                source_name=log.log_id,
                content=log.raw or log.message,
                confidence=1.0,
                metadata={
                    "log_level": log.level.value,
                    **({"service_name": log.service_name} if log.service_name else {}),
                    **({"environment": log.environment} if log.environment else {}),
                },
            )
            for log in logs
        ]

    def build_likely_failure_point(
        self,
        stack_trace: list[StackTraceFrame],
    ) -> str | None:
        if not stack_trace:
            return None

        last_frame = stack_trace[-1]

        if last_frame.file_path and last_frame.line_number and last_frame.function_name:
            return (
                f"{last_frame.file_path}:{last_frame.line_number} "
                f"in {last_frame.function_name}"
            )

        return last_frame.raw_frame

    def build_summary(
        self,
        exception_type: str | None,
        exception_message: str | None,
        likely_failure_point: str | None,
        log_count: int,
    ) -> str:
        if exception_type and exception_message and likely_failure_point:
            return (
                f"Analyzed {log_count} log entries. Found {exception_type}: "
                f"{exception_message}. Likely failure point: {likely_failure_point}."
            )

        if exception_type and exception_message:
            return (
                f"Analyzed {log_count} log entries. Found {exception_type}: "
                f"{exception_message}."
            )

        if likely_failure_point:
            return (
                f"Analyzed {log_count} log entries. No explicit exception was found, "
                f"but stack trace points to {likely_failure_point}."
            )

        return (
            f"Analyzed {log_count} log entries. No explicit exception or stack trace "
            "was found in the provided logs."
        )

    def log_text(self, log: LogEntry) -> str:
        return log.raw or log.message

    def unique(self, values: list[str] | object) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = value.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(normalized)

        return unique_values