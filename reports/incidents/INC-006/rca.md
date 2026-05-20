# RCA Report for Incident INC-006

## Incident Summary

Users reported that the command 'summarize the document' returns a summary of only a small chunk of the document instead of a full document summary, indicating a mismatch between user expectations and the actual functionality in use.

## Impact

This issue affects user experience by failing to meet expectations for document summarization, potentially reducing the trust in the system's capabilities and leading to frustration among users.

## Symptoms

- Users received chunk-level summaries instead of expected full document summaries.
- User feedback indicated that the summary only covered the first section of the document.

## Log Findings

- Received query for summarization (EVID-LOG-FF9DDBC2).
- Routing strategy selected was 'semantic_search' instead of the expected 'parent_child' (EVID-LOG-55171BD2).
- Retrieved chunks using the 'semantic_search' strategy (EVID-LOG-273719EF).
- User feedback indicated that the summary only covered the first section (EVID-LOG-9EBDD650).

## Code Findings

- The RuleBasedRouterStrategy in `src/rag/routing/rule_based.py` maps summary queries to 'parent_child' strategy but appears to have failed in this instance (EVID-src/rag/routing/rule_based.py:1-80).
- Tests in `tests/rag/routing/test_rule_based_router.py` confirm that summary queries should route to the 'parent_child' strategy (EVID-tests/rag/routing/test_rule_based_router.py:1-80).

## Knowledge Base Findings

- The knowledge base specifies that summary queries should use document-level retrieval, not chunk-level retrieval (evidence-kb-query-routing-expectations).
- The expected retrieval strategies for the system are `hybrid`, `parent_child`, and `fusion` (evidence-kb-retrieval-strategies).

## Hypotheses Considered

- H1: The router is incorrectly routing summary queries to chunk-level retrieval due to a bug in the routing logic.
- H2: The selected_document handling during query routing is not verifying against user-selected documents properly.

## Final Root Cause

The incident is most likely caused by the routing for summary queries being incorrectly mapped to 'semantic_search' rather than 'parent_child', as evidenced by the check in `tests/rag/routing/test_rule_based_router.py`, which confirms that such queries should trigger the document-level retrieval strategy.

## Technical Explanation

Logs indicate that a query to summarize a document was received and processed; however, the routing logic selected 'semantic_search' instead of the expected 'parent_child' strategy. This resulted in the retrieval of only chunks rather than a full document summary. Documentation also states that summary queries must leverage document-level retrieval, further validating that the observed behavior deviates from documented expectations.

## Evidence

- EVID-LOG-FF9DDBC2
- EVID-LOG-55171BD2
- EVID-LOG-273719EF
- EVID-LOG-9EBDD650
- kb-query-routing-expectations
- kb-retrieval-strategies

## Confidence

Score: 0.8

Reason: Sufficient evidence quality and diversity support the hypothesis of the routing error, suggesting a strong correlation between observed symptoms and the routing logic implementation.

## Recommended Fix

Inspect and fix the routing logic in the RuleBasedRouterStrategy to ensure that summary queries correctly trigger the 'parent_child' strategy for document-level retrieval.

## Preventive Actions

Implement more robust routing validation checks during query processing to ensure compliance with expected behavior, possibly enriched with more integrated tests for each retrieval scenario.

## Tests to Add

- Add tests to validate that summary queries are correctly routed to the 'parent_child' strategy under all conditions.
- Create test cases that simulate user feedback scenarios to ensure correct retrieval behavior is achieved.

## Open Questions

- What steps should be taken if other query patterns are found to be incorrectly routed?
- How can we improve user feedback mechanisms to capture issues like this faster in the future?

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
