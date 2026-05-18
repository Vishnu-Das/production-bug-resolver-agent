from __future__ import annotations

from bug_resolver.schemas import ContextPlan, KnowledgeContext


class KnowledgeBaseRules:
    """
    Deterministic rules for preparing knowledge-base retrieval.

    The agent coordinates.
    The provider retrieves.
    These rules prepare, deduplicate, rank, and limit the result set.
    """

    def build_search_queries(self, context_plan: ContextPlan) -> list[str]:
        queries: list[str] = []

        queries.extend(context_plan.knowledge_search_queries)

        for hint in context_plan.missing_evidence_hints:
            queries.append(hint)

        return self.unique(queries)

    def prioritize_contexts(
        self,
        contexts: list[KnowledgeContext],
        context_plan: ContextPlan,
    ) -> list[KnowledgeContext]:
        priority_terms = {
            *context_plan.knowledge_search_queries,
            *context_plan.files_to_prioritize,
            *context_plan.functions_to_prioritize,
        }

        return sorted(
            contexts,
            key=lambda context: (
                self._matches_priority_terms(context, priority_terms),
                context.relevance_score or 0.0,
            ),
            reverse=True,
        )

    def limit_contexts(
        self,
        contexts: list[KnowledgeContext],
        limit: int,
    ) -> list[KnowledgeContext]:
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

    def _matches_priority_terms(
        self,
        context: KnowledgeContext,
        priority_terms: set[str],
    ) -> bool:
        searchable_text = " ".join(
            [
                context.document_name,
                context.section_title or "",
                context.file_path or "",
                context.content,
            ]
        ).lower()

        return any(term.lower() in searchable_text for term in priority_terms if term)