"""Local Python AST code graph provider for structural code evidence."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from bug_resolver.providers.graph.base import CodeGraphProvider
from bug_resolver.retrieval.code_file_loader import CodeFile, CodeFileLoader
from bug_resolver.rules.code_evidence_path_rules import CodeEvidencePathRules
from bug_resolver.schemas import CodeGraphContext


TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


@dataclass
class _SymbolRecord:
    file_path: str
    relative_path: str
    symbol_name: str
    symbol_type: str
    qualified_symbol: str
    line_start: int
    line_end: int
    snippet: str
    calls: set[str] = field(default_factory=set)
    called_by: set[str] = field(default_factory=set)
    imports: set[str] = field(default_factory=set)
    imported_by: set[str] = field(default_factory=set)
    config_keys: set[str] = field(default_factory=set)
    config_readers: set[str] = field(default_factory=set)
    module_dependency_calls: set[str] = field(default_factory=set)

    @property
    def context_id(self) -> str:
        return f"{self.relative_path}:{self.qualified_symbol}"


class PythonASTCodeGraphProvider(CodeGraphProvider):
    """
    Build and search a lightweight in-memory Python AST graph.

    The provider intentionally avoids external graph databases. It extracts
    symbols, function/method calls, module imports, and config/env-var reads
    from local Python files and ranks them deterministically against queries.
    """

    def __init__(self, repo_path: str | Path) -> None:
        self._file_loader = CodeFileLoader(
            repo_path,
            supported_extensions={".py"},
        )
        self._path_rules = CodeEvidencePathRules()
        self._symbols: list[_SymbolRecord] | None = None

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
        query_tokens = self._tokens(query_text)
        if not query_tokens:
            return []

        scored_symbols = [
            (self._score_symbol(symbol, query_tokens, query_text), symbol)
            for symbol in symbols
        ]
        top_symbols = [
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
        ][:limit]

        return [
            self._to_context(
                symbol=symbol,
                query=query_text,
                relevance_score=self._score_symbol(symbol, query_tokens, query_text),
            )
            for symbol in top_symbols
        ]

    def _load_symbols(self) -> list[_SymbolRecord]:
        if self._symbols is None:
            self._symbols = self._build_symbols(self._file_loader.load_files())
        return self._symbols

    def _build_symbols(self, code_files: list[CodeFile]) -> list[_SymbolRecord]:
        symbols: list[_SymbolRecord] = []

        for code_file in code_files:
            try:
                module = ast.parse(code_file.content)
            except SyntaxError:
                continue

            imports = self._module_imports(module)
            module_assignment_calls = self._module_assignment_calls(module)
            lines = code_file.content.splitlines()

            for node in module.body:
                if isinstance(node, ast.ClassDef):
                    symbols.append(
                        self._symbol_from_node(
                            code_file=code_file,
                            lines=lines,
                            node=node,
                            symbol_name=node.name,
                            symbol_type="class",
                            imports=imports,
                            module_assignment_calls=module_assignment_calls,
                        )
                    )
                    for child in node.body:
                        if isinstance(child, ast.AsyncFunctionDef):
                            symbols.append(
                                self._symbol_from_node(
                                    code_file=code_file,
                                    lines=lines,
                                    node=child,
                                    symbol_name=child.name,
                                    symbol_type="async_method",
                                    imports=imports,
                                    module_assignment_calls=module_assignment_calls,
                                    parent_symbol=node.name,
                                )
                            )
                        if isinstance(child, ast.FunctionDef):
                            symbols.append(
                                self._symbol_from_node(
                                    code_file=code_file,
                                    lines=lines,
                                    node=child,
                                    symbol_name=child.name,
                                    symbol_type="method",
                                    imports=imports,
                                    module_assignment_calls=module_assignment_calls,
                                    parent_symbol=node.name,
                                )
                            )
                    continue

                if isinstance(node, ast.AsyncFunctionDef):
                    symbols.append(
                        self._symbol_from_node(
                            code_file=code_file,
                            lines=lines,
                            node=node,
                            symbol_name=node.name,
                            symbol_type="async_function",
                            imports=imports,
                            module_assignment_calls=module_assignment_calls,
                        )
                    )
                    continue

                if isinstance(node, ast.FunctionDef):
                    symbols.append(
                        self._symbol_from_node(
                            code_file=code_file,
                            lines=lines,
                            node=node,
                            symbol_name=node.name,
                            symbol_type="function",
                            imports=imports,
                            module_assignment_calls=module_assignment_calls,
                        )
                    )

        self._attach_reverse_relationships(symbols)
        return symbols

    def _module_imports(self, module: ast.Module) -> set[str]:
        imports: set[str] = set()

        for node in module.body:
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
                imports.update(f"{node.module}.{alias.name}" for alias in node.names)

        return imports

    def _module_assignment_calls(self, module: ast.Module) -> dict[str, set[str]]:
        assignments: dict[str, set[str]] = {}

        for node in module.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None

            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value

            if value is None or not isinstance(value, ast.Call):
                continue

            call_name = self._call_name(value.func)
            if not call_name:
                continue

            for target in targets:
                target_name = self._assignment_target_name(target)
                if target_name:
                    assignments.setdefault(target_name, set()).add(call_name)

        return assignments

    def _assignment_target_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, (ast.Tuple, ast.List)):
            names = [
                self._assignment_target_name(element)
                for element in node.elts
            ]
            return next((name for name in names if name), None)

        return None

    def _symbol_from_node(
        self,
        *,
        code_file: CodeFile,
        lines: list[str],
        node: ast.AST,
        symbol_name: str,
        symbol_type: str,
        imports: set[str],
        module_assignment_calls: dict[str, set[str]],
        parent_symbol: str | None = None,
    ) -> _SymbolRecord:
        line_start = self._line_start(node)
        line_end = self._line_end(node)
        qualified_symbol = f"{parent_symbol}.{symbol_name}" if parent_symbol else symbol_name
        snippet = "\n".join(lines[line_start - 1 : line_end]).strip()

        return _SymbolRecord(
            file_path=code_file.file_path,
            relative_path=code_file.relative_path.replace("\\", "/"),
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            qualified_symbol=qualified_symbol,
            line_start=line_start,
            line_end=line_end,
            snippet=snippet,
            calls=self._calls(node),
            imports=imports,
            config_keys=self._config_keys(node),
            module_dependency_calls=self._module_dependency_calls(
                node,
                module_assignment_calls,
            ),
        )

    def _calls(self, node: ast.AST) -> set[str]:
        calls: set[str] = set()

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            call_name = self._call_name(child.func)
            if call_name:
                calls.add(call_name)

        return calls

    def _config_keys(self, node: ast.AST) -> set[str]:
        config_keys: set[str] = set()

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            call_name = self._call_name(child.func)
            if call_name not in {"getenv", "os.getenv", "os.environ.get"}:
                continue

            if child.args and isinstance(child.args[0], ast.Constant):
                value = child.args[0].value
                if isinstance(value, str) and value:
                    config_keys.add(value)

        config_keys.update(self._uppercase_names(node))
        return config_keys

    def _uppercase_names(self, node: ast.AST) -> set[str]:
        config_names: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name) and child.id.isupper() and len(child.id) > 2:
                config_names.add(child.id)

        return config_names

    def _module_dependency_calls(
        self,
        node: ast.AST,
        module_assignment_calls: dict[str, set[str]],
    ) -> set[str]:
        dependency_calls: set[str] = set()

        for child in ast.walk(node):
            if not isinstance(child, ast.Name):
                continue
            dependency_calls.update(module_assignment_calls.get(child.id, set()))

        return dependency_calls

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            parent = self._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr

        if isinstance(node, ast.Subscript):
            return self._call_name(node.value)

        return None

    def _attach_reverse_relationships(self, symbols: list[_SymbolRecord]) -> None:
        by_name: dict[str, list[_SymbolRecord]] = {}
        by_import_name: dict[str, list[_SymbolRecord]] = {}

        for symbol in symbols:
            by_name.setdefault(symbol.symbol_name, []).append(symbol)
            by_name.setdefault(symbol.qualified_symbol, []).append(symbol)

            module_name = Path(symbol.relative_path).with_suffix("").as_posix().replace("/", ".")
            by_import_name.setdefault(module_name, []).append(symbol)

        for caller in symbols:
            for call in caller.calls:
                call_leaf = call.rsplit(".", maxsplit=1)[-1]
                for callee in by_name.get(call_leaf, []):
                    if callee is caller:
                        continue
                    callee.called_by.add(caller.qualified_symbol)
                    caller.config_keys.update(callee.config_keys)
                    if callee.config_keys:
                        caller.config_readers.add(callee.qualified_symbol)
                    caller.config_readers.update(callee.config_readers)

            for dependency_call in caller.module_dependency_calls:
                call_leaf = dependency_call.rsplit(".", maxsplit=1)[-1]
                for callee in by_name.get(call_leaf, []):
                    if callee is caller:
                        continue
                    caller.config_keys.update(callee.config_keys)
                    if callee.config_keys:
                        caller.config_readers.add(callee.qualified_symbol)
                    caller.config_readers.update(callee.config_readers)

            for imported_module in caller.imports:
                for imported_symbol in by_import_name.get(imported_module, []):
                    if imported_symbol is caller:
                        continue
                    imported_symbol.imported_by.add(caller.relative_path)

    def _score_symbol(
        self,
        symbol: _SymbolRecord,
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
        haystack_tokens = self._tokens(haystack)
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

    def _to_context(
        self,
        *,
        symbol: _SymbolRecord,
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

    def _content_summary(self, symbol: _SymbolRecord) -> str:
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

    def _line_start(self, node: ast.AST) -> int:
        line_numbers = [getattr(node, "lineno", 1)]
        for decorator in getattr(node, "decorator_list", []):
            line_numbers.append(getattr(decorator, "lineno", line_numbers[0]))
        return min(line_numbers)

    def _line_end(self, node: ast.AST) -> int:
        return getattr(node, "end_lineno", getattr(node, "lineno", 1))

    def _tokens(self, value: str) -> set[str]:
        tokens: set[str] = set()
        for token in TOKEN_PATTERN.findall(value.lower()):
            tokens.add(token)
            if "_" in token:
                tokens.update(part for part in token.split("_") if part)
        return tokens
