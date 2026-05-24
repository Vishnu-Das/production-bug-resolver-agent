"""Signal profiles and mode terms used by code query planning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeQuerySignalProfile:
    """Configurable signal expansion profile for Code RAG queries."""

    name: str
    triggers: frozenset[str]
    expansions: frozenset[str]


DEFAULT_CODE_QUERY_SIGNAL_PROFILES = (
    CodeQuerySignalProfile(
        name="upload_dedup",
        triggers=frozenset(
            {
                "upload",
                "uploads",
                "uploaded",
                "duplicate",
                "duplicates",
                "dedupe",
                "dedup",
                "deduplication",
                "deduplicate",
                "content_hash",
                "filename",
                "filenames",
                "ingest",
                "ingestion",
                "document",
                "documents",
                "record",
                "records",
            }
        ),
        expansions=frozenset(
            {
                "content_hash",
                "content",
                "hash",
                "filename",
                "file",
                "files",
                "dedupe",
                "dedup",
                "deduplication",
                "deduplicate",
                "duplicate",
                "duplicates",
                "upload",
                "uploads",
                "uploaded",
                "service",
                "handler",
                "handle",
                "ingest",
                "ingestion",
                "document",
                "documents",
                "record",
                "records",
                "processed_uploads",
                "processed",
            }
        ),
    ),
    CodeQuerySignalProfile(
        name="reranking",
        triggers=frozenset(
            {
                "reranker",
                "reranking",
                "rerank",
                "rank",
                "ranking",
                "ranked",
                "scores",
                "score",
                "order_changed",
                "model",
                "config",
                "configuration",
            }
        ),
        expansions=frozenset(
            {
                "reranker",
                "reranking",
                "rerank",
                "rank",
                "ranking",
                "ranked",
                "scores",
                "score",
                "order_changed",
                "order",
                "ordering",
                "model",
                "config",
                "configuration",
                "fallback",
                "relevance",
            }
        ),
    ),
    CodeQuerySignalProfile(
        name="summary_routing",
        triggers=frozenset(
            {
                "summary",
                "summarize",
                "overview",
                "key_points",
                "semantic_search",
                "document_summary",
                "parent_child",
            }
        ),
        expansions=frozenset(
            {
                "summary",
                "summarize",
                "overview",
                "key",
                "points",
                "route",
                "routing",
                "router",
                "query",
                "document_summary",
                "semantic_search",
                "parent_child",
                "retrieval",
                "strategy",
            }
        ),
    ),
)


DEFAULT_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "after",
        "an",
        "and",
        "are",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "more",
        "need",
        "of",
        "on",
        "or",
        "the",
        "this",
        "to",
        "with",
    }
)

TEST_MODE_TERMS = frozenset(
    {
        "assert",
        "coverage",
        "fixture",
        "pytest",
        "regression",
        "test",
        "tests",
        "unittest",
    }
)

TEST_IDENTIFIER_PREFIXES = (
    "assert",
    "mock",
    "pytest",
    "test",
    "unittest",
)

CONFIG_MODE_TERMS = frozenset(
    {
        "compose",
        "config",
        "configuration",
        "docker",
        "env",
        "environment",
        "requirements",
        "setting",
        "settings",
        "toml",
        "yaml",
        "yml",
    }
)

