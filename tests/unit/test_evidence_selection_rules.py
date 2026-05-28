"""Tests for incident-term extraction rules."""

from __future__ import annotations

from bug_resolver.rules.evidence_selection_rules import EvidenceSelectionRules
from bug_resolver.schemas import EvidenceItem, EvidenceSourceType, Incident, WorkflowState


def make_state(*, title: str, description: str) -> WorkflowState:
    return WorkflowState(
        incident=Incident(
            incident_id="INC-TEST",
            title=title,
            description=description,
            affected_service="target_service",
            affected_area="runtime quality",
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


def test_incident_terms_include_runtime_log_tokens_without_expansion() -> None:
    state = make_state(
        title="Duplicate documents after upload",
        description="Users see duplicate citations.",
    )
    add_log(
        state,
        'content_hash="abc123" dedupe_key="filename" duplicate_content_detected=true',
    )

    terms = EvidenceSelectionRules().selection_terms(state)

    assert {"duplicate", "upload", "content_hash", "filename"} <= terms
    assert "deduplication" not in terms
    assert "identity" not in terms


def test_incident_terms_keep_observed_quality_tokens() -> None:
    state = make_state(
        title="Answers cite unrelated sources",
        description="Answer quality is worse after deployment.",
    )
    add_log(
        state,
        'reranker_model=null scores="0.0,0.0,0.0,0.0" order_changed=false',
    )

    terms = EvidenceSelectionRules().selection_terms(state)

    assert {"scores", "order_changed", "reranker_model", "quality"} <= terms
    assert "configuration" not in terms


def test_generic_text_returns_base_tokens() -> None:
    state = make_state(
        title="Cache refresh delayed",
        description="Background worker returned stale records.",
    )

    terms = EvidenceSelectionRules().selection_terms(state)

    assert {"cache", "refresh", "delayed", "background", "worker", "stale"} <= terms


def test_stopwords_are_removed_from_base_terms() -> None:
    state = make_state(
        title="The service is not responding",
        description="Users report that the service is slow.",
    )

    terms = EvidenceSelectionRules().selection_terms(state)

    assert "the" not in terms
    assert "is" not in terms
    assert "that" not in terms
    assert "service" not in terms
    assert "responding" in terms
    assert "slow" in terms


def test_tokens_split_snake_case_and_keep_original_token() -> None:
    tokens = EvidenceSelectionRules().tokens("content_hash order_changed")

    assert {"content_hash", "content", "hash"} <= tokens
    assert {"order_changed", "order", "changed"} <= tokens
