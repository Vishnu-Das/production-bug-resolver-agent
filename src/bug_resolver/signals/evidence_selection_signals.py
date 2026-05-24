"""Signal expansion profiles used for selecting RCA evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalProfile:
    """Configurable domain signal expansion profile."""

    name: str
    triggers: frozenset[str]
    expansions: frozenset[str]


DEFAULT_SIGNAL_PROFILES = (
    SignalProfile(
        name="upload_dedup",
        triggers=frozenset(
            {
                "upload",
                "uploads",
                "uploaded",
                "duplicate",
                "duplicates",
                "dedupe",
                "deduplication",
                "content_hash",
                "filename",
                "filenames",
                "ingest",
                "ingestion",
                "pdf",
                "citation",
                "citations",
            }
        ),
        expansions=frozenset(
            {
                "upload",
                "uploaded",
                "duplicate",
                "dedup",
                "deduplication",
                "content_hash",
                "content",
                "hash",
                "filename",
                "file",
                "ingest",
                "ingestion",
                "citation",
                "citations",
                "processed_uploads",
            }
        ),
    ),
    SignalProfile(
        name="reranking",
        triggers=frozenset(
            {
                "reranker",
                "reranking",
                "rerank",
                "ranked",
                "ranking",
                "scores",
                "score",
                "order_changed",
                "hybrid",
                "relevance",
            }
        ),
        expansions=frozenset(
            {
                "reranker",
                "reranking",
                "rerank",
                "ranking",
                "ranked",
                "scores",
                "score",
                "order_changed",
                "ordering",
                "hybrid",
                "retrieval",
                "relevance",
                "reranking_model_name",
                "model",
                "config",
                "configuration",
                "fallback",
                "source",
                "sources",
            }
        ),
    ),
    SignalProfile(
        name="summary_routing",
        triggers=frozenset(
            {
                "summary",
                "summarize",
                "overview",
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


DEFAULT_STOPWORDS = frozenset(
    {
        "a",
        "after",
        "and",
        "are",
        "as",
        "but",
        "by",
        "conversational",
        "conversational_rag",
        "document",
        "documents",
        "for",
        "from",
        "in",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "rag",
        "retrieval",
        "service",
        "strategies",
        "strategy",
        "that",
        "the",
        "their",
        "this",
        "to",
        "with",
        "without",
        "users",
    }
)

