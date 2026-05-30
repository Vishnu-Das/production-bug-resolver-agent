"""Deterministic rules for incident-driven context retrieval planning."""

from __future__ import annotations

from collections.abc import Iterable

from bug_resolver.schemas import (
    FileContextRequest,
    GraphExpansionRequest,
    IncidentFacts,
    RetrievalAnchor,
    RetrievalPlan,
    RetrievalQuery,
)


class RetrievalPlanningRules:
    """Build repo-agnostic retrieval requests from grounded incident facts."""

    def build_plan(self, facts: IncidentFacts) -> RetrievalPlan:
        """Create a retrieval plan without executing any retrieval route."""
        return RetrievalPlan(
            anchors=self.build_anchors(facts),
            exact_queries=self.build_exact_queries(facts),
            structural_queries=self.build_structural_queries(facts),
            semantic_queries=self.build_semantic_queries(facts),
            file_context_requests=self.build_file_context_requests(facts),
            graph_expansion_requests=self.build_graph_expansion_requests(facts),
            kb_queries=self.build_kb_queries(facts),
        )

    def build_anchors(self, facts: IncidentFacts) -> list[RetrievalAnchor]:
        """Create grounded anchors from every parsed fact category."""
        anchors: list[RetrievalAnchor] = []

        for frame in facts.stack_frames:
            anchors.append(
                RetrievalAnchor(
                    value=frame.file_path,
                    anchor_type="file_path",
                    source="stack_frame",
                    file_path=frame.file_path,
                )
            )
            if frame.line_number is not None:
                anchors.append(
                    RetrievalAnchor(
                        value=str(frame.line_number),
                        anchor_type="line_number",
                        source="stack_frame",
                        file_path=frame.file_path,
                        line_number=frame.line_number,
                    )
                )
            if frame.function_name:
                anchors.append(
                    RetrievalAnchor(
                        value=frame.function_name,
                        anchor_type="function_name",
                        source="stack_frame",
                        file_path=frame.file_path,
                        line_number=frame.line_number,
                    )
                )
            if frame.class_name:
                anchors.append(
                    RetrievalAnchor(
                        value=frame.class_name,
                        anchor_type="class_name",
                        source="stack_frame",
                        file_path=frame.file_path,
                        line_number=frame.line_number,
                    )
                )

        anchors.extend(
            self._simple_anchors(
                facts.exception_types,
                anchor_type="exception_type",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.error_terms,
                anchor_type="error_term",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                (str(code) for code in facts.status_codes),
                anchor_type="status_code",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.trace_ids,
                anchor_type="trace_id",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.request_ids,
                anchor_type="request_id",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.quoted_terms,
                anchor_type="quoted_term",
                source="incident_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.config_like_terms,
                anchor_type="config_like_term",
                source="runtime_text",
            )
        )
        anchors.extend(
            self._simple_anchors(
                facts.candidate_symbols,
                anchor_type="candidate_symbol",
                source="incident_text",
            )
        )

        return self._deduplicate_anchors(anchors)

    def build_file_context_requests(self, facts: IncidentFacts) -> list[FileContextRequest]:
        """Request source lines around stack-frame locations."""
        requests = [
            FileContextRequest(
                file_path=frame.file_path,
                line_number=frame.line_number,
                before_lines=40,
                after_lines=40,
                reason=self._file_context_reason(frame.file_path, frame.line_number),
            )
            for frame in facts.stack_frames
        ]
        return self._deduplicate_file_requests(requests)

    def build_graph_expansion_requests(
        self,
        facts: IncidentFacts,
    ) -> list[GraphExpansionRequest]:
        """Request shallow graph expansion around grounded stack frames and symbols."""
        requests: list[GraphExpansionRequest] = []
        covered_symbols: set[str] = set()

        for frame in facts.stack_frames:
            requests.append(
                GraphExpansionRequest(
                    file_path=frame.file_path,
                    symbol_name=frame.function_name,
                    line_number=frame.line_number,
                    max_depth=1,
                    reason=self._graph_reason(frame.file_path, frame.function_name),
                )
            )
            if frame.function_name:
                covered_symbols.add(frame.function_name)
            if frame.class_name:
                covered_symbols.add(frame.class_name)

        for symbol in facts.candidate_symbols:
            if symbol in covered_symbols:
                continue
            requests.append(
                GraphExpansionRequest(
                    symbol_name=symbol,
                    max_depth=1,
                    reason=f"Expand structural context around incident symbol {symbol}",
                )
            )

        return self._deduplicate_graph_requests(requests)

    def build_exact_queries(self, facts: IncidentFacts) -> list[RetrievalQuery]:
        """Create compact exact-match queries from grounded runtime facts."""
        queries: list[RetrievalQuery] = []
        queries.extend(
            self._queries_for_values(
                facts.exception_types,
                purpose="Find exact exception occurrence",
                priority=90,
                source_hint="exception_type",
            )
        )
        queries.extend(
            self._queries_for_values(
                facts.config_like_terms,
                purpose="Find exact config/env reference",
                priority=90,
                source_hint="config_like_term",
            )
        )
        queries.extend(
            self._queries_for_values(
                self._symbol_values(facts),
                purpose="Find exact function or symbol reference",
                priority=90,
                source_hint="candidate_symbol",
            )
        )
        queries.extend(
            self._queries_for_values(
                (self._compact(value) for value in facts.error_terms),
                purpose="Find exact error text occurrence",
                priority=88,
                source_hint="error_term",
            )
        )
        queries.extend(
            self._queries_for_values(
                [*facts.trace_ids, *facts.request_ids],
                purpose="Find exact runtime identifier occurrence",
                priority=85,
                source_hint="runtime_identifier",
            )
        )
        return self._deduplicate_queries(queries)

    def build_structural_queries(self, facts: IncidentFacts) -> list[RetrievalQuery]:
        """Plan structural definition and usage lookup for grounded symbols."""
        return self._deduplicate_queries(
            self._queries_for_values(
                self._symbol_values(facts),
                purpose="Find structural definition or usage",
                priority=75,
                source_hint="candidate_symbol",
            )
        )

    def build_semantic_queries(self, facts: IncidentFacts) -> list[RetrievalQuery]:
        """Create a small set of readable semantic queries for contextual search."""
        queries = [
            RetrievalQuery(
                query=self._compact(
                    " ".join(
                        value
                        for value in (facts.summary, facts.description)
                        if value
                    )
                ),
                purpose="Find implementation context for incident description",
                priority=60,
                source_hint="incident_text",
            )
        ]

        error_query = self._combined_compact(facts.error_terms, limit=3)
        if error_query:
            queries.append(
                RetrievalQuery(
                    query=error_query,
                    purpose="Find implementation context for runtime errors",
                    priority=58,
                    source_hint="error_term",
                )
            )

        quoted_query = self._combined_compact(facts.quoted_terms, limit=3)
        if quoted_query:
            queries.append(
                RetrievalQuery(
                    query=quoted_query,
                    purpose="Find implementation context for quoted symptoms",
                    priority=56,
                    source_hint="quoted_term",
                )
            )

        return self._deduplicate_queries(queries, query_text_only=True)

    def build_kb_queries(self, facts: IncidentFacts) -> list[RetrievalQuery]:
        """Create documentation-oriented queries for expected behavior context."""
        queries = [
            RetrievalQuery(
                query=self._compact(
                    " ".join(
                        value
                        for value in (
                            facts.summary,
                            facts.description,
                            "expected behavior documentation",
                        )
                        if value
                    )
                ),
                purpose="Find documentation for expected behavior",
                priority=50,
                source_hint="incident_text",
            )
        ]

        quoted_query = self._combined_compact(facts.quoted_terms, limit=3)
        if quoted_query:
            queries.append(
                RetrievalQuery(
                    query=f"{quoted_query} troubleshooting documentation",
                    purpose="Find known behavior or troubleshooting notes",
                    priority=48,
                    source_hint="quoted_term",
                )
            )

        error_query = self._combined_compact(facts.error_terms, limit=2)
        if error_query:
            queries.append(
                RetrievalQuery(
                    query=f"{error_query} troubleshooting",
                    purpose="Find known behavior or troubleshooting notes",
                    priority=46,
                    source_hint="error_term",
                )
            )

        return self._deduplicate_queries(queries, query_text_only=True)

    def _simple_anchors(
        self,
        values: Iterable[str],
        *,
        anchor_type: str,
        source: str,
    ) -> list[RetrievalAnchor]:
        return [
            RetrievalAnchor(
                value=value,
                anchor_type=anchor_type,
                source=source,
            )
            for value in values
            if value
        ]

    def _queries_for_values(
        self,
        values: Iterable[str],
        *,
        purpose: str,
        priority: int,
        source_hint: str,
    ) -> list[RetrievalQuery]:
        return [
            RetrievalQuery(
                query=value,
                purpose=purpose,
                priority=priority,
                source_hint=source_hint,
            )
            for value in values
            if value
        ]

    def _symbol_values(self, facts: IncidentFacts) -> list[str]:
        return self._unique_strings(
            [
                *(
                    frame.function_name
                    for frame in facts.stack_frames
                    if frame.function_name
                ),
                *(
                    frame.class_name
                    for frame in facts.stack_frames
                    if frame.class_name
                ),
                *facts.candidate_symbols,
            ]
        )

    def _file_context_reason(self, file_path: str, line_number: int | None) -> str:
        location = f"{file_path}:{line_number}" if line_number is not None else file_path
        return f"Read source context around stack trace location {location}"

    def _graph_reason(self, file_path: str, symbol_name: str | None) -> str:
        if symbol_name:
            return f"Expand structural context around stack trace function {symbol_name}"
        return f"Expand structural context around stack trace file {file_path}"

    def _compact(self, value: str, *, max_length: int = 200) -> str:
        compact_value = " ".join(value.split())
        if len(compact_value) <= max_length:
            return compact_value
        return compact_value[: max_length - 3].rstrip() + "..."

    def _combined_compact(self, values: Iterable[str], *, limit: int) -> str:
        return self._compact(" ".join(self._unique_strings(values)[:limit]))

    def _deduplicate_anchors(self, anchors: Iterable[RetrievalAnchor]) -> list[RetrievalAnchor]:
        unique_anchors: list[RetrievalAnchor] = []
        seen: set[tuple[str, str, str, str | None, int | None]] = set()
        for anchor in anchors:
            key = (
                anchor.anchor_type,
                anchor.source,
                anchor.value,
                anchor.file_path,
                anchor.line_number,
            )
            if key in seen:
                continue
            seen.add(key)
            unique_anchors.append(anchor)
        return unique_anchors

    def _deduplicate_queries(
        self,
        queries: Iterable[RetrievalQuery],
        *,
        query_text_only: bool = False,
    ) -> list[RetrievalQuery]:
        unique_queries: list[RetrievalQuery] = []
        seen: set[tuple[str, ...]] = set()
        for query in queries:
            key = (
                (query.query,)
                if query_text_only
                else (query.query, query.purpose, query.source_hint or "")
            )
            if key in seen:
                continue
            seen.add(key)
            unique_queries.append(query)
        return unique_queries

    def _deduplicate_file_requests(
        self,
        requests: Iterable[FileContextRequest],
    ) -> list[FileContextRequest]:
        unique_requests: list[FileContextRequest] = []
        seen: set[tuple[str, int | None]] = set()
        for request in requests:
            key = (request.file_path, request.line_number)
            if key in seen:
                continue
            seen.add(key)
            unique_requests.append(request)
        return unique_requests

    def _deduplicate_graph_requests(
        self,
        requests: Iterable[GraphExpansionRequest],
    ) -> list[GraphExpansionRequest]:
        unique_requests: list[GraphExpansionRequest] = []
        seen: set[tuple[str | None, str | None, int | None]] = set()
        for request in requests:
            key = (request.file_path, request.symbol_name, request.line_number)
            if key in seen:
                continue
            seen.add(key)
            unique_requests.append(request)
        return unique_requests

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values
