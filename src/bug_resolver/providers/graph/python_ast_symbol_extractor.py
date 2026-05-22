"""Python AST symbol extraction for local code graph evidence."""

from __future__ import annotations

import ast

from bug_resolver.providers.graph.symbol_record import SymbolRecord
from bug_resolver.retrieval.code_file_loader import CodeFile


class PythonASTSymbolExtractor:
    """Extract top-level functions, classes, and methods from Python files."""

    def extract_symbols(self, code_files: list[CodeFile]) -> list[SymbolRecord]:
        symbols: list[SymbolRecord] = []

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
    ) -> SymbolRecord:
        line_start = self._line_start(node)
        line_end = self._line_end(node)
        qualified_symbol = f"{parent_symbol}.{symbol_name}" if parent_symbol else symbol_name
        snippet = "\n".join(lines[line_start - 1 : line_end]).strip()

        return SymbolRecord(
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

    def _line_start(self, node: ast.AST) -> int:
        line_numbers = [getattr(node, "lineno", 1)]
        for decorator in getattr(node, "decorator_list", []):
            line_numbers.append(getattr(decorator, "lineno", line_numbers[0]))
        return min(line_numbers)

    def _line_end(self, node: ast.AST) -> int:
        return getattr(node, "end_lineno", getattr(node, "lineno", 1))
