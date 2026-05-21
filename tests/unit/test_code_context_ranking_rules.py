"""Tests for deterministic code context post-retrieval ranking."""

from bug_resolver.rules.code_context_ranking_rules import CodeContextRankingRules
from bug_resolver.schemas import CodeContext


def make_context(
    context_id: str,
    file_path: str,
    *,
    score: float,
    line_start: int = 1,
    line_end: int = 20,
) -> CodeContext:
    return CodeContext(
        context_id=context_id,
        file_path=file_path,
        snippet=f"snippet for {file_path}",
        line_start=line_start,
        line_end=line_end,
        relevance_score=score,
    )


def test_ranks_implementation_file_above_test_file_for_non_test_query() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("test", "tests/rag/test_service.py", score=0.95),
        make_context("impl", "src/rag/service.py", score=0.85),
    ]

    ranked = ranker.rank_contexts(contexts, queries=["retrieval service bug"], limit=2)

    assert [context.context_id for context in ranked] == ["impl", "test"]


def test_test_file_is_not_penalized_when_query_mentions_pytest() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("test", "tests/rag/test_service.py", score=0.95),
        make_context("impl", "src/rag/service.py", score=0.85),
    ]

    ranked = ranker.rank_contexts(contexts, queries=["pytest retrieval service"], limit=2)

    assert [context.context_id for context in ranked] == ["test", "impl"]


def test_query_substring_does_not_count_as_test_query() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("test", "tests/rag/test_service.py", score=0.95),
        make_context("impl", "src/rag/service.py", score=0.85),
    ]

    ranked = ranker.rank_contexts(contexts, queries=["retrieval contest failure"], limit=2)

    assert [context.context_id for context in ranked] == ["impl", "test"]


def test_config_files_are_penalized_unless_query_mentions_config() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("config", "config/retrieval.yaml", score=0.95),
        make_context("impl", "src/rag/retrieval/factory.py", score=0.85),
    ]

    ranked_without_config_query = ranker.rank_contexts(
        contexts,
        queries=["retrieval strategy bug"],
        limit=2,
    )
    ranked_with_config_query = ranker.rank_contexts(
        contexts,
        queries=["yaml config retrieval strategy"],
        limit=2,
    )

    assert [context.context_id for context in ranked_without_config_query] == [
        "impl",
        "config",
    ]
    assert [context.context_id for context in ranked_with_config_query] == [
        "config",
        "impl",
    ]


def test_init_file_is_penalized_unless_query_mentions_package_export() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("init", "src/rag/retrieval/__init__.py", score=0.95),
        make_context("impl", "src/rag/retrieval/factory.py", score=0.85),
    ]

    ranked_without_init_query = ranker.rank_contexts(
        contexts,
        queries=["retrieval factory bug"],
        limit=2,
    )
    ranked_with_init_query = ranker.rank_contexts(
        contexts,
        queries=["package export retrieval"],
        limit=2,
    )

    assert [context.context_id for context in ranked_without_init_query] == [
        "impl",
        "init",
    ]
    assert [context.context_id for context in ranked_with_init_query] == [
        "init",
        "impl",
    ]


def test_overlapping_chunks_from_same_file_are_deduplicated() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("weak-overlap", "src/rag/service.py", score=0.75, line_start=10, line_end=30),
        make_context("strong-overlap", "src/rag/service.py", score=0.90, line_start=20, line_end=40),
        make_context("separate", "src/rag/service.py", score=0.70, line_start=80, line_end=100),
    ]

    ranked = ranker.rank_contexts(contexts, queries=["retrieval service"], limit=5)

    assert [context.context_id for context in ranked] == ["strong-overlap", "separate"]


def test_support_files_are_penalized_for_backend_query() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("eval", "eval/compare_retrieval_strategies.py", score=0.96),
        make_context("ui", "src/ui/retrieval_inspector.py", score=0.95),
        make_context("impl", "src/reranker.py", score=0.84),
    ]

    ranked = ranker.rank_contexts(
        contexts,
        queries=["reranker missing config answer quality"],
        limit=3,
    )

    assert [context.context_id for context in ranked] == ["impl", "eval", "ui"]


def test_support_files_are_allowed_when_query_mentions_support_surface() -> None:
    ranker = CodeContextRankingRules()
    contexts = [
        make_context("ui", "src/ui/retrieval_inspector.py", score=0.88),
        make_context("impl", "src/reranker.py", score=0.86),
    ]

    ranked = ranker.rank_contexts(
        contexts,
        queries=["ui inspector shows wrong reranker scores"],
        limit=2,
    )

    assert [context.context_id for context in ranked] == ["ui", "impl"]
