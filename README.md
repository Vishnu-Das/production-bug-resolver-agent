# Production Bug Resolver Agent

[![CI](https://github.com/Vishnu-Das/production-bug-resolver-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Vishnu-Das/production-bug-resolver-agent/actions/workflows/ci.yml)

Production Bug Resolver Agent is a CLI-first, supervisor-led multi-agent RCA
assistant for production incidents. It uses LangGraph-style dynamic routing,
guardrails, logs, Code RAG, AST graph retrieval, Knowledge Base RAG,
historical RCA retrieval, and evidence-backed RCA/report generation.

---

<img width="1078" height="903" alt="image" src="https://github.com/user-attachments/assets/1baad765-837a-4ba7-8ed2-59cc6925c512" />

---

The project is analyze-only today. It investigates incidents and writes RCA,
solution, and optional patch-plan reports. It can generate human-reviewable
unified diff suggestions, but it does not patch code, open pull requests, or
modify the target repository.

## What It Does

- Accepts an incident ID from the CLI.
- Loads incident metadata and production-like logs.
- Uses `SupervisorAgent` to choose the next specialist agent.
- Uses `GuardrailEngine` to validate each routing decision.
- Uses specialist investigators for logs, code, AST graph relationships,
  knowledge-base context, and historical RCA context.
- Uses `EvidenceEvaluatorAgent` to decide whether more evidence is needed.
- Generates an RCA and solution recommendation.
- Optionally generates an analyze-only patch plan and safe unified diff
  suggestions.
- Saves Markdown and JSON reports locally.

## Current Architecture

```text
CLI
  -> Workflow Factory
  -> LangGraph Dynamic Workflow / Manual Dynamic Workflow
  -> Supervisor Agent
  -> Guardrail Engine
  -> Specialist Agents
       -> Log Investigator
       -> Knowledge Base Investigator
       -> Code Investigator
       -> Code Graph Investigator
       -> Historical RCA Investigator
  -> Evidence Evaluator
  -> RCA Writer
  -> Solution Recommender
  -> Optional Patch Suggester / Patch Generator
  -> Report Writer
```

The workflow is not a fixed RCA pipeline. The supervisor can route to logs,
code, graph, knowledge-base, or historical RCA evidence depending on what is
missing. Guardrails keep routing bounded and safe, including fallback routes
when the supervisor tries to move too early to RCA, repeats an unhelpful
investigation path, or attempts patch generation before the required RCA,
solution, and code-backed patch context exist.

Code retrieval combines semantic FAISS search with BM25 lexical search,
identifier boosts, focused query planning, and mode-aware ranking. The goal is
to find the production implementation owner file, not merely a semantically
similar test, router, or graph-only context.

## Workflow Modes

Manual dynamic workflow remains the default:

```powershell
bug-resolver investigate --incident-id INC-001
```

You can also select a workflow explicitly:

```powershell
bug-resolver investigate --incident-id INC-001 --workflow manual
bug-resolver investigate --incident-id INC-001 --workflow graph
```

- `manual` is the earlier dynamic workflow implementation.
- `graph` is the LangGraph-backed workflow.
- `graph` is the active milestone for dynamic orchestration testing.

If the CLI entrypoint is not available directly in your shell, run it through
`uv`:

```powershell
uv run bug-resolver investigate --incident-id INC-001 --workflow graph
```

Patch-plan artifacts are optional:

```powershell
uv run bug-resolver investigate --incident-id INC-007 --workflow graph --include-patch-plan
uv run bug-resolver investigate --incident-id INC-007 --workflow graph --include-patch-diff
```

- `--include-patch-plan` saves an analyze-only patch recommendation.
- `--include-patch-diff` also asks the patch generator for unified diff
  suggestions. The generated diffs are report artifacts only; the target repo is
  not modified.
- Patch diffs are generated only for readable source files backed by CODE
  evidence. Graph-only or test-only evidence cannot authorize production
  patches.

## Realistic Sample Incidents

The sample incidents are intentionally vague, production-style reports. The agent
must infer root cause from logs, knowledge-base context, and target repo code.

- `INC-006`: Summary questions return incomplete document summaries. Demonstrates
  KB plus code reasoning for expected routing behavior.
- `INC-007`: Users see duplicate documents after upload. Logs, KB, and code reveal
  a filename/content-hash deduplication issue.
- `INC-008`: Answers cite unrelated sources after deployment. Logs, KB, and code
  reveal a reranker configuration/fallback issue.
- `INC-009`: Reranking score behavior requires structural graph context.
  Demonstrates AST graph retrieval and config-reader/caller-chain evidence.

## Setup

Recommended Python version: 3.11.

Create a `.env` file from `.env.example` and set the required values:

```env
OPENAI_API_KEY=...
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=production-bug-resolver-agent
LLM_MODEL=gpt-4o-mini
SUPERVISOR_LLM_MODEL=
RCA_WRITER_LLM_MODEL=
SOLUTION_RECOMMENDER_LLM_MODEL=
PATCH_SUGGESTION_LLM_MODEL=
PATCH_GENERATOR_LLM_MODEL=
EMBEDDING_MODEL=text-embedding-3-small
TARGET_REPO_PATH=C:\path\to\target\repo
```

LangSmith tracing is optional. To send traces to LangSmith, set:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=production-bug-resolver-agent
```

The app also accepts the legacy LangChain names `LANGCHAIN_TRACING_V2` and
`LANGCHAIN_API_KEY`. Values from `.env` are exported into the process
environment at runtime so LangSmith decorators can see them.

`LLM_MODEL` is the default OpenAI chat model for every LLM-backed agent. Set a
role-specific model only when you want that part of the workflow to use a
different model:

- `SUPERVISOR_LLM_MODEL`
- `RCA_WRITER_LLM_MODEL`
- `SOLUTION_RECOMMENDER_LLM_MODEL`
- `PATCH_SUGGESTION_LLM_MODEL`
- `PATCH_GENERATOR_LLM_MODEL`

`EMBEDDING_MODEL` controls code-index and code-query embeddings separately.

Recommended model tiers:

| Workflow use | Best | Moderate | Minimum |
| --- | --- | --- | --- |
| Supervisor routing | `gpt-5.4-mini` | `gpt-5.4-nano` | `gpt-5.4-nano` |
| RCA writer | `gpt-5.5` | `gpt-5.4` | `gpt-5.4-mini` |
| Solution recommender | `gpt-5.4` | `gpt-5.4-mini` | `gpt-5.4-nano` |
| Patch suggestion narrative | `gpt-5.4-mini` | `gpt-5.4-nano` | `gpt-5.4-nano` |
| Patch diff generator | `gpt-5.5` | `gpt-5.4` | `gpt-5.4-mini` |
| Code index embeddings | `text-embedding-3-large` | `text-embedding-3-small` | `text-embedding-3-small` |
| Code query embeddings | `text-embedding-3-large` | `text-embedding-3-small` | `text-embedding-3-small` |

For a practical default, keep cheap models on routing and narrative polish, and
reserve the stronger model for RCA synthesis and patch diff generation. For
lower-cost runs, use `gpt-5.4-mini` for RCA and patch diff generation, with
`gpt-5.4-nano` everywhere else.

Install dependencies:

```powershell
uv sync
```

Run tests:

```powershell
uv run pytest
```

Run realistic demo incidents with the LangGraph workflow:

```powershell
uv run bug-resolver investigate --incident-id INC-006 --workflow graph
uv run bug-resolver investigate --incident-id INC-007 --workflow graph
uv run bug-resolver investigate --incident-id INC-008 --workflow graph
uv run bug-resolver investigate --incident-id INC-009 --workflow graph
```

## Reports

Reports are generated under:

```text
reports/incidents/<INCIDENT_ID>/
```

Each completed investigation writes:

- `rca.md`
- `rca.json`
- `solution.md`
- `solution.json`

If patch output is requested, it also writes:

- `patch.md`
- `patch.json`

The `reports/` directory is local generated output and should not be committed.

Curated static sample reports for portfolio and demo review are available under:

```text
examples/reports/
```

## Package Map

- `bug_resolver.cli`: Typer CLI entrypoint.
- `bug_resolver.workflows`: Manual and LangGraph dynamic workflows plus factory
  wiring.
- `bug_resolver.agents`: Supervisor, specialist investigators, evaluator, RCA
  writer, solution recommender, patch suggester/generator, and report writer.
- `bug_resolver.rules`: Deterministic guardrails, code-query planning, code
  ranking, evidence evaluation, RCA fallback, patch suggestion, and patch
  generation safety rules.
- `bug_resolver.providers`: Local adapters for incidents, logs, knowledge base,
  code context, AST graph context, historical RCA context, patch file reads, and
  report persistence.
- `bug_resolver.retrieval`: Code loading, AST-aware chunking, indexing, FAISS
  vector search, and persisted vector-store support.
- `bug_resolver.llm` and `bug_resolver.embeddings`: OpenAI-backed structured
  output and embedding clients.
- `bug_resolver.schemas`: Pydantic contracts shared across agents, providers, and
  reports.

## Current Status

Completed:

- Core schemas
- Providers
- Code RAG with FAISS
- BM25 lexical retrieval merged with semantic code search
- Focused implementation/test/config code-query planning
- Mode-aware code ranking and implementation-owner evidence checks
- Knowledge Base retrieval
- AST graph code investigator
- Historical RCA retrieval
- Supervisor-led dynamic workflow
- LangGraph-backed workflow
- Guardrails
- Evidence evaluation
- RCA and solution generation
- Optional analyze-only patch plans and unified diff suggestions
- Optional LangSmith tracing
- Realistic sample incidents

Current limitations:

- Analyze-only
- No automatic code patching or repository mutation
- No PR creation
- Local providers only
- No real Jira, Datadog, or MCP integration yet

## Roadmap

- Add web search investigator.
- Add real incident/log integrations such as Jira, Datadog, Sentry, or MCP-backed
  tools.
- Add human approval workflow for applying patches or opening PRs.
- Add richer test generation around suggested patches.
- Add API/UI later.

## Development Notes

Run tests before committing:

```powershell
uv run pytest
uv run ruff check .
```

Useful focused checks:

```powershell
uv run pytest tests/golden/test_golden_investigations.py -v
uv run pytest tests/unit/test_code_query_rules.py -v
uv run pytest tests/unit/test_patch_generator_agent.py -v
```

If the target repository changes, remove the local FAISS index so Code RAG is
rebuilt on the next investigation:

```powershell
Remove-Item -Recurse -Force storage\faiss
```

The tests use fake LLM and embedding clients where possible. They should not
require live OpenAI calls.
