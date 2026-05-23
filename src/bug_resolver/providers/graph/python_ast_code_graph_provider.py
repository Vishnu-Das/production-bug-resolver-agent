"""Local Python AST code graph provider for structural code evidence."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.providers.graph.base import CodeGraphProvider
from bug_resolver.providers.graph.code_graph_ranking_rules import CodeGraphRankingRules
from bug_resolver.providers.graph.code_graph_relationship_builder import (
    CodeGraphRelationshipBuilder,
)
from bug_resolver.providers.graph.python_ast_symbol_extractor import PythonASTSymbolExtractor
from bug_resolver.providers.graph.symbol_record import SymbolRecord
from bug_resolver.retrieval.code_file_loader import CodeFileLoader
from bug_resolver.schemas import CodeGraphContext


class PythonASTCodeGraphProvider(CodeGraphProvider):
    """
    Build and search a lightweight in-memory Python AST graph.

    The provider coordinates file loading, symbol extraction, relationship
    attachment, ranking, and context conversion. It intentionally avoids
    external graph databases.
    """

    def __init__(
        self,
        repo_path: str | Path,
        *,
        symbol_extractor: PythonASTSymbolExtractor | None = None,
        relationship_builder: CodeGraphRelationshipBuilder | None = None,
        ranking_rules: CodeGraphRankingRules | None = None,
    ) -> None:
        self._file_loader = CodeFileLoader(
            repo_path,
            supported_extensions={".py"},
        )
        self._symbol_extractor = symbol_extractor or PythonASTSymbolExtractor()
        self._relationship_builder = relationship_builder or CodeGraphRelationshipBuilder()
        self._ranking_rules = ranking_rules or CodeGraphRankingRules()
        self._symbols: list[SymbolRecord] | None = None

    async def search_graph(
        self,
        queries: list[str],
        *,
        limit: int = 5,
    ) -> list[CodeGraphContext]:
        if not queries:
            return []

        symbols = self._load_symbols()
        query_text = " ".join(queries)
        query_tokens = self._ranking_rules.query_tokens(query_text)
        if not query_tokens:
            return []

        scored_symbols = [
            (self._ranking_rules.score_symbol(symbol, query_tokens, query_text), symbol)
            for symbol in symbols
        ]
        ranked_symbols = [
            symbol
            for score, symbol in sorted(
                scored_symbols,
                key=lambda item: (
                    item[0],
                    bool(item[1].called_by),
                    bool(item[1].calls),
                    item[1].relative_path,
                    item[1].qualified_symbol,
                ),
                reverse=True,
            )
            if score > 0
        ]
        top_symbols = self._ranking_rules.prefer_primary_symbols(
            ranked_symbols,
            query_tokens,
        )[:limit]

        return [
            self._to_context(
                symbol=symbol,
                query=query_text,
                relevance_score=self._ranking_rules.score_symbol(
                    symbol,
                    query_tokens,
                    query_text,
                ),
            )
            for symbol in top_symbols
        ]

    def _load_symbols(self) -> list[SymbolRecord]:
        if self._symbols is None:
            self._symbols = self._symbol_extractor.extract_symbols(
                self._file_loader.load_files()
            )
            self._relationship_builder.attach_relationships(self._symbols)
        return self._symbols

    def _to_context(
        self,
        *,
        symbol: SymbolRecord,
        query: str,
        relevance_score: float,
    ) -> CodeGraphContext:
        content = self._content_summary(symbol)
        return CodeGraphContext(
            context_id=symbol.context_id,
            file_path=symbol.file_path,
            relative_path=symbol.relative_path,
            symbol_name=symbol.symbol_name,
            symbol_type=symbol.symbol_type,
            qualified_symbol=symbol.qualified_symbol,
            line_start=symbol.line_start,
            line_end=symbol.line_end,
            calls=sorted(symbol.calls),
            called_by=sorted(symbol.called_by),
            imports=sorted(symbol.imports),
            imported_by=sorted(symbol.imported_by),
            config_keys=sorted(symbol.config_keys),
            config_readers=sorted(symbol.config_readers),
            content=content,
            retrieval_query=query,
            relevance_score=min(relevance_score / 12, 1.0),
            metadata={"provider": "python_ast_code_graph"},
        )

    def _content_summary(self, symbol: SymbolRecord) -> str:
        parts = [
            (
                f"{symbol.relative_path}:{symbol.qualified_symbol} is a "
                f"{symbol.symbol_type} at lines {symbol.line_start}-{symbol.line_end}."
            )
        ]

        if symbol.calls:
            parts.append(f"Calls: {', '.join(sorted(symbol.calls))}.")
        if symbol.called_by:
            parts.append(f"Called by: {', '.join(sorted(symbol.called_by))}.")
        if symbol.config_keys:
            parts.append(f"Reads config keys: {', '.join(sorted(symbol.config_keys))}.")
        if symbol.config_readers:
            parts.append(
                "Config readers: "
                f"{', '.join(sorted(symbol.config_readers))}."
            )
        if symbol.imports:
            parts.append(f"Imports: {', '.join(sorted(symbol.imports))}.")

        return " ".join(parts)
