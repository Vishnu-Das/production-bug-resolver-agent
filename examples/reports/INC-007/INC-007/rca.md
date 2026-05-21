# RCA Report: Duplicate Document Ingestion Issue

## Incident Summary

Users reported seeing duplicate document records and repeated citations after uploading similar PDF files in the conversational RAG application. This issue arose after the normal upload procedures without any visible application error.

## Impact

Medium impact on user experience due to confusion from duplicate document records and citations, which can lead to a decrease in user trust and efficiency.

## Symptoms

- Duplicate document records in the system
- Repeated citations displayed in user query responses

## Log Findings

- 2026-05-20T12:14:01Z INFO conversational_rag.upload request_id=req_812b filename="benefits-guide.pdf" content_hash="sha256:9dd2a8" processed_uploads_before=0 ingestion_started=true
- 2026-05-20T12:16:34Z INFO conversational_rag.upload request_id=req_812c filename="benefits-guide-copy.pdf" content_hash="sha256:9dd2a8" processed_uploads_match=false dedupe_key="filename" ingestion_started=true
- 2026-05-20T12:18:09Z WARNING conversational_rag.retrieval request_id=req_812d duplicate_content_detected=true content_hash="sha256:9dd2a8" sources="benefits-guide.pdf,benefits-guide-copy.pdf"

## Code Findings

- The duplicate guard in the upload flow checks for existing filenames rather than content hashes in `src/services/upload_service.py`.
- Content-level deduplication relies on a stable file hash in `src/helpers/deduplication.py`, but filename-based checks are currently being applied.

## Knowledge Base Findings

- The knowledge base indicates that duplicate filenames require explicit handling before ingestion to prevent identical content from being recorded as duplicates in `sample_data/knowledge_base/upload-ingestion.md`.
- It suggests rejecting, versioning, or replacing existing documents to avoid duplication.

## Hypotheses Considered

- H1: The application accepts uploads based on filename state instead of content hash leading to duplicates.
- H2: The upload process is not properly enforcing deduplication based on content, allowing similar documents to be processed multiple times.

## Final Root Cause

The upload flow records duplicate state by filename rather than content identity. Logs show the same content hash was accepted under a different filename, and ingested again, creating duplicate document records and repeated retrieval citations.

## Technical Explanation

Runtime logs indicate two upload requests with the same content hash but distinct filenames. The second request reports `processed_uploads_match=false` and `dedupe_key="filename"`. Retrieval later confirms duplicate sources for that same content hash. The code from the upload path shows that the content hash is computed, but the deduplication check is incorrectly based on uploaded filename state.

## Evidence

- EVID-LOG-3DFA2AAD
- EVID-LOG-ADC038FA
- EVID-LOG-F0A8B17D
- src/services/upload_service.py:1-80
- src/helpers/deduplication.py:1-21
- kb-upload-ingestion

## Confidence

Score: 0.85

Reason: Confidence is high because logs show the same content hash being ingested under multiple filenames, code evidence points to upload deduplication state, and knowledge-base evidence documents expected content-hash deduplication behavior.

## Recommended Fix

Implement checks using the computed content hash as the duplicate identity for uploads, rejecting, versioning, or linking uploads with the same content hash regardless of filename before ingestion to prevent duplicate document records.

## Preventive Actions

Enhance the upload system to enforce content-based deduplication consistently across all upload scenarios to eliminate duplicate entries and improve user experience.

## Tests to Add

- Add unit tests to validate the deduplication logic based on content hash in the upload process.
- Implement integration tests to simulate user uploads with identical content and different filenames.

## Open Questions

- How can we inform users of duplicate content uploads to help understand the limitation?
- Will there be a need to process historical data for duplicates created under the current scheme?

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
