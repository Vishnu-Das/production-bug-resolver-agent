# RCA for Unsupported retrieval strategy breaks chat responses

## Incident Summary

Incident INC-002: Chat requests fail with HTTP 500 after a deployment changed the retrieval strategy configuration to an unsupported value.

## Impact

Affected service: conversational_rag. Affected area: retrieval strategy selection.

## Symptoms

- Chat requests fail with HTTP 500 after a deployment changed the retrieval strategy configuration to an unsupported value.
- 2026-05-19T11:12:43Z ERROR conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 Chat response failed during document retrieval. strategy_name=semantic selected_document=All Documents

```text
Traceback (most recent call last):
  File "src/rag/service.py", line 84, in retrieve_documents
    retrieval_strategy = RetrievalStrategyFactory.get_strategy(strategy_name)
  File "src/rag/retrieval/factory.py", line 35, in get_strategy
    raise ValueError(f"Unsupported retrieval strategy: {strategy_name}")
ValueError: Unsupported retrieval strategy: semantic
```
- 2026-05-19T11:12:43Z WARNING conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 RETRIEVAL_STRATEGY=semantic is not one of supported strategies: hybrid,parent_child,fusion

## Log Findings

- log-001 shows runtime signal: 2026-05-19T11:12:43Z ERROR conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 Chat response failed during document retrieval. strategy_name=semantic selected...
- log-002 shows runtime signal: 2026-05-19T11:12:43Z WARNING conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 RETRIEVAL_STRATEGY=semantic is not one of supported strategies: hybrid,parent...

## Code Findings

- eval/compare_retrieval_strategies.py:71-150 contains evaluation context for retrieval or answer quality checks relevant to the incident.
- src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- tests/rag/retrieval/test_retrieval_factory.py:1-60 covers retrieval strategy factory behavior for supported and unsupported strategy names.
- tests/rag/routing/test_rule_based_router.py:71-98 contains implementation context relevant to the incident.
- src/rag/retrieval/hybrid/__init__.py:1-40 contains implementation context relevant to the incident.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: Runtime failure is caused by an implementation mismatch in the code path identified by the logs and code evidence.
- H2: The observed behavior is caused by missing validation or insufficient normalization around the failing code path.

## Final Root Cause

The configured or resolved retrieval strategy was `semantic`, but `semantic` is not one of the supported retrieval strategy values. `RetrievalStrategyFactory.get_strategy` rejected the value and raised `ValueError: Unsupported retrieval strategy: semantic`.

## Technical Explanation

Runtime logs show `RETRIEVAL_STRATEGY=semantic` reaching document retrieval. The retrieval factory supports `hybrid`, `parent_child`, and `fusion`; any other value is rejected with `ValueError`. This makes the incident a configuration contract failure between runtime settings and `src/rag/retrieval/factory.py`.

## Evidence

- EVID-LOG-C4911603
- EVID-LOG-46A22D95
- eval/compare_retrieval_strategies.py:71-150
- src/rag/service.py:71-150
- tests/rag/retrieval/test_retrieval_factory.py:1-60
- tests/rag/routing/test_rule_based_router.py:71-98
- src/rag/retrieval/hybrid/__init__.py:1-40

## Confidence

Score: 0.75

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Validate `RETRIEVAL_STRATEGY` at startup and restrict it to `hybrid`, `parent_child`, or `fusion`; reject or normalize unsupported values before request handling.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test for incident INC-002.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Metadata

- evidence_count: 7
- dynamic_workflow: true
