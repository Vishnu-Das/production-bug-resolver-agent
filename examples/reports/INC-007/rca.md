# RCA Report for Incident INC-007: Duplicate Documents After Upload

## Incident Summary

Users reported seeing duplicate document records and repeated citations after uploading similar PDF files. This issue arose despite no visible application errors during the upload process.

## Impact

Medium disruption for users interacting with uploaded documents, affecting retrieval accuracy and citation integrity.

## Symptoms

- Duplicate document records visible in retrieval results
- Repeated citations in search outcomes

## Log Findings

- 2026-05-20T12:14:01Z INFO conversational_rag.upload request_id=req_812b filename="benefits-guide.pdf" content_hash="sha256:9dd2a8" processed_uploads_before=0 ingestion_started=true
- 2026-05-20T12:16:34Z INFO conversational_rag.upload request_id=req_812c filename="benefits-guide-copy.pdf" content_hash="sha256:9dd2a8" processed_uploads_match=false dedupe_key="filename" ingestion_started=true
- 2026-05-20T12:18:09Z WARNING conversational_rag.retrieval request_id=req_812d duplicate_content_detected=true content_hash="sha256:9dd2a8" sources="benefits-guide.pdf,benefits-guide-copy.pdf"

## Code Findings

- src/services/upload_service.py:11-60 computes upload content state but still gates duplicate handling through filename-based Streamlit session state before ingestion.

## Knowledge Base Findings

- sample_data/knowledge_base/upload-ingestion.md documents expected behavior relevant to the incident: Uploading a PDF should write the file, ingest the document, reset RAG caches, and make the new chunks available to retrieval. Duplicate filenames require explicit handling.
- sample_data/knowledge_base/README.md documents expected behavior relevant to the incident: Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents.

## Hypotheses Considered

- H1: The deduplication process relies solely on filenames, causing duplicate entries when content is the same but filenames differ.
- H2: The upload flow properly identifies duplicates but fails to prevent ingestion of duplicate content.

## Final Root Cause

The upload flow records duplicate state by filename rather than content identity. Logs show the same content hash was accepted under a different filename and ingested again, creating duplicate document records and repeated retrieval citations.

## Technical Explanation

Runtime logs show two upload requests with the same content hash but different filenames. The second request reports `processed_uploads_match=false` and `dedupe_key="filename"`, then retrieval later reports duplicate sources for that same content hash. Code evidence from the upload path shows the content hash is available, but the duplicate guard is still based on uploaded filename state.

## Evidence

- EVID-LOG-6B0568A5
- EVID-LOG-C81BE5BF
- EVID-LOG-D6EF5B24
- src/services/upload_service.py:handle_file_upload
- kb-upload-ingestion
- kb-README

## Confidence

Score: 0.85

Reason: Confidence is high because logs show the same content hash being ingested under multiple filenames, code evidence points to upload deduplication state, and knowledge-base evidence documents expected content-hash deduplication behavior.

## Recommended Fix

Use the computed content hash as the duplicate identity for uploads. Reject, version, or link same-content uploads before ingestion so a different filename cannot create duplicate document records.

## Preventive Actions

Implement robust checks that leverage content hashes during the upload process to prevent ingestion of duplicate files with different names.

## Tests to Add

- Unit tests to validate that uploads with the same content hash but different filenames are handled correctly during the upload process.
- Automated tests to ensure that ingestion logic verifies content identity and prevents duplicates.
- Integration tests to assess the overall upload and retrieval pipeline, focusing on maintaining unique document identities.

## Open Questions

- What strategies can be implemented to inform users when they attempt to upload a document with the same content?
- How will the system handle versioning of documents that are updated frequently without changing filenames?

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
