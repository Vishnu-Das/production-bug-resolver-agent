from __future__ import annotations

from bug_resolver.schemas import ContextPlan, CodeContext


class CodeContextRules:
    """
    Deterministic rules for preparing code context retrieval.

    The agent coordinates.
    The provider retrieves.
    These rules decide how to prepare and rank search inputs.
    """

    def build_search_queries(self, context_plan: ContextPlan) -> list[str]:
        queries: list[str] = []

        queries.extend(context_plan.code_search_queries)

        for file_path in context_plan.files_to_prioritize:
            queries.append(file_path)

        for function_name in context_plan.functions_to_prioritize:
            queries.append(function_name)

        for file_path in context_plan.files_to_prioritize:
            for function_name in context_plan.functions_to_prioritize:
                queries.append(f"{file_path} {function_name}")

        return self.unique(queries)

    def prioritize_contexts(
        self,
        contexts: list[CodeContext],
        context_plan: ContextPlan,
    ) -> list[CodeContext]:
        prioritized_files = set(context_plan.files_to_prioritize)
        prioritized_functions = set(context_plan.functions_to_prioritize)

        return sorted(
            contexts,
            key=lambda context: (
                context.file_path in prioritized_files,
                context.function_name in prioritized_functions
                if context.function_name
                else False,
                context.relevance_score or 0.0,
            ),
            reverse=True,
        )

    def limit_contexts(
        self,
        contexts: list[CodeContext],
        limit: int,
    ) -> list[CodeContext]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        return contexts[:limit]

    def unique(self, values: list[str] | object) -> list[str]:
        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                continue

            normalized = value.strip()
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            unique_values.append(normalized)

        return unique_values