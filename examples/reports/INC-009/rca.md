# RCA for Reranker config value does not affect answer ranking

## Incident Summary

Incident INC-009: After deployment, the team expected RERANKING_MODEL_NAME to control reranking behavior, but answer citations still look unrelated and reranking appears to keep the original order. The investigation needs to identify which function reads the reranker config and which request path calls reranking before response generation.

## Impact

Affected service: conversational_rag. Affected area: retrieval ranking configuration.

## Symptoms

- After deployment, the team expected RERANKING_MODEL_NAME to control reranking behavior, but answer citations still look unrelated and reranking appears to keep the original order. The investigation needs to identify which function reads the reranker config and which request path calls reranking before response generation.
- 2026-05-20T10:02:10Z INFO conversational_rag.config request_id=deploy_92a expected_config="RERANKING_MODEL_NAME" deployment_profile="production-like"
- 2026-05-20T10:05:44Z INFO conversational_rag.retrieval request_id=req_991a strategy="fusion" retrieved_docs=10 query="what is the reimbursement deadline"
- 2026-05-20T10:05:44Z WARNING conversational_rag.reranker request_id=req_991a reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T10:05:45Z WARNING conversational_rag.diagnostics request_id=req_991a structural_hint="identify config reader for RERANKING_MODEL_NAME and caller chain for rerank_documents_with_scores"

## Log Findings

- log-001 shows runtime signal: 2026-05-20T10:02:10Z INFO conversational_rag.config request_id=deploy_92a expected_config="RERANKING_MODEL_NAME" deployment_profile="production-like"
- log-002 shows runtime signal: 2026-05-20T10:05:44Z INFO conversational_rag.retrieval request_id=req_991a strategy="fusion" retrieved_docs=10 query="what is the reimbursement deadline"
- log-003 shows runtime signal: 2026-05-20T10:05:44Z WARNING conversational_rag.reranker request_id=req_991a reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- log-004 shows runtime signal: 2026-05-20T10:05:45Z WARNING conversational_rag.diagnostics request_id=req_991a structural_hint="identify config reader for RERANKING_MODEL_NAME and caller chain for rerank_docu...

## Code Findings

- src/reranker.py:rerank_documents loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.
- src/reranker.py:rerank_documents_with_scores loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.
- src/reranker.py:load_reranker loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.

## Graph Findings

- src/reranker.py:rerank_documents_with_scores shows structural code relationship: uses config from load_reranker, which reads RERANKING_MODEL_NAME; called by process_documents_with_scores; imported by src/rag/pipeline.py.
- src/reranker.py:rerank_documents shows structural code relationship: uses config from load_reranker, which reads RERANKING_MODEL_NAME; called by process_documents, stream_response; imported by src/rag/pipeline.py.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: Retrieval quality degraded because reranking was silently bypassed when the reranker model configuration was missing.
- H2: Hybrid retrieval returned candidate chunks, but answer quality fell because no cross-encoder scores reordered those candidates.

## Final Root Cause

The reranker model configuration was absent, and the reranker path silently returned the original retrieval order with neutral scores instead of warning or failing through an explicit fallback policy.

## Technical Explanation

Runtime logs show hybrid retrieval returned candidates, then reranking reported a null model with neutral scores and unchanged ordering. Code evidence from the reranker path shows missing model configuration can return unreranked documents instead of surfacing a clear warning or startup/configuration failure.

## Evidence

- EVID-LOG-0BDA6CF6
- EVID-LOG-D9DFE519
- EVID-LOG-151776A2
- EVID-LOG-71A472F9
- src/reranker.py:rerank_documents
- src/reranker.py:rerank_documents_with_scores
- src/reranker.py:load_reranker
- graph-src/reranker.py:rerank_documents_with_scores
- graph-src/reranker.py:rerank_documents

## Confidence

Score: 0.8

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
- fallback_reason: internal_evidence_prefix_in_prose

## Metadata

- evidence_count: 14
- dynamic_workflow: true
- rca_writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: internal_evidence_prefix_in_prose
