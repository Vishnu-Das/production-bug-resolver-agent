# RCA for Reuploaded PDF content is not refreshed

## Incident Summary

Incident INC-004: Users upload a revised PDF with the same filename, but the chat continues answering from the older document content.

## Impact

Affected service: conversational_rag. Affected area: document upload and ingestion.

## Symptoms

- Users upload a revised PDF with the same filename, but the chat continues answering from the older document content.
- 2026-05-19T13:21:44Z WARNING conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 upload ignored because filename already exists in session processed_uploads filename="policy_handbook.pdf" ingestion_started=false cache_reset=false
- 2026-05-19T13:22:10Z ERROR conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 stale document content served after duplicate upload filename="policy_handbook.pdf" expected_revision="2026-Q2" indexed_revision="2026-Q1"

## Log Findings

- log-001 shows runtime signal: 2026-05-19T13:21:44Z WARNING conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 upload ignored because filename already exists in session processed_uploads file...
- log-002 shows runtime signal: 2026-05-19T13:22:10Z ERROR conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 stale document content served after duplicate upload filename="policy_handbook.pdf...

## Code Findings

- src/services/upload_service.py:1-77 handles PDF uploads, duplicate filename checks, document ingestion, cache reset, and Streamlit upload state.
- src/rag/retrievers.py:1-80 contains implementation context relevant to the incident.
- src/conversationalAI.py:141-220 contains implementation context relevant to the incident.
- src/reranker.py:1-80 contains implementation context relevant to the incident.
- src/rag/cache.py:1-34 defines cache reset behavior for RAG retrievers and cached retrieval results.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: Runtime failure is caused by an implementation mismatch in the code path identified by the logs and code evidence.
- H2: The observed behavior is caused by missing validation or insufficient normalization around the failing code path.

## Final Root Cause

A revised PDF upload with the same filename was skipped by duplicate upload guards, so ingestion and cache reset did not run and retrieval continued serving stale indexed content.

## Technical Explanation

Runtime logs show a duplicate upload for `policy_handbook.pdf` was ignored before ingestion and cache reset, followed by stale answers from revision `2026-Q1` when `2026-Q2` was expected. The upload path therefore needs explicit replace/version/re-ingest behavior for same-name document revisions.

## Evidence

- EVID-LOG-1B081F12
- EVID-LOG-78EE8605
- src/services/upload_service.py:1-77
- src/rag/retrievers.py:1-80
- src/conversationalAI.py:141-220
- src/reranker.py:1-80
- src/rag/cache.py:1-34

## Confidence

Score: 0.75

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Change duplicate filename handling so revised uploads are explicitly rejected, versioned, or re-ingested with cache reset instead of being silently skipped.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test for incident INC-004.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Metadata

- evidence_count: 7
- dynamic_workflow: true
