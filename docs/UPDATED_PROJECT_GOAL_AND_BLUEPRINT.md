# Production Bug Resolver Agent — Updated Goal, Agentic Blueprint, MVP Scope, and Engineering Rules

## 1. Project Vision

The goal of this project is to build a **portfolio-grade, production-style multi-agent bug investigation and resolution assistant**.

This project is primarily intended to help learn and demonstrate:

- agentic systems
- multi-agent orchestration
- dynamic agent routing
- MCP-style tool integration
- guardrails
- Code RAG
- Knowledge Base RAG
- evidence-first RCA
- LangGraph-style workflows
- production-grade software engineering

The system should take a production incident or bug report, decide which specialist agents and tools are needed, gather evidence from logs, code, docs, historical RCAs, and later external systems, then produce an evidence-backed RCA and solution recommendation.

The first version will remain **analysis-only**, but the architecture should be designed so it can later support patch suggestions, test generation, and PR creation.

---

## 2. Product Goal

Build a **CLI-first, supervisor-led, multi-agent production bug resolver**.

The system should:

1. Accept an incident from CLI initially.
2. Later accept incidents from Jira, GitHub Issues, Linear, PagerDuty, or similar systems.
3. Use a supervisor agent to decide which specialist agent to call next.
4. Use specialist agents for logs, code, knowledge base, graph/AST, web search, historical RCA, and solution generation.
5. Use MCP-style provider abstractions for tools and external systems.
6. Use guardrails to keep the system bounded, evidence-driven, and safe.
7. Generate an RCA report with citations/evidence.
8. Store RCA reports for future retrieval.
9. Be implemented with class-based, SOLID, modular architecture.
10. Use async where appropriate.

---

## 3. Important Pivot from Original Blueprint

The earlier plan used a mostly fixed workflow:

```text
intake -> logs -> context planning -> code -> kb -> hypothesis -> RCA -> evaluator -> solution -> report
```

That is too deterministic for the main learning goal.

The updated architecture should be:

```text
Supervisor-led dynamic workflow with bounded planning, guarded subagent routing, and controlled replan loops.
```

This means:

- The model should decide which specialist agent to call based on incident details.
- The system should not blindly run all agents every time.
- The supervisor should make structured routing decisions.
- Guardrails should validate every routing decision.
- The workflow should be dynamic but bounded.
- Deterministic rules should still protect quality and safety.

---

## 4. MVP Scope

The MVP should demonstrate **real agentic orchestration**, not just a fixed pipeline.

### MVP Will Do

The MVP should:

1. Accept an incident through CLI.
2. Convert the incident into structured state.
3. Run a `SupervisorAgent` that decides the next investigation step.
4. Dynamically route to specialist agents.
5. Support at least these specialist agents:
   - `LogInvestigatorAgent`
   - `CodeInvestigatorAgent`
   - `KnowledgeBaseInvestigatorAgent`
   - `EvidenceEvaluatorAgent`
   - `RCAWriterAgent`
   - `SolutionRecommendationAgent`
   - `ReportWriterAgent`
6. Use bounded re-planning.
7. Use guardrails to prevent bad routing.
8. Use evidence-first reasoning.
9. Retrieve code context using FAISS and OpenAI embeddings.
10. Retrieve knowledge base context from README/docs.
11. Analyze logs using structured parsing and LLM-assisted reasoning.
12. Generate hypotheses only from available evidence.
13. Generate RCA only after minimum evidence conditions are satisfied.
14. Store report as Markdown and JSON.
15. Include pytest tests from day one.

### MVP Will Not Do Yet

The MVP will not initially:

- auto-edit code
- open pull requests
- connect to real Jira
- connect to real Datadog / Loki / ELK / CloudWatch
- use real MCP servers for every integration
- provide a web UI
- use a production database
- run fully autonomous unbounded loops
- perform full graph/AST reasoning from day one

---

## 5. Locked Decisions

| Area | Decision |
|---|---|
| MVP behavior | Analyze-only RCA system |
| Main architecture | Supervisor-led dynamic multi-agent orchestration |
| Interface | CLI first |
| Future API | FastAPI later |
| Future UI | UI later on top of FastAPI |
| First target repo | `conversational_rag` |
| LLM provider | OpenAI through wrapper interface |
| Embeddings | OpenAI embeddings |
| Vector store | FAISS |
| CLI framework | Typer |
| Orchestration | LangGraph |
| Workflow style | Dynamic routing with bounded loops |
| MCP strategy | Local MCP-like abstractions first, real MCP later |
| Tests | pytest from day one |
| Report format | Markdown + JSON |
| Logs | Structured parsing first, no Log RAG in MVP |
| Architecture style | Class-based, SOLID, modular, extensible |
| Async | Use async wherever appropriate |

---

## 6. Core Agentic Architecture

### Updated High-Level Flow

```text
CLI / Future Jira Ticket
        |
        v
Incident Intake
        |
        v
Supervisor Agent
        |
        | decides next specialist agent
        |
        +--> Log Investigator Agent
        +--> Code Investigator Agent
        +--> Knowledge Base Investigator Agent
        +--> Web Search Agent                [future]
        +--> Graph / AST Investigator Agent   [future]
        +--> Historical RCA Agent             [future]
        |
        v
Evidence Evaluator / Guardrails
        |
        +--> enough evidence? continue to RCA
        +--> missing evidence? return to Supervisor for re-plan
        +--> max steps reached? generate low-confidence RCA
        |
        v
RCA Writer Agent
        |
        v
Solution Recommendation Agent
        |
        v
Report Writer Agent
        |
        v
Markdown + JSON Report
```

### Key Principle

The supervisor decides **what to do next**, but deterministic guardrails decide **whether that decision is allowed**.

---

## 7. Supervisor Agent

The `SupervisorAgent` is the central planning and routing agent.

### Responsibilities

The supervisor should:

1. Understand the current incident state.
2. Inspect available evidence.
3. Decide the next best specialist agent.
4. Explain why that agent is needed.
5. Generate search/query instructions for that agent.
6. Decide when enough evidence has been gathered.
7. Decide when to move to RCA writing.
8. Decide when to stop due to max step limit.
9. Avoid repeatedly calling the same agent without new reason.
10. Produce structured decisions.

### Supervisor Must Not

The supervisor must not:

- directly write final RCA
- directly save reports
- directly call low-level tools without going through agents/providers
- run unbounded loops
- invent evidence
- bypass guardrails

### Example Supervisor Decision

```json
{
  "next_agent": "code_investigator",
  "reason": "The logs mention a TypeError in the routing module, so source code around that module is needed.",
  "queries": [
    "TypeError routing llm structured output",
    "router response schema mismatch",
    "conversation rag route query"
  ],
  "expected_evidence": [
    "failing function",
    "caller function",
    "expected response schema"
  ],
  "should_continue": true
}
```

---

## 8. Specialist Agents

### 8.1 Log Investigator Agent

Purpose: analyze runtime logs and extract evidence.

Responsibilities:

- parse console logs / production-like logs
- extract exception type
- extract stack trace
- extract file paths and line numbers
- extract request id / trace id if present
- summarize runtime failure
- produce evidence items

### 8.2 Code Investigator Agent

Purpose: retrieve and analyze relevant code context.

Responsibilities:

- search code using FAISS Code RAG
- prefer files mentioned in logs
- retrieve caller/callee context where possible
- return file path, line range, function/class metadata
- produce evidence items
- later use AST/graph provider when available

### 8.3 Knowledge Base Investigator Agent

Purpose: retrieve design and expected-behavior context.

Responsibilities:

- search README/docs
- retrieve design expectations
- retrieve workflow assumptions
- retrieve known limitations
- later retrieve ADRs/runbooks/past RCAs
- produce evidence items

### 8.4 Evidence Evaluator Agent

Purpose: judge whether the investigation has enough evidence.

Responsibilities:

- evaluate current evidence quality
- identify missing evidence
- decide whether supervisor should re-plan
- validate whether RCA can be written
- assign confidence score
- prevent unsupported RCA

### 8.5 RCA Writer Agent

Purpose: write final root-cause analysis.

Responsibilities:

- use evidence-backed hypotheses
- distinguish symptom vs root cause
- cite evidence
- include confidence
- include open questions if needed
- avoid unsupported claims

### 8.6 Solution Recommendation Agent

Purpose: suggest solution approach.

Responsibilities:

- suggest immediate fix
- suggest long-term prevention
- suggest tests
- suggest logging/monitoring improvements
- avoid generating actual patch in MVP

### 8.7 Report Writer Agent

Purpose: persist investigation output.

Responsibilities:

- save Markdown report
- save JSON report
- save evidence index
- save investigation trace
- save low-confidence warnings if applicable

---

## 9. Future Specialist Agents

Later versions should add:

### Web Search Agent

For external documentation and library-specific issues.

Examples:

- LangChain errors
- OpenAI SDK changes
- dependency behavior
- framework-specific exceptions

### Graph / AST Investigator Agent

For deeper code intelligence.

Responsibilities:

- parse AST
- find classes/functions
- build call graph
- trace caller/callee paths
- identify schema mismatch
- identify dependency edges

### Historical RCA Agent

For incident memory.

Responsibilities:

- search past RCA reports
- find similar incidents
- reuse previous learnings
- identify repeated failures

### Patch Suggestion Agent

For future patch recommendations.

Responsibilities:

- suggest code changes
- generate diff
- suggest tests
- require human approval

---

## 10. Dynamic LangGraph Workflow

The workflow should use LangGraph as a bounded dynamic state machine.

### Conceptual Flow

```text
START
  -> intake
  -> supervisor_decide
  -> guardrail_check
  -> selected_specialist_agent
  -> evidence_evaluator
  -> supervisor_decide
  -> ...
  -> rca_writer
  -> solution_recommender
  -> report_writer
  -> END
```

### Dynamic Routing

The supervisor should return a structured `AgentDecision`.

The graph should route based on:

```text
decision.next_agent
```

Allowed values:

```text
log_investigator
code_investigator
knowledge_base_investigator
web_search_investigator
graph_investigator
historical_rca_investigator
evidence_evaluator
rca_writer
solution_recommender
report_writer
finish
```

### Bounded Autonomy

The system must have:

```text
max_steps
max_replans
max_agent_invocations_per_agent
confidence_threshold
minimum_evidence_count_before_rca
allowed_agent_names
```

---

## 11. Guardrails

Guardrails are mandatory.

They should protect the project from becoming an uncontrolled agent loop.

### Guardrail Responsibilities

Guardrails should:

1. Validate supervisor decisions.
2. Reject unknown agents.
3. Prevent repeated calls to the same agent without new reason.
4. Prevent RCA generation without minimum evidence.
5. Stop execution when max steps are reached.
6. Stop execution when max replans are reached.
7. Ensure tool inputs are valid.
8. Ensure all final claims are backed by evidence.
9. Mark output as low-confidence when evidence is weak.
10. Prevent hallucinated source references.

### Example Guardrail Decision

```json
{
  "allowed": false,
  "reason": "RCA writer cannot run because minimum evidence count has not been met.",
  "fallback_next_agent": "supervisor"
}
```

---

## 12. Rules System

Rules should be first-class project components, not scattered through prompts.

Suggested package:

```text
src/bug_resolver/rules/
  base.py
  orchestration_rules.py
  evidence_rules.py
  routing_rules.py
  retry_rules.py
  rca_rules.py
  tool_rules.py
  rule_engine.py
```

### Rule Categories

1. Routing rules
2. Evidence rules
3. RCA rules
4. Retry/replan rules
5. Tool usage rules
6. Guardrail rules
7. Output quality rules
8. Future patch rules

---

## 13. Routing Rules

The supervisor must follow these rules:

1. Choose only from registered agents.
2. Prefer log investigation when no runtime evidence exists.
3. Prefer code investigation when logs mention files, functions, or stack traces.
4. Prefer knowledge base investigation when expected behavior is unclear.
5. Prefer web search only when local evidence is insufficient or external library behavior is relevant.
6. Prefer graph investigation when caller/callee or dependency relationships are needed.
7. Prefer historical RCA investigation when similar incidents may exist.
8. Do not call the same agent repeatedly with the same query.
9. Move to RCA only when evidence threshold is satisfied or max steps are reached.
10. Always explain routing decisions.

---

## 14. Evidence Rules

Evidence is the core of the system.

Every important claim must be backed by evidence.

### Evidence Sources

Evidence can come from:

```text
logs
code
knowledge_base
web
graph
historical_rca
tool_result
```

### Evidence Rules

1. Logs are primary evidence for runtime behavior.
2. Code is primary evidence for implementation behavior.
3. Knowledge base is supporting evidence for intended behavior.
4. Web search is supporting evidence for third-party/library behavior.
5. Historical RCA is supporting evidence for recurrence.
6. If evidence conflicts, mention the conflict.
7. If evidence is missing, mention the gap.
8. Never hallucinate file paths, line numbers, or function names.
9. Confidence score must reflect evidence quality.
10. RCA without evidence is invalid.

---

## 15. MCP Strategy

The MVP should use local MCP-like abstractions.

Agents should not care whether data comes from local files, real MCP servers, APIs, or databases.

### Provider Interfaces

Initial interfaces:

```python
class LogProvider(Protocol):
    async def get_logs(self, incident_id: str) -> list[LogEntry]:
        ...

class CodeContextProvider(Protocol):
    async def search_code(self, request: CodeSearchRequest) -> list[CodeContext]:
        ...

class KnowledgeBaseProvider(Protocol):
    async def search_docs(self, request: KnowledgeSearchRequest) -> list[KnowledgeContext]:
        ...

class IncidentProvider(Protocol):
    async def get_incident(self, incident_id: str) -> Incident:
        ...

class ReportStore(Protocol):
    async def save_report(self, report: RCAReport) -> ReportSaveResult:
        ...
```

### MVP Implementations

```text
FileLogProvider
FAISSCodeContextProvider
LocalKnowledgeBaseProvider
CLIIncidentProvider
FileReportStore
OpenAILLMClient
OpenAIEmbeddingClient
```

### Future MCP Implementations

```text
MCPLogProvider
MCPCodeSearchProvider
MCPKnowledgeBaseProvider
MCPJiraIncidentProvider
MCPReportStore
MCPWebSearchProvider
MCPGraphContextProvider
```

---

## 16. Async Strategy

Use async where it makes sense.

### Async Should Be Used For

- LLM calls
- embedding calls
- MCP calls
- external API calls
- file/report IO when appropriate
- concurrent retrieval from multiple providers
- future web search
- future Jira/GitHub/Datadog integrations

### Async Does Not Need To Be Forced For

- simple Pydantic validation
- pure rule checks
- pure formatting
- simple utility functions
- deterministic in-memory transformations

### Rule

Do not use async just for appearance. Use it where it improves integration, concurrency, or future extensibility.

---

## 17. Core Schemas Needed for Dynamic Orchestration

Milestone 2 should include both domain schemas and orchestration schemas.

### Domain Schemas

```text
Incident
LogEntry
LogAnalysisResult
EvidenceItem
CodeContext
KnowledgeContext
Hypothesis
RCAReport
SolutionRecommendation
ReportSaveResult
```

### Dynamic Orchestration Schemas

```text
AgentName
AgentDecision
InvestigationPlan
InvestigationStep
AgentExecutionRecord
GuardrailDecision
EvidenceEvaluationResult
ToolCallRequest
ToolCallResult
WorkflowState
```

### Why These Matter

These schemas make the project clearly agentic.

They allow the system to record:

- which agent was chosen
- why it was chosen
- what input it received
- what evidence it produced
- whether guardrails allowed the decision
- how the investigation evolved

This is important for learning, debugging, testing, and portfolio storytelling.

---

## 18. Suggested Project Structure

```text
src/
  bug_resolver/
    agents/
      base.py
      supervisor_agent.py
      log_investigator_agent.py
      code_investigator_agent.py
      knowledge_base_investigator_agent.py
      evidence_evaluator_agent.py
      rca_writer_agent.py
      solution_recommendation_agent.py
      report_writer_agent.py

    workflows/
      dynamic_bug_resolution_graph.py
      graph_factory.py

    schemas/
      incident.py
      logs.py
      evidence.py
      code_context.py
      knowledge_context.py
      hypothesis.py
      rca.py
      solution.py
      report.py
      agent.py
      guardrails.py
      workflow_state.py

    rules/
      routing_rules.py
      evidence_rules.py
      guardrail_rules.py
      retry_rules.py
      rca_rules.py
      rule_engine.py

    providers/
      logs/
      code/
      knowledge/
      incident/
      reports/

    llm/
    embeddings/
    retrieval/
    cli/
    config/
    utils/
```

---

## 19. SOLID and Engineering Principles

The project must continue to follow SOLID principles.

### Single Responsibility

Each class should have one reason to change.

Examples:

- `SupervisorAgent` decides next step.
- `CodeInvestigatorAgent` investigates code.
- `GuardrailEngine` validates decisions.
- `FileReportStore` persists reports.

### Open/Closed

Add new agents/providers without modifying existing workflow internals.

Examples:

- Add `WebSearchAgent`.
- Add `GraphInvestigatorAgent`.
- Add `JiraIncidentProvider`.
- Add `MCPLogProvider`.

### Interface Segregation

Keep interfaces focused.

Avoid one giant provider or one giant agent.

### Dependency Inversion

Agents and workflows should depend on abstractions, not concrete providers.

---

## 20. Deterministic vs Agentic Boundary

This project should intentionally combine deterministic engineering with agentic reasoning.

### Agentic / LLM-Driven

- choose next specialist agent
- generate search queries
- interpret logs
- summarize evidence
- generate hypotheses
- write RCA
- suggest solution

### Deterministic / Rule-Driven

- validate schemas
- validate allowed agents
- enforce max steps
- enforce evidence threshold
- save reports
- reject unsupported RCA
- parse known log patterns
- enforce tool input contracts
- run tests

This boundary is critical.

The goal is not randomness. The goal is controlled autonomy.

---

## 21. Testing Strategy

Tests should verify both deterministic and agentic behavior.

### Unit Tests

- schema validation
- agent decision validation
- guardrail decisions
- routing rule behavior
- evidence rule behavior
- report store
- log parser
- provider interfaces

### Integration Tests

- CLI starts investigation
- supervisor routes to expected agent for sample incident
- log investigator produces evidence
- code investigator retrieves code context
- knowledge base investigator retrieves docs
- workflow stops at max steps
- workflow does not write RCA without evidence

### Golden Tests

Golden tests should validate full investigation behavior for known sample incidents.

They should not require exact wording, but should verify:

- expected agents were called
- required evidence types exist
- RCA contains supported root cause
- report was saved
- confidence is present

---

## 22. MVP Success Criteria

The MVP is successful when:

1. CLI can start an investigation.
2. Supervisor dynamically selects at least one specialist agent.
3. Guardrails validate routing decisions.
4. Logs can be analyzed as evidence.
5. Code context can be retrieved using FAISS.
6. Knowledge base context can be retrieved.
7. Evidence evaluator can decide whether to continue or replan.
8. RCA is written only with evidence.
9. Solution recommendation is generated.
10. Markdown and JSON reports are saved.
11. Investigation trace shows agent decisions.
12. Tests pass.
13. README explains the dynamic multi-agent architecture clearly.

---

## 23. Updated Implementation Milestones

### Milestone 1 — Project Foundation

Already completed.

Includes:

- uv setup
- Python 3.11
- package structure
- Typer CLI shell
- pytest setup
- `.env.example`
- `.gitignore`
- initial push

### Milestone 2 — Core Schemas for Dynamic Agentic Workflow

Create:

- domain schemas
- evidence schemas
- agent decision schemas
- guardrail schemas
- workflow state schema

### Milestone 3 — Provider Interfaces and MCP-like Abstractions

Create async protocols for:

- logs
- code context
- knowledge base
- incident source
- report store
- LLM
- embeddings

### Milestone 4 — Rules and Guardrail Engine

Create:

- routing rules
- evidence rules
- guardrail engine
- retry/replan policy

### Milestone 5 — Basic Specialist Agents

Create:

- supervisor agent
- log investigator
- code investigator
- knowledge base investigator
- evidence evaluator

### Milestone 6 — Dynamic LangGraph Workflow

Create:

- graph state
- dynamic routing
- bounded loop
- guardrail checks
- trace recording

### Milestone 7 — Report and RCA Agents

Create:

- RCA writer
- solution recommender
- report writer
- markdown/json persistence

### Milestone 8 — End-to-End CLI Investigation

Wire:

```bash
bug-resolver investigate --incident-id INC-001
```

### Milestone 9 — Add Web Search / MCP / Graph Extensions

Add future extensions after MVP works.

---

## 24. Portfolio Story

This project should be presented as:

> A supervisor-led multi-agent production bug resolver that dynamically routes incidents to specialist agents for log investigation, code retrieval, knowledge-base lookup, evidence evaluation, RCA writing, and solution recommendation. It uses LangGraph for bounded dynamic orchestration, MCP-style provider abstractions for tools, Pydantic for structured decisions, FAISS for Code RAG, OpenAI for reasoning and embeddings, and guardrails to ensure evidence-backed RCA generation.

This portfolio story is stronger than a fixed pipeline.

---

## 25. Guiding Principle

The project should optimize for:

```text
Controlled autonomy for evidence-backed production debugging.
```

Meaning:

```text
LLMs decide the investigation path.
Rules and guardrails keep the system safe.
Evidence determines the RCA.
Architecture keeps the system extensible.
```

---

## 26. Final Updated Direction

The current final direction is:

```text
Build a CLI-first, analyze-only, supervisor-led dynamic multi-agent RCA system for bugs in the conversational_rag repo.

Use OpenAI, OpenAI embeddings, FAISS, Typer, pytest, async-capable provider interfaces, MCP-style abstractions, LangGraph dynamic routing, bounded replanning, guardrails, class-based SOLID architecture, and evidence-first RCA generation.
```

This document should replace the earlier fixed-workflow blueprint.
