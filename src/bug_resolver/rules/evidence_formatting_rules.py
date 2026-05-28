"""Shared evidence display and text formatting helpers."""

from __future__ import annotations

from pathlib import PureWindowsPath

from bug_resolver.schemas import EvidenceItem, EvidenceSourceType


class EvidenceFormattingRules:
    """Format evidence paths, symbols, and reusable evidence text."""

    def shorten(self, value: str, *, max_length: int = 180) -> str:
        if len(value) <= max_length:
            return value
        return value[: max_length - 3].rstrip() + "..."

    def location(self, evidence: EvidenceItem) -> str:
        location = self.display_path(evidence.file_path or evidence.source_name)
        symbol = self.symbol_name(evidence)
        if symbol:
            return f"{location}:{symbol}"

        if evidence.line_start and evidence.line_end:
            return f"{location}:{evidence.line_start}-{evidence.line_end}"
        return location

    def symbol_name(self, evidence: EvidenceItem) -> str | None:
        if evidence.source_type not in {EvidenceSourceType.CODE, EvidenceSourceType.GRAPH}:
            return None

        qualified_symbol = evidence.metadata.get("qualified_symbol")
        if qualified_symbol:
            return qualified_symbol

        class_name = evidence.metadata.get("class_name")
        function_name = evidence.metadata.get("function_name")

        if class_name and function_name:
            return f"{class_name}.{function_name}"

        return function_name or class_name

    def display_path(self, path: str) -> str:
        normalized_path = path.replace("\\", "/")
        for marker in ("/src/", "/tests/", "/eval/", "/docs/", "/sample_data/"):
            if marker in normalized_path:
                return f"{marker.strip('/')}/{normalized_path.split(marker, 1)[1]}"

        if ":" in path or "\\" in path:
            windows_parts = PureWindowsPath(path).parts
            for anchor in ("src", "tests", "eval", "docs", "sample_data"):
                if anchor in windows_parts:
                    return "/".join(windows_parts[windows_parts.index(anchor) :])

        return normalized_path

    def combined_text(self, evidence_items: list[EvidenceItem]) -> str:
        values: list[str] = []

        for evidence in evidence_items:
            values.extend(
                [
                    evidence.evidence_id,
                    evidence.source_name,
                    evidence.content,
                    evidence.file_path or "",
                ]
            )

            values.extend(str(value) for value in evidence.metadata.values())

        return "\n".join(value for value in values if value)

    def locations_matching(
        self,
        evidence_items: list[EvidenceItem],
        *,
        source_type: EvidenceSourceType,
        patterns: list[str],
    ) -> list[str]:
        normalized_patterns = [pattern.lower() for pattern in patterns]
        locations: list[str] = []

        for evidence in evidence_items:
            if evidence.source_type != source_type:
                continue

            location = self.location(evidence)
            normalized_location = location.lower()

            if any(pattern in normalized_location for pattern in normalized_patterns):
                locations.append(location)

        return self.unique(locations)

    def unique(self, values: list[str] | object) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = value.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(normalized)

        return unique_values
