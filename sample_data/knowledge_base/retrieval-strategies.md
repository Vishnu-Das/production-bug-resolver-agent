# Retrieval Strategy Contract

The conversational RAG application supports exactly three retrieval strategy
values at runtime:

- `hybrid`
- `parent_child`
- `fusion`

`RetrievalStrategyFactory.get_strategy` should only receive one of these values.
Configuration values such as `semantic`, `vector`, `summary`, or `default` are
not supported retrieval strategy names and should be normalized or rejected
before request handling.

When `RETRIEVAL_STRATEGY=auto`, the router is responsible for returning one of
the supported strategy names. When a static `RETRIEVAL_STRATEGY` is configured,
startup validation should catch unsupported values before chat traffic reaches
`src/rag/service.py::retrieve_documents`.
