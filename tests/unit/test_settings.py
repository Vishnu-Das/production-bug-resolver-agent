from pathlib import Path

from typer.testing import CliRunner

import bug_resolver.cli.app as cli_app
from bug_resolver.cli.app import app
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

    async def fake_run_investigation(incident_id: str) -> WorkflowState:
        assert incident_id == "INC-001"
        return state

    monkeypatch.setattr(cli_app, "_run_investigation", fake_run_investigation)

    result = runner.invoke(app, ["investigate", "--incident-id", "INC-001"])

    assert result.exit_code == 0
    assert "INC-001" in result.output
    assert "Starting dynamic investigation" in result.output
    assert "Status: completed" in result.output
    assert "evidence_count=4" in result.output
    assert "llm.py:1-80" in result.output
    assert "+1 more" in result.output
    assert "Report: reports" in result.output


def test_investigate_command_returns_nonzero_on_failure(monkeypatch) -> None:
    async def fake_run_investigation(incident_id: str) -> WorkflowState:
        raise ValueError("boom")

    monkeypatch.setattr(cli_app, "_run_investigation", fake_run_investigation)

    result = runner.invoke(app, ["investigate", "--incident-id", "INC-001"])

    assert result.exit_code == 1
    assert "Investigation failed" in result.output
    assert "boom" in result.output
