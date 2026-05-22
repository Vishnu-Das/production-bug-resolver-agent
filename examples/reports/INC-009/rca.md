# RCA Report for INC-009: Reranker Config Issue

## Incident Summary

After deployment, it was observed that the configuration value `RERANKING_MODEL_NAME` did not affect the answer ranking in the conversational RAG service. Consequently, answer citations appeared unrelated, and the original order of answers was maintained inappropriately, which necessitated an investigation into the reranking behavior and the function responsible for reading the reranker configuration.

## Impact

The incident has a high severity as it affects the retrieval ranking configuration, leading to potential miscommunication with users and inaccurate information retrieval.

## Symptoms

- Answer citations look unrelated.
- Reranking appears to keep the original order of documents.

## Log Findings

- 2026-05-20T10:02:10Z INFO conversational_rag.config request_id=deploy_92a expected_config="RERANKING_MODEL_NAME" deployment_profile="production-like"
- 2026-05-20T10:05:44Z WARNING conversational_rag.reranker request_id=req_991a reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T10:05:45Z WARNING conversational_rag.diagnostics request_id=req_991a structural_hint="identify config reader for RERANKING_MODEL_NAME and caller chain for rerank_documents_with_scores"

## Code Findings

- src/reranker.py:rerank_documents loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.
- src/reranker.py:rerank_documents_with_scores loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.
- src/reranker.py:load_reranker loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.

## Graph Findings

- src/reranker.py:rerank_documents_with_scores shows structural code relationship: calls RankedDocument, doc.metadata.get, ranked_documents.sort, reranker_model.predict; called by process_documents_with_scores; imported by src/rag/pipeline.py.
- src/reranker.py:rerank_documents shows structural code relationship: calls reranker_model.predict, scored_docs.sort; called by process_documents, stream_response; imported by src/rag/pipeline.py.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The reranker model configuration is not being loaded correctly at startup.
- H2: The reranker implementation is bypassing the configuration check leading to neutral score generation.

## Final Root Cause

The reranker model configuration was absent, and the reranker path silently returned the original retrieval order with neutral scores instead of warning or failing through an explicit fallback policy.

## Technical Explanation

Runtime logs indicate that the hybrid retrieval returned candidates, but the reranking reported a null model with neutral scores and unchanged ordering. The code evidence shows that missing model configuration can return unreranked documents instead of surfacing a clear warning or initialization error.

## Evidence

- EVID-LOG-C78F4C2A
- EVID-LOG-64541C3D
- EVID-LOG-128E5BB6
- EVID-LOG-419A38F7
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

Implement a validation step at startup to ensure required configurations are set correctly, and enhance logging to capture configuration issues more effectively.

## Tests to Add

- Test cases to validate that the `RERANKING_MODEL_NAME` is loaded correctly and triggers reranking behavior.
- Unit tests to ensure that correct warnings are raised when the model configuration is missing.

## Open Questions

- What specific scenarios lead to the reranker model being null?
- Are there other configurations that might not be properly validated?

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
