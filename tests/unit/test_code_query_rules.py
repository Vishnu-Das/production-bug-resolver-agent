"""Tests for deterministic Code RAG query enrichment."""

from bug_resolver.rules.code_query_rules import CodeQueryRules
from bug_resolver.schemas import AgentDecision, AgentName, EvidenceItem, EvidenceSourceType


def make_decision(*, queries: list[str] | None = None, reason: str = "Need code evidence"):
    return AgentDecision(
        decision_id="decision-1",
        next_agent=AgentName.CODE_INVESTIGATOR,
        reason=reason,
        queries=queries or [],
    )


def test_upload_query_enrichment_adds_content_hash_and_upload_terms() -> None:
    decision = make_decision(
        queries=[
            (
                'content_hash="abc" dedupe_key="filename" '
                "processed_uploads_match=false duplicate_content_detected=true"
            )
        ]
    )

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert queries[0].startswith("content_hash")
    assert "handle_file_upload" in joined_queries
    assert "processed_uploads" in joined_queries
    assert "duplicate_content_detected" in joined_queries
    assert "filename" in joined_queries


def test_reranker_query_enrichment_adds_config_and_symbol_terms() -> None:
    decision = make_decision(
        queries=[
            'RERANKING_MODEL_NAME="" reranker_model=null scores="0.0" order_changed=false'
        ]
    )

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert "RERANKING_MODEL_NAME" in joined_queries
    assert "load_reranker" in joined_queries
    assert "rerank_documents_with_scores" in joined_queries
    assert "order_changed" in joined_queries


def test_summary_query_enrichment_adds_routing_strategy_terms() -> None:
    decision = make_decision(queries=["summarize this document selected semantic_search"])

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert "document_summary" in joined_queries
    assert "parent_child" in joined_queries
    assert "routing" in joined_queries
    assert "strategy" in joined_queries


def test_reason_is_used_when_supervisor_queries_are_missing() -> None:
    decision = make_decision(reason="Need code for reranker_model null order_changed false")

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert queries[0] == "Need code for reranker_model null order_changed false"
    assert "rerank_documents" in joined_queries


def test_query_enrichment_uses_existing_log_evidence() -> None:
    decision = make_decision(queries=["answer quality degraded"])
    evidence_items = [
        EvidenceItem(
            evidence_id="ev-log",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content=(
                'RERANKING_MODEL_NAME="" reranker_model=null '
                'scores="0.0,0.0,0.0,0.0" order_changed=false'
            ),
        )
    ]

    queries = CodeQueryRules().enrich_queries(decision, evidence_items=evidence_items)
    joined_queries = "\n".join(queries)

    assert "answer quality degraded" in queries
    assert "RERANKING_MODEL_NAME" in joined_queries
    assert "load_reranker" in joined_queries
    assert "rerank_documents_with_scores" in joined_queries


def test_query_enrichment_ignores_unrelated_kb_evidence() -> None:
    decision = make_decision(queries=["duplicate upload documents"])
    evidence_items = [
        EvidenceItem(
            evidence_id="kb-routing",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="retrieval.md",
            content="Summary queries use parent_child retrieval and reranking improves quality.",
        )
    ]

    queries = CodeQueryRules().enrich_queries(decision, evidence_items=evidence_items)
    joined_queries = "\n".join(queries)

    assert "handle_file_upload" in joined_queries
    assert "parent_child" not in joined_queries
    assert "rerank_documents" not in joined_queries


def test_query_enrichment_deduplicates_repeated_queries() -> None:
    decision = make_decision(queries=["summary routing", "summary routing"])

    queries = CodeQueryRules().enrich_queries(decision)

    assert queries.count("summary routing") == 1
