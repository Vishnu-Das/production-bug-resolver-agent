# RCA Report for Incident INC-002

## Incident Summary

The incident involved critical failure of chat requests resulting in HTTP 500 errors after a deployment altered the retrieval strategy configuration to an unsupported value.

## Impact

Chat functionalities were severely disrupted, leading to potential loss of user engagement and satisfaction due to the inability to retrieve document responses.

## Symptoms

- HTTP 500 errors when making chat requests.
- Chat response failures during document retrieval.

## Log Findings

- EVID-LOG-90915FE1: ERROR indicating unsupported retrieval strategy: 'semantic'.
- EVID-LOG-9AF7734D: WARNING that the retrieval strategy 'semantic' is not supported.

## Code Findings

- Evidence from `service.py` shows retrieval strategy is resolved from request and calls `RetrievalStrategyFactory.get_strategy`.

## Knowledge Base Findings

- None

## Hypotheses Considered

- The retrieval strategy was incorrectly set in the configuration file.
- A recent change introduced an unsupported retrieval strategy.

## Final Root Cause

The configured or resolved retrieval strategy was `semantic`, which is not supported. The retrieval factory rejected the value and raised a `ValueError`.

## Technical Explanation

Logs reveal that `RETRIEVAL_STRATEGY=semantic` was utilized during document retrieval, while the factory only supports `hybrid`, `parent_child`, and `fusion`. This indicates a configuration mismatch between expected and provided values in the deployment settings.

## Evidence

- EVID-LOG-90915FE1
- EVID-LOG-9AF7734D
- src/rag/service.py:141-220
- src/rag/retrieval/hybrid/strategy.py:1-43
- src/rag/service.py:71-150

## Confidence

Score: 0.75

Reason: Evidence quality is assured with diverse sources highlighting the same failure mode.

## Recommended Fix

Validate `RETRIEVAL_STRATEGY` at startup; restrict to `hybrid`, `parent_child`, or `fusion`, and reject or normalize unsupported values.

## Preventive Actions

Implement a configuration validation mechanism that checks the setting of `RETRIEVAL_STRATEGY` before usage, ensuring only supported strategies are utilized.

## Tests to Add

- Unit tests to validate that only supported retrieval strategies can be configured successfully.
- Integration tests to simulate chat requests with various retrieval strategies to ensure proper handling of unsupported values.

## Open Questions

- What processes led to the deployment of an unsupported retrieval strategy?
- How can we enhance oversight to prevent unsupported configurations in the future?

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
