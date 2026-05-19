# Solution Recommendation for INC-004

## Summary

This recommendation addresses the issue of revised PDF uploads being skipped by duplicate upload guards, leading to stale indexed content. It outlines immediate and long-term steps to prevent future incidents and improve overall system reliability.

## Immediate Steps

- Change duplicate filename handling so revised uploads are explicitly rejected, versioned, or re-ingested with cache reset instead of being silently skipped.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests to ensure duplicate filename handling functions as intended.
- Centralize retrieval strategy validation to streamline and enhance error handling.
- Improve structured error handling and log raw router outputs when fallback occurs.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add a regression test specifically for incident INC-004.
- Add a test that covers the implicated implementation path for duplicate uploads.

## Monitoring Improvements

- Add structured logging around the implicated code path to aid in future incident analysis.
- Log request or trace identifiers with the error when available to improve traceability.

## Risk Notes

- The change in duplicate filename handling may introduce new behavior that needs monitoring to avoid unintended consequences.
- There is a risk that existing integrations could be affected if not properly versioned or managed after the change.

## Evidence

- EVID-LOG-69562DE2
- EVID-LOG-48ED8F7C
- src/rag/pipeline.py:1-58
- src/services/upload_service.py:1-77
- src/rag/service.py:211-246
- src/rag/retrieval/fusion/strategy.py:1-80
- src/conversationalAI.py:141-220

## Metadata

- recommendation_id: SOL-20260519-FDD2E779
- rca_report_id: RCA-20260519-2811EEB9
- confidence_score: 0.75
