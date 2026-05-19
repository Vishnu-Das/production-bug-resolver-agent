# RCA for Selected document summary returns no answer

## Incident Summary

Incident INC-003: Users selecting a specific PDF and asking for a summary receive an empty or irrelevant answer even though the document exists in the vector store.

## Impact

Affected service: conversational_rag. Affected area: selected document retrieval.

## Symptoms

- Users selecting a specific PDF and asking for a summary receive an empty or irrelevant answer even though the document exists in the vector store.
- 2026-05-19T12:03:08Z WARNING conversational_rag request_id=req-inc-003 trace_id=trace-selected-doc-003 parent_child retrieval returned no matching sources selected_document="Transformer Notes.pdf" normalized_selected="Transformer Notes.pdf" available_source="transformer_notes.pdf"
- 2026-05-19T12:03:09Z ERROR conversational_rag request_id=req-inc-003 trace_id=trace-selected-doc-003 query="summarize this document" selected_document="Transformer Notes.pdf" resolved_strategy=parent_child retrieved_docs_count=0 final_docs_count=0

## Log Findings

- log-001 shows runtime signal: 2026-05-19T12:03:08Z WARNING conversational_rag request_id=req-inc-003 trace_id=trace-selected-doc-003 parent_child retrieval returned no matching sources selected_document="Tra...
- log-002 shows the fallback resolved the summary-style query to the supported `parent_child` retrieval strategy.

## Code Findings

- eval/strategy_questions.json:1-24 contains evaluation context for retrieval or answer quality checks relevant to the incident.
- eval/questions.json:1-50 contains evaluation context for retrieval or answer quality checks relevant to the incident.
- src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- src/rag/retrieval/parent_child/strategy.py:71-114 contains implementation context relevant to the incident.
- src/rag/retrievers.py:71-133 contains implementation context relevant to the incident.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: Runtime failure is caused by an implementation mismatch in the code path identified by the logs and code evidence.
- H2: The observed behavior is caused by missing validation or insufficient normalization around the failing code path.

## Final Root Cause

Selected-document retrieval returned zero documents because the UI-selected filename did not match the stored vector metadata source for the same PDF after normalization.

## Technical Explanation

Runtime logs show `selected_document="Transformer Notes.pdf"` while available metadata contains `transformer_notes.pdf`, followed by `retrieved_docs_count=0`. The parent-child retrieval path filters sources by normalized filename, so filename casing, spacing, or underscore mismatches can exclude the intended document.

## Evidence

- EVID-LOG-2C79EA5F
- EVID-LOG-15B291C4
- eval/strategy_questions.json:1-24
- eval/questions.json:1-50
- src/rag/service.py:71-150
- src/rag/retrieval/parent_child/strategy.py:71-114
- src/rag/retrievers.py:71-133

## Confidence

Score: 0.75

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Normalize selected-document names and stored source metadata with the same case-insensitive, separator-safe, whitespace-safe rules before applying parent-child retrieval filters.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test for incident INC-003.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Generation Details

- writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: selected_hypothesis_id_not_found

## Metadata

- evidence_count: 7
- dynamic_workflow: true
- rca_writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: selected_hypothesis_id_not_found
