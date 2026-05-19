# Conversational RAG

Conversational RAG is an intelligent document assistant for grounded question answering and conversational interaction across PDF documents.

The system combines hybrid retrieval, multi-query search expansion, and cross-encoder reranking to improve retrieval accuracy and response quality.

It supports document-specific querying, streaming responses, source citations, automated evaluation pipelines, observability with tracing, and containerized deployment.

The project focuses on production-oriented RAG engineering concepts such as retrieval optimization, answer grounding, hallucination reduction, evaluation, and debugging workflows beyond basic vector search systems.

---

<img width="1547" height="1238" alt="localhost_8501_ (2)" src="https://github.com/user-attachments/assets/7df5d2bf-f3cd-4efd-92e9-27b6e388bfe4" />

---

<img width="1557" height="1249" alt="localhost_8501_ (3)" src="https://github.com/user-attachments/assets/f094f50e-b7fe-4827-aefc-d325137da6e5" />

---

<img width="1564" height="1256" alt="localhost_8501_ (4)" src="https://github.com/user-attachments/assets/2b1ab3d0-9dbf-45ec-955f-d3e1ad2d8682" />

---

## Features

- Conversational RAG with chat history awareness
- Hybrid Retrieval (Vector Search + BM25)
- MultiQuery Retrieval for improved recall
- Cross-Encoder Reranking
- Source citations with previews
- Streaming responses
- PDF upload and ingestion
- LangSmith observability and tracing
- Automated evaluation pipelines
- Dockerized deployment

---

## Architecture

```text
User Query
    ↓
History-Aware Query Rewriting
    ↓
MultiQuery Retrieval
    ↓
Hybrid Retrieval
(Vector + BM25)
    ↓
Deduplication
    ↓
Cross-Encoder Reranking
    ↓
Context Construction
    ↓
LLM Response Generation
    ↓
Streaming UI + Source Citations
```

---

## Tech Stack

| Component | Technology |
|---|---|
| LLM | OpenAI GPT |
| Framework | LangChain |
| Vector DB | ChromaDB |
| UI | Streamlit |
| Reranking | SentenceTransformers CrossEncoder |
| Observability | LangSmith |
| Containerization | Docker |
| Evaluation | Custom RAG Evaluation Pipelines |

---

## High-Level Architecture

```text
User Query
   ↓
Streamlit UI
   ↓
RAG Service
   ↓
Retrieval Strategy Resolver
   ↓
Router Strategy Factory
   ├── Rule-Based Router
   └── LLM Router
   ↓
RouterResult
   ├── strategy
   ├── reason
   ├── confidence
   └── router_type
   ↓
Retrieval Strategy Factory
   ├── Hybrid Retrieval
   ├── Parent-Child Retrieval
   └── Fusion Retrieval
   ↓
Retrieved Documents
   ↓
Cross-Encoder Reranking
   ↓
Context Construction
   ↓
Prompt Construction
   ↓
LLM Response Generation
   ↓
Streaming Answer + Sources + Debug Info
```

---

## Retrieval Strategies

The project uses a strategy-based retrieval architecture. Each retrieval strategy is isolated behind a common interface and selected through a factory.

```text
RetrievalStrategyFactory
├── HybridRetrievalStrategy
├── ParentChildRetrievalStrategy
└── FusionRetrievalStrategy
```

### 1. Hybrid Retrieval

Hybrid retrieval combines semantic and keyword-based retrieval.

It uses:

- vector search
- BM25 keyword search
- multi-query retrieval
- deduplication
- cross-encoder reranking

Best for:

- factual lookups
- exact questions
- definition-style questions
- keyword-sensitive queries

Example:

```text
"What is multi-head attention?"
```

Expected strategy:

```text
hybrid
```

---

### 2. Parent-Child Retrieval

Parent-child retrieval uses smaller child chunks for retrieval and larger parent chunks for answer context.

It uses:

- parent chunks
- child chunks
- semantic search over child chunks
- parent document reconstruction
- reranking

Best for:

- summaries
- document-level understanding
- study notes
- key concepts
- broad document questions

Example:

```text
"Summarize this document"
```

Expected strategy:

```text
parent_child
```

---

### 3. Fusion Retrieval

Fusion retrieval combines results from multiple retrieval strategies.

It uses:

- hybrid retrieval
- parent-child retrieval
- deduplication
- reranking over combined results

Best for:

- conceptual questions
- architecture explanations
- workflow questions
- comparative reasoning
- broad contextual questions

Example:

```text
"Explain transformer architecture"
```

Expected strategy:

```text
fusion
```

---

## Automatic Retrieval Routing

The system supports automatic routing using:

```text
RETRIEVAL_STRATEGY=auto
```

When auto mode is enabled, the system selects the best retrieval strategy based on the query intent.

```text
RouterStrategyFactory
├── RuleBasedRouterStrategy
└── LLMRouterStrategy
```

The router returns a structured `RouterResult`:

```text
RouterResult
├── strategy
├── reason
├── confidence
└── router_type
```

### Routing Behavior

| Query Type | Selected Strategy |
|---|---|
| Factual lookup | Hybrid Retrieval |
| Summary / study notes / key concepts | Parent-Child Retrieval |
| Conceptual / architecture / workflow explanation | Fusion Retrieval |
| Specific selected document with unclear intent | Parent-Child Retrieval |
| Unknown query | Default configured strategy |

Examples:

```text
"What is multi-head attention?"
→ hybrid

"Summarize this document"
→ parent_child

"Explain transformer architecture"
→ fusion

"How does self-attention work?"
→ fusion
```

---

## Rule-Based Router

The rule-based router uses query patterns and keywords to choose the retrieval strategy.

It is deterministic, fast, and useful as a safe fallback.

Typical routing:

```text
factual query      → hybrid
summary query      → parent_child
conceptual query   → fusion
```

---

## LLM Router

The LLM router uses structured output to select a retrieval strategy.

Instead of parsing raw text, the router expects a structured schema:

```text
LLMRouterOutput
├── strategy
├── reason
└── confidence
```

If the LLM router fails or returns an invalid strategy, the system falls back to the rule-based router.

Fallback output is marked as:

```text
router_type = llm_fallback
```

This makes the router safer and easier to debug.

---

## Strategy Configuration

You can configure retrieval strategy through environment variables.

### Fixed Strategy

```env
RETRIEVAL_STRATEGY=hybrid
```

```env
RETRIEVAL_STRATEGY=parent_child
```

```env
RETRIEVAL_STRATEGY=fusion
```

### Automatic Routing

```env
RETRIEVAL_STRATEGY=auto
```

---

## LangSmith Observability

The project includes LangSmith tracing for debugging and observability.

A single query produces a trace tree like:

```text
RAG Stream Response
├── Resolve Retrieval Strategy
├── Rule-Based Router Decision / LLM Router Decision
├── Retrieve Documents
├── Rerank Retrieved Documents
├── Build RAG Context
├── Build QA Prompt
└── LLM Response
```

This helps inspect:

- selected retrieval strategy
- router reason
- router confidence
- router type
- retrieved documents
- reranked documents
- context sent to the LLM
- retrieval latency
- reranking latency
- total response latency

### LangSmith Environment Variables

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=conversational-rag
```

For local development, keep real keys in `.env`.

Do not commit real API keys.

---

## Evaluation

The project includes automated evaluation scripts under:

```text
eval/
├── evaluate_retrieval.py
├── evaluate_answers.py
└── evaluate_with_judge.py
```

The eval system validates:

- retrieval quality
- source matching
- keyword coverage
- selected strategy
- router correctness
- answer quality
- groundedness
- hallucination risk
- latency/debug information

---

### Retrieval Evaluation

Validates:

- whether the expected source was retrieved
- whether expected keywords appear in retrieved context
- whether the router selected the expected strategy
- retrieval and reranking latency

Run:

```bash
uv run python eval/evaluate_retrieval.py
```

---

### Answer Evaluation

Validates:

- generated answer quality
- keyword coverage
- selected strategy
- source count
- latency/debug information

Run:

```bash
uv run python eval/evaluate_answers.py
```

---

### LLM-as-a-Judge Evaluation

Uses an LLM judge to evaluate:

- correctness
- groundedness
- hallucination risk
- completeness

Run:

```bash
uv run python eval/evaluate_with_judge.py
```

---

## Testing

The project includes unit tests for the core RAG architecture.

Current test areas:

```text
tests/
└── rag/
    ├── models/
    │   └── test_router_result.py
    ├── retrieval/
    │   └── test_retrieval_factory.py
    ├── routing/
    │   ├── test_llm_router.py
    │   ├── test_router_factory.py
    │   └── test_rule_based_router.py
    ├── test_service.py
    └── test_service_utils.py
```

Covered:

| Area | Status |
|---|---|
| RouterResult model | Tested |
| Rule-based router | Tested |
| LLM router | Tested with mocks |
| LLM router fallback | Tested |
| Router factory | Tested |
| Retrieval factory | Tested with mocks |
| RAG service orchestration | Tested |
| Service utility functions | Tested |

Run tests:

```bash
uv run pytest
```

Verbose mode:

```bash
uv run pytest -v
```

The tests are designed as unit tests and do not make real OpenAI, ChromaDB, or LangSmith calls.

---

## GitHub Actions

The repository includes a GitHub Actions workflow for running tests automatically.

Workflow file:

```text
.github/workflows/tests.yml
```

The workflow runs on:

- push
- pull request
- manual dispatch

Example workflow:

```yaml
name: Tests

on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest

    env:
      OPENAI_API_KEY: dummy
      LANGCHAIN_API_KEY: dummy
      LANGCHAIN_TRACING_V2: "false"
      LANGCHAIN_PROJECT: conversational-rag-tests

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install

      - name: Install dependencies
        run: uv sync --all-extras --dev

      - name: Run tests
        run: uv run pytest
```

Real API tokens are not required for unit tests because external calls are mocked.

---

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/Vishnu-Das/conversational_rag.git
cd conversational_rag
```

---

### 2. Create `.env`

```env
OPENAI_API_KEY=your_openai_api_key
HF_TOKEN=your_huggingface_token

RETRIEVAL_STRATEGY=auto
ROUTER_TYPE=rule_based

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=conversational-rag
```

For LLM-based routing:

```env
ROUTER_TYPE=llm
```

For rule-based routing:

```env
ROUTER_TYPE=rule_based
```

---

### 3. Install dependencies

```bash
uv sync
```

---

### 4. Run the app

```bash
uv run streamlit run app.py
```

Open:

```text
http://localhost:8501
```

---

## Running with Docker

Build and start:

```bash
docker compose up --build
```

Application:

```text
http://localhost:8501
```

---

## Document Ingestion

Place PDF files inside:

```text
src/data/
```

If the ChromaDB store is empty, ingestion runs during startup.

Manual ingestion:

```bash
uv run python -m src.ingest
```

With Docker:

```bash
docker compose exec conversational-rag .venv/bin/python -m src.ingest
```

---

## Retrieval Strategy Benchmark

The system supports multiple pluggable retrieval strategies through a modular strategy-based retrieval orchestration layer.

### Supported Retrieval Strategies

| Strategy | Primary Use Case |
|---|---|
| **Hybrid Retrieval** | Precise factual lookups and semantic search |
| **Parent-Child Retrieval** | Document-level understanding, summaries, and broader contextual retrieval |
| **Fusion Retrieval** | Conceptual, comparative, and architecture-level queries |
| **Auto Routing** | Dynamically selects the optimal retrieval strategy based on query intent |

---

## Benchmark Results

### Query: *What is multi-head attention?*

| Strategy | Query Type | Docs Returned | Context Length | Latency | Keyword Score |
|---|---|---|---|---|---|
| Hybrid | Factual | 4 | 6623 | 2466 ms | 1.0 |
| Parent-Child | Document-Level | 2 | 4942 | 317 ms | 1.0 |
| Fusion | Conceptual | 4 | 8624 | 2438 ms | 1.0 |
| Auto → Hybrid | Dynamic Routing | 4 | 6623 | 2007 ms | 1.0 |

---

### Query: *Summarize this document*

| Strategy | Query Type | Docs Returned | Context Length | Latency | Keyword Score |
|---|---|---|---|---|---|
| Hybrid | Factual | 4 | 8306 | 2163 ms | 1.0 |
| Parent-Child | Document-Level | 2 | 4879 | 702 ms | 1.0 |
| Fusion | Conceptual | 4 | 9077 | 2301 ms | 1.0 |
| Auto → Parent-Child | Dynamic Routing | 2 | 4879 | 1413 ms | 1.0 |

---

## Observations

### Hybrid Retrieval
- Combines:
  - semantic vector retrieval
  - BM25 keyword retrieval
  - multi-query expansion
  - cross-encoder reranking
- Performs strongly for:
  - factual questions
  - exact lookups
  - keyword-sensitive retrieval
- Provides broader retrieval coverage with higher precision.

---

### Parent-Child Retrieval
- Uses:
  - semantic child chunk retrieval
  - parent document reconstruction
  - cross-encoder reranking
- Achieved:
  - lower latency
  - fewer retrieved documents
  - efficient contextual retrieval
- Performs strongly for:
  - summaries
  - study notes
  - key concept extraction
  - document-level understanding

---

### Fusion Retrieval
- Combines:
  - Hybrid Retrieval
  - Parent-Child Retrieval
  - retrieval fusion
  - reranking over combined results
- Performs strongly for:
  - conceptual questions
  - architecture discussions
  - comparative reasoning
  - broad contextual queries
- Provides richer context at the cost of higher retrieval latency.

---

### Auto Routing
The system dynamically routes queries to the most suitable retrieval strategy.

| Query Pattern | Selected Strategy |
|---|---|
| Factual Questions | Hybrid Retrieval |
| Summaries / Key Concepts / Study Notes | Parent-Child Retrieval |
| Conceptual / Comparative / Architecture Questions | Fusion Retrieval |

Examples:

```text
"What is multi-head attention?"
→ Hybrid Retrieval

"Summarize this document"
→ Parent-Child Retrieval

"Explain transformer architecture"
→ Fusion Retrieval
```

---

## Retrieval Architecture

```text
Query Router
    ↓
Retrieval Strategy Factory
    ├── Hybrid Retrieval
    │     ├── Vector Search
    │     ├── BM25
    │     ├── MultiQuery Retrieval
    │     └── Cross-Encoder Reranking
    │
    ├── Parent-Child Retrieval
    │     ├── Parent Chunks
    │     ├── Child Chunks
    │     ├── Semantic Retrieval
    │     └── Cross-Encoder Reranking
    │
    └── Fusion Retrieval
          ├── Hybrid Retrieval
          ├── Parent-Child Retrieval
          ├── Retrieval Fusion
          └── Cross-Encoder Reranking
```

---

## Project Structure

```text
conversational_rag/
├── app.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
├── eval/
│   ├── questions.json
│   ├── evaluate_retrieval.py
│   ├── evaluate_answers.py
│   └── evaluate_with_judge.py
├── tests/
│   └── rag/
│       ├── models/
│       ├── retrieval/
│       ├── routing/
│       ├── test_service.py
│       └── test_service_utils.py
└── src/
    ├── config.py
    ├── ingest.py
    └── rag/
        ├── service.py
        ├── prompts.py
        ├── llm.py
        ├── debug.py
        ├── models/
        ├── routing/
        │   ├── factory.py
        │   ├── rule_based.py
        │   ├── llm.py
        │   └── schemas.py
        ├── retrieval/
        │   ├── factory.py
        │   ├── hybrid.py
        │   ├── parent_child.py
        │   └── fusion.py
        ├── retrievers.py
        └── pipeline.py
```

---

## Example Capabilities

- Ask questions across uploaded PDFs
- Restrict queries to specific documents
- Generate document summaries
- Extract key concepts
- View cited source chunks
- Analyze retrieval quality using LangSmith

---

## Future Improvements

- Contextual compression
- Async ingestion
- FastAPI backend
- Feedback collection
- GraphRAG
- Multi-user authentication

---

## Introduction to Retrieval Inspector in the app

<img width="1385" height="1270" alt="localhost_8501_ (5)" src="https://github.com/user-attachments/assets/a5c80503-08b3-4274-87a4-d45f4e62a757" />

---

<img width="885" height="756" alt="localhost_8501_ (7)" src="https://github.com/user-attachments/assets/32d45d7b-752c-4d5b-bec4-87c7c45a29b0" />

---

The application includes a Retrieval Inspector to make the RAG pipeline easier to debug and explain.

The inspector shows how the system selected a retrieval strategy, which documents were retrieved, how reranking changed the result order, and what final context was sent to the LLM.

This is useful for debugging questions like:

- Why did the system choose this retrieval strategy?
- Which documents were retrieved before reranking?
- Which documents were finally used for answer generation?
- Did the correct document appear in the retrieved results?
- Did reranking improve or hurt the final context?
- How much time was spent in retrieval and reranking?

### How to Enable
- just pass ```ENABLE_RETRIEVAL_INSPECTOR=true``` in the environment or put in the ```.env``` file
---



## License

MIT License
