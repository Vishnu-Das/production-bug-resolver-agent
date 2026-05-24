"""Safety signals used to validate generated patch diffs."""

PLACEHOLDER_IMPLEMENTATION_MARKERS = (
    "TODO",
    "Implementation needed",
    "... remaining code unchanged",
    "NotImplemented",
    "raise NotImplementedError",
)

UPLOAD_DEDUPE_TERMS = (
    "upload",
    "duplicate",
    "content_hash",
    "content hash",
    "ingestion",
)

UPLOAD_OWNERSHIP_TERMS = (
    "upload",
    "ingest",
    "ingestion",
    "dedup",
    "duplicate",
    "content_hash",
    "hash",
)

ROUTING_PATH_TERMS = (
    "router",
    "routing",
)

