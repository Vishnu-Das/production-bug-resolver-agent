# Solution Recommendation for INC-001

## Summary

The LLM router emitted `summary` as a retrieval strategy, which is unsupported, leading to a fallback to a rule-based router. This indicates a mismatch between the LLM router output and the expected retrieval strategy values.

## Immediate Steps

- Update the LLM router prompt or validation to emit only supported retrieval strategy values. Map `summary` to `parent_child` for relevant queries.
- Reproduce the incident locally using the same conditions that led to the failure.
- Verify the updated behavior against the log symptoms and the evidence from the RCA.

## Long-Term Steps

- Add regression tests to ensure `parent_child` is returned for summary questions over selected documents.
- Centralize the retrieval strategy validation process to ensure consistency across components.
- Improve structured error handling to provide clearer insights during failures.
- Log raw router outputs whenever a fallback occurs to understand the exact conditions leading to it.

## Tests to Add

- Add a regression test for the query "summarize this document" to assert resolution to `parent_child`.
- Add a test to handle unsupported LLM strategy values, ensuring there is a fallback reason instead of silent degradation.
- Add a contract test to confirm the LLM router only emits supported retrieval strategy enum values.

## Monitoring Improvements

- Log the raw LLM router strategy value, normalized strategy value, router type, fallback reason, request id, and trace id during router fallback events.
- Establish a metric to track unsupported LLM router strategy values to catch contract drift before it impacts users.

## Risk Notes

- There's a risk of continued user impact if unsupported strategy values persist post-fix.
- Potential confusion in user experience if there is a lack of clarity on retrieval strategies and fallbacks.

## Evidence

- EVID-LOG-0219CDEC
- EVID-LOG-6D339B49
- src/rag/service.py:71-150
- src/rag/retrieval/hybrid/__init__.py:1-40
- src/rag/retrieval/hybrid/strategy.py:1-43
- src/rag/routing/rule_based.py:71-150
- tests/rag/routing/test_llm_router.py:71-138

## Metadata

- recommendation_id: SOL-20260519-D3BCB632
- rca_report_id: RCA-20260519-E5CD5032
- confidence_score: 0.8
