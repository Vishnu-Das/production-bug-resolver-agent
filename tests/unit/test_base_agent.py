from __future__ import annotations

import pytest

from bug_resolver.agents.base import BaseAgent


class EchoAgent(BaseAgent[str, str]):
    name = "echo_agent"

    async def _run(self, input_data: str) -> str:
        return input_data.upper()


class EmptyOutputAgent(BaseAgent[str, str | None]):
    name = "empty_output_agent"

    async def _run(self, input_data: str) -> None:
        return None


@pytest.mark.asyncio
async def test_base_agent_runs_template_method() -> None:
    agent = EchoAgent()

    result = await agent.run("hello")

    assert result == "HELLO"


@pytest.mark.asyncio
async def test_base_agent_rejects_none_input() -> None:
    agent = EchoAgent()

    with pytest.raises(ValueError, match="received empty input"):
        await agent.run(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_base_agent_rejects_none_output() -> None:
    agent = EmptyOutputAgent()

    with pytest.raises(ValueError, match="produced empty output"):
        await agent.run("hello")