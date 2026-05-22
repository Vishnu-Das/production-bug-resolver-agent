"""Internal symbol record used by Python AST graph providers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SymbolRecord:
    """A Python symbol plus structural relationships discovered from AST."""

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
