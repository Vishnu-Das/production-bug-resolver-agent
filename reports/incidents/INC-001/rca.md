# RCA Report for Incident INC-001: LLM Router Fallback During Summary Questions

## Incident Summary

Users reported issues with broad summary questions in auto retrieval mode, where the system intermittently falls back to the fallback router instead of utilizing the LLM router, leading to reduced retrieval quality and less relevant answers.

## Impact

High impact on user experience and retrieval quality, particularly with summarization queries.

## Symptoms

- Intermittent fallback to the LLM fallback router during summary questions.
- Reduced relevance and quality of answers returned by the fallback router.

## Log Findings

- LLM router failed with error: 'Invalid strategy: summary'.
- Fallback indicated that summary queries should use parent_child retrieval.

## Code Findings

- LLM routing validation raises a ValueError when an unsupported strategy is returned.
- The fallback resolves summary queries to parent_child strategy.

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: The LLM router is returning an unsupported retrieval strategy for summary questions.
- H2: There is a flaw in the auto retrieval mode logic that incorrectly classifies these queries.

## Final Root Cause

The LLM router emitted `summary` as a retrieval strategy, which is not supported. The router validation raised `ValueError: Invalid strategy: summary`, causing fallback to the rule-based router that handled the query appropriately by returning `parent_child`, indicating that summary queries should align with this strategy.

## Technical Explanation

The logs show that the LLM router failed due to an invalid strategy during retrieval strategy resolution. The code indicates that the LLM routing path validates the returned strategy, and any unsupported strategy results in fallback behavior, as evidenced by the logs and corresponding code paths in both the LLM router and fallback handling.

## Evidence

- EVID-LOG-76C20202
- EVID-LOG-5C46D760
- src/rag/routing/llm.py:71-110
- src/rag/routing/rule_based.py:1-80
- src/rag/service.py:71-150

## Confidence

Score: 0.8

Reason: Moderate confidence due to clear logs indicating the error and supportive code evidence showing the routing validation process, but lacking complete LLM output data.

## Recommended Fix

Update the LLM router prompt and structured output validation to emit only supported retrieval strategy values. Normalize `summary` to `parent_child` for relevant queries or directly return `parent_child` as needed.

## Preventive Actions

Implement comprehensive schema validation for output emissions from the LLM router to ensure alignment with accepted retrieval strategies, and enhance logging for debugging retrieval strategy logic.

## Tests to Add

- Unit test for the LLM router to verify correct handling of summary queries as `parent_child`.
- Integration test for the overall retrieval strategy to ensure fallbacks occur only for truly unsupported cases.

## Open Questions

- Are there additional types of queries that are incorrectly being routed?
- What additional logging can be implemented to better capture LLM outputs for debugging?

## Low Confidence Warning

None

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- evidence_count: 7
- dynamic_workflow: true
- rca_writer: llm
- llm_output_validated: true
- fallback_used: false
