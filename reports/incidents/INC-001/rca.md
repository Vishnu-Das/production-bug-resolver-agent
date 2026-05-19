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

- tests/rag/routing/test_llm_router.py:71-138 validates the LLM router strategy and raises an error when the model returns an unsupported value.
- src/rag/retrieval/factory.py:1-42 shows relevant implementation behavior: from src.rag.retrieval.base import ( BaseRetrievalStrategy ) from src.rag.retrieval.hybrid.strategy import ( HybridRetrievalStrategy ) from src.rag.retrieval.parent_child.strate...
- src/rag/routing/rule_based.py:1-80 maps summary-style selected-document queries to the supported `parent_child` retrieval strategy.
- C:/Users/vishn/Documents/Learning AI/conversational_rag/eval/compare_retrieval_strategies.py:71-150 shows relevant implementation behavior: actual_strategy = strategy_name if strategy_name == "auto": router = RouterStrategyFactory.get_router() router_result = router.route( query=question, selected_document=selected_...
- tests/rag/retrieval/test_retrieval_factory.py:1-60 shows relevant implementation behavior: from unittest.mock import Mock, patch import pytest from src.rag.retrieval.factory import RetrievalStrategyFactory @patch("src.rag.retrieval.factory.HybridRetrievalStrategy") de...

## Knowledge Base Findings

- sample_data/knowledge_base/README.md documents expected behavior relevant to the incident: # Conversational RAG Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents. The system comb...

## Hypotheses Considered

- H1: The LLM router emitted unsupported retrieval strategy value `summary`.
- H2: Summary-style document queries are expected to map to `parent_child`, but the LLM router output contract allowed the conceptual label `summary`.
- H3: Router validation rejects unsupported LLM strategy values and triggers fallback instead of normalizing the strategy.

## Final Root Cause

The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, causing the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Technical Explanation

The runtime logs show that the LLM router failed with `ValueError: Invalid strategy: summary` during retrieval strategy resolution. This indicates that the LLM router returned a strategy value that failed the router validation step. The fallback log and supporting evidence show that the same summary-style query resolves to `parent_child`, which is the supported retrieval strategy for broad document-summary intent. Therefore, the issue is a contract mismatch between the LLM router output vocabulary and the supported retrieval strategy values used by the application.

## Evidence

- EVID-LOG-3D205121
- EVID-LOG-AD350D86
- evidence-kb-README
- evidence-tests/rag/routing/test_llm_router.py:71-138
- evidence-src/rag/retrieval/factory.py:1-42
- evidence-src/rag/routing/rule_based.py:1-80
- evidence-eval/compare_retrieval_strategies.py:71-150
- evidence-tests/rag/retrieval/test_retrieval_factory.py:1-60

## Confidence

Score: 0.85

Reason: Confidence is high because logs show the exact exception `Invalid strategy: summary`, code evidence points to the LLM routing validation path, and knowledge-base evidence describes the expected summary-query routing behavior. Confidence is not 1.0 because the exact raw LLM router output payload and prompt response were not captured.

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

## Metadata

- evidence_count: 8
- dynamic_workflow: true
