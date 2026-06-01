"""Deterministic authorization rules for evidence-backed patch targets."""

from __future__ import annotations

from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType


class PatchEvidenceAuthorizationRules:
    """Identify source files that direct code evidence can safely authorize."""

    _DIRECT_RETRIEVAL_SOURCE_TYPES = {"code_exact", "file_context"}
    _SUPPORTING_RETRIEVAL_SOURCE_TYPES = {
        "code_graph",
        "code_semantic",
        "code_structural",
    }
    _SOURCE_EXTENSIONS = (".py", ".js", ".ts", ".tsx", ".jsx")
    _SOURCE_PREFIXES = ("src/", "app/", "services/", "lib/")

    def __init__(self, code_path_rules: CodeEvidencePathRules | None = None) -> None:
        self._code_path_rules = code_path_rules or CodeEvidencePathRules()

    def direct_source_paths(self, evidence_items: list[EvidenceItem]) -> list[str]:
        """Return implementation files backed by exact or file-context evidence."""
        return self._unique(
            [
                path
                for evidence in evidence_items
                if self._is_direct_source_evidence(evidence)
                if (path := self._source_path(evidence)) is not None
                and not self._code_path_rules.is_support_path(path)
            ]
        )

    def supporting_context_paths(self, evidence_items: list[EvidenceItem]) -> list[str]:
        """Return structural or semantic source paths that may inform a patch."""
        return self._unique(
            [
                path
                for evidence in evidence_items
                if self._is_supporting_context(evidence)
                if (path := self._source_path(evidence)) is not None
            ]
        )

    def _is_direct_source_evidence(self, evidence: EvidenceItem) -> bool:
        return (
            evidence.source_type == EvidenceSourceType.CODE
            and evidence.metadata.get("retrieval_source_type")
            in self._DIRECT_RETRIEVAL_SOURCE_TYPES
        )

    def _is_supporting_context(self, evidence: EvidenceItem) -> bool:
        return (
            evidence.source_type == EvidenceSourceType.GRAPH
            or evidence.metadata.get("retrieval_source_type")
            in self._SUPPORTING_RETRIEVAL_SOURCE_TYPES
        )

    def _source_path(self, evidence: EvidenceItem) -> str | None:
        value = evidence.file_path or evidence.source_name
        path = self._normalize_path(value)
        if not path.startswith(self._SOURCE_PREFIXES):
            return None
        if not path.endswith(self._SOURCE_EXTENSIONS):
            return None
        return path

    def _normalize_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").strip().removeprefix("./")

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
