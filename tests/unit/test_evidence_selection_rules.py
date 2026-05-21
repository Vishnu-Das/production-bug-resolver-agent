"""Tests for evidence selection signal expansion rules."""

from __future__ import annotations

from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, Incident, WorkflowState


def make_state(*, title: str, description: str) -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-TEST",
            title=title,
            description=description,
            affected_service="conversational_rag",
            affected_area="retrieval quality",
        )
    )


def add_log(state: WorkflowState, content: str) -> None:
    state.add_evidence(
        EvidenceItem(
            evidence_id="ev-log",
            source_type=EvidenceSourceType.LOG,
            source_name="app.log",
            content=content,
        )
    )


def test_upload_profile_expands_content_hash_filename_and_upload_signals() -> None:
    state = make_state(
        title="Duplicate documents after upload",
        description="Users see duplicate citations.",
    )
    add_log(
        state,
        'content_hash="abc123" dedupe_key="filename" duplicate_content_detected=true',
    )

    signals = EvidenceSelectionRules().selection_signals(state)

    assert {"upload", "dedup", "deduplication", "content_hash", "filename"} <= signals
    assert {"content", "hash", "processed_uploads"} <= signals


def test_reranker_profile_expands_order_changed_scores_and_model_signals() -> None:
    state = make_state(
        title="Answers cite unrelated sources",
        description="Answer quality is worse after deployment.",
    )
    add_log(
        state,
        'reranker_model=null scores="0.0,0.0,0.0,0.0" order_changed=false',
    )

    signals = EvidenceSelectionRules().selection_signals(state)

    assert {"reranker", "scores", "score", "order_changed"} <= signals
    assert {"ranking", "model", "config", "configuration"} <= signals


def test_summary_routing_profile_expands_strategy_signals() -> None:
    state = make_state(
        title="Summary questions return chunk answers",
        description="The query used semantic_search instead of document_summary.",
    )
    add_log(state, 'query="summarize this document" strategy="semantic_search"')

    signals = EvidenceSelectionRules().selection_signals(state)

    assert {"summary", "summarize", "semantic_search", "document_summary"} <= signals
    assert {"routing", "router", "query", "parent_child"} <= signals


def test_generic_text_returns_base_tokens() -> None:
    state = make_state(
        title="Cache refresh delayed",
        description="Background worker returned stale records.",
    )

    signals = EvidenceSelectionRules().selection_signals(state)

    assert {"cache", "refresh", "delayed", "background", "worker", "stale"} <= signals


def test_stopwords_are_removed_from_base_signals() -> None:
    state = make_state(
        title="The service is not responding",
        description="Users report that the service is slow.",
    )

    signals = EvidenceSelectionRules().selection_signals(state)

    assert "the" not in signals
    assert "is" not in signals
    assert "that" not in signals
    assert "service" not in signals
    assert "responding" in signals
    assert "slow" in signals


def test_tokens_split_snake_case_and_keep_original_token() -> None:
    tokens = EvidenceSelectionRules().tokens("content_hash order_changed")

    assert {"content_hash", "content", "hash"} <= tokens
    assert {"order_changed", "order", "changed"} <= tokens
