"""Incident-grounded query planning rules for Code RAG searches."""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

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
DOCKERFILE_PATTERN = re.compile(r"\b(?:Dockerfile|docker-compose\.ya?ml)\b")

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
TEST_MODE_TERMS = frozenset({"assert", "coverage", "fixture", "pytest", "test", "tests"})
TEST_IDENTIFIER_PREFIXES = ("assert", "mock", "pytest", "test", "unittest")
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

CodeQueryMode = Literal["implementation", "test", "config", "all"]


@dataclass(frozen=True)
class CodeQueryPacket:
    """A focused code-search query scoped to one retrieval mode."""

    mode: CodeQueryMode
    query: str
    purpose: str


@dataclass(frozen=True)
class CodeSearchPlan:
    """Mode-aware search plan built from incident and collected evidence."""

    packets: tuple[CodeQueryPacket, ...]

    def queries(self, mode: CodeQueryMode = "all") -> list[str]:
        """Return de-duplicated query text for the requested mode."""
        selected_queries = [
            packet.query
            for packet in self.packets
            if mode == "all" or packet.mode in {mode, "all"}
        ]
        return self._unique(selected_queries)

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


DEFAULT_MAX_IMPLEMENTATION_QUERIES = 30


class CodeQueryRules:
    """Build focused Code RAG query packets from incident and evidence facts."""

    def __init__(
        self,
        *,
        stopwords: Collection[str] = DEFAULT_QUERY_STOPWORDS,
        max_implementation_queries: int = DEFAULT_MAX_IMPLEMENTATION_QUERIES,
    ) -> None:
        self.stopwords = frozenset(stopwords)
        self.max_implementation_queries = max_implementation_queries

    def enrich_queries(
        self,
        decision: AgentDecision,
        *,
        evidence_items: list[EvidenceItem] | None = None,
        mode: CodeQueryMode = "all",
    ) -> list[str]:
        """Return deterministic code-search queries for compatibility callers."""
        return self.build_search_plan(decision, evidence_items=evidence_items).queries(mode)

    def build_search_plan(
        self,
        decision: AgentDecision,
        *,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> CodeSearchPlan:
        """Return focused query packets without vocabulary expansion."""
        base_queries = self._base_queries(decision)
        base_text = " ".join([*base_queries, decision.reason])
        base_tokens = self._tokens(base_text)
        relevant_evidence = self._runtime_evidence(evidence_items or [], base_tokens)
        implementation_evidence = [
            evidence
            for evidence in relevant_evidence
            if self._can_seed_implementation_query(evidence)
        ]
        implementation_evidence_text = self._evidence_text(implementation_evidence)
        all_evidence_text = self._evidence_text(relevant_evidence)
        combined_text = " ".join([base_text, implementation_evidence_text])
        all_search_text = " ".join([base_text, all_evidence_text])
        config_tokens = self.extract_config_keys(combined_text)
        symbol_tokens = self.extract_exact_identifiers(
            combined_text,
            mode="implementation",
        )
        file_references = self._file_references(combined_text)
        implementation_file_references = {
            file_reference
            for file_reference in file_references
            if not self._is_support_reference(file_reference)
        }
        owner_terms = self._owner_domain_terms(self._tokens(combined_text))
        packets: list[CodeQueryPacket] = []

        for query in base_queries:
            implementation_query = self._sanitize_implementation_query(query)
            if implementation_query:
                packets.append(
                    CodeQueryPacket(
                        mode="implementation",
                        query=implementation_query,
                        purpose="incident_owner",
                    )
                )

        if owner_terms:
            packets.append(
                CodeQueryPacket(
                    mode="implementation",
                    query=" ".join(sorted(owner_terms)),
                    purpose="owner_domain_terms",
                )
            )

        for identifier in sorted(symbol_tokens):
            packets.append(
                CodeQueryPacket(
                    mode="implementation",
                    query=identifier,
                    purpose="exact_identifiers",
                )
            )

        for evidence_query in self._evidence_queries(implementation_evidence):
            packets.append(
                CodeQueryPacket(
                    mode="implementation",
                    query=evidence_query,
                    purpose="runtime_evidence",
                )
            )

        if config_tokens:
            packets.append(
                CodeQueryPacket(
                    mode="config",
                    query=" ".join(sorted(config_tokens | {"config", "configuration"})),
                    purpose="config_keys",
                )
            )

        if implementation_file_references:
            packets.append(
                CodeQueryPacket(
                    mode="implementation",
                    query=" ".join(sorted(implementation_file_references)),
                    purpose="file_references",
                )
            )

        all_tokens = self._tokens(all_search_text)
        if self._query_mentions_tests(all_tokens):
            packets.append(
                CodeQueryPacket(
                    mode="test",
                    query=" ".join(sorted(all_tokens & TEST_MODE_TERMS)),
                    purpose="test_surface",
                )
            )

        if self._query_mentions_config(all_tokens | config_tokens):
            config_terms = all_tokens & CONFIG_MODE_TERMS
            if file_references:
                config_terms = config_terms | {
                    path
                    for path in file_references
                    if self._looks_like_config_reference(path)
                }
            if config_terms:
                packets.append(
                    CodeQueryPacket(
                        mode="config",
                        query=" ".join(sorted(config_terms)),
                        purpose="config_surface",
                    )
                )

        unique_packets = self._unique_packets(packets)
        return CodeSearchPlan(tuple(self._cap_implementation_packets(unique_packets)))

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
            evidence_text = " ".join(
                [
                    evidence.source_name,
                    evidence.file_path or "",
                    evidence.content,
                    *evidence.metadata.values(),
                ]
            )
            terms = self._owner_domain_terms(self._tokens(evidence_text))
            identifiers = self.extract_exact_identifiers(
                evidence_text,
                mode="implementation",
            )
            query = self._sanitize_implementation_query(" ".join(sorted(terms | identifiers)))
            if query:
                queries.append(query)
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
        return bool(evidence_tokens & (base_tokens - self.stopwords))

    def extract_exact_identifiers(
        self,
        value: str,
        *,
        mode: CodeQueryMode = "all",
    ) -> set[str]:
        """Return exact source-like identifiers from incident and evidence text."""
        identifiers = (
            self.extract_config_keys(value)
            | self._symbol_like_tokens(value)
            | self._file_references(value)
        )
        if mode == "implementation":
            return {
                identifier
                for identifier in identifiers
                if not self._is_support_identifier(identifier)
            }
        return identifiers

    def extract_config_keys(self, value: str) -> set[str]:
        """Return uppercase config keys without lowercasing or splitting them."""
        return set(CONFIG_TOKEN_PATTERN.findall(value))

    def _tokens(self, value: str) -> set[str]:
        raw_tokens = set(re.findall(r"[a-z0-9_]+", value.lower()))
        split_tokens = {
            part
            for token in raw_tokens
            for part in token.split("_")
            if part
        }
        return raw_tokens | split_tokens

    def _symbol_like_tokens(self, value: str) -> set[str]:
        symbols = set()
        for token in SYMBOL_TOKEN_PATTERN.findall(value):
            lowered = token.lower()
            if "_" not in token and not token.isupper():
                continue
            if lowered in {"request_id", "trace_id"}:
                continue
            if lowered in self.stopwords:
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
        references = {
            file_reference.replace("\\", "/")
            for file_reference in FILE_REFERENCE_PATTERN.findall(value)
        }
        references.update(DOCKERFILE_PATTERN.findall(value))
        return references

    def _can_seed_implementation_query(self, evidence: EvidenceItem) -> bool:
        if evidence.source_type == EvidenceSourceType.LOG:
            return True

        path = evidence.file_path or evidence.source_name
        if self._is_support_reference(path):
            return False

        return evidence.source_type in {
            EvidenceSourceType.KNOWLEDGE_BASE,
            EvidenceSourceType.GRAPH,
        }

    def _sanitize_implementation_query(self, query: str) -> str:
        kept_terms: list[str] = []
        for term in query.split():
            stripped = term.strip()
            if not stripped:
                continue
            if self._is_support_identifier(stripped):
                continue
            kept_terms.append(stripped)
        return " ".join(kept_terms)

    def _is_support_identifier(self, value: str) -> bool:
        normalized = value.replace("\\", "/").strip().lower()
        if not normalized:
            return False
        if self._is_support_reference(normalized):
            return True
        normalized_name = normalized.rsplit("/", maxsplit=1)[-1]
        return normalized_name.startswith(TEST_IDENTIFIER_PREFIXES)

    def _is_support_reference(self, value: str) -> bool:
        normalized = value.replace("\\", "/").strip().lower()
        if not normalized:
            return False

        path_parts = [part for part in normalized.split("/") if part]
        name = path_parts[-1] if path_parts else normalized
        return (
            any(part in {"test", "tests", "eval", "examples", "notebooks"} for part in path_parts)
            or name.startswith("test_")
            or name.endswith("_test.py")
            or name.endswith(".ipynb")
        )

    def _owner_domain_terms(self, tokens: set[str]) -> set[str]:
        terms = {
            token
            for token in tokens
            if not self._is_support_identifier(token)
            and token not in self.stopwords
            and len(token) > 2
            and not token.isdigit()
        }
        if len(terms) <= 18:
            return terms

        exact_terms = {token for token in terms if "_" in token or "." in token}
        remaining = sorted(terms - exact_terms)
        return set(sorted(exact_terms)[:18]) | set(remaining[: max(0, 18 - len(exact_terms))])

    def _query_mentions_tests(self, tokens: set[str]) -> bool:
        return bool(tokens & TEST_MODE_TERMS)

    def _query_mentions_config(self, tokens: set[str]) -> bool:
        return bool(tokens & CONFIG_MODE_TERMS) or any(token.isupper() for token in tokens)

    def _looks_like_config_reference(self, path: str) -> bool:
        normalized = path.replace("\\", "/").lower()
        return (
            normalized.endswith((".toml", ".json", ".yaml", ".yml", ".env", ".ini", ".cfg"))
            or normalized in {"dockerfile", ".env.example", "docker-compose.yml"}
            or "/config/" in f"/{normalized}"
            or "/settings/" in f"/{normalized}"
        )

    def _unique_packets(self, packets: list[CodeQueryPacket]) -> list[CodeQueryPacket]:
        unique_packets: list[CodeQueryPacket] = []
        seen: set[tuple[str, str]] = set()

        for packet in packets:
            normalized_query = " ".join(packet.query.split())
            if not normalized_query:
                continue
            key = (packet.mode, normalized_query)
            if key in seen:
                continue
            seen.add(key)
            unique_packets.append(
                CodeQueryPacket(
                    mode=packet.mode,
                    query=normalized_query,
                    purpose=packet.purpose,
                )
            )

        return unique_packets

    def _cap_implementation_packets(
        self,
        packets: list[CodeQueryPacket],
    ) -> list[CodeQueryPacket]:
        if self.max_implementation_queries <= 0:
            return packets

        implementation_packets = [
            packet for packet in packets if packet.mode == "implementation"
        ]
        if len(implementation_packets) <= self.max_implementation_queries:
            return packets

        selected_implementation_keys = {
            (packet.mode, packet.query)
            for packet in sorted(
                implementation_packets,
                key=self._packet_priority,
            )[: self.max_implementation_queries]
        }
        return [
            packet
            for packet in packets
            if packet.mode != "implementation"
            or (packet.mode, packet.query) in selected_implementation_keys
        ]

    def _packet_priority(self, packet: CodeQueryPacket) -> tuple[int, int, str]:
        purpose_order = {
            "incident_owner": 0,
            "owner_domain_terms": 1,
            "runtime_evidence": 2,
            "exact_identifiers": 3,
            "file_references": 4,
        }
        return (
            purpose_order.get(packet.purpose, 99),
            len(packet.query),
            packet.query,
        )
