"""Tests for deterministic context retrieval planning."""

from __future__ import annotations

import inspect

import bug_resolver.rules.retrieval_planning_rules as retrieval_planning_rules
from bug_resolver.retrieval.context_retrieval_planner import ContextRetrievalPlanner
from bug_resolver.schemas import IncidentFacts, StackFrame


def test_planner_creates_file_context_from_stack_frame() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-001",
            summary="Request processing fails",
            stack_frames=[
                StackFrame(
                    file_path="src/app.py",
                    line_number=42,
                    function_name="handle_request",
                )
            ],
        )
    )

    assert len(plan.file_context_requests) == 1
    assert plan.file_context_requests[0].file_path == "src/app.py"
    assert plan.file_context_requests[0].line_number == 42
    assert plan.file_context_requests[0].before_lines == 40
    assert plan.file_context_requests[0].after_lines == 40
    assert {
        (anchor.anchor_type, anchor.value)
        for anchor in plan.anchors
    } >= {
        ("file_path", "src/app.py"),
        ("line_number", "42"),
        ("function_name", "handle_request"),
    }


def test_planner_creates_graph_expansion_from_stack_frame() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-002",
            summary="Request processing fails",
            stack_frames=[
                StackFrame(
                    file_path="src/app.py",
                    line_number=42,
                    function_name="handle_request",
                )
            ],
        )
    )

    assert len(plan.graph_expansion_requests) == 1
    request = plan.graph_expansion_requests[0]
    assert request.file_path == "src/app.py"
    assert request.symbol_name == "handle_request"
    assert request.line_number == 42
    assert request.max_depth == 1


def test_planner_creates_exact_queries_for_exception_config_and_symbols() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-003",
            summary="Request processing fails",
            exception_types=["TypeError"],
            config_like_terms=["OPENAI_API_KEY"],
            candidate_symbols=["handle_request"],
        )
    )

    queries = {query.query: query for query in plan.exact_queries}

    assert queries["TypeError"].purpose == "Find exact exception occurrence"
    assert queries["OPENAI_API_KEY"].purpose == "Find exact config/env reference"
    assert queries["handle_request"].purpose == "Find exact function or symbol reference"
    assert queries["TypeError"].priority > plan.semantic_queries[0].priority


def test_planner_creates_semantic_queries_from_summary_description_and_quoted_terms() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-004",
            summary="Checkout request returns an error",
            description="Users cannot complete a purchase.",
            quoted_terms=["payment method was declined"],
        )
    )

    queries = [query.query for query in plan.semantic_queries]

    assert any("Checkout request returns an error" in query for query in queries)
    assert any("Users cannot complete a purchase." in query for query in queries)
    assert "payment method was declined" in queries


def test_planner_creates_kb_queries_for_expected_behavior_context() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-005",
            summary="Checkout request returns an error",
            description="Users cannot complete a purchase.",
            quoted_terms=["payment method was declined"],
        )
    )

    queries = [query.query for query in plan.kb_queries]

    assert any("expected behavior documentation" in query for query in queries)
    assert any("Checkout request returns an error" in query for query in queries)
    assert any("payment method was declined" in query for query in queries)
    assert plan.semantic_queries[0].priority > plan.kb_queries[0].priority


def test_planner_deduplicates_queries_and_anchors() -> None:
    repeated_frame = StackFrame(
        file_path="src/app.py",
        line_number=42,
        function_name="handle_request",
    )
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-006",
            summary="Request processing fails",
            exception_types=["TypeError", "TypeError"],
            candidate_symbols=["handle_request", "handle_request"],
            stack_frames=[repeated_frame, repeated_frame],
        )
    )

    assert len(plan.file_context_requests) == 1
    assert len(plan.graph_expansion_requests) == 1
    assert len(
        [
            anchor
            for anchor in plan.anchors
            if anchor.anchor_type == "exception_type" and anchor.value == "TypeError"
        ]
    ) == 1
    assert len(
        [
            query
            for query in plan.exact_queries
            if query.query == "handle_request"
            and query.purpose == "Find exact function or symbol reference"
        ]
    ) == 1


def test_planner_handles_minimal_facts() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-007",
            summary="Background task is delayed",
        )
    )

    assert plan.semantic_queries
    assert plan.kb_queries
    assert plan.file_context_requests == []
    assert plan.graph_expansion_requests == []


def test_planner_adds_graph_expansion_for_uncovered_candidate_symbol() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-008",
            summary="Request processing fails",
            candidate_symbols=["handle_request"],
        )
    )

    assert len(plan.graph_expansion_requests) == 1
    assert plan.graph_expansion_requests[0].symbol_name == "handle_request"
    assert plan.graph_expansion_requests[0].file_path is None


def test_planner_is_repo_agnostic() -> None:
    plan = ContextRetrievalPlanner().plan(
        IncidentFacts(
            incident_id="INC-009",
            summary="Request processing fails",
            exception_types=["TypeError"],
            config_like_terms=["OPENAI_API_KEY"],
            candidate_symbols=["handle_request"],
            stack_frames=[
                StackFrame(
                    file_path="src/app.py",
                    line_number=42,
                    function_name="handle_request",
                )
            ],
        )
    )
    module_source = inspect.getsource(retrieval_planning_rules)

    assert plan.file_context_requests[0].file_path == "src/app.py"
    assert "handle_request" in [query.query for query in plan.exact_queries]
    assert "rag" not in module_source
    assert "router" not in module_source
    assert "reranker" not in module_source
    assert "upload" not in module_source
    assert "content_hash" not in module_source
