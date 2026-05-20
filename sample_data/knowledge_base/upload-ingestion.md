# Upload And Ingestion Notes

Uploading a PDF should write the file, ingest the document, reset RAG caches,
and make the new chunks available to retrieval.

Duplicate filenames require explicit handling. If a revised PDF is uploaded with
the same filename, the application should not silently return before ingestion.
It should either reject the upload with a user-visible message, version the file,
or replace and re-ingest the existing document.

The upload path in `src/services/upload_service.py` uses
`st.session_state.processed_uploads` and an existing-file check. These guards can
prevent ingestion and cache reset when a user uploads a new document version with
the same filename.

Content-level deduplication should use a stable file hash, not only the upload
filename. Two filenames with the same content hash should not create duplicate
document records or duplicate retrieval citations.
