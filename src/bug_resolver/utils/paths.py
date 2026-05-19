"""Path display helpers for converting local paths to repo-relative output."""

from __future__ import annotations


_REPO_MARKERS = (
    "src/",
    "tests/",
    "eval/",
    "docs/",
    "sample_data/",
    "README.md",
    "pyproject.toml",
)


def to_repo_relative_display_path(path: str | None) -> str:
    """Convert local/absolute paths to repo-relative display paths.

    This is for user-facing reports and prompts. It prevents leaking local
    machine paths like C:/Users/... into RCA/solution output.
    """
    if not path:
        return "unknown"

    normalized = path.replace("\\", "/").strip()

    for marker in _REPO_MARKERS:
        marker_index = normalized.find(marker)
        if marker_index >= 0:
            return normalized[marker_index:]

    return normalized
