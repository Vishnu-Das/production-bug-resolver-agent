"""Deterministic query enrichment rules for Code RAG searches."""

from __future__ import annotations

import re

from bug_resolver.schemas.evidence import EvidenceItem
from bug_resolver.schemas.common import EvidenceSourceType
from bug_resolver.schemas.orchestration import AgentDecision


CONFIG_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
SYMBOL_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")


class CodeQueryRules:
    """Build focused Code RAG queries from supervisor decisions and signal terms."""

    def enrich_queries(
        self,
        decision: AgentDecision,
        *,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> list[str]:
        """Return deterministic code-search queries with focused signal expansions."""
        evidence_text = self._evidence_text(evidence_items or [])
        base_queries = self._base_queries(decision)
        combined_text = " ".join([*base_queries, decision.reason, evidence_text])
        tokens = self._tokens(combined_text)
        config_tokens = self._config_tokens(combined_text)
        symbol_tokens = self._symbol_like_tokens(combined_text)
        enriched_queries = list(base_queries)

        for evidence_query in self._evidence_queries(evidence_items or []):
            enriched_queries.append(evidence_query)

        expansions = self._profile_expansions(tokens)
        if expansions:
            enriched_queries.append(" ".join(sorted(expansions | config_tokens | symbol_tokens)))

        if config_tokens:
            enriched_queries.append(" ".join(sorted(config_tokens | {"config", "configuration"})))

        if symbol_tokens:
            enriched_queries.append(" ".join(sorted(symbol_tokens)))

        return self._unique(enriched_queries)

    def _base_queries(self, decision: AgentDecision) -> list[str]:
        queries = [query.strip() for query in decision.queries if query.strip()]
        if queries:
            return queries

        return [decision.reason.strip()]

    def _evidence_text(self, evidence_items: list[EvidenceItem]) -> str:
        values: list[str] = []
        for evidence in self._runtime_evidence(evidence_items):
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
        for evidence in self._runtime_evidence(evidence_items):
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

    def _runtime_evidence(self, evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
        return [
            evidence
            for evidence in evidence_items
            if evidence.source_type == EvidenceSourceType.LOG
        ]

    def _profile_expansions(self, tokens: set[str]) -> set[str]:
        expansions: set[str] = set()

        if tokens & {
            "upload",
            "uploads",
            "uploaded",
            "duplicate",
            "duplicates",
            "dedupe",
            "deduplication",
            "content_hash",
            "filename",
            "processed_uploads",
            "duplicate_content_detected",
            "ingestion_started",
        }:
            expansions.update(
                {
                    "content_hash",
                    "content",
                    "hash",
                    "filename",
                    "dedupe",
                    "deduplication",
                    "duplicate",
                    "duplicate_content_detected",
                    "processed_uploads",
                    "upload",
                    "ingestion",
                    "handle_file_upload",
                }
            )

        if tokens & {
            "reranker",
            "reranking",
            "rerank",
            "reranker_model",
            "reranking_model_name",
            "order_changed",
            "scores",
            "score",
        }:
            expansions.update(
                {
                    "RERANKING_MODEL_NAME",
                    "reranker_model",
                    "reranker",
                    "reranking",
                    "rerank",
                    "rerank_documents",
                    "rerank_documents_with_scores",
                    "load_reranker",
                    "scores",
                    "order_changed",
                    "neutral",
                    "fallback",
                    "config",
                }
            )

        if tokens & {
            "summary",
            "summarize",
            "overview",
            "semantic_search",
            "document_summary",
            "parent_child",
        }:
            expansions.update(
                {
                    "summary",
                    "summarize",
                    "document_summary",
                    "semantic_search",
                    "parent_child",
                    "routing",
                    "router",
                    "retrieval",
                    "strategy",
                    "route",
                }
            )

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
        return symbols

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
