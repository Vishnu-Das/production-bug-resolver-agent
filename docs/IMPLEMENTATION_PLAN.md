# Implementation Plan

This plan follows the updated project direction: build a CLI-first, analyze-only,
supervisor-led dynamic multi-agent RCA system.

The project is no longer a fixed RCA pipeline. The workflow must allow a
`SupervisorAgent` to decide which specialist agent should run next, while
deterministic guardrails validate every routing decision and keep the
investigation bounded, evidence-driven, and safe.

## Milestone 1 - Project Foundation

Status: done.

Completed foundation:

- Python 3.11 project structure.
- `uv` dependency management.
- Typer CLI shell.
- `pytest` test setup.
- Source package under `src/bug_resolver`.
- Initial provider, schema, agent, workflow, retrieval, config, and test layout.
- `.env.example`, `.gitignore`, README, and initial project metadata.

Acceptance criteria:

- The package can be imported from tests.
- The CLI entry point exists.
- The repository has a clear modular package layout.

## Milestone 2 - Core Schemas for Dynamic Agentic Workflow

Goal: define the structured data contracts that make dynamic orchestration
testable, inspectable, and safe.

Create or refine domain schemas:

- `Incident`
- `LogEntry`
- `LogAnalysisResult`
- `EvidenceItem`
- `CodeContext`
- `KnowledgeContext`
- `Hypothesis`
- `RCAReport`
- `SolutionRecommendation`
- `ReportSaveResult`

Create or refine orchestration schemas:

- `AgentName`
- `AgentDecision`
- `InvestigationStep`
- `InvestigationTrace`
- `InvestigationStatus`
- `AgentExecutionRecord`
- `AgentRunStatus`
- `GuardrailDecision`
- `EvidenceEvaluationResult`
- `WorkflowState`
- `ToolCallRequest`
- `ToolCallResult`

Schema requirements:

- `AgentDecision` must include the selected next agent, reason, queries or
  instructions, expected evidence, and continue/stop intent.
- `WorkflowState` must track incident details, evidence, decisions, agent
  invocation counts, replan counts, final RCA, solution recommendation, report
  save result, and low-confidence flags.
- Evidence must always include source type, summary, citation or locator fields,
  confidence, and enough metadata to support final RCA claims.
- Guardrail results must include whether the decision is allowed, the reason,
  and an optional fallback route.

Acceptance criteria:

- Unit tests cover schema validation.
- Invalid agent names are rejected.
- Evidence and workflow state can represent a multi-step dynamic investigation.

## Milestone 3 - Async Provider Interfaces and MCP-like Abstractions

Goal: define async provider contracts for local tools and future external
systems, without implementing real MCP servers yet.

Create or refine async protocols for:

- `IncidentProvider`
- `LogProvider`
- `CodeContextProvider`
- `KnowledgeBaseProvider`
- `ReportStore`
- `LLMClient`
- `EmbeddingClient`

MVP provider implementations:

- `FileIncidentProvider` or CLI-backed incident intake.
- `FileLogProvider`.
- `FAISSCodeContextProvider`.
- `LocalKnowledgeBaseProvider`.
- `FileReportStore`.
- `OpenAILLMClient`.
- `OpenAIEmbeddingClient`.

Important scope boundary:

- These are MCP-style local abstractions for the MVP.
- Real MCP adapters are a later extension and should not block the MVP.
- Agents must depend on provider interfaces, not concrete file/API classes.

Acceptance criteria:

- Provider protocols are narrow and async where useful.
- Unit tests verify provider interfaces and local provider behavior.
- No agent needs to know whether data came from files, APIs, or future MCP
  servers.

## Milestone 4 - Rules and Guardrail Engine

Goal: create deterministic controls around the supervisor-led workflow.

Implement rule categories:

- Routing rules.
- Evidence sufficiency rules.
- RCA eligibility rules.
- Retry and replan rules.
- Tool input validation rules.
- Output quality rules.

Implement guardrail behavior:

- Reject unknown or unregistered agents.
- Prevent repeated calls to the same agent with the same query and no new reason.
- Enforce `max_steps`.
- Enforce `max_replans`.
- Enforce `max_agent_invocations_per_agent`.
- Prevent RCA writing before minimum evidence requirements are met, unless max
  steps force a low-confidence report.
- Mark investigations as low confidence when evidence is weak.
- Prevent hallucinated file paths, line numbers, and unsupported source
  references.

Acceptance criteria:

- Unit tests cover allowed and rejected routing decisions.
- RCA generation is blocked when evidence thresholds are not met.
- Max-step and max-replan limits stop the workflow predictably.
- Guardrail decisions are recorded in the investigation trace.
- Guardrail engine behavior is deterministic and makes no LLM calls.

## Milestone 5 - Supervisor Agent

Goal: implement the central routing agent for dynamic investigation.

The `SupervisorAgent` must:

- Inspect the current incident, evidence, prior decisions, and guardrail state.
- Choose the next specialist agent from the registered agent set.
- Explain why that agent is needed.
- Produce focused queries or instructions for that agent.
- State expected evidence.
- Decide when to ask for more evidence, move to RCA, or stop.
- Return a structured `AgentDecision`.

The `SupervisorAgent` must not:

- Write the final RCA directly.
- Save reports directly.
- Bypass specialist agents/providers.
- Bypass guardrails.
- Run unbounded loops.
- Invent evidence.

Acceptance criteria:

- Unit tests use fake LLM clients to verify structured supervisor decisions.
- The supervisor chooses log investigation when no runtime evidence exists.
- The supervisor chooses code investigation when logs mention files, functions,
  stack traces, or implementation behavior.
- The supervisor chooses knowledge-base investigation when expected behavior is
  unclear.
- The supervisor moves toward RCA only when guardrails allow it.

## Milestone 6 - Specialist Investigation Agents

Goal: implement MVP specialist agents that produce evidence, not final answers.

Implement `LogInvestigatorAgent`:

- Parse structured or production-like logs.
- Extract exception type, message, stack trace, file paths, line numbers,
  request IDs, trace IDs, and runtime symptoms.
- Produce log-sourced evidence items.

Implement `CodeInvestigatorAgent`:

- Retrieve relevant code context using FAISS and OpenAI embeddings.
- Prefer files, functions, and stack frames mentioned in log evidence.
- Return file paths, line ranges, symbols, snippets, and implementation
  summaries.
- Produce code-sourced evidence items.

Implement `KnowledgeBaseInvestigatorAgent`:

- Search README and docs for intended behavior, design constraints, known
  limitations, and workflow assumptions.
- Produce knowledge-base evidence items.

Implement `EvidenceEvaluatorAgent`:

- Score evidence quality.
- Identify missing evidence.
- Decide whether the supervisor should replan.
- Decide whether RCA writing is allowed from an evidence perspective.
- Assign confidence and low-confidence warnings.

Acceptance criteria:

- Each specialist has focused unit tests.
- Each specialist returns structured outputs.
- Each evidence item has a source and citation/locator.
- Specialist agents do not decide global workflow routing except through their
  returned evidence/evaluation results.

## Milestone 7 - Dynamic LangGraph Workflow

Goal: wire the supervisor, guardrails, specialists, and evaluator into a bounded
dynamic graph.

Conceptual graph:

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

Workflow requirements:

- Route based on `AgentDecision.next_agent`.
- Run guardrail validation before executing the selected next agent.
- Record every supervisor decision, guardrail decision, agent execution, and
  evidence addition.
- Support bounded replan loops.
- Stop cleanly at max steps.
- Generate low-confidence RCA only when limits force completion with incomplete
  evidence.
- Avoid blindly running every specialist for every incident.

Allowed MVP routes:

- `log_investigator`
- `code_investigator`
- `knowledge_base_investigator`
- `evidence_evaluator`
- `rca_writer`
- `solution_recommender`
- `report_writer`
- `finish`

Acceptance criteria:

- Integration tests prove dynamic routing runs at least one specialist selected
  by the supervisor.
- Tests prove the graph does not execute all specialists by default.
- Tests prove max-step and replan limits work.
- Tests prove the investigation trace records routing and guardrail decisions.

## Milestone 8 - RCA, Solution, and Report Agents

Goal: generate final outputs only after evidence and guardrails permit it.

Implement `RCAWriterAgent`:

- Write an evidence-backed root-cause analysis.
- Distinguish symptoms from root cause.
- Cite evidence for every important claim.
- Include confidence and open questions.
- Avoid unsupported claims.

Implement `SolutionRecommendationAgent`:

- Recommend an immediate fix.
- Recommend long-term prevention.
- Recommend tests.
- Recommend logging or monitoring improvements.
- Avoid generating actual code patches in the MVP.

Implement `ReportWriterAgent`:

- Save Markdown report.
- Save JSON report.
- Save evidence index.
- Save investigation trace.
- Include low-confidence warnings when applicable.

Acceptance criteria:

- Unit tests verify reports are saved as Markdown and JSON.
- Tests verify RCA generation fails or is blocked without evidence.
- Tests verify report output includes evidence, trace, confidence, RCA, and
  solution recommendation.

## Milestone 9 - End-to-End CLI Investigation

Goal: expose the MVP through a CLI-first workflow.

Target command:

```bash
bug-resolver investigate --incident-id INC-001
```

CLI behavior:

- Load incident details from the configured incident provider or CLI input.
- Run the dynamic supervisor-led workflow.
- Print concise investigation progress.
- Save Markdown and JSON reports.
- Return clear success, low-confidence, or failure status.

Acceptance criteria:

- End-to-end CLI test runs with fake providers and fake LLM responses.
- The CLI produces a saved report path.
- The CLI output explains which agents ran.
- The CLI does not require real external systems for MVP tests.

## Milestone 10 - Testing, Documentation, and Portfolio Polish

Goal: make the project understandable, reliable, and portfolio-ready.

Testing tasks:

- Add unit tests for schemas, rules, guardrails, agents, providers, and report
  persistence.
- Add integration tests for dynamic workflow behavior.
- Add golden tests for known sample incidents.
- Keep tests deterministic by using fake providers and fake LLM clients.

Documentation tasks:

- Update README with the supervisor-led architecture.
- Document the difference between agentic decisions and deterministic
  guardrails.
- Document provider abstractions and future MCP adapter strategy.
- Document the end-to-end CLI flow.
- Include an example investigation trace.

Acceptance criteria:

- Tests pass.
- README explains the dynamic multi-agent architecture.
- The portfolio story is clear: controlled autonomy for evidence-backed
  production debugging.

## Milestone 11 - Future Extensions After MVP

These are intentionally outside the first MVP.

Future specialist agents:

- `WebSearchAgent` for third-party documentation and library behavior.
- `GraphASTInvestigatorAgent` for call graphs, AST parsing, and dependency
  relationships.
- `HistoricalRCAAgent` for incident memory and recurrence detection.
- `PatchSuggestionAgent` for proposed diffs after human approval.

Future integrations:

- Real MCP adapters.
- Jira, GitHub Issues, Linear, or PagerDuty incident intake.
- Datadog, Loki, ELK, or CloudWatch log providers.
- FastAPI service layer.
- Web UI on top of the API.
- Patch suggestion, test generation, and PR creation workflows.

Acceptance criteria:

- Extensions can be added through new providers and agents without rewriting the
  core workflow.
- The analyze-only MVP remains stable while future capabilities are introduced.
