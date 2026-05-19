# Solution Recommendation for INC-003

## Summary

Recommended solution based on RCA RCA-20260519-19C18A25: Selected-document retrieval returned zero documents because the UI-selected filename did not match the stored vector metadata source for the same PDF after normalization.

## Immediate Steps

- Normalize selected-document names and stored source metadata with the same case-insensitive, separator-safe, whitespace-safe rules before applying parent-child retrieval filters.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.
- Add input and output contract checks around the implicated code path.
- Document the expected behavior and failure mode for future incidents.

## Tests to Add

- Add a regression test for incident INC-003.
- Add a test covering the implicated implementation path.

## Monitoring Improvements

- Add structured logging around the implicated code path.
- Log request or trace identifiers with the error when available.

## Risk Notes

- None

## Evidence

- EVID-LOG-1D114892
- EVID-LOG-B6EB492A
- src/rag/service.py:1-80
- eval/strategy_questions.json:1-24
- src/rag/service.py:71-150
- eval/questions.json:1-50
- src/rag/service.py:141-220

## Metadata

- recommendation_id: SOL-20260519-D8873728
- rca_report_id: RCA-20260519-19C18A25
- confidence_score: 0.75
