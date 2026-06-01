"""Deterministic extraction rules for incident and runtime facts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from bug_resolver.schemas.retrieval import StackFrame


PYTHON_TRACEBACK_FRAME_PATTERN = re.compile(
    r'File\s+"(?P<path>[^"]+\.py)",\s+line\s+(?P<line>\d+)'
    r"(?:,\s+in\s+(?P<function>[A-Za-z_][A-Za-z0-9_.<>]*))?"
)
PYTHON_PATH_LINE_PATTERN = re.compile(
    r"(?P<path>[A-Za-z0-9_./\\-]+\.py):(?P<line>\d+)"
    r"(?:\s+in\s+(?P<function>[A-Za-z_][A-Za-z0-9_.<>]*))?"
)
PYTHON_PATH_LINE_TEXT_PATTERN = re.compile(
    r"(?P<path>[A-Za-z0-9_./\\-]+\.py)\s+line\s+(?P<line>\d+)"
    r"(?:\s+in\s+(?P<function>[A-Za-z_][A-Za-z0-9_.<>]*))?"
)
EXCEPTION_TYPE_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Error|Exception)\b")
ERROR_LINE_PATTERN = re.compile(
    r"\b(?:error|exception|traceback|failed|failure|timeout|refused|invalid|missing)\b",
    re.IGNORECASE,
)
HTTP_STATUS_PATTERN = re.compile(
    r"\b(?:http(?:\s+status)?|status(?:_code)?|returned|response(?:\s+status)?)"
    r"\s*[:=]?\s*(?P<code>[45]\d{2})\b",
    re.IGNORECASE,
)
HTTP_STATUS_REASON_PATTERN = re.compile(
    r"\b(?P<code>[45]\d{2})\s+"
    r"(?:bad request|unauthorized|forbidden|not found|conflict|unprocessable entity|"
    r"too many requests|internal server error|bad gateway|service unavailable|"
    r"gateway timeout)\b",
    re.IGNORECASE,
)
TRACE_ID_PATTERN = re.compile(
    r"\btrace[_-]?id\b\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9_.:/-]+)",
    re.IGNORECASE,
)
REQUEST_ID_PATTERN = re.compile(
    r"\b(?:x-request-id|request[_-]?id)\b\s*[:=]\s*[\"']?"
    r"(?P<value>[A-Za-z0-9_.:/-]+)",
    re.IGNORECASE,
)
QUOTED_TERM_PATTERN = re.compile(r"(?P<quote>[\"'])(?P<value>[^\n\r\"']+)(?P=quote)")
CONFIG_LIKE_TERM_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
FUNCTION_CALL_PATTERN = re.compile(r"\b(?P<value>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
DOTTED_CALL_PATTERN = re.compile(
    r"\b(?P<value>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\("
)
CLASS_LIKE_PATTERN = re.compile(r"\b(?P<value>[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+)\b")
STRUCTURED_KEY_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_])(?:"(?P<json_key>[A-Za-z_][A-Za-z0-9_]*)"\s*:|'
    r"(?P<plain_key>[A-Za-z_][A-Za-z0-9_-]*)\s*=)"
)
STRUCTURED_VALUE_PATTERN = re.compile(
    r'(?<![A-Za-z0-9_])(?:"?(?P<key>[A-Za-z_][A-Za-z0-9_-]*)"?\s*[:=]\s*)'
    r'(?:"(?P<double_quoted>[^"]*)"|\'(?P<single_quoted>[^\']*)\'|'
    r"(?P<bare>[^\s,}\]]+))"
)
SNAKE_CASE_RUNTIME_TERM_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![A-Za-z0-9_.])"
)
UUID_PATTERN = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)
LONG_HASH_PATTERN = re.compile(r"\A(?:[A-Za-z0-9_-]+:)?[0-9a-f]{24,}\Z", re.IGNORECASE)
HTTP_STATUS_CODES = frozenset({400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504})
EVENT_VALUE_KEYS = frozenset({"event", "action", "name"})
IGNORED_LOG_KEYS = frozenset(
    {
        "request_id",
        "requestid",
        "trace_id",
        "traceid",
        "x_request_id",
    }
)


class IncidentParsingRules:
    """Extract grounded repo-agnostic facts from incident and runtime text."""

    def extract_stack_frames(self, texts: Sequence[str]) -> list[StackFrame]:
        frames: list[StackFrame] = []
        seen: set[tuple[str, int | None, str | None]] = set()

        for text in texts:
            for pattern in (
                PYTHON_TRACEBACK_FRAME_PATTERN,
                PYTHON_PATH_LINE_PATTERN,
                PYTHON_PATH_LINE_TEXT_PATTERN,
            ):
                for match in pattern.finditer(text):
                    frame = StackFrame(
                        file_path=match.group("path"),
                        line_number=int(match.group("line")),
                        function_name=match.group("function"),
                    )
                    key = (frame.file_path, frame.line_number, frame.function_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    frames.append(frame)

        return frames

    def extract_exception_types(self, texts: Sequence[str]) -> list[str]:
        return self._unique_strings(
            match.group(0)
            for text in texts
            for match in EXCEPTION_TYPE_PATTERN.finditer(text)
        )

    def extract_error_terms(self, texts: Sequence[str]) -> list[str]:
        terms: list[str] = []
        for text in texts:
            for line in text.splitlines():
                compact_line = " ".join(line.split())
                if not compact_line:
                    continue
                if ERROR_LINE_PATTERN.search(compact_line) or EXCEPTION_TYPE_PATTERN.search(
                    compact_line
                ):
                    terms.append(compact_line[:240].rstrip())

        return self._unique_strings(terms)

    def extract_status_codes(self, texts: Sequence[str]) -> list[int]:
        codes: list[int] = []
        for text in texts:
            for pattern in (HTTP_STATUS_PATTERN, HTTP_STATUS_REASON_PATTERN):
                for match in pattern.finditer(text):
                    code = int(match.group("code"))
                    if code in HTTP_STATUS_CODES:
                        codes.append(code)

        return self._unique_ints(codes)

    def extract_trace_ids(self, texts: Sequence[str]) -> list[str]:
        return self._extract_ids(texts, TRACE_ID_PATTERN)

    def extract_request_ids(self, texts: Sequence[str]) -> list[str]:
        return self._extract_ids(texts, REQUEST_ID_PATTERN)

    def extract_quoted_terms(self, texts: Sequence[str]) -> list[str]:
        return self._unique_strings(
            value
            for text in texts
            for match in QUOTED_TERM_PATTERN.finditer(text)
            if 1 <= len(value := match.group("value").strip()) <= 160
        )

    def extract_config_like_terms(self, texts: Sequence[str]) -> list[str]:
        return self._unique_strings(
            match.group(0)
            for text in texts
            for match in CONFIG_LIKE_TERM_PATTERN.finditer(text)
        )

    def extract_log_key_terms(self, runtime_texts: Sequence[str]) -> list[str]:
        """Extract code-searchable keys from structured runtime text."""
        return self._unique_strings(
            key
            for text in runtime_texts
            for match in STRUCTURED_KEY_PATTERN.finditer(text)
            if not self._is_identifier_key(key := self._normalized_log_key(match))
        )

    def extract_event_terms(self, runtime_texts: Sequence[str]) -> list[str]:
        """Extract conservative event-like values and snake-case runtime tokens."""
        structured_values = [
            value
            for text in runtime_texts
            for match in STRUCTURED_VALUE_PATTERN.finditer(text)
            if match.group("key").casefold().replace("-", "_") in EVENT_VALUE_KEYS
            if (value := self._structured_value(match))
            and self._is_searchable_runtime_term(value)
        ]
        standalone_terms = [
            match.group(0)
            for text in runtime_texts
            for match in SNAKE_CASE_RUNTIME_TERM_PATTERN.finditer(text)
            if self._is_searchable_runtime_term(match.group(0))
            and not self._is_identifier_key(match.group(0))
        ]
        return self._unique_strings([*structured_values, *standalone_terms])

    def extract_candidate_symbols(
        self,
        texts: Sequence[str],
        *,
        stack_frames: Sequence[StackFrame] = (),
    ) -> list[str]:
        exception_types = set(self.extract_exception_types(texts))
        config_like_terms = set(self.extract_config_like_terms(texts))
        values: list[str] = [
            frame.function_name
            for frame in stack_frames
            if frame.function_name is not None
        ]

        for text in texts:
            values.extend(match.group("value") for match in DOTTED_CALL_PATTERN.finditer(text))
            values.extend(match.group("value") for match in FUNCTION_CALL_PATTERN.finditer(text))
            values.extend(
                match.group("value")
                for match in CLASS_LIKE_PATTERN.finditer(text)
                if match.group("value") not in exception_types
                and match.group("value") not in config_like_terms
            )

        return self._unique_strings(values)

    def _normalized_log_key(self, match: re.Match[str]) -> str:
        return (match.group("json_key") or match.group("plain_key")).replace("-", "_")

    def _structured_value(self, match: re.Match[str]) -> str:
        return (
            match.group("double_quoted")
            or match.group("single_quoted")
            or match.group("bare")
            or ""
        ).strip()

    def _is_identifier_key(self, value: str) -> bool:
        normalized = value.casefold().replace("-", "_")
        return normalized in IGNORED_LOG_KEYS or normalized.endswith("_id")

    def _is_searchable_runtime_term(self, value: str) -> bool:
        normalized = value.strip().strip("\"'").casefold()
        if not normalized or len(normalized) > 100:
            return False
        if normalized in {"true", "false", "null", "none"}:
            return False
        if normalized.startswith(("req_", "req-", "trace_", "trace-")):
            return False
        if UUID_PATTERN.fullmatch(normalized) or LONG_HASH_PATTERN.fullmatch(normalized):
            return False
        if "." in normalized or "/" in normalized or "\\" in normalized:
            return False
        return bool(re.fullmatch(r"[a-z][a-z0-9_]*", normalized))

    def unique(self, values: Iterable[str]) -> list[str]:
        """Return non-empty string values once, preserving first-seen order."""
        return self._unique_strings(values)

    def _extract_ids(self, texts: Sequence[str], pattern: re.Pattern[str]) -> list[str]:
        return self._unique_strings(
            match.group("value").rstrip("\"'")
            for text in texts
            for match in pattern.finditer(text)
        )

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values

    def _unique_ints(self, values: Iterable[int]) -> list[int]:
        unique_values: list[int] = []
        seen: set[int] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values
