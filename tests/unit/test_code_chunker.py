import pytest

from bug_resolver.retrieval.code_chunker import SimpleCodeChunker
from bug_resolver.retrieval.code_file_loader import CodeFile


def test_simple_code_chunker_chunks_file_with_line_numbers():
    code_file = CodeFile(
        file_path="/repo/app.py",
        relative_path="app.py",
        content="\n".join(
            [
                "line 1",
                "line 2",
                "line 3",
                "line 4",
                "line 5",
            ]
        ),
        extension=".py",
    )

    chunker = SimpleCodeChunker(max_lines_per_chunk=3, overlap_lines=1)

    chunks = chunker.chunk_file(code_file)

    assert len(chunks) == 2

    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 3
    assert chunks[0].snippet == "line 1\nline 2\nline 3"
    assert chunks[0].language == "python"

    assert chunks[1].line_start == 3
    assert chunks[1].line_end == 5
    assert chunks[1].snippet == "line 3\nline 4\nline 5"


def test_simple_code_chunker_chunks_multiple_files():
    files = [
        CodeFile(
            file_path="/repo/a.py",
            relative_path="a.py",
            content="print('a')",
            extension=".py",
        ),
        CodeFile(
            file_path="/repo/README.py",
            relative_path="README.py",
            content="# README",
            extension=".py",
        ),
    ]

    chunker = SimpleCodeChunker()

    chunks = chunker.chunk_files(files)

    assert len(chunks) == 2
    assert chunks[0].language == "python"
    assert chunks[1].language == "python"


def test_simple_code_chunker_rejects_invalid_max_lines():
    with pytest.raises(ValueError, match="max_lines_per_chunk must be greater than 0"):
        SimpleCodeChunker(max_lines_per_chunk=0)


def test_simple_code_chunker_rejects_negative_overlap():
    with pytest.raises(ValueError, match="overlap_lines cannot be negative"):
        SimpleCodeChunker(overlap_lines=-1)


def test_simple_code_chunker_rejects_overlap_greater_than_max_lines():
    with pytest.raises(ValueError, match="overlap_lines must be smaller than max_lines_per_chunk"):
        SimpleCodeChunker(max_lines_per_chunk=10, overlap_lines=10)