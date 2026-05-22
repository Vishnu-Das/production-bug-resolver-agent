# Production Bug Resolver Agent

[![CI](https://github.com/Vishnu-Das/production-bug-resolver-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Vishnu-Das/production-bug-resolver-agent/actions/workflows/ci.yml)

Production Bug Resolver Agent is a CLI-first, supervisor-led multi-agent RCA
assistant for production incidents. It uses LangGraph-style dynamic routing,
guardrails, logs, Code RAG, Knowledge Base RAG, and evidence-backed RCA/report
generation.

---

<img width="1078" height="903" alt="image" src="https://github.com/user-attachments/assets/1baad765-837a-4ba7-8ed2-59cc6925c512" />

---

The project is analyze-only today. It investigates incidents and writes RCA plus
solution reports, but it does not patch code, open pull requests, or modify the
target repository.

## What It Does

- Accepts an incident ID from the CLI.
- Loads incident metadata and production-like logs.
- Uses `SupervisorAgent` to choose the next specialist agent.
- Uses `GuardrailEngine` to validate each routing decision.
- Uses `LogInvestigatorAgent`, `KnowledgeBaseInvestigatorAgent`, and
  `CodeInvestigatorAgent` to gather evidence.
- Uses `EvidenceEvaluatorAgent` to decide whether more evidence is needed.
- Generates an RCA and solution recommendation.
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
  -> Evidence Evaluator
  -> RCA Writer
  -> Solution Recommender
  -> Report Writer
```

The workflow is not a fixed RCA pipeline. The supervisor can route to logs, code,
or knowledge-base evidence depending on what is missing. Guardrails keep routing
bounded and safe, including fallback routes when the supervisor tries to move too
early to RCA or repeats an unhelpful investigation path.

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

## Realistic Sample Incidents

The sample incidents are intentionally vague, production-style reports. The agent
must infer root cause from logs, knowledge-base context, and target repo code.

- `INC-006`: Summary questions return incomplete document summaries. Demonstrates
  KB plus code reasoning for expected routing behavior.
- `INC-007`: Users see duplicate documents after upload. Logs, KB, and code reveal
  a filename/content-hash deduplication issue.
- `INC-008`: Answers cite unrelated sources after deployment. Logs, KB, and code
  reveal a reranker configuration/fallback issue.

## Setup

Recommended Python version: 3.11.

Create a `.env` file from `.env.example` and set the required values:

```env
OPENAI_API_KEY=...
TARGET_REPO_PATH=C:\path\to\target\repo
```

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
  writer, solution recommender, and report writer.
- `bug_resolver.rules`: Deterministic guardrails, evidence evaluation rules, RCA
  fallback rules, and solution fallback rules.
- `bug_resolver.providers`: Local adapters for incidents, logs, knowledge base,
  code context, and report persistence.
- `bug_resolver.retrieval`: Code loading, chunking, indexing, and FAISS vector
  search.
- `bug_resolver.schemas`: Pydantic contracts shared across agents, providers, and
  reports.

## Current Status

Completed:

- Core schemas
- Providers
- Code RAG with FAISS
- Knowledge Base retrieval
- Supervisor-led dynamic workflow
- LangGraph-backed workflow
- Guardrails
- Evidence evaluation
- RCA and solution generation
- Realistic sample incidents

Current limitations:

- Analyze-only
- No automatic code patching
- No PR creation
- Local providers only
- No real Jira, Datadog, or MCP integration yet

## Roadmap

- Improve Code RAG ranking and file-path prioritization.
- Add graph/AST code investigator.
- Add web search investigator.
- Add historical RCA retrieval.
- Add patch suggestion and test generation with human approval.
- Add API/UI later.

## Development Notes

Run tests before committing:

```powershell
uv run pytest
uv run ruff check .
```

If the target repository changes, remove the local FAISS index so Code RAG is
rebuilt on the next investigation:

```powershell
Remove-Item -Recurse -Force storage\faiss
```

The tests use fake LLM and embedding clients where possible. They should not
require live OpenAI calls.
