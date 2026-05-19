import asyncio

import typer
from rich.console import Console

from bug_resolver.config.settings import get_settings
from bug_resolver.workflows import build_dynamic_workflow

app = typer.Typer(
    name="bug-resolver",
    help="CLI for the Production Bug Resolver Agent.",
    no_args_is_help=True,
)

console = Console()


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
    incident_id: str = typer.Option(..., "--incident-id", "-i", help="Incident id to investigate."),
) -> None:
    """Run a dynamic supervisor-led bug investigation for an incident."""
    console.print("[bold cyan]Starting dynamic investigation[/bold cyan]")
    console.print(f"Incident ID: {incident_id}")

    try:
        state = asyncio.run(_run_investigation(incident_id=incident_id))
    except Exception as exc:
        console.print(f"[bold red]Investigation failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Status: [bold]{state.investigation_status.value}[/bold]")
    console.print(f"Evidence items: {len(state.evidence_items)}")
    console.print(f"Agent steps: {len(state.trace.steps)}")
    _print_trace(state)

    if state.final_report_path is not None:
        console.print(f"Report: {state.final_report_path}")

    if state.errors:
        console.print("[bold red]Errors:[/bold red]")
        for error in state.errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    if state.low_confidence:
        console.print("[yellow]Investigation completed with low confidence.[/yellow]")


def _print_trace(state) -> None:
    if not state.trace.steps:
        return

    guardrails_by_id = {
        guardrail.guardrail_id: guardrail
        for guardrail in state.trace.guardrail_decisions
    }

    console.print("[bold]Trace:[/bold]")
    for step in state.trace.steps:
        detail_parts = [f"{step.step_number}. {step.agent_name.value}", step.run_status.value]
        if step.evidence_ids:
            detail_parts.append(
                f"evidence_count={len(step.evidence_ids)}"
            )
            detail_parts.append(
                f"evidence={_compact_evidence_ids(step.evidence_ids)}"
            )

        guardrail = (
            guardrails_by_id.get(step.guardrail_id)
            if step.guardrail_id is not None
            else None
        )
        if guardrail is not None and not guardrail.allowed:
            rules = ",".join(guardrail.violated_rules)
            fallback = (
                guardrail.fallback_next_agent.value
                if guardrail.fallback_next_agent is not None
                else "none"
            )
            detail_parts.append(f"blocked={rules}")
            detail_parts.append(f"fallback={fallback}")

        console.print(f"- {' | '.join(detail_parts)}")


def _compact_evidence_ids(evidence_ids: list[str], *, limit: int = 3) -> str:
    compact_ids = [_compact_evidence_id(evidence_id) for evidence_id in evidence_ids[:limit]]
    remaining_count = len(evidence_ids) - len(compact_ids)
    if remaining_count > 0:
        compact_ids.append(f"+{remaining_count} more")
    return ", ".join(compact_ids)


def _compact_evidence_id(evidence_id: str) -> str:
    if evidence_id.startswith("EVID-LOG-"):
        return evidence_id

    value = evidence_id.removeprefix("evidence-")
    if ":" in value:
        path, line_range = value.rsplit(":", 1)
        return f"{path.split('/')[-1]}:{line_range}"

    return value.split("/")[-1]


async def _run_investigation(incident_id: str):
    settings = get_settings()
    workflow = await build_dynamic_workflow(settings)
    return await workflow.run(incident_id)
