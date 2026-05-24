"""Path-role signals for separating owner code from support surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodePathRole:
    """A code path role that is usually secondary unless the query asks for it."""

    name: str
    path_terms: frozenset[str]
    query_terms: frozenset[str]


DEFAULT_SUPPORT_PATH_ROLES = (
    CodePathRole(
        name="test",
        path_terms=frozenset({"test", "tests", "pytest", "unittest"}),
        query_terms=frozenset({"test", "tests", "pytest", "unittest", "regression", "assert"}),
    ),
    CodePathRole(
        name="evaluation",
        path_terms=frozenset({"eval", "evaluation", "evaluations", "benchmark", "benchmarks"}),
        query_terms=frozenset(
            {"eval", "evaluation", "benchmark", "benchmarks", "metric", "metrics", "compare"}
        ),
    ),
    CodePathRole(
        name="ui",
        path_terms=frozenset(
            {"ui", "frontend", "front_end", "view", "views", "component", "components", "streamlit"}
        ),
        query_terms=frozenset(
            {"ui", "frontend", "front_end", "screen", "page", "view", "component", "streamlit"}
        ),
    ),
    CodePathRole(
        name="demo",
        path_terms=frozenset({"demo", "demos", "example", "examples", "sample", "samples"}),
        query_terms=frozenset({"demo", "demos", "example", "examples", "sample", "samples"}),
    ),
    CodePathRole(
        name="notebook",
        path_terms=frozenset({"notebook", "notebooks", "jupyter", "ipynb"}),
        query_terms=frozenset({"notebook", "notebooks", "jupyter", "ipynb"}),
    ),
    CodePathRole(
        name="script",
        path_terms=frozenset({"script", "scripts"}),
        query_terms=frozenset({"script", "scripts", "migration", "one_off", "automation"}),
    ),
    CodePathRole(
        name="debug_tool",
        path_terms=frozenset({"debug", "debugger", "inspector", "devtool", "devtools", "diagnostic"}),
        query_terms=frozenset(
            {"debug", "debugger", "inspector", "devtool", "devtools", "diagnostic", "diagnostics"}
        ),
    ),
)

