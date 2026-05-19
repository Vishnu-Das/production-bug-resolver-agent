# Solution Recommendation for INC-004

## Summary

Recommended solution based on RCA RCA-20260519-83573411: A revised PDF upload with the same filename was skipped by duplicate upload guards, so ingestion and cache reset did not run and retrieval continued serving stale indexed content.

## Immediate Steps

- Change duplicate filename handling so revised uploads are explicitly rejected, versioned, or re-ingested with cache reset instead of being silently skipped.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add a regression test for incident INC-004.
- Add a test covering the implicated implementation path.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- None

## Evidence

- EVID-LOG-1B081F12
- EVID-LOG-78EE8605
- src/services/upload_service.py:1-77
- src/rag/retrievers.py:1-80
- src/conversationalAI.py:141-220
- src/reranker.py:1-80
- src/rag/cache.py:1-34

## Metadata

- recommendation_id: SOL-20260519-D3AFF33B
- rca_report_id: RCA-20260519-83573411
- confidence_score: 0.75
