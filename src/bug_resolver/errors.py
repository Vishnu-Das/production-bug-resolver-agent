"""Project-level errors with user-facing recovery metadata."""

from __future__ import annotations

from typing import Any


class BugResolverError(Exception):
    """Base exception for errors that should be shown cleanly to users."""

    code = "bug_resolver_error"
    default_recoverable = False
    default_suggested_action = "Review the logs for more details."

    def __init__(
        self,
        message: str,
        *,
        component: str | None = None,
        recoverable: bool | None = None,
        suggested_action: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = self.__class__.code
        self.message = message
        self.component = component or self.__class__.__name__
        self.recoverable = (
            self.default_recoverable if recoverable is None else recoverable
        )
        self.suggested_action = suggested_action or self.default_suggested_action
        self.context = {
            str(key): str(value)
            for key, value in (context or {}).items()
            if value is not None
        }

    @property
    def user_message(self) -> str:
        return f"{self.component}: {self.message}"


class ConfigurationError(BugResolverError, ValueError):
    """Configuration is missing or invalid."""

    code = "configuration_error"
    default_suggested_action = "Check environment variables and configured paths."


class ProviderError(BugResolverError):
    """A local or external provider failed while loading context."""

    code = "provider_error"
    default_recoverable = True
    default_suggested_action = (
        "Check the provider configuration and rerun the investigation."
    )


class RetrievalError(ProviderError):
    """A retrieval/indexing provider failed."""

    code = "retrieval_error"
    default_suggested_action = (
        "Rebuild the retrieval index or check the target repository path."
    )


class LLMGenerationError(BugResolverError):
    """The LLM provider failed to return a usable response."""

    code = "llm_generation_error"
    default_suggested_action = (
        "Check the LLM provider credentials, model, and network connectivity."
    )


class EmbeddingGenerationError(RetrievalError):
    """The embedding provider failed to return embeddings."""

    code = "embedding_generation_error"
    default_suggested_action = (
        "Check embedding provider credentials, model, and network connectivity."
    )


class ReportWriteError(BugResolverError):
    """Report artifacts could not be persisted."""

    code = "report_write_error"
    default_suggested_action = "Check report output permissions and disk space."


class PatchGenerationSafetyError(BugResolverError):
    """Patch generation was blocked by a safety rule."""

    code = "patch_generation_safety_error"
    default_recoverable = True
    default_suggested_action = (
        "Gather source CODE evidence for the implementation owner before patching."
    )


def normalize_error(
    error: Exception,
    *,
    component: str,
    recoverable: bool | None = None,
    context: dict[str, Any] | None = None,
) -> BugResolverError:
    """Return a BugResolverError for workflow/reporting paths."""
    if isinstance(error, BugResolverError):
        if recoverable is None and not context:
            return error
        merged_context = {**error.context, **{str(k): str(v) for k, v in (context or {}).items()}}
        normalized = BugResolverError(
            error.message,
            component=error.component or component,
            recoverable=error.recoverable if recoverable is None else recoverable,
            suggested_action=error.suggested_action,
            context=merged_context,
        )
        normalized.code = error.code
        return normalized

    return BugResolverError(
        str(error),
        component=component,
        recoverable=False if recoverable is None else recoverable,
        context={
            "exception_type": type(error).__name__,
            **{str(k): str(v) for k, v in (context or {}).items()},
        },
    )
