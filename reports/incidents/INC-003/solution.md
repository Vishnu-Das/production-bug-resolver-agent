# Solution Recommendation for INC-003

## Summary

Recommended solution based on RCA RCA-20260519-BC1EB683: Selected-document retrieval returned zero documents because the UI-selected filename did not match the stored vector metadata source for the same PDF after normalization.

## Immediate Steps

- Normalize selected-document names and stored source metadata with the same case-insensitive, separator-safe, whitespace-safe rules before applying parent-child retrieval filters.
- Reproduce the incident locally using the same failure scenario.
- Verify the fix against the log symptoms and selected RCA evidence.

## Long-Term Steps

- Add regression tests to ensure selected-document retrieval functionality is reliable.
- Centralize retrieval strategy validation to prevent discrepancies in document retrieval.
- Improve structured error handling to provide clearer insights into retrieval failures.
- Log raw router outputs when fallback occurs to assist in diagnosing issues quickly.
- Add input and output contract checks around the implicated code path to safeguard against future discrepancies.
- Document the expected behavior and failure mode for future incidents to inform developers.

## Tests to Add

- Add a regression test specifically for incident INC-003 to ensure similar issues do not reoccur.
- Add a test that covers the implicated implementation path to validate the integrity of document retrieval.

## Monitoring Improvements

- Add structured logging around the implicated code path to facilitate better monitoring of retrieval processes.
- Log request or trace identifiers with the error when available to assist in tracking down issues in the system.

## Risk Notes

- Improper normalization of filenames may continue to cause silent failures in document retrieval if not addressed promptly.
- Insufficient logging could lead to challenges in diagnosing issues when failures occur.

## Evidence

- EVID-LOG-41F27B74
- EVID-LOG-D00148C6
- eval/strategy_questions.json:1-24
- eval/questions.json:1-50
- src/vectorstore.py:71-111
- src/rag/service.py:71-150
- src/ingest.py:71-85

## Metadata

- recommendation_id: SOL-20260519-0518E4B5
- rca_report_id: RCA-20260519-BC1EB683
- confidence_score: 0.75
