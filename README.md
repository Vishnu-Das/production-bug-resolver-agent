# Production Bug Resolver Agent

CLI-first, analyze-only production RCA assistant for investigating incidents with a
supervisor-led dynamic multi-agent workflow.

The system collects evidence from logs, target repository code, and local knowledge-base
documents. A supervisor LLM decides which specialist agent should run next, deterministic
guardrails validate every route, and bounded replanning prevents runaway investigations.
RCA and solution writers are LLM-first with deterministic fallbacks, and generated reports
record which path was used.

<img width="759" height="461" alt="Screenshot 2026-05-20 104201" src="https://github.com/user-attachments/assets/ff7236a4-77be-4260-8b14-8653fee77a13" />


## Architecture

- `bug_resolver.cli`: Typer CLI entrypoint.
- `bug_resolver.workflows`: Dynamic workflow orchestration and runtime factory wiring.
- `bug_resolver.agents`: Supervisor, specialist investigators, evaluator, RCA writer,
  solution recommender, and report writer.
- `bug_resolver.rules`: Deterministic guardrails, evaluation rules, RCA fallback rules, and
  solution fallback rules.
- `bug_resolver.providers`: Local provider adapters for incidents, logs, knowledge base,
  code context, and report persistence.
- `bug_resolver.retrieval`: Code loading, chunking, indexing, and FAISS vector search.
- `bug_resolver.schemas`: Pydantic contracts shared across agents, providers, and reports.

## Investigation Flow

1. Load the incident from `sample_data/incidents`.
2. Ask the supervisor which agent should run next.
3. Validate the supervisor decision with deterministic guardrails.
4. Run the selected specialist agent to collect evidence.
5. Evaluate whether the evidence is sufficient.
6. Generate RCA, solution recommendation, and report artifacts.

The workflow is not a fixed pipeline. The supervisor can choose logs, code, or knowledge-base
context depending on what is missing, while guardrails keep routing safe and bounded.

## Local Setup

Create a `.env` file from `.env.example` and set the required values:

```env
OPENAI_API_KEY=...
TARGET_REPO_PATH=C:\path\to\target\repo
```

Run an investigation:

```powershell
uv run bug-resolver investigate --incident-id INC-001
```

Reports are written under `reports/incidents/<INCIDENT_ID>/` as:

- `rca.md`
- `rca.json`
- `solution.md`
- `solution.json`

## Development

Run the test suite and lint checks before committing:

```powershell
uv run pytest
uv run ruff check .
```

The tests use fake LLM and embedding clients where possible. They should not require live
OpenAI calls.

## Documentation Style

Python files follow PEP 257-style docstrings:

- Every source and test module has a short module docstring.
- Public production classes and functions have concise role docstrings.
- Comments are reserved for non-obvious control flow or safety checks.
- Generated report artifacts and sample JSON data are kept as data, not prose-heavy docs.

Keep documentation crisp: explain why a component exists, what boundary it owns, and what a
new developer must know to change it safely.
