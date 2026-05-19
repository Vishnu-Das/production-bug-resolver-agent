# RCA Report for Incident INC-001

## Incident Summary

Users reported that broad summary questions in auto retrieval mode intermittently used the fallback router instead of the LLM router, leading to reduced retrieval quality and less relevant answers.

## Impact

High impact on the quality of responses generated for user queries regarding broad summaries, leading to potential user dissatisfaction and decreased trust in the conversational agent's capabilities.

## Symptoms

- LLM router fails during summary questions
- Fallback routing occurs for summary queries
- Users receive less relevant answers

## Log Findings

- 2026-05-19T10:45:12Z ERROR conversational_rag request_id=req-inc-001 trace_id=trace-router-001 LLM router failed. Fallback used. Error: Invalid strategy: summary. Fallback reason: summary queries should use parent_child retrieval.
- 2026-05-19T10:45:12Z WARNING conversational_rag request_id=req-inc-001 trace_id=trace-router-001 router_type=llm_fallback query="summarize this document" selected_document="transformer_notes.pdf" resolved_strategy=parent_child

## Code Findings

- The LLM router raises ValueError for invalid strategy in `src/rag/routing/llm.py` resulting in fallback to another router.
- The fallback resolves summary-type queries correctly to parent_child retrieval in the routing logic.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The LLM router emits an unsupported retrieval strategy causing the fallback to occur.
- H2: The retrieval prompt fed to the LLM is incorrectly configured, leading to invalid strategies being returned.

## Final Root Cause

The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, causing the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Technical Explanation

The runtime logs show that the LLM router failed with `ValueError: Invalid strategy: summary` during retrieval strategy resolution. This indicates that the LLM router returned a strategy value that failed the router validation step. Code evidence from `src/rag/routing/llm.py` points to the LLM routing path where the returned strategy is validated. The fallback log and supporting evidence show that the same summary-style query resolves to `parent_child`, which is the supported retrieval strategy for broad document-summary intent. The issue arises from a contract mismatch between the LLM router output vocabulary and the supported retrieval strategy values used by the application.

## Evidence

- EVID-LOG-6E169B71
- EVID-LOG-6225C4F0
- tests/rag/routing/test_llm_router.py:71-138
- src/rag/routing/llm.py:71-110
- src/rag/retrieval/parent_child/strategy.py:71-114

## Confidence

Score: 0.8

Reason: Confidence is moderately high because logs show the exact exception `Invalid strategy: summary`, and code/test evidence points to the LLM routing validation path. Confidence is not 1.0 because knowledge-base evidence and the exact raw LLM router output payload were not captured.

## Recommended Fix

Update the LLM router prompt and/or structured output validation so the router emits only supported retrieval strategy values. For broad summary questions over a selected document, return `parent_child` directly or normalize `summary` to `parent_child` before validation.

## Preventive Actions

Implement stricter validation on the retrieval strategy emitted from the LLM router and ensure alignment with supported strategies to prevent similar issues in the future.

## Tests to Add

- Add unit tests to confirm proper emission of supported strategies from the LLM router for summary queries.
- Create integration tests that validate the retrieval routing behavior for a variety of summary queries.

## Open Questions

- What specific changes to the LLM prompt will prevent it from emitting unsupported strategies?
- Are there other queries not currently handled by supported strategies?

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
