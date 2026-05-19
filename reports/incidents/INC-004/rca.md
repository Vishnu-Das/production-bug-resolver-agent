# RCA Report for Incident INC-004: Reuploaded PDF Content Not Refreshing

## Incident Summary

Users experienced issues where re-uploading a revised PDF with the same filename did not result in updated responses from the system, indicating that the older document content continued to be utilized instead of the new revision.

## Impact

The incident affects the accuracy of responses provided by the conversational_rag service, which relies on correctly ingested document content. This could lead to user frustration and misinformation due to stale content being served.

## Symptoms

- Revised PDF uploaded but older content served in responses.
- Warning logs indicating upload ignored due to filename conflict.
- Error logs showing stale document content served after duplicate upload.

## Log Findings

- 2026-05-19T13:21:44Z WARNING conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 upload ignored because filename already exists in session processed_uploads filename="policy_handbook.pdf" ingestion_started=false cache_reset=false
- 2026-05-19T13:22:10Z ERROR conversational_rag request_id=req-inc-004 trace_id=trace-upload-004 stale document content served after duplicate upload filename="policy_handbook.pdf" expected_revision="2026-Q2" indexed_revision="2026-Q1"

## Code Findings

- The upload_service.py implementation prevents re-uploading a file with the same name to safeguard against duplicate uploads, but it does not allow versioning or re-ingesting of updated documents with the same filename.
- The reset_rag_caches function is not triggered when a duplicate file is attempted to be uploaded, leading to stale cached content being served.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The system is configured to prevent duplicate file uploads without allowing for versioning or updates to existing files.
- H2: The caching mechanism does not properly handle updates to documents with the same filename.

## Final Root Cause

A revised PDF upload with the same filename was skipped by duplicate upload guards, so ingestion and cache reset did not run and retrieval continued serving stale indexed content.

## Technical Explanation

Runtime logs show that the upload for `policy_handbook.pdf` was ignored due to existing records in `processed_uploads`, thus bypassing the necessary ingestion and cache reset processes. As a result, when the revised document was expected, stale content from an earlier version was served instead.

## Evidence

- EVID-LOG-AFF13819
- EVID-LOG-FB73282E
- src/services/upload_service.py:1-77
- src/rag/cache.py:1-34

## Confidence

Score: 0.75

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Change duplicate filename handling so revised uploads are explicitly rejected, versioned, or re-ingested with cache reset instead of being silently skipped.

## Preventive Actions

Implement a versioning system or a clear user prompt to notify users when an existing filename is detected, allowing them to choose whether to overwrite, version, or quit the upload process.

## Tests to Add

- Unit tests for handling duplicate file uploads to ensure proper versioning or rejection handling.
- Integration tests to verify cache clearing and data retrieval accurately reflect the most recent document version.

## Open Questions

- What user experience is desirable when an uploaded file conflicts with an existing filename?
- Are there specific use cases where users need to retain multiple versions of the same document?
- How will users be informed about the impact of their file uploads on the chat responses?

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
