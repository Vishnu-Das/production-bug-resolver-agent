# RCA Report for Incident INC-009: Reranker Config Value Does Not Affect Answer Ranking

## Incident Summary

After the deployment, the conversational_rag service exhibited behavior where the expected reranking based on the RERANKING_MODEL_NAME configuration did not occur. The ranked document order remained unchanged, and the scores were consistently neutral, leading the team to investigate the root cause of this issue.

## Impact

The retrieval process's effectiveness is critically impacted, as users receive answers that do not reflect appropriate ranking, potentially degrading user experience and trust in the system.

## Symptoms

- Reranking did not change the order of documents returned
- Neutral scores were observed in the reranking process
- Warnings about null reranker model in logs were noted

## Log Findings

- 2026-05-20T10:02:10Z INFO conversational_rag.config request_id=deploy_92a expected_config="RERANKING_MODEL_NAME" deployment_profile="production-like"
- 2026-05-20T10:05:44Z WARNING conversational_rag.reranker request_id=req_991a reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T10:05:45Z WARNING conversational_rag.diagnostics request_id=req_991a structural_hint="identify config reader for RERANKING_MODEL_NAME and caller chain for rerank_documents_with_scores"

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

- H1: The RERANKING_MODEL_NAME was not properly set during deployment, leading to no effective reranker model being loaded.
- H2: The reranking function is not correctly calling or using the configured reranking model.

## Final Root Cause

The reranker model configuration was absent, causing the reranker path to silently return the original retrieval order with neutral scores instead of warning or failing through an explicit fallback policy.

## Technical Explanation

Runtime logs indicate that the hybrid retrieval returned documents, but when the reranking function was invoked, it encountered a null model, leading to neutral scores and unchanged document order. The code in the reranking path clearly indicates that without a valid model, the system defaults to return documents in the original order instead of throwing an error or warning.

## Evidence

- EVID-LOG-C59D775C
- EVID-LOG-8CFB6413
- EVID-LOG-C617C101
- EVID-LOG-4A5B22C2
- src/reranker.py:rerank_documents
- src/reranker.py:rerank_documents_with_scores
- src/reranker.py:load_reranker
- graph-src/reranker.py:rerank_documents_with_scores
- graph-src/reranker.py:rerank_documents

## Confidence

Score: 0.8

Reason: Confidence is high due to log entries that indicate a missing reranker configuration, combined with neutral rerank scores and unchanged ordering, corroborated by the supporting code behavior.

## Recommended Fix

Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode at startup, and replace silent neutral-score fallback with a clear warning or fail-fast configuration error.

## Preventive Actions

Implement rigorous configuration management practices and validation checks during deployment to ensure critical configurations are set. Additionally, improve logging to explicitly highlight configuration issues.

## Tests to Add

- Validate that a configured `RERANKING_MODEL_NAME` activates the reranking process properly and produces varying document scores.
- Introduce tests to confirm that missing reranker configurations produce immediate errors instead of silently falling back to original ordering.

## Open Questions

- What processes exist to verify that configuration values are correctly set before deployment?
- How can we enhance our logging framework to catch such configuration issues early?

## Low Confidence Warning

None

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- evidence_count: 14
- dynamic_workflow: true
- rca_writer: llm
- llm_output_validated: true
- fallback_used: false
