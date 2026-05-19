# RCA for LLM router falls back during summary questions

## Incident Summary

Incident INC-001: Users report that broad summary questions in auto retrieval mode intermittently use the fallback router instead of the LLM router, reducing retrieval quality and making answers less relevant.

## Impact

Affected service: conversational_rag. Affected area: automatic retrieval routing.

## Symptoms

- Users report that broad summary questions in auto retrieval mode intermittently use the fallback router instead of the LLM router, reducing retrieval quality and making answers less relevant.
- 2026-05-19T10:45:12Z ERROR conversational_rag request_id=req-inc-001 trace_id=trace-router-001 LLM router failed. Fallback used. Error: Invalid strategy: summary. Fallback reason: summary queries should use parent_child retrieval.

```text
Traceback (most recent call last):
  File "src/rag/service.py", line 55, in resolve_retrieval_strategy
    router_result = router.route(query=user_input, selected_document=selected_document)
  File "src/rag/routing/llm.py", line 82, in route
    raise ValueError(f"Invalid strategy: {result.strategy}")
ValueError: Invalid strategy: summary
```
- 2026-05-19T10:45:12Z WARNING conversational_rag request_id=req-inc-001 trace_id=trace-router-001 router_type=llm_fallback query="summarize this document" selected_document="transformer_notes.pdf" resolved_strategy=parent_child

## Log Findings

- log-001 shows the LLM router failed with `ValueError: Invalid strategy: summary` and triggered fallback.
- log-002 shows the fallback resolved the summary-style query to the supported `parent_child` retrieval strategy.

## Code Findings

- src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- src/rag/service.py:141-220 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- src/rag/retrieval/parent_child/strategy.py:71-114 contains implementation context relevant to the incident.
- tests/rag/routing/test_rule_based_router.py:1-80 maps summary-style selected-document queries to the supported `parent_child` retrieval strategy.
- src/rag/routing/rule_based.py:1-80 maps document-level summary queries to the supported `parent_child` retrieval strategy.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The LLM router emitted unsupported retrieval strategy value `summary`.
- H2: Summary-style document queries are expected to map to `parent_child`, but the LLM router output contract allowed the conceptual label `summary`.
- H3: Router validation rejects unsupported LLM strategy values and triggers fallback instead of normalizing the strategy.

## Final Root Cause

The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, causing the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Technical Explanation

The runtime logs show that the LLM router failed with `ValueError: Invalid strategy: summary` during retrieval strategy resolution. This indicates that the LLM router returned a strategy value that failed the router validation step. The fallback log and supporting evidence show that the same summary-style query resolves to `parent_child`, which is the supported retrieval strategy for broad document-summary intent. Therefore, the issue is a contract mismatch between the LLM router output vocabulary and the supported retrieval strategy values used by the application.

## Evidence

- EVID-LOG-D00A28C9
- EVID-LOG-F795570E
- src/rag/service.py:71-150
- src/rag/service.py:141-220
- src/rag/retrieval/parent_child/strategy.py:71-114
- tests/rag/routing/test_rule_based_router.py:1-80
- src/rag/routing/rule_based.py:1-80

## Confidence

Score: 0.8

Reason: Confidence is moderately high because logs show the exact exception `Invalid strategy: summary`, and code/test evidence points to the LLM routing validation path. Confidence is not 1.0 because knowledge-base evidence and the exact raw LLM router output payload were not captured.

## Recommended Fix

Update the LLM router prompt and/or structured output validation so the router emits only supported retrieval strategy values. For broad summary questions over a selected document, return `parent_child` directly or normalize `summary` to `parent_child` before validation.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test where query="summarize this document" and a selected document is present; assert the resolved strategy is `parent_child`.
- Add a test ensuring unsupported LLM strategy values are handled with a clear fallback reason and do not silently degrade routing quality.
- Add a contract test ensuring the LLM router can emit only supported retrieval strategy enum values.

## Open Questions

- What exact raw structured output did the LLM router return before validation failed?
- Does the LLM router prompt explicitly restrict strategy values to the supported retrieval strategy enum?

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
