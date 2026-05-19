# RCA for Unsupported retrieval strategy breaks chat responses

## Incident Summary

Incident INC-002: Chat requests fail with HTTP 500 after a deployment changed the retrieval strategy configuration to an unsupported value.

## Impact

Affected service: conversational_rag. Affected area: retrieval strategy selection.

## Symptoms

- Chat requests fail with HTTP 500 after a deployment changed the retrieval strategy configuration to an unsupported value.
- 2026-05-19T11:12:43Z ERROR conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 Chat response failed during document retrieval. strategy_name=semantic selected_document=All Documents

```text
Traceback (most recent call last):
  File "src/rag/service.py", line 84, in retrieve_documents
    retrieval_strategy = RetrievalStrategyFactory.get_strategy(strategy_name)
  File "src/rag/retrieval/factory.py", line 35, in get_strategy
    raise ValueError(f"Unsupported retrieval strategy: {strategy_name}")
ValueError: Unsupported retrieval strategy: semantic
```
- 2026-05-19T11:12:43Z WARNING conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 RETRIEVAL_STRATEGY=semantic is not one of supported strategies: hybrid,parent_child,fusion

## Log Findings

- log-001 shows runtime signal: 2026-05-19T11:12:43Z ERROR conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 Chat response failed during document retrieval. strategy_name=semantic selected...
- log-002 shows runtime signal: 2026-05-19T11:12:43Z WARNING conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 RETRIEVAL_STRATEGY=semantic is not one of supported strategies: hybrid,parent...

## Code Findings

- src/rag/retrieval/factory.py:1-42 shows relevant implementation behavior: from src.rag.retrieval.base import ( BaseRetrievalStrategy ) from src.rag.retrieval.hybrid.strategy import ( HybridRetrievalStrategy ) from src.rag.retrieval.parent_child.strate...
- src/rag/service.py:71-150 shows relevant implementation behavior: user_input: str, selected_document: Optional[str], ) -> Tuple[str, Optional[RouterResult]]: strategy_name = RETRIEVAL_STRATEGY router_result = None if RETRIEVAL_STRATEGY == "aut...
- src/rag/retrieval/hybrid/strategy.py:1-43 shows relevant implementation behavior: from typing import List, Optional from langchain_core.documents import Document from src.rag.retrieval.base import BaseRetrievalStrategy from src.rag.retrievers import ( get_his...
- src/rag/retrieval/hybrid/__init__.py:1-40 shows relevant implementation behavior: from typing import List, Optional from langchain_core.documents import Document from src.rag.retrieval.base import BaseRetrievalStrategy from src.rag.retrievers import ( get_his...
- tests/rag/retrieval/test_retrieval_factory.py:1-60 shows relevant implementation behavior: from unittest.mock import Mock, patch import pytest from src.rag.retrieval.factory import RetrievalStrategyFactory @patch("src.rag.retrieval.factory.HybridRetrievalStrategy") de...

## Knowledge Base Findings

- None

## Hypotheses Considered

- H1: Runtime failure is caused by an implementation mismatch in the code path identified by the logs and code evidence.
- H2: The observed behavior is caused by missing validation or insufficient normalization around the failing code path.

## Final Root Cause

The incident is most likely caused by a mismatch between the runtime failure observed in logs and the implementation behavior shown in src/rag/retrieval/factory.py:1-42.

## Technical Explanation

EVID-LOG-9A35466D: log-001 shows runtime signal: 2026-05-19T11:12:43Z ERROR conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 Chat response failed during document retrieval. strategy_name=semantic selected... EVID-LOG-8E849FA9: log-002 shows runtime signal: 2026-05-19T11:12:43Z WARNING conversational_rag request_id=req-inc-002 trace_id=trace-retrieval-002 RETRIEVAL_STRATEGY=semantic is not one of supported strategies: hybrid,parent... evidence-src/rag/retrieval/factory.py:1-42: src/rag/retrieval/factory.py:1-42 shows relevant implementation behavior: from src.rag.retrieval.base import ( BaseRetrievalStrategy ) from src.rag.retrieval.hybrid.strategy import ( HybridRetrievalStrategy ) from src.rag.retrieval.parent_child.strate... evidence-src/rag/service.py:71-150: src/rag/service.py:71-150 shows relevant implementation behavior: user_input: str, selected_document: Optional[str], ) -> Tuple[str, Optional[RouterResult]]: strategy_name = RETRIEVAL_STRATEGY router_result = None if RETRIEVAL_STRATEGY == "aut... evidence-src/rag/retrieval/hybrid/strategy.py:1-43: src/rag/retrieval/hybrid/strategy.py:1-43 shows relevant implementation behavior: from typing import List, Optional from langchain_core.documents import Document from src.rag.retrieval.base import BaseRetrievalStrategy from src.rag.retrievers import ( get_his... evidence-src/rag/retrieval/hybrid/__init__.py:1-40: src/rag/retrieval/hybrid/__init__.py:1-40 shows relevant implementation behavior: from typing import List, Optional from langchain_core.documents import Document from src.rag.retrieval.base import BaseRetrievalStrategy from src.rag.retrievers import ( get_his... evidence-tests/rag/retrieval/test_retrieval_factory.py:1-60: tests/rag/retrieval/test_retrieval_factory.py:1-60 shows relevant implementation behavior: from unittest.mock import Mock, patch import pytest from src.rag.retrieval.factory import RetrievalStrategyFactory @patch("src.rag.retrieval.factory.HybridRetrievalStrategy") de...

## Evidence

- EVID-LOG-9A35466D
- EVID-LOG-8E849FA9
- evidence-src/rag/retrieval/factory.py:1-42
- evidence-src/rag/service.py:71-150
- evidence-src/rag/retrieval/hybrid/strategy.py:1-43
- evidence-src/rag/retrieval/hybrid/__init__.py:1-40
- evidence-tests/rag/retrieval/test_retrieval_factory.py:1-60

## Confidence

Score: 0.75

Reason: Confidence is based on available evidence quality, source diversity, and evaluator result: Evidence is sufficient to proceed to RCA writing.

## Recommended Fix

Inspect and fix the code path at src/rag/retrieval/factory.py:1-42.

## Preventive Actions

Add regression tests, centralize retrieval strategy validation, improve structured error handling, and log raw router outputs when fallback occurs.

## Tests to Add

- Add a regression test for incident INC-002.
- Add a test covering the implicated implementation path.

## Open Questions

- None

## Low Confidence Warning

None

## Metadata

- evidence_count: 7
- dynamic_workflow: true
