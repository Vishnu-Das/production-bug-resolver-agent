# Solution Recommendation for INC-003

## Summary

Recommended solution based on RCA RCA-20260519-738A834E: Selected-document retrieval returned zero documents because the UI-selected filename did not match the stored vector metadata source for the same PDF after normalization.

## Immediate Steps

- Normalize selected-document names and stored source metadata with the same case-insensitive, separator-safe, whitespace-safe rules before applying parent-child retrieval filters.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Implement a robust validation mechanism for document filenames to ensure consistency and correctness before storing them in the vector store.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Create tests to confirm that filenames are normalized before retrieval processes are executed.
- Test retrieval functionality with various casing, spacing, and formatting scenarios to ensure document matching works correctly.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- Filename normalization may introduce additional complexity in filenames if not carefully defined.
- Potential for other document retrieval scenarios to be overlooked if they are not checked against normalization rules.

## Evidence

- EVID-LOG-EA5A6718
- EVID-LOG-E1E9F537
- src/rag/service.py:141-220
- src/rag/service.py:71-150
- src/rag/cache.py:1-34

## Generation Details

- writer: llm
- llm_output_validated: true
- fallback_used: false

## Metadata

- recommendation_id: SOL-20260519-F54F4056
- rca_report_id: RCA-20260519-738A834E
- confidence_score: 0.75
- solution_writer: llm
- llm_output_validated: true
- fallback_used: false
