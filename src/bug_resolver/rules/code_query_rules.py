"""Deterministic query enrichment rules for Code RAG searches."""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from bug_resolver.schemas.common import EvidenceSourceType
from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.orchestration import AgentDecision


CONFIG_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
SYMBOL_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")
FUNCTION_CALL_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
QUALIFIED_SYMBOL_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)\b"
)
FILE_REFERENCE_PATTERN = re.compile(
    r"\b[a-zA-Z0-9_./\\-]+\.(?:py|toml|json|yaml|yml|env|ini|cfg)\b"
)


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


class CodeQueryRules:
    """Build focused Code RAG queries from supervisor decisions and signal terms."""

    def __init__(
        self,
        *,
        signal_profiles: Sequence[CodeQuerySignalProfile] = (
            DEFAULT_CODE_QUERY_SIGNAL_PROFILES
        ),
        stopwords: Collection[str] = DEFAULT_QUERY_STOPWORDS,
    ) -> None:
        self.signal_profiles = tuple(signal_profiles)
        self.stopwords = frozenset(stopwords)

    def enrich_queries(
        self,
        decision: AgentDecision,
        *,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> list[str]:
        """Return deterministic code-search queries with focused signal expansions."""
        base_queries = self._base_queries(decision)
        base_text = " ".join([*base_queries, decision.reason])
        base_tokens = self._tokens(base_text)
        relevant_evidence = self._runtime_evidence(evidence_items or [], base_tokens)
        evidence_text = self._evidence_text(relevant_evidence)
        combined_text = " ".join([base_text, evidence_text])
        tokens = self._tokens(combined_text)
        config_tokens = self._config_tokens(combined_text)
        symbol_tokens = self._symbol_like_tokens(combined_text)
        file_references = self._file_references(combined_text)
        enriched_queries = list(base_queries)

        for evidence_query in self._evidence_queries(relevant_evidence):
            enriched_queries.append(evidence_query)

        expansions = self._profile_expansions(tokens)
        if expansions:
            enriched_queries.append(
                " ".join(sorted(expansions | config_tokens | symbol_tokens))
            )

        if config_tokens:
            enriched_queries.append(
                " ".join(sorted(config_tokens | {"config", "configuration"}))
            )

        if symbol_tokens:
            enriched_queries.append(" ".join(sorted(symbol_tokens)))

        if file_references:
            enriched_queries.append(" ".join(sorted(file_references)))

        return self._unique(enriched_queries)

    def _base_queries(self, decision: AgentDecision) -> list[str]:
        queries = [query.strip() for query in decision.queries if query.strip()]
        if queries:
            return queries

        return [decision.reason.strip()]

    def _evidence_text(self, evidence_items: list[EvidenceItem]) -> str:
        values: list[str] = []
        for evidence in evidence_items:
            values.extend(
                [
                    evidence.evidence_id,
                    evidence.source_name,
                    evidence.file_path or "",
                    evidence.content,
                    *evidence.metadata.values(),
                ]
            )

        return " ".join(value for value in values if value)

    def _evidence_queries(self, evidence_items: list[EvidenceItem]) -> list[str]:
        queries: list[str] = []
        for evidence in evidence_items:
            tokens = self._tokens(
                " ".join(
                    [
                        evidence.source_name,
                        evidence.file_path or "",
                        evidence.content,
                        *evidence.metadata.values(),
                    ]
                )
            )
            expansions = self._profile_expansions(tokens)
            if expansions:
                queries.append(" ".join(sorted(expansions)))

        return queries

    def _runtime_evidence(
        self,
        evidence_items: list[EvidenceItem],
        base_tokens: set[str],
    ) -> list[EvidenceItem]:
        return [
            evidence
            for evidence in evidence_items
            if self._should_use_evidence(evidence, base_tokens)
        ]

    def _should_use_evidence(
        self,
        evidence: EvidenceItem,
        base_tokens: set[str],
    ) -> bool:
        if evidence.source_type == EvidenceSourceType.LOG:
            return True

        if evidence.source_type not in {
            EvidenceSourceType.KNOWLEDGE_BASE,
            EvidenceSourceType.GRAPH,
        }:
            return False

        evidence_tokens = self._tokens(
            " ".join(
                [
                    evidence.source_name,
                    evidence.file_path or "",
                    evidence.content,
                    *evidence.metadata.values(),
                ]
            )
        )
        meaningful_base_tokens = base_tokens - self.stopwords

        if evidence_tokens & meaningful_base_tokens:
            return True

        base_expansions = self._profile_expansions(base_tokens)
        evidence_expansions = self._profile_expansions(evidence_tokens)
        return bool(base_expansions & evidence_expansions)

    def _profile_expansions(self, tokens: set[str]) -> set[str]:
        expansions: set[str] = set()

        for profile in self.signal_profiles:
            if tokens & profile.triggers:
                expansions.update(profile.expansions)

        return expansions

    def _tokens(self, value: str) -> set[str]:
        raw_tokens = set(re.findall(r"[a-z0-9_]+", value.lower()))
        split_tokens = {
            part
            for token in raw_tokens
            for part in token.split("_")
            if part
        }
        return raw_tokens | split_tokens

    def _config_tokens(self, value: str) -> set[str]:
        return set(CONFIG_TOKEN_PATTERN.findall(value))

    def _symbol_like_tokens(self, value: str) -> set[str]:
        symbols = set()
        for token in SYMBOL_TOKEN_PATTERN.findall(value):
            if "_" not in token:
                continue
            lowered = token.lower()
            if lowered in {"request_id"}:
                continue
            symbols.add(token)

        for function_name in FUNCTION_CALL_PATTERN.findall(value):
            if function_name in {"print", "len", "str", "int", "dict", "list", "set"}:
                continue
            symbols.add(function_name)

        for qualified_symbol in QUALIFIED_SYMBOL_PATTERN.findall(value):
            symbols.add(qualified_symbol)
            symbols.update(qualified_symbol.split("."))

        return symbols

    def _file_references(self, value: str) -> set[str]:
        return {
            file_reference.replace("\\", "/")
            for file_reference in FILE_REFERENCE_PATTERN.findall(value)
        }

    def _unique(self, queries: list[str]) -> list[str]:
        unique_queries: list[str] = []
        seen: set[str] = set()

        for query in queries:
            normalized = " ".join(query.split())
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_queries.append(normalized)

        return unique_queries
