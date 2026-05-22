"""Relationship wiring for AST-derived code graph symbols."""

from __future__ import annotations

from pathlib import Path

from bug_resolver.providers.graph.symbol_record import SymbolRecord


class CodeGraphRelationshipBuilder:
    """Attach reverse calls, imports, and config-reader relationships."""

    def attach_relationships(self, symbols: list[SymbolRecord]) -> None:
        by_name: dict[str, list[SymbolRecord]] = {}
        by_import_name: dict[str, list[SymbolRecord]] = {}

        for symbol in symbols:
            by_name.setdefault(symbol.symbol_name, []).append(symbol)
            by_name.setdefault(symbol.qualified_symbol, []).append(symbol)

            module_name = Path(symbol.relative_path).with_suffix("").as_posix().replace("/", ".")
            by_import_name.setdefault(module_name, []).append(symbol)

        for caller in symbols:
            self._attach_call_relationships(caller, by_name)
            self._attach_module_dependency_relationships(caller, by_name)
            self._attach_import_relationships(caller, by_import_name)

    def _attach_call_relationships(
        self,
        caller: SymbolRecord,
        by_name: dict[str, list[SymbolRecord]],
    ) -> None:
        for call in caller.calls:
            call_leaf = call.rsplit(".", maxsplit=1)[-1]
            for callee in by_name.get(call_leaf, []):
                if callee is caller:
                    continue
                callee.called_by.add(caller.qualified_symbol)
                self._inherit_config_reader(caller, callee)

    def _attach_module_dependency_relationships(
        self,
        caller: SymbolRecord,
        by_name: dict[str, list[SymbolRecord]],
    ) -> None:
        for dependency_call in caller.module_dependency_calls:
            call_leaf = dependency_call.rsplit(".", maxsplit=1)[-1]
            for callee in by_name.get(call_leaf, []):
                if callee is caller:
                    continue
                self._inherit_config_reader(caller, callee)

    def _attach_import_relationships(
        self,
        caller: SymbolRecord,
        by_import_name: dict[str, list[SymbolRecord]],
    ) -> None:
        for imported_module in caller.imports:
            for imported_symbol in by_import_name.get(imported_module, []):
                if imported_symbol is caller:
                    continue
                imported_symbol.imported_by.add(caller.relative_path)

    def _inherit_config_reader(self, caller: SymbolRecord, callee: SymbolRecord) -> None:
        caller.config_keys.update(callee.config_keys)
        if callee.config_keys:
            caller.config_readers.add(callee.qualified_symbol)
        caller.config_readers.update(callee.config_readers)
