"""Typer CLI entrypoint for running analyze-only bug investigations."""

import asyncio
from enum import StrEnum
from typing import Any

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bug_resolver.config.settings import get_settings
from bug_resolver.workflows import build_dynamic_workflow
from bug_resolver.workflows.graph_factory import build_dynamic_graph_workflow
from bug_resolver.schemas import AgentName

app = typer.Typer(
    name="bug-resolver",
    help="CLI for the Production Bug Resolver Agent.",
    no_args_is_help=True,
)

console = Console()


class WorkflowChoice(StrEnum):
    """CLI-selectable workflow implementations."""

    MANUAL = "manual"
    GRAPH = "graph"


@app.callback()
def main() -> None:
    """Production Bug Resolver Agent CLI."""


@app.command()
def version() -> None:
    """Show application version and basic configuration."""
    settings = get_settings()
    console.print(f"[bold green]{settings.app_name}[/bold green]")
    console.print("Version: 0.1.0")


@app.command()
def investigate(
    incident_id: str = typer.Option(
        ...,
        "--incident-id",
        "-i",
        help="Incident id to investigate.",
    ),
    workflow: WorkflowChoice = typer.Option(
        WorkflowChoice.MANUAL,
        "--workflow",
        help="Workflow implementation to run.",
    ),
    include_patch_plan: bool = typer.Option(
        False,
        "--include-patch-plan",
        help="Save an analyze-only human-reviewable patch plan with the report.",
    ),
) -> None:
    """Run a dynamic supervisor-led bug investigation for an incident."""
    console.print("[bold cyan]Starting dynamic investigation[/bold cyan]\n")

    try:
        state = asyncio.run(
            _run_investigation(
                incident_id=incident_id,
                workflow=workflow,
                include_patch_plan=include_patch_plan,
            )
        )
    except Exception as exc:
        console.print(
            Panel(
                f"[bold red]Investigation failed[/bold red]\n\n{exc}",
                title="[bold red]Error[/bold red]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(code=1) from exc

    _print_investigation_summary(
        incident_id=incident_id,
        workflow=workflow.value,
        status=state.investigation_status.value,
        evidence_count=len(state.evidence_items),
        step_count=len(state.trace.steps),
    )

    _print_trace(state)

    if state.final_report_path is not None:
        _print_report_path(str(state.final_report_path))

    if state.errors:
        _print_errors(state.errors)
        raise typer.Exit(code=1)

    if state.low_confidence:
        _print_low_confidence_warning()


def _print_investigation_summary(
    *,
    incident_id: str,
    workflow: str,
    status: str,
    evidence_count: int,
    step_count: int,
) -> None:
    """Print a compact investigation summary panel."""
    status_style = _status_style(status)

    console.print(
        Panel(
            "\n".join(
                [
                    f"📌 [bold]Incident:[/bold] {incident_id}",
                    f"⚙️  [bold]Workflow:[/bold] {workflow}",
                    f"📊 [bold]Status:[/bold] [{status_style}]{status}[/{status_style}]",
                    f"🧾 [bold]Evidence:[/bold] {evidence_count} items",
                    f"🪜 [bold]Steps:[/bold] {step_count}",
                ]
            ),
            title="[bold cyan]Production Bug Resolver[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 2),
        )
    )


def _print_trace(state: Any) -> None:
    """Print investigation trace as a Rich table."""
    if not state.trace.steps:
        return

    guardrails_by_id = {
        guardrail.guardrail_id: guardrail for guardrail in state.trace.guardrail_decisions
    }

    table = Table(
        title="[bold italic]Investigation Trace[/bold italic]",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        box=box.ROUNDED,
        row_styles=["none", "none"],
        pad_edge=True,
    )

    table.add_column("Step", justify="right", style="bold white", width=5)
    table.add_column("Agent", min_width=24)
    table.add_column("Status", min_width=13)
    table.add_column("Output", style="white", overflow="fold")
    table.add_column("Notes", style="yellow", overflow="fold")

    for step in state.trace.steps:
        guardrail = (
            guardrails_by_id.get(step.guardrail_id) if step.guardrail_id is not None else None
        )

        notes: list[str] = []
        if guardrail is not None and not guardrail.allowed:
            rules = ", ".join(guardrail.violated_rules)
            fallback = (
                guardrail.fallback_next_agent.value
                if guardrail.fallback_next_agent is not None
                else "none"
            )
            notes.append(f"blocked={rules}")
            notes.append(f"fallback={fallback}")

        table.add_row(
            str(step.step_number),
            _agent_label(step.agent_name.value),
            _run_status_label(step.run_status.value),
            _step_output_summary(step),
            "\n".join(notes) if notes else Text("—", style="dim"),
        )

    console.print()
    console.print(table)


def _print_report_path(report_path: str) -> None:
    """Print the generated report location."""
    console.print()
    console.print(
        Panel(
            f"[bold green]✅ Report written successfully[/bold green]\n\n"
            f"[white]{report_path}[/white]",
            title="[bold green]Output[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _print_errors(errors: list[str]) -> None:
    """Print workflow errors as a Rich panel."""
    console.print()
    console.print(
        Panel(
            "\n".join(f"- {error}" for error in errors),
            title="[bold red]Errors[/bold red]",
            border_style="red",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _print_low_confidence_warning() -> None:
    """Print low-confidence completion warning."""
    console.print()
    console.print(
        Panel(
            "[yellow]Investigation completed with low confidence.[/yellow]",
            title="[bold yellow]Low Confidence[/bold yellow]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _status_style(status: str) -> str:
    """Return a Rich style for an investigation status."""
    normalized = status.lower()

    if normalized == "completed":
        return "green"
    if normalized in {"failed", "error"}:
        return "red"
    if normalized in {"max_steps_reached", "low_confidence"}:
        return "yellow"

    return "white"


def _agent_label(agent_name: str) -> Text:
    """Return a styled label for an agent name."""
    if "investigator" in agent_name:
        return Text(agent_name, style="bold cyan")
    if "evaluator" in agent_name:
        return Text(agent_name, style="bold yellow")
    if "writer" in agent_name:
        return Text(agent_name, style="bold magenta")
    if "recommender" in agent_name:
        return Text(agent_name, style="bold green")

    return Text(agent_name, style="white")


def _run_status_label(status: str) -> Text:
    """Return a colored status label for an agent step."""
    normalized = status.lower()

    if normalized == "succeeded":
        return Text(" ✓ SUCCESS ", style="bold black on green")
    if normalized == "blocked":
        return Text(" BLOCKED ", style="bold black on yellow")
    if normalized == "failed":
        return Text(" FAILED ", style="bold white on red")
    if normalized == "skipped":
        return Text(" SKIPPED ", style="bold white on bright_black")

    return Text(f" {status.upper()} ", style="white")

def _step_output_summary(step: Any) -> Text | str:
    """Return a compact output summary for an investigation step."""
    if step.evidence_ids:
        return _compact_evidence_ids(step.evidence_ids)

    if step.agent_name == AgentName.EVIDENCE_EVALUATOR:
        return Text("evaluation complete", style="yellow")

    if step.agent_name == AgentName.RCA_WRITER:
        return Text("RCA generated", style="magenta")

    if step.agent_name == AgentName.SOLUTION_RECOMMENDER:
        return Text("solution generated", style="green")

    if step.agent_name == AgentName.REPORT_WRITER:
        return Text("report saved", style="green")

    return Text("—", style="dim")


def _compact_evidence_ids(evidence_ids: list[str], *, limit: int = 3) -> str:
    """Compact a list of evidence identifiers for trace display."""
    compact_ids = [_compact_evidence_id(evidence_id) for evidence_id in evidence_ids[:limit]]
    remaining_count = len(evidence_ids) - len(compact_ids)

    if remaining_count > 0:
        compact_ids.append(f"+{remaining_count} more")

    return ", ".join(compact_ids)


def _compact_evidence_id(evidence_id: str) -> str:
    """Shorten evidence IDs for compact CLI trace display."""
    if evidence_id.startswith("EVID-LOG-"):
        return evidence_id

    value = evidence_id.removeprefix("evidence-").removeprefix("graph-")
    value = value.replace("\\", "/")

    if ":" in value:
        path, symbol_or_range = value.rsplit(":", 1)
        return f"{path.split('/')[-1]}:{symbol_or_range}"

    return value.split("/")[-1]


async def _run_investigation(
    incident_id: str,
    workflow: WorkflowChoice = WorkflowChoice.MANUAL,
    include_patch_plan: bool = False,
):
    """Build and run the selected investigation workflow."""
    settings = get_settings()
    workflow_runner = (
        await build_dynamic_graph_workflow(
            settings,
            include_patch_plan=include_patch_plan,
        )
        if workflow == WorkflowChoice.GRAPH
        else await build_dynamic_workflow(
            settings,
            include_patch_plan=include_patch_plan,
        )
    )
    return await workflow_runner.run(incident_id)
