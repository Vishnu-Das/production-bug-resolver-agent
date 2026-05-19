# Solution Recommendation for INC-002

## Summary

Recommended solution based on RCA RCA-20260519-A2D768CF: The incident is most likely caused by a mismatch between the runtime failure observed in logs and the implementation behavior shown in src/rag/retrieval/factory.py:1-42.

## Immediate Steps

- Inspect and fix the code path at src/rag/retrieval/factory.py:1-42.
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

- EVID-LOG-9A35466D
- EVID-LOG-8E849FA9
- evidence-src/rag/retrieval/factory.py:1-42
- evidence-src/rag/service.py:71-150
- evidence-src/rag/retrieval/hybrid/strategy.py:1-43
- evidence-src/rag/retrieval/hybrid/__init__.py:1-40
- evidence-tests/rag/retrieval/test_retrieval_factory.py:1-60

## Metadata

- recommendation_id: SOL-20260519-84474ABC
- rca_report_id: RCA-20260519-A2D768CF
- confidence_score: 0.75
