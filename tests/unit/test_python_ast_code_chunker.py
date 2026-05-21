"""Tests for Python AST-aware source chunking."""

from bug_resolver.retrieval.code_chunker import SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFile
from bug_resolver.retrieval.python_ast_code_chunker import PythonASTCodeChunker


def make_code_file(content: str, *, relative_path: str = "app.py", extension: str = ".py") -> CodeFile:
    return CodeFile(
        file_path=f"/repo/{relative_path}",
        relative_path=relative_path,
        content=content,
        extension=extension,
    )


def test_python_ast_chunker_extracts_top_level_function_chunk() -> None:
    code_file = make_code_file(
        "\n".join(
            [
                "import os",
                "",
                "def handle_file_upload(file):",
                "    return file.name",
            ]
        )
    )

    chunks = PythonASTCodeChunker().chunk_file(code_file)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "app.py:handle_file_upload"
    assert chunks[0].line_start == 3
    assert chunks[0].line_end == 4
    assert chunks[0].metadata["symbol_name"] == "handle_file_upload"
    assert chunks[0].metadata["symbol_type"] == "function"


def test_python_ast_chunker_extracts_async_function_chunk() -> None:
    code_file = make_code_file(
        "\n".join(
            [
                "async def fetch_logs():",
                "    return []",
            ]
        )
    )

    chunks = PythonASTCodeChunker().chunk_file(code_file)

    assert chunks[0].chunk_id == "app.py:fetch_logs"
    assert chunks[0].metadata["symbol_type"] == "async_function"


def test_python_ast_chunker_extracts_class_chunk() -> None:
    code_file = make_code_file(
        "\n".join(
            [
                "class CrossEncoderReranker:",
                "    def rerank(self):",
                "        return []",
            ]
        )
    )

    chunks = PythonASTCodeChunker().chunk_file(code_file)
    class_chunk = next(chunk for chunk in chunks if chunk.metadata["symbol_type"] == "class")

    assert class_chunk.chunk_id == "app.py:CrossEncoderReranker"
    assert class_chunk.line_start == 1
    assert class_chunk.line_end == 3
    assert "class CrossEncoderReranker" in class_chunk.snippet


def test_python_ast_chunker_extracts_method_chunk_with_parent_metadata() -> None:
    code_file = make_code_file(
        "\n".join(
            [
                "class CrossEncoderReranker:",
                "    def rerank(self):",
                "        return []",
            ]
        )
    )

    chunks = PythonASTCodeChunker().chunk_file(code_file)
    method_chunk = next(chunk for chunk in chunks if chunk.metadata["symbol_type"] == "method")

    assert method_chunk.chunk_id == "app.py:CrossEncoderReranker.rerank"
    assert method_chunk.line_start == 2
    assert method_chunk.line_end == 3
    assert method_chunk.metadata["symbol_name"] == "rerank"
    assert method_chunk.metadata["parent_symbol"] == "CrossEncoderReranker"
    assert method_chunk.metadata["qualified_symbol"] == "CrossEncoderReranker.rerank"


def test_python_ast_chunker_includes_decorators_in_chunk() -> None:
    code_file = make_code_file(
        "\n".join(
            [
                "class UploadService:",
                "    @staticmethod",
                "    def validate_upload(file):",
                "        return bool(file)",
            ]
        )
    )

    chunks = PythonASTCodeChunker().chunk_file(code_file)
    method_chunk = next(chunk for chunk in chunks if chunk.metadata["symbol_type"] == "method")

    assert method_chunk.line_start == 2
    assert "@staticmethod" in method_chunk.snippet
    assert "def validate_upload" in method_chunk.snippet


def test_python_ast_chunker_falls_back_for_syntax_error_file() -> None:
    code_file = make_code_file(
        "def broken(:\n    pass\n",
        relative_path="broken.py",
    )
    chunker = PythonASTCodeChunker(
        fallback_chunker=SimpleCodeChunker(max_lines_per_chunk=10, overlap_lines=0)
    )

    chunks = chunker.chunk_file(code_file)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "broken.py:1-2"
    assert "symbol_type" not in chunks[0].metadata


def test_python_ast_chunker_falls_back_for_non_python_file() -> None:
    code_file = make_code_file(
        '{"reranker": true}',
        relative_path="config.json",
        extension=".json",
    )
    chunker = PythonASTCodeChunker(
        fallback_chunker=SimpleCodeChunker(max_lines_per_chunk=10, overlap_lines=0)
    )

    chunks = chunker.chunk_file(code_file)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "config.json:1-1"
    assert chunks[0].language == "json"
