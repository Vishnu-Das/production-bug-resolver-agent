"""Deterministic ranking rules for retrieved code contexts."""

from __future__ import annotations

import re

from pathlib import PurePosixPath
from typing import Literal

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
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

CodeContextMode = Literal["implementation", "test", "config", "all"]


class CodeContextRankingRules:
    """Rank FAISS code results for RCA-oriented implementation evidence."""

    def __init__(self, path_rules: CodeEvidencePathRules | None = None) -> None:
        self.path_rules = path_rules or CodeEvidencePathRules()

    def rank_contexts(
        self,
        contexts: list[CodeContext],
        queries: list[str],
        limit: int,
        mode: CodeContextMode | None = None,
    ) -> list[CodeContext]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        query_text = " ".join(queries).lower()
        query_tokens = self.path_rules.tokens(query_text)
        allow_support_surface = mode is None
        effective_mode = self._effective_mode(mode, query_text)
        ranked_contexts = sorted(
            contexts,
            key=lambda context: self._sort_key(
                context,
                query_text,
                query_tokens,
                effective_mode,
            ),
        )

        ranked_contexts = self._prefer_primary_contexts(
            ranked_contexts,
            query_text,
            query_tokens,
            effective_mode,
            allow_support_surface,
        )

        deduplicated_contexts: list[CodeContext] = []

        for context in ranked_contexts:
            if self._overlaps_existing_context(context, deduplicated_contexts):
                continue

            deduplicated_contexts.append(context)

            if len(deduplicated_contexts) >= limit:
                break

        return deduplicated_contexts

    def _sort_key(
        self,
        context: CodeContext,
        query_text: str,
        query_tokens: set[str],
        mode: CodeContextMode,
    ) -> tuple[float, str, int, str]:
        return (
            -self._ranking_score(context, query_text, query_tokens, mode),
            self._normalized_path(context),
            context.line_start or 0,
            context.context_id,
        )

    def _ranking_score(
        self,
        context: CodeContext,
        query_text: str,
        query_tokens: set[str],
        mode: CodeContextMode,
    ) -> float:
        score = context.relevance_score or 0.0
        path = self._normalized_path(context)

        if mode == "implementation":
            score += self._implementation_path_adjustment(path)
        elif mode == "test":
            score += self._test_path_adjustment(path)
        elif mode == "config":
            score += self._config_path_adjustment(path)
        elif self._is_source_file(path) and not self.path_rules.is_support_path(path):
            score += 0.10

        score += self._lexical_overlap_score(context, query_tokens)

        if mode == "implementation":
            score += self.path_rules.support_adjustment(
                path,
                query_tokens,
                penalty=-1.0,
                mention_bonus=0.12,
            )

        if mode != "config" and self._is_config_file(path):
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

    def _lexical_overlap_score(
        self,
        context: CodeContext,
        query_tokens: set[str],
    ) -> float:
        if not query_tokens:
            return 0.0

        path_tokens = self.path_rules.tokens(context.file_path)
        metadata_tokens = self.path_rules.tokens(
            " ".join(str(value) for value in context.metadata.values())
        )
        symbol_tokens = self.path_rules.tokens(
            " ".join(
                value
                for value in (context.class_name, context.function_name)
                if value
            )
        )
        snippet_tokens = self.path_rules.tokens(context.snippet)

        path_overlap = len(path_tokens & query_tokens) * 0.35
        symbol_overlap = len(symbol_tokens & query_tokens) * 0.45
        metadata_overlap = len(metadata_tokens & query_tokens) * 0.25
        snippet_overlap = min(len(snippet_tokens & query_tokens), 8) * 0.10

        return path_overlap + symbol_overlap + metadata_overlap + snippet_overlap

    def _prefer_primary_contexts(
        self,
        ranked_contexts: list[CodeContext],
        query_text: str,
        query_tokens: set[str],
        mode: CodeContextMode,
        allow_support_surface: bool,
    ) -> list[CodeContext]:
        if mode in {"test", "config", "all"}:
            return ranked_contexts

        if allow_support_surface and self._query_mentions_support_surface(query_tokens):
            return ranked_contexts

        primary_contexts = [
            context
            for context in ranked_contexts
            if self._is_primary_context(context, query_text)
        ]

        if not primary_contexts:
            return ranked_contexts

        return primary_contexts

    def _is_primary_context(self, context: CodeContext, query_text: str) -> bool:
        path = self._normalized_path(context)
        if self.path_rules.is_support_path(path):
            return False
        if self._is_config_file(path) and not self._query_mentions(query_text, CONFIG_QUERY_TERMS):
            return False
        if self._is_init_file(path) and not self._query_mentions(query_text, INIT_QUERY_TERMS):
            return False
        return True

    def _implementation_path_adjustment(self, path: str) -> float:
        score = 0.0
        if path.startswith(("src/", "app/", "services/", "lib/")):
            score += 0.35
        elif "/src/" in path or "/app/" in path or "/services/" in path or "/lib/" in path:
            score += 0.25
        elif self._is_source_file(path) and not self.path_rules.is_support_path(path):
            score += 0.15

        if path.startswith(("tests/", "test/", "eval/", "examples/", "notebooks/")):
            score -= 1.25
        elif any(
            marker in path
            for marker in ("/tests/", "/test/", "/eval/", "/examples/", "/notebooks/")
        ):
            score -= 1.0

        return score

    def _test_path_adjustment(self, path: str) -> float:
        if self._is_test_path(path):
            return 0.60
        if self._is_source_file(path) and not self.path_rules.is_support_path(path):
            return 0.05
        return -0.10

    def _config_path_adjustment(self, path: str) -> float:
        if self._is_config_file(path):
            return 0.70
        if self._is_source_file(path):
            return -0.20
        if self._is_config_directory(path):
            return 0.70
        return 0.0

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

    def _is_config_file(self, path: str) -> bool:
        path_obj = PurePosixPath(path)
        return (
            path_obj.suffix in CONFIG_EXTENSIONS
            or path_obj.name in {
                "dockerfile",
                ".env",
                ".env.example",
                "docker-compose.yml",
                "requirements.txt",
                "pyproject.toml",
                "readme.md",
            }
        )

    def _is_config_directory(self, path: str) -> bool:
        normalized = f"/{path.strip('/')}/"
        return any(
            marker in normalized
            for marker in ("/config/", "/configs/", "/settings/", "/docs/")
        )

    def _is_test_path(self, path: str) -> bool:
        path_obj = PurePosixPath(path)
        return (
            path.startswith(("tests/", "test/"))
            or "/tests/" in path
            or "/test/" in path
            or path_obj.name.startswith("test_")
            or path_obj.name.endswith("_test.py")
        )

    def _is_init_file(self, path: str) -> bool:
        return PurePosixPath(path).name == "__init__.py"

    def _query_mentions(self, query_text: str, terms: set[str]) -> bool:
        tokens = set(re.findall(r"[a-z0-9_]+", query_text.lower()))
        return bool(tokens & terms)

    def _query_mentions_support_surface(self, query_tokens: set[str]) -> bool:
        return any(
            query_tokens & role.query_terms
            for role in self.path_rules.support_roles
        )

    def _effective_mode(
        self,
        mode: CodeContextMode | None,
        query_text: str,
    ) -> CodeContextMode:
        if mode is not None:
            return mode

        if self._query_mentions(query_text, TEST_QUERY_TERMS):
            return "test"

        explicit_config_terms = CONFIG_QUERY_TERMS - {"config", "configuration"}
        if self._query_mentions(query_text, explicit_config_terms):
            return "config"

        return "implementation"
