"""Patch-context providers used by analyze-only patch generation."""

from bug_resolver.providers.patches.base import PatchContextProvider
from bug_resolver.providers.patches.local_file_patch_context_provider import (
    LocalFilePatchContextProvider,
)

__all__ = [
    "LocalFilePatchContextProvider",
    "PatchContextProvider",
]
