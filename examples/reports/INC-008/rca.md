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

- src/reranker.py:63-122 loads the cross-encoder reranker and defines fallback behavior for scoring and ordering retrieved documents.
- src/ui/retrieval_inspector.py:165-285 contains implementation context relevant to the incident.
- eval/compare_retrieval_strategies.py:58-154 contains evaluation context for retrieval or answer quality checks relevant to the incident.

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

- EVID-LOG-F84E91A8
- EVID-LOG-A7EA5804
- EVID-LOG-C29EFB7C
- EVID-LOG-2C44CDFC
- src/reranker.py:rerank_documents_with_scores
- src/ui/retrieval_inspector.py:render_retrieval_inspector
- eval/compare_retrieval_strategies.py:evaluate_strategy

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

- evidence_count: 9
- dynamic_workflow: true
- rca_writer: deterministic_fallback
- llm_output_validated: false
- fallback_used: true
- fallback_reason: internal_evidence_prefix_in_prose
