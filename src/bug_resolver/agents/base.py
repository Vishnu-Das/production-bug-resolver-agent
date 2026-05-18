from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """
    Base class for all agents.

    This gives every agent the same execution shape:

    public run()
        -> validate input
        -> execute agent-specific logic
        -> validate output
        -> return structured result

    Individual agents only implement _run().
    """

    name: str = "base_agent"

    async def run(self, input_data: InputT) -> OutputT:
        self._validate_input(input_data)
        output = await self._run(input_data)
        self._validate_output(output)
        return output

    def _validate_input(self, input_data: InputT) -> None:
        if input_data is None:
            raise ValueError(f"{self.name} received empty input.")

    def _validate_output(self, output: OutputT) -> None:
        if output is None:
            raise ValueError(f"{self.name} produced empty output.")

    @abstractmethod
    async def _run(self, input_data: InputT) -> OutputT:
        """Execute the agent-specific logic."""
        raise NotImplementedError