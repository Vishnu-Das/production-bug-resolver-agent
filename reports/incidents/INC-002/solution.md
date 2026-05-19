# Solution Recommendation for INC-002

## Summary

Recommended solution based on RCA RCA-20260519-EBCA1712: The configured or resolved retrieval strategy was `semantic`, which is not supported. The retrieval factory rejected the value and raised a `ValueError`.

## Immediate Steps

- Validate `RETRIEVAL_STRATEGY` at startup; restrict to `hybrid`, `parent_child`, or `fusion`, and reject or normalize unsupported values.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Implement a configuration validation mechanism that checks the setting of `RETRIEVAL_STRATEGY` before usage, ensuring only supported strategies are utilized.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Unit tests to validate that only supported retrieval strategies can be configured successfully.
- Integration tests to simulate chat requests with various retrieval strategies to ensure proper handling of unsupported values.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- Failure to implement the immediate fix may lead to recurring incidents related to unsupported retrieval strategies.
- Lack of oversight on configuration changes could result in further deployment issues.

## Evidence

- EVID-LOG-90915FE1
- EVID-LOG-9AF7734D
- src/rag/service.py:141-220
- src/rag/retrieval/hybrid/strategy.py:1-43
- src/rag/service.py:71-150

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260519-4E32FA67
- rca_report_id: RCA-20260519-EBCA1712
- confidence_score: 0.75
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
