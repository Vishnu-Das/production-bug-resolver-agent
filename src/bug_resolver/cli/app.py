import typer
from rich.console import Console

from bug_resolver.config.settings import get_settings

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
    """Run bug investigation for an incident.

    This is a placeholder command for the first skeleton commit.
    The real workflow will be wired after schemas, providers, and agents are ready.
    """
    console.print("[bold cyan]Starting investigation[/bold cyan]")
    console.print(f"Incident ID: {incident_id}")
    console.print("[yellow]Workflow is not wired yet. Skeleton is ready.[/yellow]")