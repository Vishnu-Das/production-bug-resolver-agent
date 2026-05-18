# Production Bug Resolver Agent — Goal, MVP Blueprint, Long-Term Roadmap, and Engineering Rules

## 1. Project Vision

The goal of this project is to build a **production-grade multi-agent bug investigation and resolution assistant**.

The system should help investigate production bugs by collecting evidence from multiple sources such as logs, code context, knowledge base documents, and eventually external platforms like Jira, GitHub Issues, observability tools, and web search.

The first version will focus on **analysis-only RCA generation**. Later versions can evolve into a more autonomous bug resolver that can suggest patches, generate tests, and eventually prepare pull requests.

### High-Level Vision

Build a system that can take an incident or bug report, understand the symptoms, inspect logs, retrieve relevant code and documentation, reason over the evidence, generate a root cause analysis, suggest a solution, and store the investigation report for future use.

### Long-Term Positioning

This project should become a flagship AI engineering portfolio project demonstrating:

- Multi-agent architecture
- LangGraph-style orchestration
- MCP-style tool abstractions
- Code RAG
- Knowledge Base RAG
- AST / Graph-based code understanding
- Log analysis
- Evidence-first RCA generation
- Production engineering principles
- SOLID and clean architecture
- Extensible platform integration
- Test-driven implementation
- Future patch and PR automation

---

## 2. Product Goal

### Primary Goal

Build a **CLI-based multi-agent production bug resolver** that investigates bugs in a target repository using:

- incident description
- console logs / production-like logs
- code retrieval
- README / knowledge base documents
- structured multi-agent reasoning
- controlled retry loops
- evidence-backed RCA generation
- solution recommendation
- RCA report storage

### First Target Repository

The first target codebase will be the existing `conversational_rag` repository.

The project should use this repo as the initial source for:

- code RAG
- generated bugs
- console logs
- knowledge base documents
- README-based context
- future graph and AST experiments

---

## 3. MVP Scope

The MVP is intentionally focused.

### MVP Will Do

The MVP should:

1. Accept an incident through CLI.
2. Load logs for the incident using a local MCP-like abstraction.
3. Analyze logs and extract error details.
4. Plan what code and knowledge base context is needed.
5. Retrieve relevant code using FAISS-based Code RAG.
6. Retrieve relevant documentation using README / docs-based Knowledge Base RAG.
7. Generate root-cause hypotheses.
8. Evaluate evidence and confidence.
9. Retry context retrieval if evidence is insufficient.
10. Generate an RCA report.
11. Suggest a solution approach.
12. Save the report as Markdown and JSON.
13. Include tests from day one.

### MVP Will Not Do Yet

The MVP will not initially:

- auto-edit source code
- generate pull requests
- connect to real Jira
- connect to real Datadog / Loki / ELK / CloudWatch
- use real MCP servers for every integration
- provide a web UI
- use a production database
- perform full graph-based code reasoning from day one
- run autonomous unbounded agent loops

---

## 4. Locked MVP Decisions

| Area | Decision |
|---|---|
| MVP behavior | Analyze-only RCA system |
| Interface | CLI first |
| Future API | FastAPI later |
| Future UI | UI later on top of FastAPI |
| Target repo | `conversational_rag` |
| LLM provider | OpenAI through wrapper interface |
| Embeddings | OpenAI embeddings |
| Vector store | FAISS |
| CLI framework | Typer |
| Workflow | Fixed workflow with controlled retry / loopback |
| MCP strategy | Local MCP-like abstractions first, real MCP later |
| Tests | pytest from day one |
| Report format | Markdown + JSON |
| Logs | Structured parsing first, no Log RAG in MVP |
| Architecture style | Class-based, SOLID, modular, extensible |

---

## 5. Long-Term Goals

The long-term goal is to evolve the MVP into a complete production bug resolver platform.

### Long-Term Capabilities

Future versions should support:

1. Jira / Linear / GitHub Issues as bug intake sources.
2. Real MCP servers for logs, code, knowledge base, issue tracker, and report storage.
3. Datadog / Loki / ELK / CloudWatch integrations.
4. Historical incident search.
5. Semantic retrieval over past RCA reports.
6. AST-based code understanding.
7. Code graph construction.
8. Graph RAG for codebase reasoning.
9. Function call path tracing.
10. Dependency analysis.
11. Ownership and module-boundary awareness.
12. Patch suggestion.
13. Test generation.
14. Pull request draft generation.
15. Human approval workflow.
16. FastAPI backend.
17. Web UI dashboard.
18. Observability for agent runs.
19. Evaluation framework for RCA quality.
20. Incident memory from previous reports.

### Final Direction

The project may eventually become:

```text
Incident Platform / Jira Ticket
        -> Production Bug Resolver Agent
        -> Logs + Code + Docs + Historical RCAs + Web Search
        -> RCA
        -> Fix Plan
        -> Patch Suggestion
        -> Tests
        -> Human Approval
        -> PR Draft
```

---

## 6. Core System Flow

### MVP Flow

```text
CLI Incident Input
        |
        v
Incident Intake Agent
        |
        v
Log Analysis Agent
        |
        v
Context Planning Agent
        |
        +------------------------+
        |                        |
        v                        v
Code Context Agent        Knowledge Base Agent
        |                        |
        +-----------+------------+
                    |
                    v
Hypothesis Agent
                    |
                    v
RCA Agent
                    |
                    v
Evidence Evaluator Agent
                    |
        +-----------+------------+
        |                        |
confidence high          confidence low and retry available
        |                        |
        v                        v
Solution Agent        Context Planning Agent
        |
        v
Report Writer Agent
        |
        v
Markdown + JSON RCA Report
```

### Workflow Philosophy

The MVP workflow should be mostly deterministic, but not blindly linear.

It should support controlled retry loops when the evidence is weak.

This gives the system agentic behavior without making it unpredictable.

---

## 7. Retry / Loopback Rules

The workflow should support a retry loop based on evidence confidence.

### Retry Conditions

The system should retry context retrieval when:

- RCA confidence is below threshold.
- important evidence is missing.
- log analysis points to files not retrieved by Code RAG.
- hypotheses conflict with each other.
- RCA is too generic.
- solution cannot be tied back to evidence.

### Default Retry Policy

```text
confidence_threshold = 0.75
max_retries = 2
```

### Retry Behavior

If confidence is low:

1. Evidence Evaluator identifies missing evidence.
2. Context Planning Agent generates improved search queries.
3. Code Context Agent and Knowledge Base Agent retrieve more context.
4. Hypothesis Agent regenerates hypotheses.
5. RCA Agent regenerates RCA.
6. Evidence Evaluator checks again.

If retries are exhausted, the system should still produce an RCA, but clearly mark it as low-confidence.

### No Infinite Loops

The orchestrator must never run uncontrolled loops.

All loopbacks must have:

- max retry count
- stopping condition
- reason for retry
- updated search plan
- final fallback behavior

---

## 8. Main Agent and Subagent Design

The system should use a main orchestrator and focused subagents.

### Main Agent / Orchestrator

The main agent is responsible for workflow control.

Responsibilities:

- Maintain investigation state.
- Call subagents in correct order.
- Apply retry rules.
- Prevent infinite loops.
- Decide whether enough evidence exists.
- Ensure final report is generated.
- Ensure agent outputs are structured.
- Ensure the final RCA is evidence-backed.

The main agent should not directly perform every task itself.

### Subagents

Subagents should be focused, testable classes.

Initial subagents:

1. `IncidentIntakeAgent`
2. `LogAnalysisAgent`
3. `ContextPlanningAgent`
4. `CodeContextAgent`
5. `KnowledgeBaseAgent`
6. `HypothesisAgent`
7. `RCAAgent`
8. `EvidenceEvaluatorAgent`
9. `SolutionRecommendationAgent`
10. `ReportWriterAgent`

---

## 9. Agent Responsibilities

### 9.1 Incident Intake Agent

Purpose:

Convert raw CLI input into a structured incident object.

Responsibilities:

- Normalize user-provided bug description.
- Attach incident id.
- Identify severity if provided.
- Identify affected area if obvious.
- Preserve raw input.

Output:

- `Incident`

---

### 9.2 Log Analysis Agent

Purpose:

Analyze logs and extract useful debugging signals.

Responsibilities:

- Extract exception type.
- Extract exception message.
- Extract stack trace.
- Extract file paths and line numbers.
- Extract timestamps.
- Extract request id / trace id if available.
- Identify likely failure point.
- Summarize what failed.

Output:

- `LogAnalysisResult`

---

### 9.3 Context Planning Agent

Purpose:

Decide what context is needed next.

Responsibilities:

- Generate code search queries.
- Generate knowledge base search queries.
- Use log analysis to guide retrieval.
- Use previous failed retrieval attempts to improve queries.
- Generate focused search plans for retry.

Output:

- `ContextPlan`

---

### 9.4 Code Context Agent

Purpose:

Retrieve relevant code snippets from the target repository.

Responsibilities:

- Search code using FAISS-based Code RAG.
- Retrieve relevant snippets.
- Include source metadata.
- Prefer files mentioned in logs.
- Return concise but sufficient context.

Output:

- list of `CodeContext`

---

### 9.5 Knowledge Base Agent

Purpose:

Retrieve relevant documentation and design context.

Responsibilities:

- Search README and future docs.
- Retrieve expected behavior.
- Retrieve design assumptions.
- Retrieve known issue notes.
- Later retrieve past RCA reports.

Output:

- list of `KnowledgeContext`

---

### 9.6 Hypothesis Agent

Purpose:

Generate possible root-cause hypotheses from evidence.

Responsibilities:

- Generate multiple hypotheses.
- Attach supporting evidence.
- Attach contradicting evidence if any.
- Assign confidence score.
- Avoid unsupported claims.

Output:

- list of `Hypothesis`

---

### 9.7 RCA Agent

Purpose:

Generate a formal root-cause analysis.

Responsibilities:

- Select strongest hypothesis.
- Write root cause.
- Explain impact.
- Explain technical reason.
- Cite evidence.
- Identify why it happened.
- Identify why it was not caught earlier if possible.
- Include confidence score.
- Include open questions.

Output:

- `RCAReport`

---

### 9.8 Evidence Evaluator Agent

Purpose:

Check whether the RCA is sufficiently supported by evidence.

Responsibilities:

- Score RCA confidence.
- Identify missing evidence.
- Decide whether retry is needed.
- Produce improved retrieval hints.
- Prevent weak RCA from being presented as certain.

Output:

- `EvidenceEvaluationResult`

---

### 9.9 Solution Recommendation Agent

Purpose:

Suggest solution approach based on RCA.

Responsibilities:

- Suggest immediate fix.
- Suggest long-term prevention.
- Suggest tests to add.
- Suggest monitoring / logging improvements.
- Avoid generating patches in MVP.

Output:

- `SolutionRecommendation`

---

### 9.10 Report Writer Agent

Purpose:

Persist the final report.

Responsibilities:

- Save Markdown RCA report.
- Save JSON structured report.
- Save evidence metadata.
- Save low-confidence warnings if applicable.

Output:

- `ReportSaveResult`

---

## 10. Rules System

The project should include a rules layer that drives the main agent and subagents.

These rules are important because the system should behave consistently, safely, and in a production-like manner.

Rules should not be scattered randomly inside prompts or agent logic.

They should be centralized and versioned.

### Rule Categories

The rules system should include:

1. Orchestration rules
2. Evidence rules
3. RCA rules
4. Retrieval rules
5. Retry rules
6. Tool usage rules
7. Agent behavior rules
8. Output quality rules
9. Safety and guardrail rules
10. Future patch-generation rules

---

## 11. Orchestration Rules

The main agent must follow these rules:

1. Always create or load a structured incident before investigation.
2. Always analyze logs before generating hypotheses.
3. Always retrieve code context before RCA generation.
4. Always retrieve knowledge base context before RCA generation when documentation exists.
5. Never generate a final RCA without evidence.
6. Never run unbounded loops.
7. Retry only when confidence is below threshold and retry count is available.
8. If confidence remains low after retries, produce a low-confidence RCA with open questions.
9. Always store the final report.
10. Always preserve raw evidence references.

---

## 12. Evidence Rules

Evidence is the core of the system.

The system must follow evidence-first reasoning.

### Evidence Rules

1. Every RCA claim must be backed by at least one evidence item.
2. Evidence can come from logs, code, knowledge base, graph, web search, or past RCA reports.
3. Logs are primary evidence for runtime failure.
4. Code is primary evidence for implementation behavior.
5. Knowledge base is supporting evidence for intended behavior.
6. Web search is external supporting evidence, not primary evidence for local code behavior.
7. If evidence conflicts, the RCA must mention the conflict.
8. If evidence is missing, the report must say so.
9. Confidence score must reflect evidence quality.
10. Do not overstate certainty.

### Evidence Metadata

Every evidence item should carry metadata:

```text
source_type: log | code | knowledge_base | graph | web | historical_rca
source_name: string
file_path: optional string
line_start: optional int
line_end: optional int
content: string
relevance_score: optional float
confidence: optional float
```

---

## 13. RCA Rules

The RCA Agent must follow these rules:

1. RCA must be clear and technical.
2. RCA must distinguish symptoms from root cause.
3. RCA must cite evidence.
4. RCA must include confidence score.
5. RCA must include open questions if confidence is not high.
6. RCA must include immediate fix recommendation.
7. RCA must include long-term prevention recommendation.
8. RCA must avoid generic statements.
9. RCA must avoid hallucinated files, functions, and line numbers.
10. RCA must mark missing evidence explicitly.

### RCA Report Sections

The Markdown report should include:

1. Incident Summary
2. Impact
3. Symptoms
4. Log Findings
5. Code Findings
6. Knowledge Base Findings
7. Hypotheses Considered
8. Final Root Cause
9. Evidence
10. Confidence
11. Recommended Fix
12. Preventive Actions
13. Tests to Add
14. Open Questions
15. Raw References / Evidence Index

---

## 14. Retrieval Rules

### Code Retrieval Rules

1. Prefer files mentioned in logs.
2. Search by exception message.
3. Search by function names from stack trace.
4. Search by file names from stack trace.
5. Search by suspected schema names or error keys.
6. Retrieve caller and callee context where possible.
7. Return file path and line metadata.
8. Avoid returning huge irrelevant chunks.
9. On retry, use missing evidence hints to improve queries.
10. Later, combine vector retrieval with AST / graph retrieval.

### Knowledge Base Retrieval Rules

1. Search README first in MVP.
2. Later search docs, runbooks, architecture notes, ADRs, and past RCAs.
3. Retrieve expected behavior.
4. Retrieve known limitations.
5. Retrieve design assumptions.
6. Use docs as supporting evidence, not proof of runtime behavior.

### Log Retrieval Rules

For MVP, logs should be parsed and analyzed directly.

Do not use Log RAG in MVP.

Logs should be treated as structured evidence.

Future semantic log retrieval may be added for:

- historical similar incidents
- large logs
- multiple services
- distributed traces
- repeated error patterns

---

## 15. Tool Usage Rules

Tool usage should be controlled through abstractions.

The agents should depend on interfaces, not concrete implementations.

### Initial Provider Interfaces

The system should define interfaces such as:

```python
class LogProvider(Protocol):
    def get_logs(self, incident_id: str) -> list[LogEntry]:
        ...

class CodeContextProvider(Protocol):
    def search_code(self, queries: list[str]) -> list[CodeContext]:
        ...

class KnowledgeBaseProvider(Protocol):
    def search_docs(self, queries: list[str]) -> list[KnowledgeContext]:
        ...

class ReportStore(Protocol):
    def save_report(self, report: RCAReport) -> ReportSaveResult:
        ...
```

### Initial Concrete Implementations

MVP concrete implementations:

- `FileLogProvider`
- `LocalCodeRAGProvider`
- `LocalKnowledgeBaseProvider`
- `FileReportStore`
- `OpenAILLMClient`

Future concrete implementations:

- `MCPLogProvider`
- `MCPCodeContextProvider`
- `MCPKnowledgeBaseProvider`
- `MCPReportStore`
- `JiraIncidentProvider`
- `GitHubIssueProvider`
- `DatadogLogProvider`
- `LokiLogProvider`
- `ElasticLogProvider`
- `Neo4jCodeGraphProvider`

---

## 16. SOLID Principles

This project must follow SOLID principles as much as practical.

### Single Responsibility Principle

Each class should have one reason to change.

Examples:

- `LogParser` parses logs only.
- `LogAnalysisAgent` reasons about logs only.
- `ReportStore` saves reports only.
- `CodeContextProvider` retrieves code context only.

Avoid God classes.

---

### Open/Closed Principle

The system should be open for extension and closed for modification.

Examples:

- Add `DatadogLogProvider` without changing orchestration.
- Add `Neo4jGraphProvider` without changing RCA agent.
- Add `AnthropicLLMClient` without changing agent classes.
- Add `JiraIncidentProvider` without changing CLI investigation flow.

This should be achieved using:

- Protocols
- abstract base classes where needed
- adapters
- dependency injection
- factories
- strategy pattern

---

### Liskov Substitution Principle

Any implementation of an interface should be replaceable without breaking behavior.

Examples:

- `FileLogProvider` and `DatadogLogProvider` should both satisfy `LogProvider`.
- `FAISSCodeContextProvider` and `GraphCodeContextProvider` should both satisfy `CodeContextProvider` if they expose the same contract.

---

### Interface Segregation Principle

Avoid large interfaces.

Do not create one giant provider that does everything.

Prefer focused interfaces:

- `LogProvider`
- `CodeContextProvider`
- `KnowledgeBaseProvider`
- `ReportStore`
- `IncidentProvider`
- `LLMClient`
- `EmbeddingClient`

---

### Dependency Inversion Principle

High-level workflow logic should depend on abstractions, not concrete classes.

The orchestrator should depend on interfaces such as:

- `LogProvider`
- `CodeContextProvider`
- `KnowledgeBaseProvider`
- `ReportStore`
- `LLMClient`

Concrete implementations should be injected at composition time.

---

## 17. Design Patterns to Prefer

Use design patterns only where they help clarity and extensibility.

### Recommended Patterns

1. **Strategy Pattern**
   - Retrieval strategies
   - Log parsing strategies
   - Ranking strategies
   - Retry strategies

2. **Factory Pattern**
   - Provider creation
   - LLM client creation
   - Vector store creation

3. **Adapter Pattern**
   - MCP adapters
   - Jira adapter
   - Datadog adapter
   - GitHub adapter

4. **Repository Pattern**
   - Report storage
   - Incident storage
   - Historical RCA storage

5. **Template Method Pattern**
   - Base agent execution flow if useful

6. **Command Pattern**
   - CLI commands
   - Future action execution

7. **Chain / Graph Orchestration**
   - LangGraph workflow nodes and conditional edges

---

## 18. Class-Based Architecture Rule

The implementation should avoid loose function-only files except for small utilities.

Most important components should be represented as classes with clear responsibilities.

Acceptable function-only files:

- tiny utility functions
- constants
- test helpers
- simple pure transformations if justified

Preferred structure:

- classes for agents
- classes for providers
- classes for repositories
- classes for parsers
- classes for retrievers
- classes for graph builders
- classes for stores
- Pydantic models for schemas

---

## 19. Suggested Project Structure

```text
production_bug_resolver/
│
├── README.md
├── pyproject.toml
├── .env.example
├── Makefile
│
├── docs/
│   ├── PROJECT_GOAL_AND_BLUEPRINT.md
│   ├── AGENT_RULES.md
│   └── ARCHITECTURE.md
│
├── src/
│   └── bug_resolver/
│       │
│       ├── main.py
│       │
│       ├── config/
│       │   ├── settings.py
│       │   └── logging.py
│       │
│       ├── schemas/
│       │   ├── incident.py
│       │   ├── logs.py
│       │   ├── evidence.py
│       │   ├── code_context.py
│       │   ├── knowledge_context.py
│       │   ├── context_plan.py
│       │   ├── hypothesis.py
│       │   ├── rca.py
│       │   ├── solution.py
│       │   └── workflow_state.py
│       │
│       ├── agents/
│       │   ├── base.py
│       │   ├── incident_intake_agent.py
│       │   ├── log_analysis_agent.py
│       │   ├── context_planning_agent.py
│       │   ├── code_context_agent.py
│       │   ├── knowledge_base_agent.py
│       │   ├── hypothesis_agent.py
│       │   ├── rca_agent.py
│       │   ├── evidence_evaluator_agent.py
│       │   ├── solution_recommendation_agent.py
│       │   └── report_writer_agent.py
│       │
│       ├── prompts/
│       │   ├── incident_intake.py
│       │   ├── log_analysis.py
│       │   ├── context_planning.py
│       │   ├── hypothesis.py
│       │   ├── rca.py
│       │   ├── evidence_evaluation.py
│       │   └── solution.py
│       │
│       ├── rules/
│       │   ├── base.py
│       │   ├── orchestration_rules.py
│       │   ├── evidence_rules.py
│       │   ├── rca_rules.py
│       │   ├── retrieval_rules.py
│       │   ├── retry_rules.py
│       │   └── rule_engine.py
│       │
│       ├── workflows/
│       │   ├── bug_resolution_graph.py
│       │   └── graph_factory.py
│       │
│       ├── providers/
│       │   ├── logs/
│       │   │   ├── base.py
│       │   │   ├── file_log_provider.py
│       │   │   └── parsers.py
│       │   │
│       │   ├── code/
│       │   │   ├── base.py
│       │   │   ├── faiss_code_context_provider.py
│       │   │   └── code_indexer.py
│       │   │
│       │   ├── knowledge/
│       │   │   ├── base.py
│       │   │   ├── local_knowledge_base_provider.py
│       │   │   └── knowledge_indexer.py
│       │   │
│       │   ├── incident/
│       │   │   ├── base.py
│       │   │   ├── cli_incident_provider.py
│       │   │   └── jira_incident_provider.py
│       │   │
│       │   └── reports/
│       │       ├── base.py
│       │       └── file_report_store.py
│       │
│       ├── llm/
│       │   ├── base.py
│       │   ├── openai_llm_client.py
│       │   └── llm_factory.py
│       │
│       ├── embeddings/
│       │   ├── base.py
│       │   ├── openai_embedding_client.py
│       │   └── embedding_factory.py
│       │
│       ├── retrieval/
│       │   ├── chunkers.py
│       │   ├── document_loaders.py
│       │   ├── vector_store.py
│       │   └── retrievers.py
│       │
│       ├── graph/
│       │   ├── ast_parser.py
│       │   ├── graph_builder.py
│       │   ├── graph_store.py
│       │   └── graph_queries.py
│       │
│       ├── cli/
│       │   ├── app.py
│       │   └── commands.py
│       │
│       └── utils/
│           ├── ids.py
│           └── time.py
│
├── sample_data/
│   ├── incidents/
│   ├── logs/
│   ├── knowledge_base/
│   └── target_repos/
│
├── reports/
│
└── tests/
    ├── unit/
    ├── integration/
    └── golden/
```

---

## 20. Log Strategy

### MVP Log Strategy

For MVP, do not build Log RAG.

Use:

- file-based logs
- console logs
- structured parsing
- stack trace extraction
- LLM-assisted log analysis

### Why No Log RAG in MVP

The first version will likely have one incident and one log file.

For this, RAG is unnecessary.

Direct parsing and analysis are more reliable.

### Future Log Strategy

Later, add:

1. Log filtering by service, timestamp, request id, trace id.
2. Historical similar error search.
3. Semantic log retrieval.
4. Observability platform integrations.
5. Cross-service trace reconstruction.

### Important Rule

Logs are runtime evidence.

They should be treated as structured evidence first, not as ordinary documents.

---

## 21. Code RAG Strategy

### MVP Code RAG

Use FAISS and OpenAI embeddings.

The Code RAG should index the target repository.

It should retrieve:

- file path
- class name if available
- function / method name if available
- line range if possible
- code snippet
- relevance score

### Important Code RAG Rule

Code retrieval must not just return similar chunks.

It should try to retrieve context useful for RCA:

- failing function
- caller
- callee
- config/schema/model involved
- related test if available
- file mentioned in logs

### Future Code Intelligence

Add AST and graph support later.

Future capabilities:

- function definitions
- class definitions
- imports
- function calls
- method calls
- call graph
- dependency graph
- file graph
- ownership graph
- error-to-code mapping

---

## 22. Knowledge Base Strategy

### MVP Knowledge Base

Start with:

- README.md from `conversational_rag`
- optional manually written architecture notes
- optional known issues document

### Future Knowledge Base

Add:

- runbooks
- ADRs
- design docs
- troubleshooting docs
- past RCA reports
- deployment notes
- issue workflows

### Important Rule

Past RCA reports should become part of future knowledge retrieval.

This allows the system to learn from previous incidents.

---

## 23. Report Storage Strategy

The system should store each investigation.

Suggested structure:

```text
reports/
  incidents/
    INC-001/
      rca.md
      rca.json
      evidence.json
      context_plan.json
```

### Report Storage Rules

1. Always save Markdown for human readability.
2. Always save JSON for machine reuse.
3. Always save evidence references.
4. Save confidence score.
5. Save retry count.
6. Save open questions.
7. Future: index reports into knowledge base.

---

## 24. CLI Design

Initial CLI should support:

```bash
bug-resolver investigate --incident-id INC-001
```

Future commands:

```bash
bug-resolver investigate --description "Users get 500 error while asking summary questions"

bug-resolver investigate --incident-file sample_data/incidents/inc_001.json

bug-resolver index-code --repo-path ../conversational_rag

bug-resolver index-kb --docs-path sample_data/knowledge_base

bug-resolver show-report --incident-id INC-001
```

### CLI Rules

1. CLI should be thin.
2. CLI should call application services, not contain business logic.
3. CLI should return helpful errors.
4. CLI should support verbose/debug output later.

---

## 25. Testing Strategy

Tests should be added from day one.

### Unit Tests

Initial unit tests:

- schema validation
- log parser
- file log provider
- report store
- context planner output validation
- rule engine decisions
- retry policy

### Integration Tests

Initial integration tests:

- FAISS code index creation
- knowledge base index creation
- code context provider search
- knowledge base provider search
- full workflow on sample incident

### Golden Tests

Golden tests should verify that the full system produces a reasonable RCA for a known sample incident.

Example:

```text
Input: sample incident + logs
Expected: RCA mentions correct failure area, evidence, and suggested fix
```

Golden tests are useful for agentic systems because exact output may vary, but important fields should remain correct.

---

## 26. Configuration Strategy

Use configuration through environment variables and settings classes.

Suggested config:

```text
OPENAI_API_KEY
LLM_MODEL
EMBEDDING_MODEL
TARGET_REPO_PATH
REPORTS_DIR
FAISS_INDEX_DIR
KNOWLEDGE_BASE_DIR
MAX_RETRIES
CONFIDENCE_THRESHOLD
```

Use `pydantic-settings` for config management.

Rules:

1. No hardcoded API keys.
2. No hardcoded absolute paths.
3. Use `.env.example`.
4. Validate settings on startup.

---

## 27. LLM Abstraction

Do not hardcode OpenAI directly inside agents.

Define an LLM client abstraction.

Example:

```python
class LLMClient(Protocol):
    def generate_text(self, prompt: str) -> str:
        ...

    def generate_structured(self, prompt: str, output_schema: type[BaseModel]) -> BaseModel:
        ...
```

Initial implementation:

- `OpenAILLMClient`

Future implementations:

- `AnthropicLLMClient`
- `GeminiLLMClient`
- `OllamaLLMClient`

### LLM Rules

1. Prefer structured output for agent responses.
2. Validate LLM output using Pydantic.
3. Retry or fail gracefully when output is invalid.
4. Keep prompts separate from business logic.
5. Do not let LLM directly mutate state without validation.

---

## 28. Prompt Management

Prompts should be stored separately.

Rules:

1. No large prompt strings inside agent classes.
2. Each agent should have its own prompt module or template.
3. Prompts should include agent-specific rules.
4. Prompts should require structured outputs.
5. Prompts should enforce evidence-first reasoning.
6. Prompts should instruct agents to avoid unsupported claims.

---

## 29. State Management

Use a strongly typed workflow state.

Suggested state fields:

```text
incident
raw_logs
parsed_logs
log_analysis
context_plan
code_context
knowledge_context
hypotheses
rca_report
evidence_evaluation
solution_recommendation
retry_count
max_retries
final_report_path
errors
```

Rules:

1. State should be explicit.
2. Avoid hidden global state.
3. Each workflow node should read and write known state fields.
4. Validate important state transitions.
5. Keep raw evidence available.

---

## 30. Future Jira / Platform Integration

Eventually, incidents should come from platforms like:

- Jira
- Linear
- GitHub Issues
- PagerDuty
- incident management tools

This should be implemented using an `IncidentProvider` abstraction.

Example:

```python
class IncidentProvider(Protocol):
    def get_incident(self, incident_id: str) -> Incident:
        ...
```

Initial implementation:

- `CLIIncidentProvider`
- `FileIncidentProvider`

Future implementation:

- `JiraIncidentProvider`
- `GitHubIssueIncidentProvider`
- `PagerDutyIncidentProvider`

The rest of the system should not care where the incident came from.

---

## 31. Future MCP Strategy

MVP should use local abstractions.

Later, each provider can be backed by MCP.

Possible MCPs:

1. Log MCP
2. Code Search MCP
3. Knowledge Base MCP
4. Jira MCP
5. GitHub MCP
6. Report Store MCP
7. Web Search MCP
8. Graph Context MCP

### MCP Rule

Agents should not depend directly on MCP implementation details.

Agents should depend on provider interfaces.

MCP clients should be adapters behind those interfaces.

---

## 32. Future Patch Generation

Patch generation is not part of MVP.

Later, add a `PatchRecommendationAgent` or `PatchGenerationAgent`.

Patch generation must follow strict rules:

1. Generate patch only after RCA is evidence-backed.
2. Do not modify code automatically without approval.
3. Include tests with every suggested patch.
4. Explain why each change is needed.
5. Keep patch scoped to the root cause.
6. Avoid broad rewrites.
7. Human approval required before PR creation.

---

## 33. Quality Bar for the Project

This project should be treated like a production engineering project.

### Must-Have Standards

1. Type hints everywhere.
2. Pydantic schemas for structured data.
3. Class-based architecture.
4. SOLID principles.
5. Interfaces for external dependencies.
6. Dependency injection.
7. Separate prompts.
8. Separate rules.
9. Tests from day one.
10. Clean folder structure.
11. Meaningful README.
12. `.env.example`.
13. Reproducible CLI commands.
14. Stored reports.
15. Evidence-backed outputs.

### Avoid

1. One giant agent file.
2. Raw dictionaries passed everywhere.
3. Business logic inside CLI.
4. Prompts mixed with agent logic.
5. Hardcoded provider implementations.
6. Unbounded autonomous loops.
7. RCA without evidence.
8. Hallucinated source references.
9. Overengineering before MVP works.
10. Function-only architecture for core modules.

---

## 34. MVP Success Criteria

The MVP is successful when:

1. A CLI command can run an investigation for a sample incident.
2. Logs are loaded and analyzed.
3. Code context is retrieved from `conversational_rag` using FAISS.
4. Knowledge base context is retrieved from README/docs.
5. Hypotheses are generated.
6. RCA is produced with evidence.
7. Confidence is evaluated.
8. Retry happens if confidence is low.
9. Solution recommendation is generated.
10. Markdown and JSON reports are saved.
11. Tests pass.
12. Code follows class-based SOLID design.

---

## 35. Suggested First Implementation Order

### Step 1: Project Skeleton

Create:

- package structure
- pyproject
- config
- schemas
- base interfaces
- CLI shell
- tests folder

### Step 2: Core Schemas

Create Pydantic models:

- `Incident`
- `LogEntry`
- `LogAnalysisResult`
- `EvidenceItem`
- `CodeContext`
- `KnowledgeContext`
- `ContextPlan`
- `Hypothesis`
- `RCAReport`
- `SolutionRecommendation`
- `WorkflowState`

### Step 3: Provider Interfaces

Create:

- `LogProvider`
- `CodeContextProvider`
- `KnowledgeBaseProvider`
- `ReportStore`
- `LLMClient`
- `EmbeddingClient`

### Step 4: Local Providers

Implement:

- `FileLogProvider`
- `FAISSCodeContextProvider`
- `LocalKnowledgeBaseProvider`
- `FileReportStore`
- `OpenAILLMClient`
- `OpenAIEmbeddingClient`

### Step 5: Agents

Implement agents one by one:

1. Incident Intake Agent
2. Log Analysis Agent
3. Context Planning Agent
4. Code Context Agent
5. Knowledge Base Agent
6. Hypothesis Agent
7. RCA Agent
8. Evidence Evaluator Agent
9. Solution Recommendation Agent
10. Report Writer Agent

### Step 6: Workflow

Implement LangGraph workflow with conditional retry.

### Step 7: CLI

Expose:

```bash
bug-resolver investigate --incident-id INC-001
```

### Step 8: Tests

Add:

- unit tests
- integration tests
- golden test for full sample incident

---

## 36. Guiding Principle

The project should always optimize for this:

```text
Evidence-first, modular, extensible, production-style agentic debugging.
```

The system should not just sound intelligent. It should show how it reached the conclusion using logs, code, documents, and structured reasoning.

The strongest differentiator of this project should be:

```text
Not just RAG. Not just agents. A production-grade evidence-backed bug investigation workflow.
```

---

## 37. Current Finalized Direction

The current finalized direction is:

```text
Build a CLI-first, analyze-only, multi-agent RCA system for bugs in the conversational_rag repo.
Use OpenAI, OpenAI embeddings, FAISS, Typer, pytest, class-based SOLID architecture, local MCP-like abstractions, and a fixed LangGraph workflow with controlled retry loops.
```

This document should be treated as the project guiding document.

Implementation decisions should be checked against this document before adding new components or changing architecture.
