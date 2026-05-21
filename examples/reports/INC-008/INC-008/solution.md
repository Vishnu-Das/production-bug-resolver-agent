# Solution Recommendation for INC-008

## Summary

The root cause of the incident was identified as the absence of a reranker model configuration, which led to silent fallback behavior that resulted in unrelated sources being cited. Immediate and long-term actions are recommended to address this issue and prevent recurrence.

## Immediate Steps

- Require `RERANKING_MODEL_NAME` or an explicit reranking-disabled mode at startup, and replace silent neutral-score fallback with a clear warning or fail-fast configuration error.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests for reranking functionality.
- Centralize retrieval strategy validation processes to ensure consistent evaluation.
- Improve structured error handling in the reranking code path.
- Log raw router outputs when fallback scenarios occur.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add a startup/configuration test that fails or warns clearly when `RERANKING_MODEL_NAME` is missing.
- Add a retrieval pipeline test proving reranking changes candidate ordering or reports an explicit disabled state.

## Monitoring Improvements

- Add structured logging around the implicated code path for better traceability.
- Log request or trace identifiers with the error when available.

## Risk Notes

- Risk of further incidents if the reranker configuration issue is not resolved promptly.
- Potential impacts on retrieval accuracy if neutral scores are returned without appropriate warnings.

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

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260521-9635EC34
- rca_report_id: RCA-20260521-451927FB
- confidence_score: 0.85
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
