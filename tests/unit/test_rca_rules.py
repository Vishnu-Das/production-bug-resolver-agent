"""Tests for deterministic RCA evidence selection rules."""

from __future__ import annotations

from bug_resolver.rules.rca_rules import RCARules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, Incident, WorkflowState


def make_state(*, title: str, description: str, affected_area: str) -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-TEST",
            title=title,
            description=description,
            affected_service="example_service",
            affected_area=affected_area,
        )
    )


def add_evidence(
    state: WorkflowState,
    *,
    evidence_id: str,
    source_type: EvidenceSourceType,
    source_name: str,
    content: str,
    file_path: str | None = None,
    relevance_score: float = 0.7,
) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id=evidence_id,
            source_type=source_type,
            source_name=source_name,
            content=content,
            file_path=file_path,
            relevance_score=relevance_score,
        )
    )


def test_upload_code_findings_prefer_overlapping_path_and_content() -> None:
    state = make_state(
        title="Users see duplicate documents after upload",
        description="Users see duplicate document records and repeated citations.",
        affected_area="document upload and ingestion",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="upload.log",
        content=(
            'content_hash="abc123" dedupe_key="filename" '
            "duplicate_content_detected=true repeated citations"
        ),
    )
    add_evidence(
        state,
        evidence_id="ev-upload",
        source_type=EvidenceSourceType.CODE,
        source_name="app/upload/handler.py",
        file_path="app/upload/handler.py",
        content="processed_uploads uses filename state while content_hash is available",
    )
    add_evidence(
        state,
        evidence_id="ev-dedup",
        source_type=EvidenceSourceType.CODE,
        source_name="lib/dedup/content_identity.py",
        file_path="lib/dedup/content_identity.py",
        content="deduplication helper compares content hash identity",
    )
    add_evidence(
        state,
        evidence_id="ev-retrieval",
        source_type=EvidenceSourceType.CODE,
        source_name="retrieval/strategy_factory.py",
        file_path="retrieval/strategy_factory.py",
        content="retrieval strategy factory maps strategy names",
    )
    add_evidence(
        state,
        evidence_id="ev-routing",
        source_type=EvidenceSourceType.CODE,
        source_name="routing/query_router.py",
        file_path="routing/query_router.py",
        content="router selects retrieval strategies for queries",
    )

    findings = RCARules().build_code_findings(state)
    joined_findings = "\n".join(findings)

    assert "app/upload/handler.py" in joined_findings
    assert "lib/dedup/content_identity.py" in joined_findings
    assert "retrieval/strategy_factory.py" not in joined_findings


def test_reranker_code_findings_prefer_overlapping_path_and_content() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="reranker.log",
        content='reranker_model=null scores="0.0,0.0,0.0,0.0" order_changed=false',
    )
    add_evidence(
        state,
        evidence_id="ev-reranker",
        source_type=EvidenceSourceType.CODE,
        source_name="ranking/model_config.py",
        file_path="ranking/model_config.py",
        content="loads cross encoder reranker and returns neutral scores when missing",
    )
    add_evidence(
        state,
        evidence_id="ev-pipeline",
        source_type=EvidenceSourceType.CODE,
        source_name="answering/ranking_pipeline.py",
        file_path="answering/ranking_pipeline.py",
        content="hybrid retrieval candidates are reranked before answer context",
    )
    add_evidence(
        state,
        evidence_id="ev-routing",
        source_type=EvidenceSourceType.CODE,
        source_name="routing/query_router.py",
        file_path="routing/query_router.py",
        content="router selects retrieval strategies for summary and lookup queries",
    )
    add_evidence(
        state,
        evidence_id="ev-upload",
        source_type=EvidenceSourceType.CODE,
        source_name="documents/upload_handler.py",
        file_path="documents/upload_handler.py",
        content="upload service stores documents",
    )

    findings = RCARules().build_code_findings(state)
    joined_findings = "\n".join(findings)

    assert "ranking/model_config.py" in joined_findings
    assert "answering/ranking_pipeline.py" in joined_findings
    assert "routing/query_router.py" not in joined_findings


def test_code_findings_penalize_support_paths_for_backend_incident() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="reranker.log",
        content='reranker_model=null scores="0.0,0.0,0.0,0.0" order_changed=false',
    )
    add_evidence(
        state,
        evidence_id="ev-reranker",
        source_type=EvidenceSourceType.CODE,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        content="reranker model config returns neutral scores when missing",
    )
    add_evidence(
        state,
        evidence_id="ev-eval",
        source_type=EvidenceSourceType.CODE,
        source_name="eval/compare_retrieval_strategies.py",
        file_path="eval/compare_retrieval_strategies.py",
        content="evaluation compares reranker model config scores and answer quality",
        relevance_score=0.95,
    )
    add_evidence(
        state,
        evidence_id="ev-ui",
        source_type=EvidenceSourceType.CODE,
        source_name="src/ui/retrieval_inspector.py",
        file_path="src/ui/retrieval_inspector.py",
        content="ui inspector displays reranker scores and answer quality",
        relevance_score=0.95,
    )

    findings = RCARules().build_code_findings(state)
    evidence_ids = RCARules().evidence_ids(state)
    joined_findings = "\n".join(findings)

    assert "src/reranker.py" in joined_findings
    assert "eval/compare_retrieval_strategies.py" not in joined_findings
    assert "src/ui/retrieval_inspector.py" not in joined_findings
    assert "ev-reranker" in evidence_ids
    assert "ev-eval" not in evidence_ids
    assert "ev-ui" not in evidence_ids


def test_code_findings_allow_support_paths_when_incident_mentions_them() -> None:
    state = make_state(
        title="Retrieval inspector UI shows wrong reranker scores",
        description="The debug inspector page shows stale reranker scores after deployment.",
        affected_area="retrieval inspector UI",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="ui.log",
        content="ui inspector debug panel shows stale reranker scores",
    )
    add_evidence(
        state,
        evidence_id="ev-ui",
        source_type=EvidenceSourceType.CODE,
        source_name="src/ui/retrieval_inspector.py",
        file_path="src/ui/retrieval_inspector.py",
        content="retrieval inspector ui renders reranker scores",
    )
    add_evidence(
        state,
        evidence_id="ev-reranker",
        source_type=EvidenceSourceType.CODE,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        content="reranker produces scores for retrieved documents",
    )

    findings = RCARules().build_code_findings(state)
    joined_findings = "\n".join(findings)

    assert "src/ui/retrieval_inspector.py" in joined_findings


def test_code_findings_prefer_symbol_location_when_metadata_exists() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-reranker",
            source_type=EvidenceSourceType.CODE,
            source_name="src/reranker.py",
            file_path="src/reranker.py",
            line_start=63,
            line_end=122,
            content="reranker_model returns neutral scores when model is missing",
            relevance_score=0.8,
            metadata={
                "qualified_symbol": "CrossEncoderReranker.rerank",
                "symbol_type": "method",
            },
        )
    )

    findings = RCARules().build_code_findings(state)

    assert "src/reranker.py:CrossEncoderReranker.rerank" in findings[0]
    assert "src/reranker.py:63-122" not in findings[0]


def test_code_findings_fall_back_to_line_range_without_symbol_metadata() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-reranker",
            source_type=EvidenceSourceType.CODE,
            source_name="src/reranker.py",
            file_path="src/reranker.py",
            line_start=63,
            line_end=122,
            content="reranker_model returns neutral scores when model is missing",
            relevance_score=0.8,
        )
    )

    findings = RCARules().build_code_findings(state)

    assert "src/reranker.py:63-122" in findings[0]


def test_reranker_kb_findings_prefer_overlapping_content() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="reranker.log",
        content='RERANKING_MODEL_NAME="" reranker_model=null order_changed=false',
    )
    add_evidence(
        state,
        evidence_id="kb-routing",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-a.md",
        content="Summary-style queries should use document-level retrieval.",
    )
    add_evidence(
        state,
        evidence_id="kb-reranking",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-b.md",
        content="Missing reranker config should warn clearly instead of silent bypass.",
    )
    add_evidence(
        state,
        evidence_id="kb-upload",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-c.md",
        content="Upload deduplication should use content hash identity.",
    )
    add_evidence(
        state,
        evidence_id="kb-readme",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="README.md",
        content="The RAG app supports retrieval and chat over documents.",
    )

    findings = RCARules().build_knowledge_base_findings(state)
    joined_findings = "\n".join(findings)

    assert "document-b.md" in joined_findings
    assert "document-a.md" not in joined_findings


def test_upload_kb_findings_prefer_overlapping_content() -> None:
    state = make_state(
        title="Users see duplicate documents after upload",
        description="Users see duplicate records after uploading similar PDF files.",
        affected_area="document upload and ingestion",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="upload.log",
        content='content_hash="abc123" dedupe_key="filename" duplicate_content_detected=true',
    )
    add_evidence(
        state,
        evidence_id="kb-routing",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-a.md",
        content="Summary-style queries should use document-level retrieval.",
    )
    add_evidence(
        state,
        evidence_id="kb-upload",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-b.md",
        content="Content-level deduplication should use a stable file hash.",
    )
    add_evidence(
        state,
        evidence_id="kb-reranking",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-c.md",
        content="Hybrid retrieval should rerank candidate chunks.",
    )
    add_evidence(
        state,
        evidence_id="kb-readme",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="README.md",
        content="The app supports document upload and retrieval.",
    )

    findings = RCARules().build_knowledge_base_findings(state)
    joined_findings = "\n".join(findings)

    assert "document-b.md" in joined_findings
    assert "document-a.md" not in joined_findings


def test_upload_rca_evidence_ids_use_focused_code_and_kb_selection() -> None:
    state = make_state(
        title="Users see duplicate documents after upload",
        description="Users see duplicate records after uploading similar PDF files.",
        affected_area="document upload and ingestion",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="upload.log",
        content='content_hash="abc123" dedupe_key="filename" duplicate_content_detected=true',
    )
    add_evidence(
        state,
        evidence_id="ev-upload",
        source_type=EvidenceSourceType.CODE,
        source_name="app/upload/handler.py",
        file_path="app/upload/handler.py",
        content="processed_uploads uses filename state while content_hash is available",
    )
    add_evidence(
        state,
        evidence_id="ev-dedup",
        source_type=EvidenceSourceType.CODE,
        source_name="lib/dedup/content_identity.py",
        file_path="lib/dedup/content_identity.py",
        content="deduplication helper compares content hash identity",
    )
    add_evidence(
        state,
        evidence_id="ev-retrieval",
        source_type=EvidenceSourceType.CODE,
        source_name="retrieval/fusion_strategy.py",
        file_path="retrieval/fusion_strategy.py",
        content="fusion retrieval combines semantic and keyword candidates",
    )
    add_evidence(
        state,
        evidence_id="kb-upload",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-a.md",
        content="Content-level deduplication should use a stable file hash.",
    )
    add_evidence(
        state,
        evidence_id="kb-retrieval",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-b.md",
        content="Fusion retrieval combines vector search and keyword search.",
    )

    evidence_ids = RCARules().evidence_ids(state)

    assert "ev-log" in evidence_ids
    assert "ev-upload" in evidence_ids
    assert "ev-dedup" in evidence_ids
    assert "kb-upload" in evidence_ids
    assert "ev-retrieval" not in evidence_ids
    assert "kb-retrieval" not in evidence_ids


def test_reranker_rca_evidence_ids_include_ranking_code_and_kb() -> None:
    state = make_state(
        title="Answers cite unrelated sources after deployment",
        description="Answer quality is worse and cited sources look unrelated.",
        affected_area="retrieval ranking quality",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="reranker.log",
        content='reranker_model=null scores="0.0,0.0,0.0,0.0" order_changed=false',
    )
    add_evidence(
        state,
        evidence_id="ev-reranker",
        source_type=EvidenceSourceType.CODE,
        source_name="ranking/model_config.py",
        file_path="ranking/model_config.py",
        content="loads cross encoder reranker and returns neutral scores when missing",
    )
    add_evidence(
        state,
        evidence_id="ev-routing",
        source_type=EvidenceSourceType.CODE,
        source_name="routing/query_router.py",
        file_path="routing/query_router.py",
        content="router selects retrieval strategies for summary and lookup queries",
    )
    add_evidence(
        state,
        evidence_id="kb-reranking",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-a.md",
        content="Missing reranker model config should warn clearly instead of silent bypass.",
    )
    add_evidence(
        state,
        evidence_id="kb-routing",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="document-b.md",
        content="Summary-style queries should use document-level retrieval.",
    )

    evidence_ids = RCARules().evidence_ids(state)

    assert "ev-log" in evidence_ids
    assert "ev-reranker" in evidence_ids
    assert "kb-reranking" in evidence_ids
    assert "ev-routing" not in evidence_ids
    assert "kb-routing" not in evidence_ids


def test_rca_evidence_ids_include_selected_graph_evidence() -> None:
    state = make_state(
        title="Reranker silently keeps original retrieval order",
        description=(
            "Answers cite unrelated sources after deployment. Logs mention reranking "
            "model configuration and unchanged document order."
        ),
        affected_area="retrieval quality",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="reranker_model=null scores=0.0 order_changed=false",
    )
    add_evidence(
        state,
        evidence_id="ev-code",
        source_type=EvidenceSourceType.CODE,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        content="def rerank_documents(...): return documents",
    )
    add_evidence(
        state,
        evidence_id="ev-graph",
        source_type=EvidenceSourceType.GRAPH,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        content=(
            "src/reranker.py:rerank_documents calls load_reranker and reads "
            "RERANKING_MODEL_NAME."
        ),
    )
    add_evidence(
        state,
        evidence_id="ev-unrelated-graph",
        source_type=EvidenceSourceType.GRAPH,
        source_name="src/upload.py",
        file_path="src/upload.py",
        content="src/upload.py:handle_upload calls save_file.",
    )

    evidence_ids = RCARules().evidence_ids(state)

    assert "ev-log" in evidence_ids
    assert "ev-code" in evidence_ids
    assert "ev-graph" in evidence_ids
    assert "ev-unrelated-graph" not in evidence_ids


def test_graph_findings_describe_structural_relationships() -> None:
    state = make_state(
        title="Reranker config value does not affect answer ranking",
        description=(
            "The investigation needs to identify which function reads "
            "RERANKING_MODEL_NAME and which request path calls reranking."
        ),
        affected_area="retrieval ranking configuration",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="structural_hint caller chain RERANKING_MODEL_NAME",
    )
    add_evidence(
        state,
        evidence_id="ev-code",
        source_type=EvidenceSourceType.CODE,
        source_name="src/reranker.py",
        file_path="src/reranker.py",
        content="def rerank_documents_with_scores(...): pass",
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-graph",
            source_type=EvidenceSourceType.GRAPH,
            source_name="src/reranker.py",
            file_path="src/reranker.py",
            content="Graph evidence for rerank_documents_with_scores.",
            metadata={
                "qualified_symbol": "rerank_documents_with_scores",
                "calls": (
                    "load_reranker, doc.metadata.get, ranked_documents.sort, "
                    "reranker_model.predict, zip"
                ),
                "called_by": "answer_question, test_reranker_flow",
                "config_keys": "RERANKING_MODEL_NAME",
                "config_readers": "load_reranker",
            },
        )
    )

    findings = RCARules().build_graph_findings(state)

    assert findings == [
        (
            "src/reranker.py:rerank_documents_with_scores shows structural code "
            "relationship: uses config from load_reranker, which reads "
            "RERANKING_MODEL_NAME; calls reranker_model.predict; called by answer_question."
        )
    ]
    assert "doc.metadata.get" not in findings[0]
    assert "ranked_documents.sort" not in findings[0]
    assert "reranker_model.predict" in findings[0]
    assert "test_reranker_flow" not in findings[0]
    assert "zip" not in findings[0]


def test_graph_findings_prefer_implementation_evidence_over_tests() -> None:
    state = make_state(
        title="Reranker config value does not affect answer ranking",
        description=(
            "The investigation needs the caller chain for reranking and "
            "RERANKING_MODEL_NAME."
        ),
        affected_area="retrieval ranking configuration",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="structural_hint caller chain RERANKING_MODEL_NAME reranker_model=null",
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-graph-src",
            source_type=EvidenceSourceType.GRAPH,
            source_name="src/reranker.py",
            file_path="src/reranker.py",
            content="rerank_documents_with_scores uses reranker config.",
            relevance_score=0.7,
            metadata={
                "qualified_symbol": "rerank_documents_with_scores",
                "config_keys": "RERANKING_MODEL_NAME",
                "config_readers": "load_reranker",
            },
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-graph-test",
            source_type=EvidenceSourceType.GRAPH,
            source_name="tests/rag/test_service.py",
            file_path="tests/rag/test_service.py",
            content=(
                "test reranking caller chain RERANKING_MODEL_NAME retrieval "
                "strategy config model scores"
            ),
            relevance_score=0.99,
            metadata={
                "qualified_symbol": "test_stream_response_reranking",
                "config_keys": "RERANKING_MODEL_NAME",
                "calls": "patch, mock_router.assert_called_once_with",
            },
        )
    )

    findings = RCARules().build_graph_findings(state)
    evidence_ids = RCARules().evidence_ids(state)
    joined_findings = "\n".join(findings)

    assert "src/reranker.py:rerank_documents_with_scores" in joined_findings
    assert "tests/rag/test_service.py" not in joined_findings
    assert "ev-graph-src" in evidence_ids
    assert "ev-graph-test" not in evidence_ids


def test_generic_findings_are_kept_when_only_one_item_exists() -> None:
    state = make_state(
        title="Unknown incident",
        description="Users report an intermittent issue.",
        affected_area="unknown",
    )
    add_evidence(
        state,
        evidence_id="ev-code",
        source_type=EvidenceSourceType.CODE,
        source_name="src/example.py",
        file_path="src/example.py",
        content="implementation context",
    )
    add_evidence(
        state,
        evidence_id="ev-kb",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="README.md",
        content="operational context",
    )

    rules = RCARules()

    assert rules.build_code_findings(state) == [
        "src/example.py contains implementation context relevant to the incident."
    ]
    assert rules.build_knowledge_base_findings(state) == [
        "README.md documents expected behavior relevant to the incident: operational context"
    ]


def test_historical_findings_are_separate_supporting_context() -> None:
    state = make_state(
        title="Duplicate records are happening again",
        description="This looks similar to a previous RCA.",
        affected_area="document ingestion",
    )
    add_evidence(
        state,
        evidence_id="historical-INC-OLD",
        source_type=EvidenceSourceType.HISTORICAL_RCA,
        source_name="Prior duplicate upload incident",
        content=(
            "Similar prior incident INC-OLD: duplicate records. Prior RCA root "
            "cause: upload deduplication used unstable document identity."
        ),
        file_path="reports/incidents/INC-OLD/rca.json",
        relevance_score=0.9,
    )

    findings = RCARules().build_historical_findings(state)

    assert findings == [
        (
            "reports/incidents/INC-OLD/rca.json describes similar prior incident "
            "prior: Similar prior incident INC-OLD: duplicate records. Prior RCA "
            "root cause: upload deduplication used unstable document identity."
        )
    ]


def test_generic_evidence_id_fallback_keeps_evidence_when_no_strong_term_exists() -> None:
    state = make_state(
        title="Unknown incident",
        description="Users report an intermittent issue.",
        affected_area="unknown",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="runtime behavior needs investigation",
    )
    add_evidence(
        state,
        evidence_id="ev-code-a",
        source_type=EvidenceSourceType.CODE,
        source_name="alpha.py",
        file_path="alpha.py",
        content="alpha implementation context",
    )
    add_evidence(
        state,
        evidence_id="ev-code-b",
        source_type=EvidenceSourceType.CODE,
        source_name="beta.py",
        file_path="beta.py",
        content="beta implementation context",
    )
    add_evidence(
        state,
        evidence_id="ev-code-c",
        source_type=EvidenceSourceType.CODE,
        source_name="gamma.py",
        file_path="gamma.py",
        content="gamma implementation context",
    )
    add_evidence(
        state,
        evidence_id="ev-code-d",
        source_type=EvidenceSourceType.CODE,
        source_name="delta.py",
        file_path="delta.py",
        content="delta implementation context",
    )
    add_evidence(
        state,
        evidence_id="ev-kb-a",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="alpha.md",
        content="alpha operational context",
    )
    add_evidence(
        state,
        evidence_id="ev-kb-b",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="beta.md",
        content="beta operational context",
    )
    add_evidence(
        state,
        evidence_id="ev-kb-c",
        source_type=EvidenceSourceType.KNOWLEDGE_BASE,
        source_name="gamma.md",
        content="gamma operational context",
    )

    assert RCARules().evidence_ids(state) == [
        "ev-log",
        "ev-code-a",
        "ev-code-b",
        "ev-code-c",
        "ev-code-d",
        "ev-kb-a",
        "ev-kb-b",
        "ev-kb-c",
    ]


def test_rca_evidence_ids_preserve_direct_source_snippet_with_graph_context() -> None:
    state = make_state(
        title="Request processing fails",
        description="A runtime event shows repeated processing.",
        affected_area="request processing",
    )
    add_evidence(
        state,
        evidence_id="ev-log",
        source_type=EvidenceSourceType.LOG,
        source_name="app.log",
        content="processing_started repeated_processing_detected=true",
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-semantic",
            source_type=EvidenceSourceType.CODE,
            source_name="src/services/processor.py",
            file_path="src/services/processor.py",
            content="Semantic summary of process_record implementation.",
            relevance_score=0.95,
            metadata={"retrieval_source_type": "code_semantic", "rank": "1"},
        )
    )
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-exact",
            source_type=EvidenceSourceType.CODE,
            source_name="src/services/processor.py",
            file_path="src/services/processor.py",
            line_start=19,
            line_end=20,
            content="19: if record_id in processed_records:\n20:     return",
            relevance_score=0.9,
            metadata={"retrieval_source_type": "code_exact", "rank": "2"},
        )
    )
    add_evidence(
        state,
        evidence_id="ev-graph",
        source_type=EvidenceSourceType.GRAPH,
        source_name="src/services/processor.py",
        file_path="src/services/processor.py",
        content="process_request calls process_record.",
    )

    evidence_ids = RCARules().evidence_ids(state)

    assert "ev-exact" in evidence_ids
    assert "ev-graph" in evidence_ids
