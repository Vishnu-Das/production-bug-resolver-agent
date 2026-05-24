"""Signals used when rendering deterministic RCA finding text."""

from __future__ import annotations

from dataclasses import dataclass


NOISY_GRAPH_VALUES = {
    "dict",
    "float",
    "int",
    "len",
    "list",
    "round",
    "set",
    "str",
    "time.perf_counter",
    "traceable",
    "zip",
    "doc.metadata.get",
    "logger.debug",
    "logger.error",
    "logger.info",
    "logger.warning",
    "ranked_documents.sort",
    "reranker_model.predict",
    "scored_docs.sort",
    "st.error",
    "st.warning",
}

NOISY_GRAPH_SUFFIXES = (
    ".append",
    ".extend",
    ".get",
    ".items",
    ".keys",
    ".predict",
    ".sort",
    ".values",
)


@dataclass(frozen=True)
class PathSummarySignal:
    """Path-token signal for deterministic finding summaries."""

    required_terms: frozenset[str]
    any_terms: frozenset[str]
    summary_template: str

    def matches(self, path_tokens: set[str]) -> bool:
        return self.required_terms <= path_tokens and (
            not self.any_terms or bool(path_tokens & self.any_terms)
        )


PATH_SUMMARY_SIGNALS = (
    PathSummarySignal(
        required_terms=frozenset({"retrieval", "factory"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} maps configured retrieval strategy names to concrete "
            "retrieval strategy implementations and rejects unsupported values."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"service", "rag"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} resolves the retrieval strategy, retrieves documents, "
            "reranks results, and builds the final RAG response path."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"routing", "llm"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} invokes the LLM router and validates that the returned "
            "strategy is one of the supported retrieval strategy values."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"routing", "rule", "based"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} maps document-level summary queries to the supported "
            "`parent_child` retrieval strategy."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"cache"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} defines cache reset behavior for RAG retrievers and "
            "cached retrieval results."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"upload"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} computes upload content state but still gates duplicate "
            "handling through filename-based Streamlit session state before ingestion."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset(),
        any_terms=frozenset({"reranker", "reranking", "rerank"}),
        summary_template=(
            "{location} loads the cross-encoder reranker and defines fallback "
            "behavior for scoring and ordering retrieved documents."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"pipeline"}),
        any_terms=frozenset(),
        summary_template=(
            "{location} deduplicates retrieved documents and sends them through "
            "reranking before answer context is built."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset(),
        any_terms=frozenset({"ingest", "ingestion"}),
        summary_template=(
            "{location} coordinates document ingestion into standard and "
            "parent-child retrieval indexes."
        ),
    ),
    PathSummarySignal(
        required_terms=frozenset({"tests"}),
        any_terms=frozenset({"routing", "retrieval"}),
        summary_template="{location} covers routing or retrieval behavior relevant to the incident.",
    ),
    PathSummarySignal(
        required_terms=frozenset(),
        any_terms=frozenset({"eval", "evaluation"}),
        summary_template=(
            "{location} contains evaluation context for retrieval or answer "
            "quality checks relevant to the incident."
        ),
    ),
)
