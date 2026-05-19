# Solution Recommendation for INC-003

## Summary

Recommended solution based on RCA RCA-20260519-8DBD23B6: Selected-document retrieval returned zero documents due to a mismatch between the UI-selected filename and the stored vector metadata source after normalization.

## Immediate Steps

- Normalize selected-document names and stored source metadata using consistent case-insensitive, separator-safe, and whitespace-safe rules before applying parent-child retrieval filters.
- Reproduce the incident locally using the same failure scenario outlined in the RCA.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests to ensure document retrieval functionality works correctly under varied filename conditions.
- Centralize retrieval strategy validation to maintain consistency across implementations and usability in future developments.
- Improve structured error handling to provide clearer feedback and prevent similar issues from occurring unnoticed.
- Log raw router outputs during fallback occurrences to better understand retrieval failures in the future.

## Tests to Add

- Add a regression test specifically for incident INC-003 to validate resolution and ensure similar issues do not arise.
- Implement test cases covering the full implementation path related to document retrieval to identify potential failure points.

## Monitoring Improvements

- Add structured logging around the document retrieval code path to capture detailed runtime information including filename matching processes.
- Log request or trace identifiers with the error details for better tracking of issues when they occur.

## Risk Notes

- The risk of document mismatch may occur again if filename handling processes remain inconsistent or inadequately normalized in future code implementations.
- Potential delays in incident identification may arise if structured logging is not adequately implemented and monitored.

## Evidence

- EVID-LOG-2C79EA5F
- EVID-LOG-15B291C4
- eval/strategy_questions.json:1-24
- eval/questions.json:1-50
- src/rag/service.py:71-150
- src/rag/retrieval/parent_child/strategy.py:71-114
- src/rag/retrievers.py:71-133

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260519-EF188871
- rca_report_id: RCA-20260519-8DBD23B6
- confidence_score: 0.75
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
