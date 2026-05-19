# Solution Recommendation for INC-001

## Summary

Recommended solution based on RCA RCA-20260519-3D7B48C0: The LLM router emitted `summary` as a retrieval strategy, but `summary` is not a supported retrieval strategy value. The router validation raised `ValueError: Invalid strategy: summary`, causing the system to fall back to the rule-based router. The fallback resolved the same summary-style document query to `parent_child`, indicating that this query intent should map to the supported `parent_child` strategy rather than `summary`.

## Immediate Steps

- Update the LLM router prompt and/or structured output validation to ensure it emits only supported retrieval strategies.
- For broad summary questions over a selected document, return `parent_child` directly or normalize `summary` to `parent_child` before validation.
- Reproduce the incident locally using the same failure scenario to ensure understanding of the issue.
- Verify the proposed fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Implement stricter validation on the retrieval strategy emitted from the LLM router to prevent unsupported strategies.
- Ensure alignment between the LLM router output schema, prompt instructions, and supported retrieval strategy values to prevent contract mismatches.
- Document the supported retrieval strategies and the expected mappings for summary-style selected-document questions, making them accessible to the development team.

## Tests to Add

- Add unit tests to confirm the LLM router emits only supported strategies for summary queries, specifically covering cases that previously caused issues.
- Create integration tests that validate the retrieval routing behavior for a variety of summary queries, ensuring expected outputs occur without fallback.

## Monitoring Improvements

- Log the raw LLM router strategy value, normalized strategy value, router type, fallback reason, request id, and trace id for every occurrence of router fallback.
- Introduce a metric for tracking unsupported LLM router strategy values to provide visibility into any potential contract drifts before they affect users.

## Risk Notes

- There is a risk that the solution may not address all possible unsupported concepts that could arise in the future unless thorough validation is continuously maintained.
- The ongoing alignment between multiple components (prompt instructions and strategy enum) must be rigorously governed to prevent future discrepancies.

## Evidence

- EVID-LOG-6E169B71
- EVID-LOG-6225C4F0
- tests/rag/routing/test_llm_router.py:71-138
- src/rag/routing/llm.py:71-110
- src/rag/retrieval/parent_child/strategy.py:71-114

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260519-55B69DCA
- rca_report_id: RCA-20260519-3D7B48C0
- confidence_score: 0.8
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
