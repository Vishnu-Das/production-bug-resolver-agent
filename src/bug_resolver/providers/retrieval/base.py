"""Provider protocols for incident-driven context retrieval routes."""

from typing import Protocol, runtime_checkable

from bug_resolver.schemas import (
    EvidenceCandidate,
    FileContextRequest,
    GraphExpansionRequest,
    RetrievalQuery,
)


@runtime_checkable
class FileContextProvider(Protocol):
    """Contract for reading source context around grounded file locations."""

    async def read_context(
        self,
        requests: list[FileContextRequest],
    ) -> list[EvidenceCandidate]:
        """Read source context for requested file locations."""
        ...


@runtime_checkable
class ExactSearchProvider(Protocol):
    """Contract for exact text search over target repository content."""

    async def search_exact(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Search for exact occurrences of grounded incident facts."""
        ...


@runtime_checkable
class StructuralSearchProvider(Protocol):
    """Contract for structural definition and usage search."""

    async def search_structure(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Search for structural definitions and usages."""
        ...


@runtime_checkable
class SemanticCodeSearchProvider(Protocol):
    """Contract for semantic code search."""

    async def search_semantic_code(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Search code using contextual incident descriptions."""
        ...


@runtime_checkable
class CodeGraphExpansionProvider(Protocol):
    """Contract for graph expansion around grounded code locations."""

    async def expand_context(
        self,
        requests: list[GraphExpansionRequest],
    ) -> list[EvidenceCandidate]:
        """Expand caller, callee, and relationship context."""
        ...


@runtime_checkable
class KnowledgeSearchProvider(Protocol):
    """Contract for knowledge-base and documentation search."""

    async def search_knowledge(
        self,
        queries: list[RetrievalQuery],
    ) -> list[EvidenceCandidate]:
        """Search documentation for expected behavior context."""
        ...
