# RCA for Answers cite unrelated sources after deployment

## Incident Summary

Incident INC-008: Users report that answers recently started citing sources that look unrelated to their questions. The service still returns responses and there are no 500 errors, but answer quality appears worse after deployment.

## Impact

Affected service: conversational_rag. Affected area: retrieval ranking quality.

## Symptoms

- Users report that answers recently started citing sources that look unrelated to their questions. The service still returns responses and there are no 500 errors, but answer quality appears worse after deployment.
- 2026-05-20T09:02:10Z INFO conversational_rag.config request_id=deploy_91f RERANKING_MODEL_NAME="" deployment_profile="demo"
- 2026-05-20T09:07:42Z INFO conversational_rag.retrieval request_id=req_913f strategy="hybrid" retrieved_docs=10 query="what is the reimbursement deadline"
- 2026-05-20T09:07:42Z WARNING conversational_rag.reranker request_id=req_913f reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T09:08:05Z WARNING conversational_rag.response request_id=req_913f user_feedback="answer cited onboarding policy instead of reimbursement policy"

## Log Findings

- log-001 shows runtime signal: 2026-05-20T09:02:10Z INFO conversational_rag.config request_id=deploy_91f RERANKING_MODEL_NAME="" deployment_profile="demo"
- log-002 shows runtime signal: 2026-05-20T09:07:42Z INFO conversational_rag.retrieval request_id=req_913f strategy="hybrid" retrieved_docs=10 query="what is the reimbursement deadline"
- log-003 shows runtime signal: 2026-05-20T09:07:42Z WARNING conversational_rag.reranker request_id=req_913f reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- log-004 shows runtime signal: 2026-05-20T09:08:05Z WARNING conversational_rag.response request_id=req_913f user_feedback="answer cited onboarding policy instead of reimbursement policy"

## Code Findings

- src/rag/routing/rule_based.py:71-150 maps document-level summary queries to the supported `parent_child` retrieval strategy.
- src/rag/service.py:71-150 resolves the retrieval strategy, retrieves documents, reranks results, and builds the final RAG response path.
- src/rag/retrieval/hybrid/strategy.py:1-43 contains implementation context relevant to the incident.
- eval/compare_retrieval_strategies.py:71-150 contains evaluation context for retrieval or answer quality checks relevant to the incident.
- src/rag/retrieval/parent_child/strategy.py:71-114 contains implementation context relevant to the incident.

## Knowledge Base Findings

- sample_data/knowledge_base/README.md documents expected behavior relevant to the incident: # Conversational RAG Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents. The system comb...
- sample_data/knowledge_base/query-routing-expectations.md documents expected behavior relevant to the incident: # Query Routing Expectations Summary-style queries such as: - "summarize this document" - "give me an overview" - "what are the key points" must use document-level retrieval, no...
- sample_data/knowledge_base/selected-document-routing.md documents expected behavior relevant to the incident: # Selected Document Retrieval Notes Selected-document retrieval depends on matching the UI-selected filename to the `source` metadata stored in the vector database. The matching...
- sample_data/knowledge_base/retrieval-strategies.md documents expected behavior relevant to the incident: # Retrieval Strategy Contract The conversational RAG application supports exactly three retrieval strategy values at runtime: - `hybrid` - `parent_child` - `fusion` `RetrievalSt...
- sample_data/knowledge_base/upload-ingestion.md documents expected behavior relevant to the incident: # Upload And Ingestion Notes Uploading a PDF should write the file, ingest the document, reset RAG caches, and make the new chunks available to retrieval. Duplicate filenames re...

## Hypotheses Considered

- H1: Retrieval quality degraded because reranking was silently bypassed when the reranker model configuration was missing.
- H2: Hybrid retrieval returned candidate chunks, but answer quality fell because no cross-encoder scores reordered those candidates.

## Final Root Cause

The reranker model configuration was absent, and the reranker path silently returned the original retrieval order with neutral scores instead of warning or failing through an explicit fallback policy.

## Technical Explanation

Runtime logs show hybrid retrieval returned candidates, then reranking reported a null model with neutral scores and unchanged ordering. Code evidence from the reranker path shows missing model configuration can return unreranked documents instead of surfacing a clear warning or startup/configuration failure.

## Evidence

- EVID-LOG-0FC354B1
- EVID-LOG-74DFCA4E
- EVID-LOG-71C42F59
- EVID-LOG-1F93EE1C
- kb-README
- kb-query-routing-expectations
- kb-selected-document-routing
- kb-retrieval-strategies
- kb-upload-ingestion
- src/rag/routing/rule_based.py:71-150
- src/rag/service.py:71-150
- src/rag/retrieval/hybrid/strategy.py:1-43
- eval/compare_retrieval_strategies.py:71-150
- src/rag/retrieval/parent_child/strategy.py:71-114

## Confidence

Score: 0.85

Reason: Confidence is high because logs show missing reranker configuration, neutral rerank scores, and unchanged ordering; code and knowledge-base evidence explain that silent reranker bypass degrades retrieval quality.

## Recommended Fix

Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode at startup, and replace silent neutral-score fallback with a clear warning or fail-fast configuration error.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a startup/configuration test that fails or warns clearly when `RERANKING_MODEL_NAME` is missing.
- Add a retrieval pipeline test proving reranking changes candidate ordering or reports an explicit disabled state.

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
