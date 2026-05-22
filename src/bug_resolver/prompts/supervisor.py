"""Prompt helper for supervisor routing decisions."""

from __future__ import annotations

from bug_resolver.schemas.workflow_state import WorkflowState


class SupervisorPromptBuilder:
    """
    Standalone supervisor system prompt template for prompt experiments.

    The production SupervisorAgent uses this helper for its runtime system prompt
    so routing guidance stays outside the agent implementation.
    """

    def build_system_prompt(self) -> str:
        return (
            "You are the supervisor for a production bug investigation.\n\n"
            "## Goal\n\n"
            "Choose exactly one next specialist agent for the current investigation step.\n\n"
            "You decide routing only. You must not:\n"
            "- fetch logs, code, docs, or graph evidence yourself\n"
            "- write the final RCA\n"
            "- recommend the final solution\n"
            "- save reports\n"
            "- bypass guardrails\n"
            "- invent evidence, file paths, functions, or source references\n\n"
            "## Agent choices\n\n"
            "- `log_investigator`: Use when runtime behavior, logs, errors, warnings, "
            "request traces, or stack traces are needed.\n"
            "- `code_investigator`: Use when implementation code, file/function behavior, "
            "exception location, or source-level evidence is needed.\n"
            "- `graph_investigator`: Use for structural code questions such as callers, "
            "callees, imports, config reads, ownership, or class/function relationships. "
            "Prefer this after code evidence already exists. Use it before code evidence "
            "only when there is a strong structural signal such as a Python file path, "
            "config key, function name, class name, or `Class.method` reference.\n"
            "- `knowledge_base_investigator`: Use when design intent, expected behavior, "
            "README/docs, workflow rules, architecture context, or product behavior "
            "expectations are needed.\n"
            "- `evidence_evaluator`: Use when evidence sufficiency is unclear, especially "
            "after a specialist has produced evidence.\n"
            "- `rca_writer`: Use only when evidence appears sufficient for a supported RCA.\n"
            "- `solution_recommender`: Use only after an RCA exists.\n"
            "- `report_writer`: Use only after both RCA and solution recommendation exist.\n"
            "- `finish`: Use only when a report is saved, or when the investigation must "
            "stop because it is bounded/low-confidence.\n\n"
            "## Routing rules\n\n"
            "- If no evidence has been collected yet, choose `log_investigator` first "
            "unless the incident already contains an exact code location.\n"
            "- Prefer `code_investigator` before `graph_investigator` for broad "
            "implementation questions.\n"
            "- Prefer `graph_investigator` only when structural relationships are needed.\n"
            "- Prefer `knowledge_base_investigator` when expected behavior or design "
            "intent is unclear.\n"
            "- Do not choose `evidence_evaluator`, `rca_writer`, `solution_recommender`, "
            "`report_writer`, or `finish` before evidence has been collected.\n"
            "- Do not repeatedly call the same agent with the same reason and queries.\n"
            "- Move to RCA only when the collected evidence appears sufficient.\n"
            "- Always choose exactly one next agent.\n"
            "- Always return structured output matching the expected schema.\n\n"
            "## Output requirements\n\n"
            "Your response must provide:\n"
            "- the next agent\n"
            "- a concise reason\n"
            "- focused queries or instructions for that agent\n"
            "- expected evidence the agent should return\n"
            "- whether the workflow should continue\n"
        )

    def build_user_prompt(self, state: WorkflowState) -> str:
        """Build the runtime supervisor prompt from the current workflow state."""
        incident = state.incident
        evidence_summary = self._format_evidence_summary(state)
        previous_decisions = self._format_previous_decisions(state)
        evaluation_summary = self._format_evaluation_summary(state)
        allowed_agents = ", ".join(agent.value for agent in state.allowed_agent_names)

        return (
            "Decide the next investigation step.\n\n"
            f"Incident ID: {incident.incident_id}\n"
            f"Title: {incident.title}\n"
            f"Description: {incident.description}\n"
            f"Severity: {incident.severity.value}\n"
            f"Affected service: {incident.affected_service or 'unknown'}\n\n"
            f"Investigation status: {state.investigation_status.value}\n"
            f"Evidence count: {len(state.evidence_items)}\n"
            f"Minimum evidence before RCA: {state.minimum_evidence_count_before_rca}\n"
            f"Replans: {state.replan_count}/{state.max_replans}\n"
            f"Steps: {len(state.trace.steps)}/{state.max_steps}\n"
            f"Allowed agents: {allowed_agents}\n\n"
            f"Evidence summary:\n{evidence_summary}\n\n"
            f"Evidence evaluation:\n{evaluation_summary}\n\n"
            f"Previous supervisor decisions:\n{previous_decisions}\n\n"
            "Return the best next agent, a concise reason, useful queries or "
            "instructions for that agent, expected evidence, and whether the "
            "workflow should continue."
        )

    def _format_evidence_summary(self, state: WorkflowState) -> str:
        if not state.evidence_items:
            return "- No evidence has been collected yet."

        lines: list[str] = []
        for evidence in state.evidence_items:
            location = evidence.source_name
            if evidence.file_path:
                location = evidence.file_path
            if evidence.line_start and evidence.line_end:
                location = f"{location}:{evidence.line_start}-{evidence.line_end}"

            lines.append(
                f"- {evidence.evidence_id} [{evidence.source_type.value}] "
                f"{location}: {evidence.content}"
            )

        return "\n".join(lines)

    def _format_previous_decisions(self, state: WorkflowState) -> str:
        if not state.trace.decisions:
            return "- No previous supervisor decisions."

        return "\n".join(
            (f"- {decision.decision_id}: {decision.next_agent.value} because {decision.reason}")
            for decision in state.trace.decisions
        )

    def _format_evaluation_summary(self, state: WorkflowState) -> str:
        if state.evidence_evaluation is None:
            return "- Evidence has not been evaluated yet."

        evaluation = state.evidence_evaluation
        missing_evidence = ", ".join(evaluation.missing_evidence) or "none"
        return (
            f"- confidence={evaluation.confidence_score}; "
            f"retry_required={evaluation.retry_required}; "
            f"missing_evidence={missing_evidence}; reason={evaluation.reason}"
        )
