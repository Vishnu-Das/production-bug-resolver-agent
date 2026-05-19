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

    if state.final_report_path is not None:
        console.print(f"Report: {state.final_report_path}")

    if state.errors:
        console.print("[bold red]Errors:[/bold red]")
        for error in state.errors:
            console.print(f"- {error}")
        raise typer.Exit(code=1)

    if state.low_confidence:
        console.print("[yellow]Investigation completed with low confidence.[/yellow]")

async def _run_investigation(incident_id: str):
    settings = get_settings()
    workflow = await build_dynamic_workflow(settings)
    return await workflow.run(incident_id)
