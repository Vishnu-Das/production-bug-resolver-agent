# Selected Document Retrieval Notes

Selected-document retrieval depends on matching the UI-selected filename to the
`source` metadata stored in the vector database.

The matching behavior should be case-insensitive and should normalize path
separators, URL encoding, and whitespace. If a user selects `Transformer
Notes.pdf`, but stored metadata contains `transformer_notes.pdf`, parent-child
retrieval can return zero matching sources even though the document exists.

For document-level questions such as "summarize this document", the router
should resolve to `parent_child`, and the parent-child retriever should either
find matching sources or emit a clear diagnostic explaining the filename
mismatch.
