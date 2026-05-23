"""Shared logging and optional LangSmith tracing helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast


try:  # pragma: no cover - exercised only when langsmith is installed.
    from langsmith.run_helpers import traceable as _langsmith_traceable
except Exception:  # pragma: no cover - optional dependency behavior.
    _langsmith_traceable = None


FuncT = TypeVar("FuncT", bound=Callable[..., Any])

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(*, debug: bool = False, log_level: str | None = None) -> None:
    """Configure application logging for CLI runs."""
    configured_level = log_level or os.getenv("LOG_LEVEL")
    if configured_level:
        level = logging.getLevelName(configured_level.upper())
        if not isinstance(level, int):
            level = logging.DEBUG if debug else logging.INFO
    else:
        level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        force=True,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING if not debug else logging.INFO)
    logging.getLogger("openai").setLevel(logging.WARNING if not debug else logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


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


def log_debug_payload(
    logger: logging.Logger,
    message: str,
    *,
    payload: object,
    max_length: int = 1200,
) -> None:
    """Log verbose payload only when DEBUG logging is enabled."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s %s", message, truncate(payload, max_length=max_length))


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
