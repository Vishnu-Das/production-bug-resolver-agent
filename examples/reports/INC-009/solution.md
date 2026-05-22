# Solution Recommendation for INC-009

## Summary

The reranker model configuration was absent, and the reranker path silently returned the original retrieval order with neutral scores instead of warning or failing through an explicit fallback policy.

## Immediate Steps

- Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode at startup, and replace silent neutral-score fallback with a clear warning or fail-fast configuration error.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.
- Validate the caller/callee, config-reader, or ownership path identified by graph evidence before applying the fix.

## Long-Term Steps

- Add regression tests to ensure the reranking model configuration is validated on startup.
- Centralize retrieval strategy validation to ensure consistency across components.
- Improve structured error handling for better visibility on failures.
- Log raw router outputs when fallback occurs for easier troubleshooting.

## Tests to Add

- Add a startup/configuration test that fails or warns clearly when `RERANKING_MODEL_NAME` is missing.
- Add a retrieval pipeline test proving reranking changes candidate ordering or reports an explicit disabled state.

## Monitoring Improvements

- Add structured logging around the implicated code path to capture significant events and errors.
- Log request or trace identifiers with the error when available.

## Risk Notes

- Without immediate action, the system may continue to silently fail in reranking scenarios, leading to degraded user experience.
- Failure to properly address the rerank configuration can cause future incidents or regressions.

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

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260522-469EC1AD
- rca_report_id: RCA-20260522-E8A11C24
- confidence_score: 0.8
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
