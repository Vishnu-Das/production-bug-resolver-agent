# RCA Report for Answers Citing Unrelated Sources After Deployment

## Incident Summary

Following a recent deployment, users reported that the conversational_rag service started to return answers that cite unrelated sources. Although no 500 errors occurred, feedback indicated a noticeable decline in answer quality.

## Impact

High impact on user satisfaction and reliability of the service, as relevant sources are not being accurately cited in responses, leading to a potential reduction in trust and effectiveness of the conversational assistant.

## Symptoms

- Returned answers cite unrelated or irrelevant sources.
- Degraded quality of responses compared to prior deployments.
- User feedback explicitly points to incorrect citations.
- Service operates without 500 errors, indicating stability in backend operations.

## Log Findings

- 2026-05-20T09:02:10Z INFO conversational_rag.config request_id=deploy_91f RERANKING_MODEL_NAME="" deployment_profile="demo"
- 2026-05-20T09:07:42Z INFO conversational_rag.retrieval request_id=req_913f strategy="hybrid" retrieved_docs=10 query="what is the reimbursement deadline"
- 2026-05-20T09:07:42Z WARNING conversational_rag.reranker request_id=req_913f reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T09:08:05Z WARNING conversational_rag.response request_id=req_913f user_feedback="answer cited onboarding policy instead of reimbursement policy"

## Code Findings

- src/reranker.py:rerank_documents defines fallback behavior if the reranking model is not configured properly.
- src/reranker.py:rerank_documents_with_scores processes retrieved documents, returning them unchanged if no model is loaded.
- src/rag/retrieval/hybrid/strategy.py:HybridRetrievalStrategy.retrieve handles document retrieval but does not enforce strict checks on model availability.

## Graph Findings

- src/reranker.py:rerank_documents_with_scores is called by process_documents_with_scores, which orchestrates document processing after retrieval.
- src/rag/service.py:stream_response shows relationships to several core methods handling query result processing and reranking.

## Knowledge Base Findings

- sample_data/knowledge_base/README.md outlines the role of hybrid retrieval in improving accuracy and response relevance.
- sample_data/knowledge_base/retrieval-strategies.md specifies the acceptable retrieval strategies and their intended operational logic.

## Hypotheses Considered

- H1: The reranking model was not deployed correctly, causing outputs to rely on default behavior with unchanged document order.
- H2: Document retrieval strategies are operating incorrectly, resulting in irrelevant sources being cited.

## Final Root Cause

The reranker model configuration was absent, leading to fallback behavior where retrieved documents returned neutral scores and maintained their original order, instead of warning about misconfiguration or failing explicitly.

## Technical Explanation

Logs indicate that hybrid retrieval was performed successfully, but the reranker identified no loaded model at runtime. Consequently, it returned the original document order with neutral scores, failing to improve retrieval quality. This situation bypasses necessary reevaluation of document relevance for question answering, resulting in unfiltered citations in user responses.

## Evidence

- EVID-LOG-421C1259
- EVID-LOG-9BFE5F83
- EVID-LOG-D134312C
- EVID-LOG-14032D15
- src/reranker.py:rerank_documents
- src/reranker.py:rerank_documents_with_scores
- src/rag/retrieval/hybrid/strategy.py:HybridRetrievalStrategy.retrieve
- graph-src/reranker.py:rerank_documents_with_scores
- graph-src/rag/service.py:stream_response
- kb-README
- kb-retrieval-strategies

## Confidence

Score: 0.85

Reason: Confidence is high since logs clearly show missing reranker configuration resulting in default behavior and unchanged document order. This aligns with the code and knowledge base explanations about how reranking should operate effectively.

## Recommended Fix

Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode at startup, and replace silent neutral-score fallback with a clear warning or fail-fast configuration error.

## Preventive Actions

Implement stricter validation checks for model configurations during startup and enhance logging to capture potential misconfigurations early in the workflow.

## Tests to Add

- Unit tests to ensure the reranker raises an error or warning if the model is missing during initialization.
- Integration tests that verify that the service does not proceed with neutral-ranking behavior when misconfigurations occur.
- End-to-end tests that ensure documents are correctly reranked and matched with relevant queries.

## Open Questions

- What additional checks can be implemented to warn users of misconfigurations during deployment?
- How can we improve the observability of the retrieval and reranking processes to catch issues earlier?
- Should we provide better documentation for deployment processes and required configurations?

## Low Confidence Warning

None

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- evidence_count: 19
- dynamic_workflow: true
- rca_writer: llm
- llm_output_validated: true
- fallback_used: false
