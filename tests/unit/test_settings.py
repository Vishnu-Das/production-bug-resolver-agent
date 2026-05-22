"""Tests for CLI commands and settings-driven workflow execution."""

from pathlib import Path

from typer.testing import CliRunner

import bug_resolver.cli.app as cli_app
from bug_resolver.cli.app import WorkflowChoice, app
from bug_resolver.schemas import (
    AgentName,
    AgentRunStatus,
    Incident,
    InvestigationStatus,
    InvestigationStep,
    WorkflowState,
)

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "Production Bug Resolver Agent" in result.output


def test_investigate_command_runs_dynamic_workflow(monkeypatch) -> None:
    state = WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Bug",
            description="Something failed",
        ),
        investigation_status=InvestigationStatus.COMPLETED,
        final_report_path=Path("reports/incidents/INC-001/rca.md"),
    )
    state.add_investigation_step(
        InvestigationStep(
            step_number=1,
            agent_name=AgentName.CODE_INVESTIGATOR,
            run_status=AgentRunStatus.SUCCEEDED,
            evidence_ids=[
                "evidence-src/rag/routing/llm.py:1-80",
                "evidence-tests/rag/routing/test_llm_router.py:71-138",
                "evidence-tests/rag/routing/test_rule_based_router.py:1-80",
                "evidence-src/rag/routing/factory.py:1-37",
            ],
        )
    )

    async def fake_run_investigation(
        incident_id: str,
        workflow: WorkflowChoice = WorkflowChoice.MANUAL,
    ) -> WorkflowState:
        assert incident_id == "INC-001"
        assert workflow == WorkflowChoice.MANUAL
        return state

    monkeypatch.setattr(cli_app, "_run_investigation", fake_run_investigation)

    result = runner.invoke(app, ["investigate", "--incident-id", "INC-001"])

    assert result.exit_code == 0
    assert "INC-001" in result.output
    assert "Starting dynamic investigation" in result.output
    assert "Production Bug Resolver" in result.output
    assert "Status:" in result.output
    assert "completed" in result.output
    assert "Output" in result.output
    assert "Investigation Trace" in result.output
    assert "code_investigator" in result.output
    assert "SUCCESS" in result.output
    assert "llm.py:1-80" in result.output
    assert "Report written" in result.output
    assert "reports" in result.output
    assert "rca.md" in result.output

def test_investigate_command_returns_nonzero_on_failure(monkeypatch) -> None:
    async def fake_run_investigation(
        incident_id: str,
        workflow: WorkflowChoice = WorkflowChoice.MANUAL,
    ) -> WorkflowState:
        assert workflow == WorkflowChoice.MANUAL
        raise ValueError("boom")

    monkeypatch.setattr(cli_app, "_run_investigation", fake_run_investigation)

    result = runner.invoke(app, ["investigate", "--incident-id", "INC-001"])

    assert result.exit_code == 1
    assert "Investigation failed" in result.output
    assert "boom" in result.output


def test_investigate_command_can_select_graph_workflow(monkeypatch) -> None:
    state = WorkflowState(
        incident=Incident(
            incident_id="INC-001",
            title="Bug",
            description="Something failed",
        ),
        investigation_status=InvestigationStatus.COMPLETED,
    )

    async def fake_run_investigation(
        incident_id: str,
        workflow: WorkflowChoice = WorkflowChoice.MANUAL,
    ) -> WorkflowState:
        assert incident_id == "INC-001"
        assert workflow == WorkflowChoice.GRAPH
        return state

    monkeypatch.setattr(cli_app, "_run_investigation", fake_run_investigation)

    result = runner.invoke(
        app,
        ["investigate", "--incident-id", "INC-001", "--workflow", "graph"],
    )

    assert result.exit_code == 0
    assert "Starting dynamic investigation" in result.output
    assert "Status: completed" in result.output
