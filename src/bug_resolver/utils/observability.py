"""Shared logging and optional LangSmith tracing helpers."""

from __future__ import annotations

import logging
import os
import json
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast


try:  # pragma: no cover - exercised only when langsmith is installed.
    from langsmith.run_helpers import traceable as _langsmith_traceable
except Exception:  # pragma: no cover - optional dependency behavior.
    _langsmith_traceable = None


FuncT = TypeVar("FuncT", bound=Callable[..., Any])

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReadableLogFormatter(logging.Formatter):
    """Human-friendly formatter with spacing and aligned metadata."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, DATE_FORMAT)
        logger_name = self._short_logger_name(record.name)
        header = f"{timestamp} | {record.levelname:<7} | {logger_name}"
        message = self._indent_message(record.getMessage())

        rendered = f"\n{header}\n  {message}"

        if record.exc_info:
            rendered = f"{rendered}\n{self._indent_message(self.formatException(record.exc_info))}"

        if record.stack_info:
            rendered = f"{rendered}\n{self._indent_message(record.stack_info)}"

        return rendered

    def _indent_message(self, message: str) -> str:
        return "\n  ".join(message.splitlines())

    def _short_logger_name(self, logger_name: str) -> str:
        return logger_name.removeprefix("bug_resolver.")


def configure_logging(
    *,
    debug: bool = False,
    log_level: str | None = None,
    log_dir: str | Path = "logs",
    log_file_name: str = "bug-resolver.log",
) -> Path:
    """Configure UTF-8 file logging for CLI runs and return the log path."""
    configured_level = log_level or os.getenv("LOG_LEVEL")
    if configured_level:
        level = logging.getLevelName(configured_level.upper())
        if not isinstance(level, int):
            level = logging.DEBUG if debug else logging.INFO
    else:
        level = logging.DEBUG if debug else logging.INFO

    log_path = Path(log_dir) / log_file_name
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.close()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setLevel(level)
    file_handler.setFormatter(ReadableLogFormatter())
    root_logger.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING if not debug else logging.INFO)
    logging.getLogger("openai").setLevel(logging.WARNING if not debug else logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return log_path


def configure_langsmith_tracing(
    *,
    enabled: bool,
    api_key: str = "",
    project: str = "",
    endpoint: str = "",
) -> bool:
    """Export LangSmith settings from AppSettings into process env.

    Pydantic reads .env values into AppSettings, but LangSmith checks os.environ.
    This bridge lets local .env configuration activate tracing for decorated runs.
    """
    if not enabled:
        return _env_flag_enabled("LANGSMITH_TRACING") or _env_flag_enabled(
            "LANGCHAIN_TRACING_V2"
        )

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"

    if api_key:
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGCHAIN_API_KEY"] = api_key

    if project:
        os.environ["LANGSMITH_PROJECT"] = project

    if endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = endpoint

    logger = get_logger(__name__)
    logger.info(
        "langsmith tracing configured enabled=true project=%s endpoint_configured=%s api_key_configured=%s",
        os.getenv("LANGSMITH_PROJECT", ""),
        bool(os.getenv("LANGSMITH_ENDPOINT")),
        bool(os.getenv("LANGSMITH_API_KEY")),
    )
    return True


def _env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the bug_resolver namespace."""
    return logging.getLogger(name)


def traceable(name: str, *, run_type: str = "chain") -> Callable[[FuncT], FuncT]:
    """Return a LangSmith trace decorator when available, otherwise a no-op."""
    if _langsmith_traceable is None:
        return _identity_decorator

    return cast(
        Callable[[FuncT], FuncT],
        _langsmith_traceable(name=name, run_type=run_type),
    )


def _identity_decorator(func: FuncT) -> FuncT:
    return func


def truncate(value: object, *, max_length: int = 500) -> str:
    """Return compact single-line text for log records."""
    text = " ".join(str(value).split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def truncate_multiline(value: str, *, max_length: int = 1200) -> str:
    """Return readable text with line breaks preserved and bounded length."""
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def format_debug_payload(payload: object, *, max_length: int = 1200) -> str:
    """Render structured debug payloads in a readable bounded format."""
    value = payload
    if hasattr(payload, "model_dump"):
        value = payload.model_dump(mode="json")  # type: ignore[attr-defined]

    try:
        rendered = json.dumps(value, indent=2, default=str)
    except TypeError:
        rendered = str(value)

    return truncate_multiline(rendered, max_length=max_length)


def log_debug_payload(
    logger: logging.Logger,
    message: str,
    *,
    payload: object,
    max_length: int = 1200,
) -> None:
    """Log verbose payload only when DEBUG logging is enabled."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "%s\n%s",
            message,
            format_debug_payload(payload, max_length=max_length),
        )


def log_async_call(name: str) -> Callable[[FuncT], FuncT]:
    """Log start/end/error around async functions without changing behavior."""

    def decorator(func: FuncT) -> FuncT:
        logger = get_logger(func.__module__)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.debug("%s started", name)
            try:
                result = await func(*args, **kwargs)
            except Exception:
                logger.exception("%s failed", name)
                raise
            logger.debug("%s finished", name)
            return result

        return cast(FuncT, wrapper)

    return decorator
