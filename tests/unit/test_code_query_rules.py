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
    assert "processed_uploads" in joined_queries
    assert "duplicate_content_detected" in joined_queries
    assert "filename" in joined_queries
    assert "dedup" in joined_queries
    assert "ingestion" in joined_queries
    assert "service" in joined_queries
    assert "handler" in joined_queries


def test_upload_query_enrichment_does_not_invent_target_repo_symbols() -> None:
    decision = make_decision(queries=["duplicate files appear after upload"])

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert "upload" in joined_queries
    assert "dedup" in joined_queries
    assert "handle_file_upload" not in joined_queries
    assert "upload_service.py" not in joined_queries


def test_reranker_query_enrichment_adds_generic_config_terms() -> None:
    decision = make_decision(
        queries=[
            'RERANKING_MODEL_NAME="" reranker_model=null scores="0.0" order_changed=false'
        ]
    )

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert "RERANKING_MODEL_NAME" in joined_queries
    assert "reranker_model" in joined_queries
    assert "config" in joined_queries
    assert "reranking" in joined_queries
    assert "order_changed" in joined_queries


def test_query_enrichment_preserves_observed_function_names() -> None:
    decision = make_decision(
        queries=["caller chain shows load_reranker() reads RERANKING_MODEL_NAME"]
    )

    queries = CodeQueryRules().enrich_queries(decision)
    joined_queries = "\n".join(queries)

    assert "load_reranker" in joined_queries
    assert "RERANKING_MODEL_NAME" in joined_queries


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
    assert "reranking" in joined_queries
    assert "config" in joined_queries


def test_query_enrichment_uses_existing_log_evidence_generically() -> None:
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
    assert "reranker_model" in joined_queries
    assert "reranking" in joined_queries
    assert "order_changed" in joined_queries


def test_query_enrichment_uses_relevant_kb_evidence() -> None:
    decision = make_decision(queries=["duplicate upload documents"])
    evidence_items = [
        EvidenceItem(
            evidence_id="kb-upload",
            source_type=EvidenceSourceType.KNOWLEDGE_BASE,
            source_name="ingestion-guide.md",
            content=(
                "Duplicate uploads should compare content_hash values before "
                "creating document records."
            ),
        )
    ]

    queries = CodeQueryRules().enrich_queries(decision, evidence_items=evidence_items)
    joined_queries = "\n".join(queries)

    assert "content_hash" in joined_queries
    assert "duplicate" in joined_queries
    assert "upload" in joined_queries


def test_query_enrichment_uses_relevant_graph_evidence() -> None:
    decision = make_decision(queries=["reranker configuration fallback"])
    evidence_items = [
        EvidenceItem(
            evidence_id="graph-1",
            source_type=EvidenceSourceType.GRAPH,
            source_name="graph",
            file_path="src/search.py",
            content="SearchPipeline.rerank calls load_model() before scoring.",
            metadata={"qualified_symbol": "SearchPipeline.rerank"},
        )
    ]

    queries = CodeQueryRules().enrich_queries(decision, evidence_items=evidence_items)
    joined_queries = "\n".join(queries)

    assert "SearchPipeline.rerank" in joined_queries
    assert "load_model" in joined_queries
    assert "src/search.py" in joined_queries


def test_query_enrichment_uses_graph_owner_hints_for_follow_up_code_search() -> None:
    decision = make_decision(queries=["duplicate upload content_hash ingestion"])
    evidence_items = [
        EvidenceItem(
            evidence_id="graph-src/ingest.py:ingest_single_document",
            source_type=EvidenceSourceType.GRAPH,
            source_name="src/ingest.py",
            file_path="src/ingest.py",
            content=(
                "src/ingest.py:ingest_single_document is called by handle_file_upload "
                "and imported by src/services/upload_service.py."
            ),
            metadata={
                "qualified_symbol": "ingest_single_document",
                "called_by": "handle_file_upload",
                "imported_by": "src/services/upload_service.py",
            },
        )
    ]

    queries = CodeQueryRules().enrich_queries(decision, evidence_items=evidence_items)
    joined_queries = "\n".join(queries)

    assert "src/ingest.py" in joined_queries
    assert "src/services/upload_service.py" in joined_queries
    assert "handle_file_upload" in joined_queries
    assert "ingest_single_document" in joined_queries


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

    assert "dedup" in joined_queries
    assert "parent_child" not in joined_queries
    assert "reranking" not in joined_queries


def test_query_enrichment_deduplicates_repeated_queries() -> None:
    decision = make_decision(queries=["summary routing", "summary routing"])

    queries = CodeQueryRules().enrich_queries(decision)

    assert queries.count("summary routing") == 1
