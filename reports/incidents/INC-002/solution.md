# Solution Recommendation for INC-002

## Summary

Recommended solution based on RCA RCA-20260519-ECD728FB: The configured or resolved retrieval strategy was `semantic`, but `semantic` is not one of the supported retrieval strategy values. `RetrievalStrategyFactory.get_strategy` rejected the value and raised `ValueError: Unsupported retrieval strategy: semantic`.

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

- EVID-LOG-D7A53BF1
- EVID-LOG-A00CA8AE
- src/rag/service.py:141-220
- src/rag/cache.py:1-34
- main.py:1-6
- src/rag/service.py:1-80
- src/rag/service.py:71-150

## Metadata

- recommendation_id: SOL-20260519-550BE096
- rca_report_id: RCA-20260519-ECD728FB
- confidence_score: 0.75
