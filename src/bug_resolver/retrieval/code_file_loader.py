from pathlib import Path
from pydantic import Field

from bug_resolver.schemas.common import StrictBaseModel


SUPPORTED_CODE_EXTENSIONS = {
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
}


class CodeFile(StrictBaseModel):
    file_path: str = Field(..., min_length=1)
    relative_path: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    extension: str = Field(..., min_length=1)


class CodeFileLoader:
    def __init__(
        self,
        repo_path: str | Path,
        supported_extensions: set[str] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.supported_extensions = supported_extensions or SUPPORTED_CODE_EXTENSIONS

    def load_files(self) -> list[CodeFile]:
        if not self.repo_path.exists():
            return []

        code_files: list[CodeFile] = []

        for file_path in self.repo_path.rglob("*"):
            if self._should_skip(file_path):
                continue

            content = file_path.read_text(encoding="utf-8")

            if not content.strip():
                continue

            code_files.append(
                CodeFile(
                    file_path=str(file_path),
                    relative_path=str(file_path.relative_to(self.repo_path)),
                    content=content,
                    extension=file_path.suffix.lower(),
                )
            )

        return code_files

    def _should_skip(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return True

        if file_path.suffix.lower() not in self.supported_extensions:
            return True

        ignored_parts = {
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "node_modules",
            "dist",
            "build",
        }

        return any(part in ignored_parts for part in file_path.parts)