# RCA Report for Incident INC-007: Duplicate Document Records After Upload

## Incident Summary

Users reported seeing duplicate document records and repeated citations after uploading similar PDF files. The issue appears after normal upload flows and does not show a visible application error.

## Impact

Not specified

## Symptoms

- Users see duplicate document records after uploads
- Repeated citations in search results

## Log Findings

- 2026-05-20T12:14:01Z INFO conversational_rag.upload request_id=req_812b filename="benefits-guide.pdf" content_hash="sha256:9dd2a8" processed_uploads_before=0 ingestion_started=true
- 2026-05-20T12:16:34Z INFO conversational_rag.upload request_id=req_812c filename="benefits-guide-copy.pdf" content_hash="sha256:9dd2a8" processed_uploads_match=false dedupe_key="filename" ingestion_started=true
- 2026-05-20T12:18:09Z WARNING conversational_rag.retrieval request_id=req_812d duplicate_content_detected=true content_hash="sha256:9dd2a8" sources="benefits-guide.pdf,benefits-guide-copy.pdf"

## Code Findings

- The upload function checks for existing filenames in `st.session_state.processed_uploads` but does not consider content hash for deduplication (src/services/upload_service.py:1-80).
- The deduplication logic in `deduplicate_docs` uses both content and source but the upload flow solely relies on filename checks to prevent duplicates (src/helpers/deduplication.py:1-21).

## Knowledge Base Findings

- Uploading a PDF should write the file, ingest the document, reset RAG caches, and make new chunks available to retrieval (sample_data/knowledge_base/upload-ingestion.md).
- Content-level deduplication should use a stable file hash, not just the upload filename (sample_data/knowledge_base/upload-ingestion.md).

## Hypotheses Considered

- H1: The deduplication mechanism is failing to recognize documents with the same content hash if they have different filenames.
- H2: Upload flow logic does not properly account for existing document versions, allowing duplicates to be created.

## Final Root Cause

The upload flow records duplicate state by filename rather than content identity. Logs show the same content hash was accepted under a different filename and ingested again, creating duplicate document records and repeated retrieval citations.

## Technical Explanation

Runtime logs show two upload requests with the same content hash but different filenames. The second request reports `processed_uploads_match=false` and `dedupe_key="filename"`, then retrieval later reports duplicate sources for that same content hash. Code evidence from the upload path shows the content hash is available, but the duplicate guard is still based on uploaded filename state.

## Evidence

- EVID-LOG-71D7BD68
- EVID-LOG-1DF98EAE
- EVID-LOG-6CB17050
- kb-upload-ingestion
- src/services/upload_service.py:1-80
- src/helpers/deduplication.py:1-21

## Confidence

Score: 0.85

Reason: Confidence is high because logs show the same content hash being ingested under multiple filenames, code evidence points to upload deduplication state, and knowledge-base evidence documents expected content-hash deduplication behavior.

## Recommended Fix

Implement checks to use the computed content hash as the duplicate identity for uploads. Reject, version, or link same-content uploads before ingestion so that a different filename cannot create duplicate document records.

## Preventive Actions

Revise the upload handling logic to incorporate content hash checks for deduplication consistently across the application, ensuring accurate document management regardless of filename.

## Tests to Add

- Unit tests to validate document ingestion behavior with same content but different filenames.
- Integration tests to verify that uploading a document with an existing content hash prevents duplicate ingestion.

## Open Questions

- Are there any other parts of the application where filename-based duplicate checks are utilized?
- What impact will changing the deduplication criterion have on existing documents already uploaded?

## Low Confidence Warning

None

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- evidence_count: 13
- dynamic_workflow: true
- rca_writer: llm
- llm_output_validated: true
- fallback_used: false
