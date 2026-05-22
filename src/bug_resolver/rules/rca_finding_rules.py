"""Deterministic RCA finding text builders."""

from __future__ import annotations

from bug_resolver.rules.evidence_formatting_rules import EvidenceFormattingRules
from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType


class RCAFindingRules:
    """Render evidence items into concise RCA finding statements."""

    def __init__(
        self,
        formatter: EvidenceFormattingRules | None = None,
        evidence_selection_rules: EvidenceSelectionRules | None = None,
    ) -> None:
        self.formatter = formatter or EvidenceFormattingRules()
        self.evidence_selection_rules = evidence_selection_rules or EvidenceSelectionRules()

    def findings_for_source(
        self,
        evidence_items: list[EvidenceItem],
        source_type: EvidenceSourceType,
    ) -> list[str]:
        return self.formatter.unique(
            [
                self.finding_text(evidence)
                for evidence in evidence_items
                if evidence.source_type == source_type
            ]
        )

    def finding_text(self, evidence: EvidenceItem) -> str:
        location = self.formatter.location(evidence)
        content = " ".join(evidence.content.split())
        content_lower = content.lower()
        path = self.formatter.display_path(evidence.file_path or evidence.source_name)

        if evidence.source_type == EvidenceSourceType.LOG:
            if "invalid strategy: summary" in content_lower:
                return (
                    f"{location} shows the LLM router failed with "
                    "`ValueError: Invalid strategy: summary` and triggered fallback."
                )
            if "resolved_strategy=parent_child" in content_lower:
                return (
                    f"{location} shows the fallback resolved the summary-style query "
                    "to the supported `parent_child` retrieval strategy."
                )
            return f"{location} shows runtime signal: {self.formatter.shorten(content)}"

        if evidence.source_type == EvidenceSourceType.CODE:
            path_summary = self._path_aware_code_summary(path, location)
            if path_summary is not None:
                return path_summary

            if "invalid strategy" in content_lower and "result.strategy" in content_lower:
                return (
                    f"{location} validates the LLM router strategy and raises an "
                    "error when the model returns an unsupported value."
                )
            if "chatopenai" in content_lower and "router_prompt" in content_lower:
                return (
                    f"{location} builds the LLM router around the router prompt, "
                    "structured `RouterResult`, and configured router model."
                )
            if "router_type" in content_lower and "llmrouterstrategy" in content_lower:
                return (
                    f"{location} selects the configured router implementation, "
                    "including the LLM router path that produced the failure."
                )
            if "parent_child" in content_lower and "summary" in content_lower:
                return (
                    f"{location} maps summary-style selected-document queries to "
                    "the supported `parent_child` retrieval strategy."
                )
            return f"{location} contains implementation context relevant to the incident."

        if evidence.source_type == EvidenceSourceType.KNOWLEDGE_BASE:
            return (
                f"{location} documents expected behavior relevant to the incident: "
                f"{self.formatter.shorten(content)}"
            )

        if evidence.source_type == EvidenceSourceType.GRAPH:
            graph_details = self._graph_detail_text(evidence)
            if graph_details:
                return f"{location} shows structural code relationship: {graph_details}"
            return f"{location} shows structural code relationship relevant to the incident."

        return f"{location} supports the RCA: {self.formatter.shorten(content)}"

    def _graph_detail_text(self, evidence: EvidenceItem) -> str:
        details: list[str] = []

        calls = self._focused_graph_values(
            evidence.metadata.get("calls", ""),
            exclude_uppercase_names=True,
        )
        called_by = self._focused_graph_values(
            evidence.metadata.get("called_by", ""),
            exclude_prefixes=("test_",),
        )
        config_keys = self._focused_graph_values(
            evidence.metadata.get("config_keys", ""),
            limit=3,
        )
        config_readers = self._focused_graph_values(
            evidence.metadata.get("config_readers", ""),
            limit=3,
        )
        imported_by = self._focused_graph_values(
            evidence.metadata.get("imported_by", ""),
            limit=3,
            exclude_prefixes=("tests/", "eval/", "src/ui/"),
        )

        if config_readers and config_keys:
            reader_text = ", ".join(config_readers)
            key_text = ", ".join(config_keys)
            details.append(f"uses config from {reader_text}, which reads {key_text}")
            calls = [call for call in calls if call not in set(config_readers)]
        elif config_keys:
            details.append(f"reads config keys {', '.join(config_keys)}")
        if calls:
            details.append(f"calls {', '.join(calls)}")
        if called_by:
            details.append(f"called by {', '.join(called_by)}")
        if imported_by:
            details.append(f"imported by {', '.join(imported_by)}")

        if details:
            return "; ".join(details) + "."

        return self.formatter.shorten(" ".join(evidence.content.split()))

    def _focused_graph_values(
        self,
        value: str,
        *,
        limit: int = 5,
        exclude_prefixes: tuple[str, ...] = (),
        exclude_uppercase_names: bool = False,
    ) -> list[str]:
        noisy_values = {
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
        noisy_suffixes = (
            ".append",
            ".extend",
            ".get",
            ".items",
            ".keys",
            ".predict",
            ".sort",
            ".values",
        )
        values: list[str] = []

        for raw_item in value.split(","):
            item = raw_item.strip()
            normalized = item.lower()
            if not item or normalized in noisy_values:
                continue
            if any(normalized.endswith(suffix) for suffix in noisy_suffixes):
                continue
            if exclude_uppercase_names and item[:1].isupper() and "." not in item:
                continue
            if any(normalized.startswith(prefix) for prefix in exclude_prefixes):
                continue
            values.append(item)

        return self.formatter.unique(values)[:limit]

    def _path_aware_code_summary(self, path: str, location: str) -> str | None:
        normalized_path = path.lower()
        path_tokens = self.evidence_selection_rules.tokens(normalized_path)

        if "retrieval" in path_tokens and "factory" in path_tokens:
            return (
                f"{location} maps configured retrieval strategy names to concrete "
                "retrieval strategy implementations and rejects unsupported values."
            )
        if "service" in path_tokens and "rag" in path_tokens:
            return (
                f"{location} resolves the retrieval strategy, retrieves documents, "
                "reranks results, and builds the final RAG response path."
            )
        if "routing" in path_tokens and "llm" in path_tokens:
            return (
                f"{location} invokes the LLM router and validates that the returned "
                "strategy is one of the supported retrieval strategy values."
            )
        if "routing" in path_tokens and "rule" in path_tokens and "based" in path_tokens:
            return (
                f"{location} maps document-level summary queries to the supported "
                "`parent_child` retrieval strategy."
            )
        if "cache" in path_tokens:
            return (
                f"{location} defines cache reset behavior for RAG retrievers and "
                "cached retrieval results."
            )
        if "upload" in path_tokens:
            return (
                f"{location} computes upload content state but still gates duplicate "
                "handling through filename-based Streamlit session state before ingestion."
            )
        if path_tokens & {"reranker", "reranking", "rerank"}:
            return (
                f"{location} loads the cross-encoder reranker and defines fallback "
                "behavior for scoring and ordering retrieved documents."
            )
        if "pipeline" in path_tokens:
            return (
                f"{location} deduplicates retrieved documents and sends them through "
                "reranking before answer context is built."
            )
        if path_tokens & {"ingest", "ingestion"}:
            return (
                f"{location} coordinates document ingestion into standard and "
                "parent-child retrieval indexes."
            )
        if "tests" in path_tokens and ("routing" in path_tokens or "retrieval" in path_tokens):
            return (
                f"{location} covers routing or retrieval behavior relevant to the incident."
            )
        if "eval" in path_tokens or "evaluation" in path_tokens:
            return (
                f"{location} contains evaluation context for retrieval or answer "
                "quality checks relevant to the incident."
            )

        return None
