# Query Routing Expectations

Summary-style queries such as:

- "summarize this document"
- "give me an overview"
- "what are the key points"

must use document-level retrieval, not chunk-level semantic search.

The expected strategy for summary queries is document_summary or equivalent
document-level retrieval.

Semantic chunk retrieval is intended for factual lookup and narrow Q&A.
