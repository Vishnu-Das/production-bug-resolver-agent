"""Python AST-aware code chunking with line-window fallback."""

from __future__ import annotations

import ast

from bug_resolver.retrieval.code_chunker import CodeChunk, SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFile


class PythonASTCodeChunker:
    """Split Python files into symbol chunks and delegate other files to fallback."""

    def __init__(self, fallback_chunker: SimpleCodeChunker | None = None) -> None:
        self.fallback_chunker = fallback_chunker or SimpleCodeChunker()

    def chunk_file(self, code_file: CodeFile) -> list[CodeChunk]:
        if code_file.extension.lower() != ".py":
            return self.fallback_chunker.chunk_file(code_file)

        try:
            module = ast.parse(code_file.content)
        except SyntaxError:
            return self.fallback_chunker.chunk_file(code_file)

        lines = code_file.content.splitlines()
        chunks: list[CodeChunk] = []

        for node in module.body:
            if isinstance(node, ast.ClassDef):
                chunks.append(
                    self._build_chunk(
                        code_file=code_file,
                        lines=lines,
                        node=node,
                        symbol_name=node.name,
                        symbol_type="class",
                    )
                )
                chunks.extend(
                    self._method_chunks(
                        code_file=code_file,
                        lines=lines,
                        class_node=node,
                    )
                )
                continue

            if isinstance(node, ast.AsyncFunctionDef):
                chunks.append(
                    self._build_chunk(
                        code_file=code_file,
                        lines=lines,
                        node=node,
                        symbol_name=node.name,
                        symbol_type="async_function",
                    )
                )
                continue

            if isinstance(node, ast.FunctionDef):
                chunks.append(
                    self._build_chunk(
                        code_file=code_file,
                        lines=lines,
                        node=node,
                        symbol_name=node.name,
                        symbol_type="function",
                    )
                )

        if not chunks:
            return self.fallback_chunker.chunk_file(code_file)

        return chunks

    def chunk_files(self, code_files: list[CodeFile]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []

        for code_file in code_files:
            chunks.extend(self.chunk_file(code_file))

        return chunks

    def _method_chunks(
        self,
        *,
        code_file: CodeFile,
        lines: list[str],
        class_node: ast.ClassDef,
    ) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []

        for child in class_node.body:
            if isinstance(child, ast.AsyncFunctionDef):
                chunks.append(
                    self._build_chunk(
                        code_file=code_file,
                        lines=lines,
                        node=child,
                        symbol_name=child.name,
                        symbol_type="async_method",
                        parent_symbol=class_node.name,
                    )
                )
                continue

            if isinstance(child, ast.FunctionDef):
                chunks.append(
                    self._build_chunk(
                        code_file=code_file,
                        lines=lines,
                        node=child,
                        symbol_name=child.name,
                        symbol_type="method",
                        parent_symbol=class_node.name,
                    )
                )

        return chunks

    def _build_chunk(
        self,
        *,
        code_file: CodeFile,
        lines: list[str],
        node: ast.AST,
        symbol_name: str,
        symbol_type: str,
        parent_symbol: str | None = None,
    ) -> CodeChunk:
        line_start = self._line_start(node)
        line_end = self._line_end(node)
        qualified_symbol = f"{parent_symbol}.{symbol_name}" if parent_symbol else symbol_name
        snippet = "\n".join(lines[line_start - 1 : line_end]).strip()

        metadata = {
            "extension": code_file.extension,
            "symbol_name": symbol_name,
            "symbol_type": symbol_type,
            "qualified_symbol": qualified_symbol,
        }

        if parent_symbol:
            metadata["parent_symbol"] = parent_symbol

        return CodeChunk(
            chunk_id=f"{code_file.relative_path}:{qualified_symbol}",
            file_path=code_file.file_path,
            relative_path=code_file.relative_path,
            snippet=snippet,
            line_start=line_start,
            line_end=line_end,
            language="python",
            metadata=metadata,
        )

    def _line_start(self, node: ast.AST) -> int:
        line_numbers = [getattr(node, "lineno", 1)]

        for decorator in getattr(node, "decorator_list", []):
            line_numbers.append(getattr(decorator, "lineno", line_numbers[0]))

        return min(line_numbers)

    def _line_end(self, node: ast.AST) -> int:
        return getattr(node, "end_lineno", getattr(node, "lineno", 1))
