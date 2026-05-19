Milestone 1 — Project Foundation
Done.

Milestone 2 — Core Schemas for Dynamic Agentic Workflow
- Domain schemas
- Evidence schemas
- Agent decision schemas
- Guardrail schemas
- Workflow state schema

Milestone 3 — Async Provider Interfaces and MCP-like Abstractions
- LogProvider
- CodeContextProvider
- KnowledgeBaseProvider
- IncidentProvider
- ReportStore
- LLMClient
- EmbeddingClient

Milestone 4 — Rules and Guardrail Engine
- Routing rules
- Evidence rules
- Guardrail checks
- Replan / retry policy

Milestone 5 — Basic Specialist Agents
- SupervisorAgent
- LogInvestigatorAgent
- CodeInvestigatorAgent
- KnowledgeBaseInvestigatorAgent
- EvidenceEvaluatorAgent

Milestone 6 — Dynamic LangGraph Workflow
- Supervisor routing
- Guardrail node
- Specialist agent routing
- Bounded loops
- Investigation trace

Milestone 7 — RCA, Solution, and Report Agents
- RCAWriterAgent
- SolutionRecommendationAgent
- ReportWriterAgent
- Markdown + JSON reports

Milestone 8 — End-to-End CLI Investigation
- bug-resolver investigate --incident-id INC-001

Milestone 9 — Extensions
- Web Search Agent
- Real MCP adapters
- Graph / AST Agent
- Historical RCA Agent
- Patch Suggestion Agent