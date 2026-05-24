"""Deterministic ranking for AST-derived code graph symbols."""

from __future__ import annotations

import re

from bug_resolver.providers.graph.symbol_record import SymbolRecord
from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


class CodeGraphRankingRules:
    """Score symbols against structural graph queries."""

    def __init__(self, path_rules: CodeEvidencePathRules | None = None) -> None:
        self._path_rules = path_rules or CodeEvidencePathRules()

    def query_tokens(self, value: str) -> set[str]:
        tokens: set[str] = set()
        for token in TOKEN_PATTERN.findall(value.lower()):
            tokens.add(token)
            if "_" in token:
                tokens.update(part for part in token.split("_") if part)
        return tokens

    def score_symbol(
        self,
        symbol: SymbolRecord,
        query_tokens: set[str],
        query_text: str,
    ) -> float:
        haystack = " ".join(
            [
                symbol.relative_path,
                symbol.symbol_name,
                symbol.symbol_type,
                symbol.qualified_symbol,
                " ".join(symbol.calls),
                " ".join(symbol.called_by),
                " ".join(symbol.imports),
                " ".join(symbol.imported_by),
                " ".join(symbol.config_keys),
                " ".join(symbol.config_readers),
                symbol.snippet,
            ]
        )
        haystack_tokens = self.query_tokens(haystack)
        overlap = len(query_tokens & haystack_tokens)
        if overlap == 0:
            return 0.0

        score = float(overlap)
        lowered_query = query_text.lower()
        if symbol.symbol_name.lower() in lowered_query:
            score += 3.0
        if symbol.qualified_symbol.lower() in lowered_query:
            score += 4.0
        if any(config_key.lower() in lowered_query for config_key in symbol.config_keys):
            score += 3.0
        if symbol.called_by:
            score += 0.5
        if symbol.calls:
            score += 0.5
        if symbol.relative_path.startswith("src/"):
            score += 1.0

        score += self._path_rules.support_adjustment(
            symbol.relative_path,
            query_tokens,
            penalty=-6.0,
            mention_bonus=1.0,
        )

        return score

    def prefer_primary_symbols(
        self,
        ranked_symbols: list[SymbolRecord],
        query_tokens: set[str],
    ) -> list[SymbolRecord]:
        """Drop support symbols when primary implementation symbols are available."""
        if self._query_mentions_support_surface(query_tokens):
            return ranked_symbols

        primary_symbols = [
            symbol
            for symbol in ranked_symbols
            if not self._path_rules.is_support_path(symbol.relative_path)
        ]

        return primary_symbols or ranked_symbols

    def _query_mentions_support_surface(self, query_tokens: set[str]) -> bool:
        return any(
            query_tokens & role.query_terms
            for role in self._path_rules.support_roles
        )
