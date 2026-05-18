from typer.testing import CliRunner

from bug_resolver.cli.app import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "Production Bug Resolver Agent" in result.output


def test_investigate_command_placeholder() -> None:
    result = runner.invoke(app, ["investigate", "--incident-id", "INC-001"])

    assert result.exit_code == 0
    assert "INC-001" in result.output
    assert "Skeleton is ready" in result.output