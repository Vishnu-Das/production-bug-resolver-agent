# RCA Report for Incident INC-008

## Incident Summary

Following a recent deployment, users reported that the conversational RAG service began citing sources that were unrelated to their questions. While there were no internal server errors, the quality of the answers provided significantly decreased, prompting further investigation.

## Impact

User trust in the service may decline due to inaccuracies in source citation, potentially leading to decreased usage and engagement with the system.

## Symptoms

- Answers citing unrelated sources.
- Quality of responses has visibly degraded after deployment.

## Log Findings

- 2026-05-20T09:02:10Z INFO conversational_rag.config request_id=deploy_91f RERANKING_MODEL_NAME="" deployment_profile="demo"
- 2026-05-20T09:07:42Z INFO conversational_rag.retrieval request_id=req_913f strategy="hybrid" retrieved_docs=10 query="what is the reimbursement deadline"
- 2026-05-20T09:07:42Z WARNING conversational_rag.reranker request_id=req_913f reranker_model=null ranked_docs=4 scores="0.0,0.0,0.0,0.0" order_changed=false
- 2026-05-20T09:08:05Z WARNING conversational_rag.response request_id=req_913f user_feedback="answer cited onboarding policy instead of reimbursement policy"

## Code Findings

- The absence of a configured reranking model leads to neutral scores in reranked documents, which could return unreranked documents without warnings or errors as indicated in the code evidence from the reranker path.

## Knowledge Base Findings

- The knowledge base emphasizes that a valid `RERANKING_MODEL_NAME` must be present for hybrid retrieval to ensure quality control and the effectiveness of the answer generation.

## Hypotheses Considered

- H1: The reranker model was not correctly configured during the latest deployment, resulting in improper scoring and ordering of retrieved documents.
- H2: Changes in retrieval strategy may have led to an incorrect prioritization of sources, affecting the relevancy of cited materials.

## Final Root Cause

The reranker model configuration was absent, causing the reranking process to silently bypass necessary evaluations, thereby degrading the quality of the answer citations.

## Technical Explanation

Logs indicate that although the hybrid retrieval returned candidates, the absence of the reranking model (null) resulted in unchanged document ordering with neutral scores. Analysis shows that without a properly configured model, the system should ideally fail and notify administrators, rather than return results with evaluated neutral scores.

## Evidence

- EVID-LOG-400F413C
- EVID-LOG-3A945581
- EVID-LOG-B050A0B8
- kb-reranking-configuration

## Confidence

Score: 0.85

Reason: Log contents clearly show the missing reranker configuration alongside neutral rerank scores and unchanged document order; supported by coding logic and knowledge-base guidelines emphasizing the importance of proper reranking configurations for retrieval quality.

## Recommended Fix

Implement a requirement for a valid `RERANKING_MODEL_NAME` or explicitly denote a disabled reranking mode at startup. Additionally, replace any silent neutral-score fallback functionality with a clear warning or configuration error to prevent similar issues in the future.

## Preventive Actions

Establish a robust check mechanism during deployment to ensure that all necessary configuration parameters, including `RERANKING_MODEL_NAME`, are validated beforehand. Enhance logging to explicitly alert for any missing configurations that impact response quality.

## Tests to Add

- Add unit tests for reranking configuration validation to catch missing model names before service deployment.
- Implement integration tests to evaluate the retrieval and reranking process, checking the end-to-end flow of responses for accuracy and alignment with expected document sources.

## Open Questions

- What additional configurations might contribute to ensuring the retrieval strategy operates as intended?
- How can we further improve user feedback collection to identify issues more rapidly in the future?

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
