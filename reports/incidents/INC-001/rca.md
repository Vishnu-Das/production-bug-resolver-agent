# RCA Report for INC-001: LLM Router Fallback during Summary Questions

## Incident Summary

Users reported that when using broad summary questions in auto retrieval mode, the system intermittently falls back to a less effective router instead of utilizing the LLM router, thereby degrading the retrieval quality of answers.

## Impact

Loss of retrieval accuracy on broad summary questions which affects user trust and satisfaction with the application.

## Symptoms

- Errors logged indicating LLM router fallback
- Inconsistent retrieval results when querying summary-related documents
- Reduction in answer relevancy for summary questions

## Log Findings

- 2026-05-19T10:45:12Z ERROR conversational_rag request_id=req-inc-001 trace_id=trace-router-001 LLM router failed. Fallback used. Error: Invalid strategy: summary. Fallback reason: summary queries should use parent_child retrieval.
- 2026-05-19T10:45:12Z WARNING conversational_rag request_id=req-inc-001 trace_id=trace-router-001 router_type=llm_fallback query="summarize this document" selected_document="transformer_notes.pdf" resolved_strategy=parent_child

## Code Findings

- The LLM router validation step returns a ValueError when an unsupported strategy like 'summary' is produced, as seen in the path C:\Users\vishn\Documents\Learning AI\conversational_rag\src\rag\routing\llm.py:71-110.
- The fallback router properly resolves broad summary queries using the parent_child strategy, confirming that this is the expected behavior for such queries.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The LLM router is incorrectly generating 'summary' as a retrieval strategy, causing it to fall back to the rule-based router.
- H2: The fallback behavior is a safety mechanism ensuring that unsupported retrieval strategies do not result in system failures.

## Final Root Cause

The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, which caused the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Technical Explanation

The runtime logs show that the LLM router failed with `ValueError: Invalid strategy: summary` during retrieval strategy resolution. This indicates that the LLM router returned a strategy value that failed the router validation step. Code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\src\rag\routing\llm.py:71-110 points to the LLM routing path where the returned strategy is validated. The fallback log and supporting evidence show that the same summary-style query resolves to `parent_child`, which serves as the supported retrieval strategy for broad document-summary intent. Therefore, the issue is a contract mismatch between the LLM router output vocabulary and the supported retrieval strategy values used by the application.

## Evidence

- EVID-LOG-AAF4A2E5
- EVID-LOG-03350DDE
- src/rag/routing/llm.py:71-110
- src/rag/retrieval/parent_child/strategy.py:1-80
- src/rag/retrieval/parent_child/strategy.py:71-114

## Confidence

Score: 0.8

Reason: Confidence is moderately high because logs show the exact exception `Invalid strategy: summary`, and code/test evidence points to the LLM routing validation path. Confidence is not 1.0 due to a lack of knowledge-base evidence and the exact raw LLM router output payload not being captured.

## Recommended Fix

Update the LLM router prompt and/or structured output validation so the router emits only supported retrieval strategy values. For broad summary questions over a selected document, return `parent_child` directly or normalize `summary` to `parent_child` before validation.

## Preventive Actions

Establish a more robust validation mechanism for router strategy outputs to ensure they conform to the predefined set of acceptable strategies before they are returned.

## Tests to Add

- Test scenarios where the LLM router returns unsupported strategies to ensure proper fallback behavior is triggered.
- Unit tests to validate that valid strategies are consistently returned for summary queries.

## Open Questions

- What specific conditions lead the LLM router to output the invalid strategy 'summary'?
- How can we improve logging around the retrieval strategies to capture more detailed output for analysis?

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
