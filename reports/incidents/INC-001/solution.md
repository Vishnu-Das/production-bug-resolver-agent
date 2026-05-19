# Solution Recommendation for INC-001

## Summary

Recommended solution based on RCA RCA-20260519-E6CA5783: The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, causing the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Immediate Steps

- Update the LLM router prompt and/or structured output validation so the router emits only supported retrieval strategy values. For broad summary questions over a selected document, return `parent_child` directly or normalize `summary` to `parent_child` before validation.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.
- Keep the LLM router output schema, prompt instructions, and retrieval strategy enum in sync so unsupported conceptual labels cannot be emitted.
- Document the supported retrieval strategies and the expected mapping for summary-style selected-document questions.

## Tests to Add

- Add a regression test where query="summarize this document" and a selected document is present; assert the resolved strategy is `parent_child`.
- Add a test ensuring unsupported LLM strategy values are handled with a clear fallback reason and do not silently degrade routing quality.
- Add a contract test ensuring the LLM router can emit only supported retrieval strategy enum values.

## Monitoring Improvements

- Log the raw LLM router strategy value, normalized strategy value, router type, fallback reason, request id, and trace id whenever router fallback occurs.
- Add a metric for unsupported LLM router strategy values so `summary`-style contract drift is visible before it affects users.

## Risk Notes

- Some open questions remain, so the recommendation should be validated before implementation.

## Evidence

- EVID-LOG-4A218560
- EVID-LOG-838187AE
- evidence-tests/rag/routing/test_llm_router.py:71-138
- evidence-eval/evaluate_with_judge.py:71-150
- evidence-tests/rag/routing/test_llm_router.py:1-80
- evidence-src/rag/routing/llm.py:71-110
- evidence-tests/rag/routing/test_rule_based_router.py:1-80

## Metadata

- recommendation_id: SOL-20260519-2DDE97EC
- rca_report_id: RCA-20260519-E6CA5783
- confidence_score: 0.8
