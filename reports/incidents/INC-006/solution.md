# Solution Recommendation for INC-006

## Summary

Recommended solution based on RCA RCA-20260520-BF884028: The incident is most likely caused by the routing for summary queries being incorrectly mapped to 'semantic_search' rather than 'parent_child', as evidenced by the check in `tests/rag/routing/test_rule_based_router.py`, which confirms that such queries should trigger the document-level retrieval strategy.

## Immediate Steps

- Inspect and fix the routing logic in the RuleBasedRouterStrategy to ensure that summary queries correctly trigger the 'parent_child' strategy for document-level retrieval.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Implement more robust routing validation checks during query processing to ensure compliance with expected behavior, possibly enriched with more integrated tests for each retrieval scenario.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add tests to validate that summary queries are correctly routed to the 'parent_child' strategy under all conditions.
- Create test cases that simulate user feedback scenarios to ensure correct retrieval behavior is achieved.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- Consider the potential for other query patterns to also be incorrectly routed; a comprehensive review of query routing logic may be necessary.
- The fix requires careful validation to avoid introducing new routing issues.

## Evidence

- EVID-LOG-FF9DDBC2
- EVID-LOG-55171BD2
- EVID-LOG-273719EF
- EVID-LOG-9EBDD650
- kb-query-routing-expectations
- kb-retrieval-strategies

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260520-564D1DF9
- rca_report_id: RCA-20260520-BF884028
- confidence_score: 0.8
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
