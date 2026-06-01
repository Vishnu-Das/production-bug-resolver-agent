"""Tests for deterministic retrieval evidence normalization."""

from __future__ import annotations

from bug_resolver.retrieval.evidence_normalizer import EvidenceNormalizer
from bug_resolver.schemas import EvidenceCandidate, RetrievalEvidenceSourceType


def _candidate(**updates: object) -> EvidenceCandidate:
    values: dict[str, object] = {
        "candidate_id": "candidate-1",
        "source_type": RetrievalEvidenceSourceType.CODE_EXACT,
        "retriever_name": "exact_search",
        "content": "1: raise TypeError('bad input')",
    }
    values.update(updates)
    return EvidenceCandidate.model_validate(values)


def test_evidence_normalizer_drops_blank_content_candidate() -> None:
    candidate = EvidenceCandidate.model_construct(
        candidate_id="candidate-1",
        source_type=RetrievalEvidenceSourceType.CODE_EXACT,
        retriever_name="exact_search",
        content=" \n\t ",
    )

    normalized = EvidenceNormalizer().normalize([candidate])

    assert normalized == []


def test_evidence_normalizer_normalizes_file_path() -> None:
    candidate = _candidate(file_path="./src\\app.py")

    normalized = EvidenceNormalizer().normalize([candidate])

    assert normalized[0].file_path == "src/app.py"


def test_evidence_normalizer_deduplicates_matched_terms() -> None:
    candidate = _candidate(
        matched_terms=[" TypeError ", "TypeError", "", "handle_request"]
    )

    normalized = EvidenceNormalizer().normalize([candidate])

    assert normalized[0].matched_terms == ["TypeError", "handle_request"]


def test_evidence_normalizer_trims_content_edges() -> None:
    candidate = _candidate(content="\n  \n40: def handle_request():\n41:     return True\n \n")

    normalized = EvidenceNormalizer().normalize([candidate])

    assert normalized[0].content == "40: def handle_request():\n41:     return True"


def test_evidence_normalizer_preserves_candidate_id_and_metadata() -> None:
    candidate = _candidate(metadata={"purpose": "Find exact exception occurrence"})

    normalized = EvidenceNormalizer().normalize([candidate])

    assert normalized[0].candidate_id == "candidate-1"
    assert normalized[0].metadata == {"purpose": "Find exact exception occurrence"}
