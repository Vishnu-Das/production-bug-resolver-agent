# Solution Recommendation for INC-002

## Summary

Recommended solution based on RCA RCA-20260519-564C3613: The configured or resolved retrieval strategy was `semantic`, but `semantic` is not one of the supported retrieval strategy values. `RetrievalStrategyFactory.get_strategy` rejected the value and raised `ValueError: Unsupported retrieval strategy: semantic`.

## Immediate Steps

- Validate `RETRIEVAL_STRATEGY` at startup and restrict it to `hybrid`, `parent_child`, or `fusion`; reject or normalize unsupported values before request handling.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add a regression test for incident INC-002.
- Add a test covering the implicated implementation path.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- None

## Evidence

- EVID-LOG-C4911603
- EVID-LOG-46A22D95
- eval/compare_retrieval_strategies.py:71-150
- src/rag/service.py:71-150
- tests/rag/retrieval/test_retrieval_factory.py:1-60
- tests/rag/routing/test_rule_based_router.py:71-98
- src/rag/retrieval/hybrid/__init__.py:1-40

## Metadata

- recommendation_id: SOL-20260519-1C09B824
- rca_report_id: RCA-20260519-564C3613
- confidence_score: 0.75
