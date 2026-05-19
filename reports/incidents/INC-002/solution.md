# Solution Recommendation for INC-002

## Summary

Recommended solution based on RCA RCA-20260519-97FBB6C1: The configured retrieval strategy was `semantic`, which is unsupported by the system. The factory method `RetrievalStrategyFactory.get_strategy` raised a `ValueError` exception when attempting to utilize this strategy, leading to chat requests failing.

## Immediate Steps

- Implement a validation mechanism for the `RETRIEVAL_STRATEGY` configuration at startup to ensure it is one of the supported values: `hybrid`, `parent_child`, or `fusion`. Any unsupported value should be rejected or adjusted.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Establish configuration management practices to ensure that deployment settings are reviewed and validated before deployment, particularly for critical configurations like retrieval strategies.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add unit tests to verify that unsupported retrieval strategies are rejected and handled gracefully.
- Create integration tests to ensure that valid `RETRIEVAL_STRATEGY` values are processed and yield expected behavior.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- There might be risks associated with the introduction of validation checks if not properly tested, which could lead to false positives and legitimate requests being rejected.
- Inadequate documentation and training on configuration management may lead to future occurrences of similar incidents.

## Evidence

- EVID-LOG-AC3763A6
- EVID-LOG-EE46901D
- src/rag/retrieval/factory.py:1-42
- tests/rag/retrieval/test_retrieval_factory.py:1-60

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260519-6957DC3C
- rca_report_id: RCA-20260519-97FBB6C1
- confidence_score: 0.75
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
