"""Deterministic RCA finding text builders."""

from __future__ import annotations

from bug_resolver.rules.evidence_formatting_rules import EvidenceFormattingRules
from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType

NOISY_GRAPH_VALUES = {
    "dict",
    "float",
    "int",
    "len",
    "list",
    "round",
    "set",
    "str",
    "traceable",
    "zip",
    "logger.debug",
    "logger.error",
    "logger.info",
    "logger.warning",
}
NOISY_GRAPH_SUFFIXES = (
    ".append",
    ".extend",
    ".get",
    ".items",
    ".keys",
    ".sort",
    ".values",
)


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

        if evidence.source_type == EvidenceSourceType.LOG:
            return f"{location} shows runtime evidence: {self.formatter.shorten(content)}"

        if evidence.source_type == EvidenceSourceType.CODE:
            symbol = evidence.metadata.get("qualified_symbol") or evidence.metadata.get(
                "function_name",
                "",
            )
            if symbol:
                return (
                    f"{location} contains source evidence for `{symbol}`: "
                    f"{self.formatter.shorten(content)}"
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

        if evidence.source_type == EvidenceSourceType.HISTORICAL_RCA:
            historical_incident_id = evidence.metadata.get("historical_incident_id", "prior")
            return (
                f"{location} describes similar prior incident {historical_incident_id}: "
                f"{self.formatter.shorten(content)}"
            )

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
        values: list[str] = []

        for raw_item in value.split(","):
            item = raw_item.strip()
            normalized = item.lower()
            if not item or normalized in NOISY_GRAPH_VALUES:
                continue
            if any(normalized.endswith(suffix) for suffix in NOISY_GRAPH_SUFFIXES):
                continue
            if exclude_uppercase_names and item[:1].isupper() and "." not in item:
                continue
            if any(normalized.startswith(prefix) for prefix in exclude_prefixes):
                continue
            values.append(item)

        return self.formatter.unique(values)[:limit]

