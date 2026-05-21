# RCA for Summary questions return chunk-level answers instead of full document summaries

## Incident Summary

Incident INC-006: Users report that "summarize the document" only summarizes one small chunk. There is no exception, but product expectations say summary-style queries should use document-level retrieval rather than chunk-level semantic search.

## Impact

Affected service: conversational_rag. Affected area: query routing and retrieval strategy selection.

## Symptoms

- Users report that "summarize the document" only summarizes one small chunk. There is no exception, but product expectations say summary-style queries should use document-level retrieval rather than chunk-level semantic search.
- 2026-05-20T11:03:12Z INFO conversational_rag.query request_id=req_711a Received query="summarize this document"
- 2026-05-20T11:03:12Z INFO conversational_rag.routing request_id=req_711a Router selected strategy="semantic_search" reason="query asks about document content"
- 2026-05-20T11:03:13Z INFO conversational_rag.retrieval request_id=req_711a Retrieved 3 chunks using strategy="semantic_search"
- 2026-05-20T11:03:14Z WARNING conversational_rag.response request_id=req_711a User feedback="summary only covered first section"

## Log Findings

- log-001 shows runtime signal: 2026-05-20T11:03:12Z INFO conversational_rag.query request_id=req_711a Received query="summarize this document"
- log-002 shows runtime signal: 2026-05-20T11:03:12Z INFO conversational_rag.routing request_id=req_711a Router selected strategy="semantic_search" reason="query asks about document content"
- log-003 shows runtime signal: 2026-05-20T11:03:13Z INFO conversational_rag.retrieval request_id=req_711a Retrieved 3 chunks using strategy="semantic_search"
- log-004 shows runtime signal: 2026-05-20T11:03:14Z WARNING conversational_rag.response request_id=req_711a User feedback="summary only covered first section"

## Code Findings

- src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- src/rag/retrieval/parent_child/strategy.py:71-114 contains implementation context relevant to the incident.
- src/rag/retrieval/hybrid/strategy.py:1-43 contains implementation context relevant to the incident.
- src/rag/routing/rule_based.py:71-150 maps document-level summary queries to the supported `parent_child` retrieval strategy.
- src/rag/retrievers.py:71-133 contains implementation context relevant to the incident.

## Knowledge Base Findings

- sample_data/knowledge_base/README.md documents expected behavior relevant to the incident: # Conversational RAG Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents. The system comb...
- sample_data/knowledge_base/query-routing-expectations.md documents expected behavior relevant to the incident: # Query Routing Expectations Summary-style queries such as: - "summarize this document" - "give me an overview" - "what are the key points" must use document-level retrieval, no...
- sample_data/knowledge_base/selected-document-routing.md documents expected behavior relevant to the incident: # Selected Document Retrieval Notes Selected-document retrieval depends on matching the UI-selected filename to the `source` metadata stored in the vector database. The matching...
- sample_data/knowledge_base/retrieval-strategies.md documents expected behavior relevant to the incident: # Retrieval Strategy Contract The conversational RAG application supports exactly three retrieval strategy values at runtime: - `hybrid` - `parent_child` - `fusion` `RetrievalSt...
- sample_data/knowledge_base/upload-ingestion.md documents expected behavior relevant to the incident: # Upload And Ingestion Notes Uploading a PDF should write the file, ingest the document, reset RAG caches, and make the new chunks available to retrieval. Duplicate filenames re...

## Hypotheses Considered

- H1: Runtime failure is caused by an implementation mismatch in the code path identified by the logs and code evidence.
- H2: The observed behavior is caused by missing validation or insufficient normalization around the failing code path.

## Final Root Cause

The incident is most likely caused by a mismatch between the runtime failure observed in logs and the implementation behavior shown in src/rag/service.py:71-150.

## Technical Explanation

EVID-LOG-C1DAD463: log-001 shows runtime signal: 2026-05-20T11:03:12Z INFO conversational_rag.query request_id=req_711a Received query="summarize this document" EVID-LOG-73A81F15: log-002 shows runtime signal: 2026-05-20T11:03:12Z INFO conversational_rag.routing request_id=req_711a Router selected strategy="semantic_search" reason="query asks about document content" EVID-LOG-D77749F3: log-003 shows runtime signal: 2026-05-20T11:03:13Z INFO conversational_rag.retrieval request_id=req_711a Retrieved 3 chunks using strategy="semantic_search" EVID-LOG-8750B6F1: log-004 shows runtime signal: 2026-05-20T11:03:14Z WARNING conversational_rag.response request_id=req_711a User feedback="summary only covered first section" evidence-kb-README: sample_data/knowledge_base/README.md documents expected behavior relevant to the incident: # Conversational RAG Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents. The system comb... evidence-kb-query-routing-expectations: sample_data/knowledge_base/query-routing-expectations.md documents expected behavior relevant to the incident: # Query Routing Expectations Summary-style queries such as: - "summarize this document" - "give me an overview" - "what are the key points" must use document-level retrieval, no... evidence-kb-selected-document-routing: sample_data/knowledge_base/selected-document-routing.md documents expected behavior relevant to the incident: # Selected Document Retrieval Notes Selected-document retrieval depends on matching the UI-selected filename to the `source` metadata stored in the vector database. The matching... evidence-kb-retrieval-strategies: sample_data/knowledge_base/retrieval-strategies.md documents expected behavior relevant to the incident: # Retrieval Strategy Contract The conversational RAG application supports exactly three retrieval strategy values at runtime: - `hybrid` - `parent_child` - `fusion` `RetrievalSt... evidence-kb-upload-ingestion: sample_data/knowledge_base/upload-ingestion.md documents expected behavior relevant to the incident: # Upload And Ingestion Notes Uploading a PDF should write the file, ingest the document, reset RAG caches, and make the new chunks available to retrieval. Duplicate filenames re... evidence-src/rag/service.py:71-150: src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path. evidence-src/rag/retrieval/parent_child/strategy.py:71-114: src/rag/retrieval/parent_child/strategy.py:71-114 contains implementation context relevant to the incident. evidence-src/rag/retrieval/hybrid/strategy.py:1-43: src/rag/retrieval/hybrid/strategy.py:1-43 contains implementation context relevant to the incident. evidence-src/rag/routing/rule_based.py:71-150: src/rag/routing/rule_based.py:71-150 maps document-level summary queries to the supported `parent_child` retrieval strategy. evidence-src/rag/retrievers.py:71-133: src/rag/retrievers.py:71-133 contains implementation context relevant to the incident.

## Evidence

- EVID-LOG-C1DAD463
- EVID-LOG-73A81F15
- EVID-LOG-D77749F3
- EVID-LOG-8750B6F1
- kb-README
- kb-query-routing-expectations
- kb-selected-document-routing
- kb-retrieval-strategies
- kb-upload-ingestion
- src/rag/service.py:71-150
- src/rag/retrieval/parent_child/strategy.py:71-114
- src/rag/retrieval/hybrid/strategy.py:1-43
- src/rag/routing/rule_based.py:71-150
- src/rag/retrievers.py:71-133

## Confidence

Score: 0.8

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Inspect and fix the code path at src/rag/service.py:71-150.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test for incident INC-006.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Generation Details

- writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: invalid_evidence_id

## Metadata

- evidence_count: 14
- dynamic_workflow: true
- rca_writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: invalid_evidence_id
