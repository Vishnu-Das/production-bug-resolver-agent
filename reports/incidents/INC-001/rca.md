# RCA for LLM router falls back during summary questions

## Incident Summary

Incident INC-001: Users report that broad summary questions in auto retrieval mode intermittently use the fallback router instead of the LLM router, reducing retrieval quality and making answers less relevant.

## Impact

Affected service: conversational_rag. Affected area: automatic retrieval routing.

## Symptoms

- Users report that broad summary questions in auto retrieval mode intermittently use the fallback router instead of the LLM router, reducing retrieval quality and making answers less relevant.
- 2026-05-19T10:45:12Z ERROR conversational_rag request_id=req-inc-001 trace_id=trace-router-001 LLM router failed. Fallback used. Error: Invalid strategy: summary. Fallback reason: summary queries should use parent_child retrieval.
Traceback (most recent call last):
  File "src/rag/service.py", line 55, in resolve_retrieval_strategy
    router_result = router.route(query=user_input, selected_document=selected_document)
  File "src/rag/routing/llm.py", line 82, in route
    raise ValueError(f"Invalid strategy: {result.strategy}")
ValueError: Invalid strategy: summary
- 2026-05-19T10:45:12Z WARNING conversational_rag request_id=req-inc-001 trace_id=trace-router-001 router_type=llm_fallback query="summarize this document" selected_document="transformer_notes.pdf" resolved_strategy=parent_child

## Log Findings

- Retrieved log evidence from log-001.
- Retrieved log evidence from log-002.

## Code Findings

- Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:771-850.
- Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\tests\rag\routing\test_rule_based_router.py:1-80.
- Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\tests\rag\routing\test_llm_router.py:71-138.
- Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\src\rag\routing\rule_based.py:1-80.
- Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:281-360.

## Knowledge Base Findings

- Retrieved knowledge_base evidence from sample_data\knowledge_base\README.md.

## Hypotheses Considered

- None

## Final Root Cause

The incident is most likely caused by the implementation behavior shown in C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:771-850, matching the runtime failure observed in logs.

## Technical Explanation

EVID-LOG-B2924331: Retrieved log evidence from log-001. EVID-LOG-E3B6AF26: Retrieved log evidence from log-002. evidence-kb-README: Retrieved knowledge_base evidence from sample_data\knowledge_base\README.md. evidence-README.md:771-850: Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:771-850. evidence-tests\rag\routing\test_rule_based_router.py:1-80: Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\tests\rag\routing\test_rule_based_router.py:1-80. evidence-tests\rag\routing\test_llm_router.py:71-138: Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\tests\rag\routing\test_llm_router.py:71-138. evidence-src\rag\routing\rule_based.py:1-80: Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\src\rag\routing\rule_based.py:1-80. evidence-README.md:281-360: Retrieved code evidence from C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:281-360.

## Evidence

- EVID-LOG-B2924331
- EVID-LOG-E3B6AF26
- evidence-kb-README
- evidence-README.md:771-850
- evidence-tests\rag\routing\test_rule_based_router.py:1-80
- evidence-tests\rag\routing\test_llm_router.py:71-138
- evidence-src\rag\routing\rule_based.py:1-80
- evidence-README.md:281-360

## Confidence

Score: 1.0

Reason: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Inspect and fix the code path at C:\Users\vishn\Documents\Learning AI\conversational_rag\README.md:771-850.

## Preventive Actions

Add regression tests, improve structured error handling, and improve logging around the failing code path.

## Tests to Add

- Add a regression test for incident INC-001.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Metadata

- evidence_count: 8
- dynamic_workflow: true
