"""Deterministic ranking rules for retrieved code contexts."""

from __future__ import annotations

import re

from pathlib import PurePosixPath

from bug_resolver.schemas.code_context import CodeContext


TEST_QUERY_TERMS = {
    "test",
    "tests",
    "pytest",
    "unittest",
    "regression",
    "assert",
}

CONFIG_QUERY_TERMS = {
    "config",
    "configuration",
    "settings",
    "env",
    "environment",
    "json",
    "yaml",
    "yml",
    "toml",
    "docker",
    "compose",
}

INIT_QUERY_TERMS = {
    "init",
    "__init__",
    "package",
    "export",
    "exports",
}

SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".cs",
}

CONFIG_EXTENSIONS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
}


class CodeContextRankingRules:
    """Rank FAISS code results for RCA-oriented implementation evidence."""

    def rank_contexts(
        self,
        contexts: list[CodeContext],
        queries: list[str],
        limit: int,
    ) -> list[CodeContext]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        query_text = " ".join(queries).lower()
        ranked_contexts = sorted(
            contexts,
            key=lambda context: self._sort_key(context, query_text),
        )

        deduplicated_contexts: list[CodeContext] = []

        for context in ranked_contexts:
            if self._overlaps_existing_context(context, deduplicated_contexts):
                continue

            deduplicated_contexts.append(context)

            if len(deduplicated_contexts) >= limit:
                break

        return deduplicated_contexts

    def _sort_key(self, context: CodeContext, query_text: str) -> tuple[float, str, int, str]:
        return (
            -self._ranking_score(context, query_text),
            self._normalized_path(context),
            context.line_start or 0,
            context.context_id,
        )

    def _ranking_score(self, context: CodeContext, query_text: str) -> float:
        score = context.relevance_score or 0.0
        path = self._normalized_path(context)

        if self._is_source_file(path) and not self._is_test_file(path):
            score += 0.15

        if self._is_test_file(path):
            if self._query_mentions(query_text, TEST_QUERY_TERMS):
                score += 0.10
            else:
                score -= 0.25

        if self._is_config_file(path):
            if self._query_mentions(query_text, CONFIG_QUERY_TERMS):
                score += 0.05
            else:
                score -= 0.30

        if self._is_init_file(path):
            if self._query_mentions(query_text, INIT_QUERY_TERMS):
                score += 0.05
            else:
                score -= 0.20

        return score

    def _overlaps_existing_context(
        self,
        context: CodeContext,
        existing_contexts: list[CodeContext],
    ) -> bool:
        return any(
            self._same_file(context, existing_context)
            and self._line_ranges_overlap(context, existing_context)
            for existing_context in existing_contexts
        )

    def _same_file(self, left: CodeContext, right: CodeContext) -> bool:
        return self._normalized_path(left) == self._normalized_path(right)

    def _line_ranges_overlap(self, left: CodeContext, right: CodeContext) -> bool:
        if (
            left.line_start is None
            or left.line_end is None
            or right.line_start is None
            or right.line_end is None
        ):
            return False

        return max(left.line_start, right.line_start) <= min(left.line_end, right.line_end)

    def _normalized_path(self, context: CodeContext) -> str:
        return context.file_path.replace("\\", "/").lower()

    def _is_source_file(self, path: str) -> bool:
        return PurePosixPath(path).suffix in SOURCE_EXTENSIONS

    def _is_test_file(self, path: str) -> bool:
        file_name = PurePosixPath(path).name
        return (
            "/tests/" in path
            or path.startswith("tests/")
            or file_name.startswith("test_")
            or file_name.endswith("_test.py")
        )

    def _is_config_file(self, path: str) -> bool:
        path_obj = PurePosixPath(path)
        return (
            path_obj.suffix in CONFIG_EXTENSIONS
            or path_obj.name in {"dockerfile", ".env", ".env.example"}
        )

    def _is_init_file(self, path: str) -> bool:
        return PurePosixPath(path).name == "__init__.py"

    def _query_mentions(self, query_text: str, terms: set[str]) -> bool:
        tokens = set(re.findall(r"[a-z0-9_]+", query_text.lower()))
        return bool(tokens & terms)
