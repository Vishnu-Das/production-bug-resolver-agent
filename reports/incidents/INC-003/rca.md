# RCA for Selected Document Summary Returns No Answer

## Incident Summary

Users experienced an issue where selecting a specific PDF document to summarize resulted in either an empty or irrelevant answer. This occurred despite the document being present in the vector store.

## Impact

High severity incident affecting the conversational_rag service, specifically the selected document retrieval functionality.

## Symptoms

- Empty or irrelevant answers from the document summary request.
- The specified document exists in the vector store.

## Log Findings

- WARNING: retrieval returned no matching sources for selected_document='Transformer Notes.pdf' (log-001)
- ERROR: retrieved_docs_count=0 and final_docs_count=0 for query 'summarize this document' with selected_document='Transformer Notes.pdf' (log-002)

## Code Findings

- The retrieval strategy implementation may misidentify documents based on filename normalization (src/rag/service.py:141-220, src/rag/service.py:71-150).
- Caching mechanism in place; however, it may not account for document filename discrepancies (src/rag/cache.py:1-34).

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The issue is caused by a mismatch between the filename provided by the UI and the filename in the vector store due to differences in case or format.
- H2: An error in the retrieval strategy implementation causes it to fail in fetching correct documents.

## Final Root Cause

Selected-document retrieval returned zero documents because the UI-selected filename did not match the stored vector metadata source for the same PDF after normalization.

## Technical Explanation

Runtime logs indicate `selected_document="Transformer Notes.pdf"` while the available metadata contains `transformer_notes.pdf`. The parent-child retrieval path filters sources by normalized filename, so discrepancies in casing or formatting can lead to exclusion of the intended document.

## Evidence

- EVID-LOG-EA5A6718
- EVID-LOG-E1E9F537
- src/rag/service.py:141-220
- src/rag/service.py:71-150
- src/rag/cache.py:1-34

## Confidence

Score: 0.75

Reason: Confidence level is based on the quality and diversity of evidence available, combined with a thorough evaluation process.

## Recommended Fix

Normalize selected-document names and stored source metadata with the same case-insensitive, separator-safe, whitespace-safe rules before applying parent-child retrieval filters.

## Preventive Actions

Implement a robust validation mechanism for document filenames to ensure consistency and correctness before storing them in the vector store.

## Tests to Add

- Create tests to confirm that filenames are normalized before retrieval processes are executed.
- Test retrieval functionality with various casing, spacing, and formatting scenarios to ensure document matching works correctly.

## Open Questions

- What specific rules should be defined for filename normalization?
- Are there other document retrieval scenarios affected by similar normalization issues?

## Low Confidence Warning

None

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- evidence_count: 7
- dynamic_workflow: true
- rca_writer: llm
- llm_output_validated: true
- fallback_used: false
