"""Utilities for splitting source files into line-aware retrieval chunks."""

from pydantic import Field

from bug_resolver.retrieval.code_file_loader import CodeFile
from bug_resolver.schemas.common import StrictBaseModel


class CodeChunk(StrictBaseModel):
    """Line-aware source snippet prepared for embedding and retrieval."""

    chunk_id: str = Field(..., min_length=1)
    file_path: str = Field(..., min_length=1)
    relative_path: str = Field(..., min_length=1)
    snippet: str = Field(..., min_length=1)
    line_start: int = Field(..., ge=1)
    line_end: int = Field(..., ge=1)
    language: str = Field(..., min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class SimpleCodeChunker:
    """Split loaded source files into overlapping fixed-size chunks."""

    def __init__(
        self,
        max_lines_per_chunk: int = 80,
        overlap_lines: int = 10,
    ) -> None:
        if max_lines_per_chunk <= 0:
            raise ValueError("max_lines_per_chunk must be greater than 0")

        if overlap_lines < 0:
            raise ValueError("overlap_lines cannot be negative")

        if overlap_lines >= max_lines_per_chunk:
            raise ValueError("overlap_lines must be smaller than max_lines_per_chunk")

        self.max_lines_per_chunk = max_lines_per_chunk
        self.overlap_lines = overlap_lines

    def chunk_file(self, code_file: CodeFile) -> list[CodeChunk]:
        lines = code_file.content.splitlines()

        if not lines:
            return []

        chunks: list[CodeChunk] = []
        start_index = 0
        chunk_number = 1

        while start_index < len(lines):
            end_index = min(start_index + self.max_lines_per_chunk, len(lines))
            chunk_lines = lines[start_index:end_index]
            snippet = "\n".join(chunk_lines).strip()

            if snippet:
                line_start = start_index + 1
                line_end = end_index

                chunks.append(
                    CodeChunk(
                        chunk_id=f"{code_file.relative_path}:{line_start}-{line_end}",
                        file_path=code_file.file_path,
                        relative_path=code_file.relative_path,
                        snippet=snippet,
                        line_start=line_start,
                        line_end=line_end,
                        language=self._detect_language(code_file.extension),
                        metadata={
                            "extension": code_file.extension,
                            "chunk_number": str(chunk_number),
                        },
                    )
                )

                chunk_number += 1

            if end_index == len(lines):
                break

            start_index = end_index - self.overlap_lines

        return chunks

    def chunk_files(self, code_files: list[CodeFile]) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []

        for code_file in code_files:
            chunks.extend(self.chunk_file(code_file))

        return chunks

    def _detect_language(self, extension: str) -> str:
        extension_to_language = {
            ".py": "python",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
        }

        return extension_to_language.get(extension, "text")
